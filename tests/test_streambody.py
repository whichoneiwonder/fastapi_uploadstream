from typing import Annotated

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