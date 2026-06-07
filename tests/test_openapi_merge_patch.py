"""Tests for OpenAPI schema merge/patch behavior with multiple StreamBody dependencies.

This module tests how OpenAPI schemas are merged when multiple StreamBody
dependencies are used, including description propagation and examples handling.
"""

from typing import Annotated, AsyncIterator

import pytest
from fastapi import Body, Depends, FastAPI

from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

# Multiple StreamBody Dependencies: Merge and Patch Tests
# ---------------------------------------------------------------------------


def test_multiple_streambody_params() -> None:
    """Multiple StreamBody dependencies should raise an error."""
    app = FastAPI()
    install_uploadstream_openapi(app)
    with pytest.raises(ValueError, match="Multiple StreamBody dependencies found"):

        @app.post("/upload")
        async def upload(
            stream1: Annotated[
                UploadStream,
                StreamBody(media_types="application/octet-stream"),
            ],
            stream2: Annotated[
                UploadStream,
                StreamBody(media_types="text/plain"),
            ],
        ) -> None: ...

        app.openapi()


def test_nested_streambody_params() -> None:
    """Multiple StreamBody dependencies should raise an error."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    async def nested_dependency(
        stream: Annotated[
            UploadStream,
            StreamBody(media_types="application/octet-stream"),
        ],
    ) -> AsyncIterator[bytes]:
        yield b"nested data"
        async for chunk in stream.iter_chunks(1024):
            yield chunk

    with pytest.raises(ValueError, match="Multiple StreamBody dependencies found"):

        @app.post("/upload")
        async def upload(
            stream2: Annotated[
                UploadStream,
                StreamBody(media_types="text/plain"),
            ],
            stream1: Annotated[
                AsyncIterator[bytes],
                Depends(nested_dependency),
            ],
        ) -> None: ...

        app.openapi()


def test_body_and_streambody_params() -> None:
    """Multiple StreamBody dependencies should raise an error."""
    app = FastAPI()
    install_uploadstream_openapi(app)
    with pytest.raises(ValueError, match="StreamBody cannot be combined"):

        @app.post("/upload")
        async def upload(
            stream1: Annotated[
                UploadStream,
                StreamBody(media_types="application/octet-stream"),
            ],
            body: Annotated[
                str,
                Body(...),
            ],
        ) -> None: ...

        app.openapi()


# ---------------------------------------------------------------------------
# Description Propagation Tests
# ---------------------------------------------------------------------------


def test_description_propagation_in_single_streambody() -> None:
    """Description from StreamBody should appear in request body."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(description="Upload a binary file"),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]

    assert request_body["description"] == "Upload a binary file"


def test_title_propagation_in_schema() -> None:
    """Title from StreamBody should appear in schema."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(title="File Data"),
        ],
    ) -> None: ...

    schema = app.openapi()
    binary_schema = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]["schema"]

    assert binary_schema["title"] == "File Data"


def test_deprecated_propagation_in_schema() -> None:
    """Deprecated flag from StreamBody should appear in schema."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(deprecated=True),
        ],
    ) -> None: ...

    schema = app.openapi()
    binary_schema = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]["schema"]

    assert binary_schema["deprecated"] is True


def test_json_schema_extra_propagation() -> None:
    """json_schema_extra from StreamBody should be merged into schema."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(
                json_schema_extra={
                    "maxLength": 10485760,  # 10MB
                    "x-stream": True,
                    "x-custom-field": "custom-value",
                }
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    binary_schema = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]["schema"]

    assert binary_schema["maxLength"] == 10485760
    assert binary_schema["x-stream"] is True
    assert binary_schema["x-custom-field"] == "custom-value"


# ---------------------------------------------------------------------------
# Examples Field Behavior Tests
# ---------------------------------------------------------------------------


def test_examples_list_conversion_to_map() -> None:
    """Examples list should be converted to numbered map in media type object."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(examples=["first", "second", "third"]),
        ],
    ) -> None: ...

    schema = app.openapi()
    media_type = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]

    assert "examples" in media_type
    assert media_type["examples"] == {
        "example-0": {"value": "first"},
        "example-1": {"value": "second"},
        "example-2": {"value": "third"},
    }


def test_openapi_examples_in_media_type() -> None:
    """openapi_examples should appear in media type object."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    named_examples = {
        "small": {"summary": "Small file", "value": "x" * 100},
        "large": {"summary": "Large file", "value": "y" * 1000},
    }

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(openapi_examples=named_examples),
        ],
    ) -> None: ...

    schema = app.openapi()
    media_type = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]

    assert media_type["examples"] == named_examples


def test_openapi_examples_precedence_over_examples_list() -> None:
    """openapi_examples should take precedence over examples list."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(
                examples=["ignored1", "ignored2"],
                openapi_examples={"main": {"value": "used"}},
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    media_type = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]

    # openapi_examples should be used
    assert media_type["examples"] == {"main": {"value": "used"}}
