"""Streaming raw request-body helpers for FastAPI.

This package provides a dependency-first runtime wrapper plus an optional
OpenAPI hook that documents those dependencies as binary request bodies.
"""

from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

from anyio import EndOfStream, create_memory_object_stream, create_task_group
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.params import File as FileFieldInfo
from fastapi.params import Form as FormFieldInfo
from fastapi.routing import APIRoute


def size_from_request(request: Request) -> int | None:
    """Return the request Content-Length header as an integer when possible."""
    if content_size := request.headers.get("content-length"):
        try:
            return int(content_size)
        except ValueError:
            return None
    return None


def _normalize_media_types(media_types: str | Iterable[str]) -> tuple[str, ...]:
    """Normalize media type strings to a deduplicated tuple.

    Args:
        media_types: A single media type string or iterable of media type strings.

    Returns:
        A tuple of normalized media types, or ("*/*",) if no valid types provided.
    """
    if isinstance(media_types, str):
        normalized = [media_types.strip()]
    else:
        normalized = [value.strip() for value in media_types if value.strip()]

    if not normalized:
        return ("*/*",)

    return tuple(dict.fromkeys(normalized))


def _media_type_matches(content_type: str, allowed_media_type: str) -> bool:
    """Check if a content type matches an allowed media type pattern.

    Supports wildcard matching for type patterns like "application/*".

    Args:
        content_type: The actual content type from the request.
        allowed_media_type: The pattern to match against (may include "*").

    Returns:
        True if the content type matches the allowed pattern.
    """
    if allowed_media_type == "*/*":
        return True

    content_base = content_type.split(";", 1)[0].strip().lower()
    allowed_base = allowed_media_type.strip().lower()

    if allowed_base.endswith("/*"):
        prefix = allowed_base[:-1]
        return content_base.startswith(prefix)

    return content_base == allowed_base


class UploadStream:
    """A streaming view of a raw request body.

    This object intentionally mimics only the subset of UploadFile behavior that
    is meaningful for one-pass, non-multipart request streaming.
    """

    def __init__(
        self,
        request: Request,
        receiver: MemoryObjectReceiveStream[bytes],
        cancel_receive: Callable[[], object],
    ) -> None:
        """Wrap the incoming request stream as a file-like binary reader."""
        self.request = request
        self.filename = request.headers.get("x-filename")
        self.size = size_from_request(request)
        self.content_type = request.headers.get("content-type", "*/*")

        self._receiver = receiver
        self._cancel_receive = cancel_receive
        self._buffer = bytearray()
        self._eof = False
        self._closed = False

    async def _pull_chunk(self) -> bytes:
        """Pull the next chunk from the receive stream.

        Returns:
            The next chunk of bytes, or empty bytes if EOF is reached.
        """
        if self._eof:
            return b""

        try:
            return await self._receiver.receive()
        except EndOfStream:
            self._eof = True
            return b""

    async def read(self, size: int = -1) -> bytes:
        """Read bytes from the streamed request body."""
        if self._closed:
            return b""

        if size == 0:
            return b""
        if size < -1:
            raise ValueError("size must be >= -1")

        if size == -1:
            chunks = [bytes(self._buffer)]
            self._buffer.clear()
            while True:
                chunk = await self._pull_chunk()
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)

        while len(self._buffer) < size and not self._eof:
            chunk = await self._pull_chunk()
            if not chunk:
                break
            self._buffer.extend(chunk)

        if not self._buffer:
            return b""

        out = bytes(self._buffer[:size])
        del self._buffer[:size]
        return out

    async def seek(self, offset: int) -> None:
        """Advance the stream by consuming and discarding bytes.

        Args:
            offset: Number of bytes to advance. Must be non-negative.

        Raises:
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Negative seek position: {offset}")
        if offset == 0:
            return

        remaining = offset
        while remaining > 0:
            chunk = await self.read(remaining)
            if not chunk:
                break
            remaining -= len(chunk)

    async def iter_chunks(self, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        """Yield the request body in chunks of specified size.

        Args:
            chunk_size: Size of each chunk in bytes. Defaults to 64KB. Must be positive.

        Yields:
            Chunks of bytes until EOF.

        Raises:
            ValueError: If chunk_size is not positive.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

        while True:
            chunk = await self.read(chunk_size)
            if not chunk:
                break
            yield chunk

    async def close(self) -> None:
        """Stop background request pumping and close the receive stream."""
        if self._closed:
            return

        self._closed = True
        self._cancel_receive()
        await self._receiver.aclose()


