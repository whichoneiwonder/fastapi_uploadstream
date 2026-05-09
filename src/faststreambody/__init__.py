"""Streaming raw request-body helpers for FastAPI.

This package provides a dependency-first runtime wrapper plus an optional
OpenAPI hook that documents those dependencies as binary request bodies.
"""

from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

from anyio import EndOfStream, create_memory_object_stream, create_task_group
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastapi import FastAPI, HTTPException, Request, status
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
    if isinstance(media_types, str):
        normalized = [media_types.strip()]
    else:
        normalized = [value.strip() for value in media_types if value.strip()]

    if not normalized:
        return ("*/*",)

    return tuple(dict.fromkeys(normalized))


def _media_type_matches(content_type: str, allowed_media_type: str) -> bool:
    if allowed_media_type == "*/*":
        return True

    content_base = content_type.split(";", 1)[0].strip().lower()
    allowed_base = allowed_media_type.strip().lower()

    if allowed_base.endswith("/*"):
        prefix = allowed_base[:-1]
        return content_base.startswith(prefix)

    return content_base == allowed_base


class BinaryUploadFile:
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
        """Advance the stream by consuming and discarding bytes."""
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
        """Yield the request body in chunks."""
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
    """Callable dependency wrapper used with Depends(StreamBody(...))."""

    def __init__(
        self,
        *,
        media_types: str | Iterable[str] = "*/*",
        title: str | None = None,
        description: str | None = None,
        include_in_schema: bool = True,
        json_schema_extra: dict[str, Any] | None = None,
        channel_buffer_size: int = 2048,
        examples: list[Any] | None = None,
    ) -> None:
        """Capture runtime and documentation settings for a raw body dependency."""
        self.media_types = _normalize_media_types(media_types)
        self.title = title
        self.description = description
        self.include_in_schema = include_in_schema
        self.json_schema_extra = json_schema_extra or {}
        self.channel_buffer_size = channel_buffer_size
        self.examples = examples

    async def __call__(self, request: Request) -> AsyncIterator[BinaryUploadFile]:
        """Yield a streaming file-like wrapper over the incoming request body."""
        self._validate_content_type(request)

        send_stream: MemoryObjectSendStream[bytes]
        recv_stream: MemoryObjectReceiveStream[bytes]
        send_stream, recv_stream = create_memory_object_stream[bytes](self.channel_buffer_size)

        async with create_task_group() as task_group:
            upload = BinaryUploadFile(
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
        async with sender:
            async for chunk in request.stream():
                if chunk:
                    await sender.send(chunk)

    def _validate_content_type(self, request: Request) -> None:
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
        content = {
            media_type: {
                "schema": {
                    "type": "string",
                    "format": "binary",
                }
            }
            for media_type in self.media_types
        }

        if self.json_schema_extra:
            for media_content in content.values():
                media_content["schema"].update(self.json_schema_extra)

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
    # Keep compatibility with a Body-like call signature so existing usage such as
    # Depends(StreamBody(...)) does not need endpoint changes.
    _ = (
        examples,
        example,
        openapi_examples,
        deprecated,
    )

    return StreamBodyParam(
        media_types=media_types,
        title=title,
        description=description,
        include_in_schema=include_in_schema,
        json_schema_extra=json_schema_extra,
        channel_buffer_size=channel_buffer_size,
    )


def install_streambody_openapi(app: FastAPI) -> FastAPI:
    """Teach FastAPI's OpenAPI generator about StreamBody dependencies."""
    # TODO: Add an APIRouter helper that auto-installs this hook the first time a
    # router with StreamBody dependencies is included in an app. A practical shape
    # is `StreamBodyRouter(APIRouter)` plus `include_streambody_router(app, router)`
    # that calls `install_streambody_openapi(app)` once (guarded by a private flag)
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


def _inject_streambody_openapi(app: FastAPI, openapi_schema: dict[str, Any]) -> None:
    """Patch generated OpenAPI paths with binary requestBody entries."""
    paths = openapi_schema.setdefault("paths", {})

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        stream_bodies = _collect_streambody_dependencies(route)
        if not stream_bodies:
            continue

        path_item = paths.get(route.path_format)
        if not path_item:
            continue

        for method in route.methods or []:
            operation = path_item.get(method.lower())
            if not operation:
                continue

            visible_stream_bodies = [
                stream_body for stream_body in stream_bodies if stream_body.include_in_schema
            ]
            if not visible_stream_bodies:
                continue

            request_body = operation.setdefault("requestBody", {})
            request_body.setdefault("required", True)
            content = request_body.setdefault("content", {})

            for stream_body in visible_stream_bodies:
                content.update(stream_body.openapi_request_body()["content"])


def _collect_streambody_dependencies(route: APIRoute) -> list[StreamBodyParam]:
    """Find StreamBodyParam instances reachable from an APIRoute dependency tree."""
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
    "BinaryUploadFile",
    "StreamBody",
    "StreamBodyParam",
    "install_streambody_openapi",
    "size_from_request",
]
