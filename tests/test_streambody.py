import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

import anyio
import pytest
from fastapi import Body, FastAPI, Form, UploadFile
from httpx import ASGITransport, AsyncClient

from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

from .types import ASGIMessage, HTTPDisconnectMessage, HTTPRequestMessage, HTTPScope

# @pytest.fixture
pytest_mark = pytest.mark.parametrize("backend", ["asyncio", "trio"])
# def anyio_backend(backend: Literal["asyncio", "trio"]) -> str:


def _build_runtime_app(*, include_in_schema: bool = True) -> FastAPI:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            UploadStream,
            StreamBody(
                media_types=["application/octet-stream", "text/plain"],
                include_in_schema=include_in_schema,
            ),
        ],
    ) -> dict[str, object]:
        first = await body_content.read(3)
        rest = await body_content.read()
        return {
            "first": first.hex(),
            "rest": rest.hex(),
            "size": body_content.size,
            "filename": body_content.filename,
            "content_type": body_content.content_type,
        }

    return app


@pytest.mark.anyio
async def test_streambody_streams_request_without_preloading() -> None:
    app = _build_runtime_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/binary",
            content=b"abcdef",
            headers={
                "content-type": "application/octet-stream",
                "x-filename": "payload.bin",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "first": "616263",
        "rest": "646566",
        "size": 6,
        "filename": "payload.bin",
        "content_type": "application/octet-stream",
    }


@pytest.mark.anyio
async def test_streambody_rejects_unsupported_content_type() -> None:
    app = _build_runtime_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/binary",
            content=b"abc",
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 415
    payload = response.json()
    assert "Unsupported content-type" in payload["detail"]
    assert "application/octet-stream" in payload["detail"]


def test_openapi_includes_binary_request_body_content_types() -> None:
    app = _build_runtime_app()
    schema = app.openapi()

    request_body = schema["paths"]["/binary"]["post"]["requestBody"]
    assert request_body["required"] is True

    content = request_body["content"]
    assert set(content.keys()) == {"application/octet-stream", "text/plain"}
    assert content["application/octet-stream"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    assert content["text/plain"]["schema"] == {
        "type": "string",
        "format": "binary",
    }


def test_openapi_respects_include_in_schema_false() -> None:
    app = _build_runtime_app(include_in_schema=False)
    schema = app.openapi()

    operation = schema["paths"]["/binary"]["post"]
    assert "requestBody" not in operation


def test_openapi_applies_json_schema_extra_to_binary_schema() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/custom")
    async def upload_custom(
        body_content: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                json_schema_extra={"maxLength": 1024},
            ),
        ],
    ) -> dict[str, int]:
        return {"size": len(await body_content.read())}

    schema = app.openapi()
    binary_schema = schema["paths"]["/custom"]["post"]["requestBody"]["content"]["application/octet-stream"]["schema"]

    assert binary_schema["type"] == "string"
    assert binary_schema["format"] == "binary"
    assert binary_schema["maxLength"] == 1024


@pytest.mark.anyio
async def test_streambody_starts_before_full_request_body_is_available() -> None:
    first_chunk_was_read = anyio.Event()
    release_second_chunk = anyio.Event()

    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            UploadStream,
            StreamBody(media_types="application/octet-stream"),
        ],
    ) -> dict[str, str]:
        first = await body_content.read(3)
        first_chunk_was_read.set()
        rest = await body_content.read()
        return {
            "first": first.decode("ascii"),
            "rest": rest.decode("ascii"),
        }

    receive_call_count = 0

    async def receive() -> ASGIMessage:
        nonlocal receive_call_count
        receive_call_count += 1

        if receive_call_count == 1:
            return HTTPRequestMessage(type="http.request", body=b"abc", more_body=True)

        if receive_call_count == 2:
            await release_second_chunk.wait()
            return HTTPRequestMessage(type="http.request", body=b"def", more_body=False)

        return HTTPDisconnectMessage(type="http.disconnect")

    sent_messages: list[ASGIMessage] = []

    async def send(message: ASGIMessage) -> None:
        sent_messages.append(message)

    scope: HTTPScope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/binary",
        "raw_path": b"/binary",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/octet-stream"),
            (b"content-length", b"6"),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(app, scope, receive, send)  # type: ignore

        # The endpoint must be able to read the first bytes before the rest arrives.
        with anyio.fail_after(1):
            await first_chunk_was_read.wait()

        release_second_chunk.set()

    status = next(
        message["status"]  # type: ignore
        for message in sent_messages
        if message["type"] == "http.response.start"
    )
    response_body_messages = (
        message.get("body", b"")
        for message in sent_messages
        if message["type"] == "http.response.body"
    )
    body = b"".join(response_body_messages)

    assert status == 200
    assert json.loads(body) == {"first": "abc", "rest": "def"}