class StreamBodyParam:
    """Callable dependency wrapper used with StreamBody(...)."""

    def __init__(
        self,
        *,
        media_types: str | Iterable[str] = "*/*",
        title: str | None = None,
        description: str | None = None,
        example: object | None = None,
        examples: list[Any] | None = None,
        openapi_examples: dict[str, Any] | None = None,
        deprecated: bool | str | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        channel_buffer_size: int = 2048,
    ) -> None:
        """Capture runtime and documentation settings for a raw body dependency."""
        self.media_types = _normalize_media_types(media_types)
        self.title = title
        self.description = description
        self.example = example
        self.examples = examples
        self.openapi_examples = openapi_examples
        self.deprecated = deprecated
        self.include_in_schema = include_in_schema
        self.json_schema_extra = json_schema_extra or {}
        self.channel_buffer_size = channel_buffer_size

    async def __call__(self, request: Request) -> AsyncIterator[UploadStream]:
        """Yield a streaming file-like wrapper over the incoming request body."""
        self._validate_content_type(request)

        send_stream: MemoryObjectSendStream[bytes]
        recv_stream: MemoryObjectReceiveStream[bytes]
        send_stream, recv_stream = create_memory_object_stream[bytes](self.channel_buffer_size)

        async with create_task_group() as task_group:
            upload = UploadStream(
                request=request,
                receiver=recv_stream,
                cancel_receive=task_group.cancel_scope.cancel,
            )
            task_group.start_soon(self._recv_from_request, request, send_stream)

            try:
                yield upload
            finally:
                await upload.close()

    async def _recv_from_request(
        self,
        request: Request,
        sender: MemoryObjectSendStream[bytes],
    ) -> None:
        """Pump request body chunks into the send stream.

        Runs as a background task that continuously reads from the request
        and forwards chunks to the send stream until the body is exhausted.

        Args:
            request: The incoming HTTP request.
            sender: The send stream to forward chunks to.
        """
        async with sender:
            async for chunk in request.stream():
                if chunk:
                    await sender.send(chunk)

    def _validate_content_type(self, request: Request) -> None:
        """Validate that the request content type matches allowed media types.

        Args:
            request: The incoming HTTP request.

        Raises:
            HTTPException: If content type is not in the allowed media types.
        """
        content_type = request.headers.get("content-type", "*/*")

        if any(_media_type_matches(content_type, allowed) for allowed in self.media_types):
            return

        allowed = ", ".join(self.media_types)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(f"Unsupported content-type '{content_type}'. Expected one of: {allowed}"),
        )

    def openapi_request_body(self) -> dict[str, Any]:
        """Return an OpenAPI requestBody block for a binary upload."""
        content: dict[str, Any] = {}

        for media_type in self.media_types:
            schema: dict[str, Any] = {"type": "string", "format": "binary"}

            if self.title is not None:
                schema["title"] = self.title
            if self.deprecated:
                schema["deprecated"] = True
            if self.json_schema_extra:
                schema.update(self.json_schema_extra)

            media_type_obj: dict[str, Any] = {"schema": schema}

            if self.openapi_examples:
                media_type_obj["examples"] = self.openapi_examples
            elif self.examples:
                media_type_obj["examples"] = {f"example-{i}": {"value": v} for i, v in enumerate(self.examples)}

            if self.example is not None:
                media_type_obj["example"] = self.example

            content[media_type] = media_type_obj

        request_body: dict[str, Any] = {"content": content}
        if self.description is not None:
            request_body["description"] = self.description

        return request_body


