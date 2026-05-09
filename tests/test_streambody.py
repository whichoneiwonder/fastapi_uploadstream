from collections.abc import AsyncIterator
import json
from typing import Annotated

import anyio
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from faststreambody import BinaryUploadFile, StreamBody, install_streambody_openapi


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _build_runtime_app(*, include_in_schema: bool = True) -> FastAPI:
    app = FastAPI()
    install_streambody_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            BinaryUploadFile,
            Depends(
                StreamBody(
                    media_types=["application/octet-stream", "text/plain"],
                    include_in_schema=include_in_schema,
                )
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
    install_streambody_openapi(app)

    @app.post("/custom")
    async def upload_custom(
        body_content: Annotated[
            BinaryUploadFile,
            Depends(
                StreamBody(
                    media_types="application/octet-stream",
                    json_schema_extra={"maxLength": 1024},
                )
            ),
        ],
    ) -> dict[str, int]:
        return {"size": len(await body_content.read())}

    schema = app.openapi()
    binary_schema = schema["paths"]["/custom"]["post"]["requestBody"]["content"][
        "application/octet-stream"
    ]["schema"]

    assert binary_schema["type"] == "string"
    assert binary_schema["format"] == "binary"
    assert binary_schema["maxLength"] == 1024


@pytest.mark.anyio
async def test_streambody_starts_before_full_request_body_is_available() -> None:
    first_chunk_was_read = anyio.Event()
    release_second_chunk = anyio.Event()

    app = FastAPI()
    install_streambody_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            BinaryUploadFile,
            Depends(StreamBody(media_types="application/octet-stream")),
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

    async def receive() -> dict[str, object]:
        nonlocal receive_call_count
        receive_call_count += 1

        if receive_call_count == 1:
            return {"type": "http.request", "body": b"abc", "more_body": True}

        if receive_call_count == 2:
            await release_second_chunk.wait()
            return {"type": "http.request", "body": b"def", "more_body": False}

        return {"type": "http.disconnect"}

    sent_messages: list[dict[str, object]] = []

    async def send(message: dict[str, object]) -> None:
        sent_messages.append(message)

    scope = {
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
        task_group.start_soon(app, scope, receive, send)

        # The endpoint must be able to read the first bytes before the rest arrives.
        with anyio.fail_after(1):
            await first_chunk_was_read.wait()

        release_second_chunk.set()

    status = next(
        message["status"]
        for message in sent_messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in sent_messages
        if message["type"] == "http.response.body"
    )

    assert status == 200
    assert json.loads(body) == {"first": "abc", "rest": "def"}


@pytest.mark.anyio
async def test_streambody_starts_before_httpx_streaming_upload_finishes() -> None:
    first_chunk_was_read = anyio.Event()
    release_second_chunk = anyio.Event()
    response_completed = anyio.Event()

    app = FastAPI()
    install_streambody_openapi(app)

    @app.post("/binary")
    async def upload_binary(
        body_content: Annotated[
            BinaryUploadFile,
            Depends(StreamBody(media_types="application/octet-stream")),
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