@pytest.mark.anyio
async def test_streambody_treats_client_disconnect_as_end_of_stream() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            UploadStream,
            StreamBody(media_types="application/octet-stream"),
        ],
    ) -> dict[str, str]:
        first = await body_content.read(3)
        rest = await body_content.read()
        return {
            "first": first.decode("ascii"),
            "rest": rest.decode("ascii"),
        }

    receive_call_count = 0

    async def receive() -> ASGIMessage:
        nonlocal receive_call_count
        receive_call_count += 1

        if receive_call_count == 1:
            return HTTPRequestMessage(type="http.request", body=b"abc", more_body=True)

        return HTTPDisconnectMessage(type="http.disconnect")

    sent_messages: list[ASGIMessage] = []

    async def send(message: ASGIMessage) -> None:
        sent_messages.append(message)

    scope: HTTPScope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/binary",
        "raw_path": b"/binary",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/octet-stream"),
            (b"content-length", b"6"),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }

    await app(scope, receive, send)  # type: ignore

    status = next(
        message["status"]  # type: ignore
        for message in sent_messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(message.get("body", b"") for message in sent_messages if message["type"] == "http.response.body")

    assert status == 200
    assert json.loads(body) == {"first": "abc", "rest": ""}


@pytest.mark.anyio
async def test_streambody_starts_before_httpx_streaming_upload_finishes() -> None:
    first_chunk_was_read = anyio.Event()
    release_second_chunk = anyio.Event()
    response_completed = anyio.Event()

    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            UploadStream,
            StreamBody(media_types="application/octet-stream"),
        ],
    ) -> dict[str, str]:
        first = await body_content.read(3)
        first_chunk_was_read.set()
        rest = await body_content.read()
        return {
            "first": first.decode("ascii"),
            "rest": rest.decode("ascii"),
        }

    async def streaming_content() -> AsyncIterator[bytes]:
        yield b"abc"
        await release_second_chunk.wait()
        yield b"def"

    response_payload: dict[str, str] | None = None

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:

        async def post_streaming_request() -> None:
            nonlocal response_payload
            response = await client.post(
                "/binary",
                content=streaming_content(),
                headers={"content-type": "application/octet-stream"},
            )
            response_payload = response.json()
            response_completed.set()

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(post_streaming_request)

            # The app should read the first chunk before the upload is complete.
            with anyio.fail_after(1):
                await first_chunk_was_read.wait()

            assert not response_completed.is_set()

            release_second_chunk.set()

            with anyio.fail_after(1):
                await response_completed.wait()

    assert response_payload == {"first": "abc", "rest": "def"}


# ---------------------------------------------------------------------------
# OpenAPI annotation field tests (title, description, example, examples, deprecated)
# ---------------------------------------------------------------------------


def _build_annotation_app(
    *,
    title: str | None = None,
    description: str | None = None,
    example: object | None = None,
    examples: list[object] | None = None,
    openapi_examples: dict[str, Any] | None = None,
    deprecated: bool | str | None = None,
    include_in_schema: bool = True,
    json_schema_extra: dict[str, object] | None = None,
) -> FastAPI:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        body: Annotated[
            UploadStream,
            StreamBody(
                title=title,
                description=description,
                example=example,
                examples=examples,
                openapi_examples=openapi_examples,
                deprecated=deprecated,
                include_in_schema=include_in_schema,
                json_schema_extra=json_schema_extra,
            ),
        ],
    ) -> None: ...

    return app


def test_openapi_applies_title_to_schema() -> None:
    app = _build_annotation_app(title="Binary Payload")
    schema = app.openapi()

    binary_schema = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]["schema"]
    assert binary_schema["title"] == "Binary Payload"


def test_openapi_applies_description_to_request_body() -> None:
    app = _build_annotation_app(description="The binary file to upload")
    schema = app.openapi()

    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    assert request_body["description"] == "The binary file to upload"