def StreamBody(
    *,
    media_types: str | list[str] = "*/*",
    title: str | None = None,
    description: str | None = None,
    examples: list[Any] | None = None,
    example: object | None = None,
    openapi_examples: dict[str, Any] | None = None,
    deprecated: bool | str | None = None,
    include_in_schema: bool = True,
    json_schema_extra: dict[str, Any] | None = None,
    channel_buffer_size: int = 2048,
) -> StreamBodyParam:
    """Create a dependency object for streamed raw body uploads."""
    return Depends(
        StreamBodyParam(
            media_types=media_types,
            title=title,
            description=description,
            example=example,
            examples=examples,
            openapi_examples=openapi_examples,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            json_schema_extra=json_schema_extra,
            channel_buffer_size=channel_buffer_size,
        )
    )


def install_uploadstream_openapi(app: FastAPI) -> FastAPI:
    """Teach FastAPI's OpenAPI generator about StreamBody dependencies."""
    # TODO: Add an APIRouter helper that auto-installs this hook the first time a
    # router with StreamBody dependencies is included in an app. A practical shape
    # is `StreamBodyRouter(APIRouter)` plus `include_streambody_router(app, router)`
    # that calls `install_uploadstream_openapi(app)` once (guarded by a private flag)
    # before delegating to `app.include_router(router)`.
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        openapi_schema = original_openapi()
        _inject_streambody_openapi(app, openapi_schema)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


def _check_streambody_conflicts(route: APIRoute) -> None:
    """Raise ValueError if a StreamBody dependency coexists with Body/Form/UploadFile params.

    Args:
        route: The API route to validate.

    Raises:
        ValueError: If incompatible parameter types are mixed on the same endpoint.
    """
    conflicting = route.dependant.body_params
    if not conflicting:
        return

    def _param_kind(field_info: object) -> str:
        if isinstance(field_info, FileFieldInfo):
            return "UploadFile"
        if isinstance(field_info, FormFieldInfo):
            return "Form"
        return "Body"

    descriptions = [f"{p.name} ({_param_kind(p.field_info)})" for p in conflicting]
    methods = ", ".join(route.methods or ["?"])
    raise ValueError(
        f"StreamBody cannot be combined with Body, Form, or UploadFile parameters on the "
        f"same endpoint ({methods} {route.path_format}). "
        f"Conflicting params: {', '.join(descriptions)}. "
        f"Use StreamBody exclusively for request body handling on this endpoint."
    )


def _inject_streambody_openapi(app: FastAPI, openapi_schema: dict[str, Any]) -> None:
    """Patch generated OpenAPI paths with binary requestBody entries.

    Scans all routes for StreamBody dependencies and injects appropriate
    binary media type definitions into their OpenAPI operation specs.

    Args:
        app: The FastAPI application.
        openapi_schema: The OpenAPI schema dict to modify in-place.
    """
    paths = openapi_schema.setdefault("paths", {})

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        stream_bodies = _collect_streambody_dependencies(route)
        if not stream_bodies:
            continue

        _check_streambody_conflicts(route)

        path_item = paths.get(route.path_format)
        if not path_item:
            continue

        for method in route.methods or []:
            operation = path_item.get(method.lower())
            if not operation:
                continue

            visible_stream_bodies = [stream_body for stream_body in stream_bodies if stream_body.include_in_schema]
            if not visible_stream_bodies:
                continue

            request_body = operation.setdefault("requestBody", {})
            request_body.setdefault("required", True)
            content = request_body.setdefault("content", {})

            for stream_body in visible_stream_bodies:
                rb = stream_body.openapi_request_body()
                content.update(rb["content"])
                if "description" in rb and "description" not in request_body:
                    request_body["description"] = rb["description"]


def _collect_streambody_dependencies(route: APIRoute) -> list[StreamBodyParam]:
    """Find StreamBodyParam instances reachable from an APIRoute dependency tree.

    Recursively traverses the dependency graph of an endpoint to collect
    all StreamBodyParam instances used in its dependencies.

    Args:
        route: The API route to scan.

    Returns:
        A list of all StreamBodyParam instances found in the dependency tree.
    """
    matches: list[StreamBodyParam] = []

    def visit(dependant: object) -> None:
        call = getattr(dependant, "call", None)
        if isinstance(call, StreamBodyParam):
            matches.append(call)

        for child in getattr(dependant, "dependencies", []):
            visit(child)

    visit(route.dependant)
    return matches


__all__ = [
    "StreamBody",
    "StreamBodyParam",
    "UploadStream",
    "install_uploadstream_openapi",
    "size_from_request",
]