def test_openapi_applies_example_to_media_type() -> None:
    app = _build_annotation_app(example="sample binary content")
    schema = app.openapi()

    media_type_obj = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]
    assert media_type_obj["example"] == "sample binary content"


def test_openapi_applies_openapi_examples_to_media_type() -> None:
    named_examples = {
        "small": {"summary": "Small file", "value": "abc"},
        "large": {"summary": "Large file", "value": "x" * 100},
    }
    app = _build_annotation_app(openapi_examples=named_examples)
    schema = app.openapi()

    media_type_obj = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]
    assert media_type_obj["examples"] == named_examples


def test_openapi_applies_examples_list_as_numbered_map() -> None:
    app = _build_annotation_app(examples=["first example", "second example"])
    schema = app.openapi()

    media_type_obj = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]
    assert media_type_obj["examples"] == {
        "example-0": {"value": "first example"},
        "example-1": {"value": "second example"},
    }


def test_openapi_applies_deprecated_to_schema() -> None:
    app = _build_annotation_app(deprecated=True)
    schema = app.openapi()

    binary_schema = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]["schema"]
    assert binary_schema["deprecated"] is True


def test_openapi_openapi_examples_takes_precedence_over_examples_list() -> None:
    named_examples = {"main": {"summary": "Main", "value": "data"}}
    app = _build_annotation_app(
        examples=["ignored example"],
        openapi_examples=named_examples,
    )
    schema = app.openapi()

    media_type_obj = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]
    assert media_type_obj["examples"] == named_examples


def test_openapi_applies_json_schema_extra_via_annotation() -> None:
    app = _build_annotation_app(json_schema_extra={"maxLength": 512, "x-custom": "value"})
    schema = app.openapi()

    binary_schema = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]["schema"]
    assert binary_schema["type"] == "string"
    assert binary_schema["format"] == "binary"
    assert binary_schema["maxLength"] == 512
    assert binary_schema["x-custom"] == "value"


def test_openapi_include_in_schema_false_hides_request_body() -> None:
    app = _build_annotation_app(include_in_schema=False)
    schema = app.openapi()

    operation = schema["paths"]["/upload"]["post"]
    assert "requestBody" not in operation


# ---------------------------------------------------------------------------
# Conflict detection: StreamBody must not coexist with Body / Form / UploadFile
# ---------------------------------------------------------------------------


def test_openapi_raises_on_streambody_mixed_with_body_param() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/mixed")
    async def ep(
        stream: Annotated[UploadStream, StreamBody()],
        name: Annotated[str, Body()],
    ) -> None: ...

    with pytest.raises(ValueError, match=r"StreamBody.*Body|Body.*StreamBody"):
        app.openapi()


def test_openapi_raises_on_streambody_mixed_with_uploadfile() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/mixed")
    async def ep(
        stream: Annotated[UploadStream, StreamBody()],
        file: UploadFile,
    ) -> None: ...

    with pytest.raises(ValueError, match=r"StreamBody.*UploadFile|UploadFile.*StreamBody"):
        app.openapi()


def test_openapi_raises_on_streambody_mixed_with_form() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/mixed")
    async def ep(
        stream: Annotated[UploadStream, StreamBody()],
        tag: Annotated[str, Form()],
    ) -> None: ...

    with pytest.raises(ValueError, match=r"StreamBody.*Form|Form.*StreamBody"):
        app.openapi()


def test_openapi_no_error_when_streambody_used_alone() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/solo")
    async def ep(stream: Annotated[UploadStream, StreamBody()]) -> None: ...

    schema = app.openapi()
    assert "requestBody" in schema["paths"]["/solo"]["post"]


def test_openapi_no_error_when_body_used_without_streambody() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/solo")
    async def ep(name: Annotated[str, Body()]) -> None: ...

    schema = app.openapi()
    assert "requestBody" in schema["paths"]["/solo"]["post"]


def test_openapi_error_with_bytes_and_uploadstream() -> None:
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/mixed")
    async def ep(
        stream: Annotated[UploadStream, StreamBody()],
        data: bytes = Body(),  # noqa FAST002
    ) -> None: ...

    with pytest.raises(ValueError, match=r"StreamBody.*Body|Body.*StreamBody"):
        app.openapi()
