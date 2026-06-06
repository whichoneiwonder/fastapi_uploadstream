"""Tests for OpenAPI schema merge/patch behavior with multiple StreamBody dependencies.

This module tests how OpenAPI schemas are merged when multiple StreamBody
dependencies are used, including description propagation and examples handling.
"""

from typing import Annotated

from fastapi import FastAPI

from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

# Multiple StreamBody Dependencies: Merge and Patch Tests
# ---------------------------------------------------------------------------


def test_multiple_streambody_with_different_media_types() -> None:
    """Multiple StreamBody dependencies with different media types should merge."""
    app = FastAPI()
    install_uploadstream_openapi(app)

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

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    assert "application/octet-stream" in content
    assert "text/plain" in content
    assert content["application/octet-stream"]["schema"]["type"] == "string"
    assert content["application/octet-stream"]["schema"]["format"] == "binary"
    assert content["text/plain"]["schema"]["type"] == "string"
    assert content["text/plain"]["schema"]["format"] == "binary"


def test_multiple_streambody_with_overlapping_media_types() -> None:
    """Multiple StreamBody dependencies with overlapping media types should merge."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(media_types=["application/octet-stream", "text/plain"]),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(media_types=["text/plain", "application/json"]),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # All unique media types should be present
    assert "application/octet-stream" in content
    assert "text/plain" in content
    assert "application/json" in content


def test_multiple_streambody_description_from_first() -> None:
    """Description should propagate from the first visible StreamBody."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                description="First stream description",
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                description="Second stream description",
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]

    # Description from first StreamBody should be used
    assert request_body["description"] == "First stream description"


def test_multiple_streambody_uses_first_available_description() -> None:
    """Description from first StreamBody with a description is used."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(media_types="application/octet-stream"),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                description="Second stream description",
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]

    # Description from the first StreamBody that has one is used
    assert request_body["description"] == "Second stream description"


def test_multiple_streambody_with_different_titles() -> None:
    """Each media type gets the title from its respective StreamBody."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                title="Binary Title",
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                title="Text Title",
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # Each media type should have its own schema with its title
    assert content["application/octet-stream"]["schema"]["title"] == "Binary Title"
    assert content["text/plain"]["schema"]["title"] == "Text Title"


def test_multiple_streambody_with_different_examples() -> None:
    """Each media type gets the examples from its respective StreamBody."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                example="binary example",
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                example="text example",
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # Each media type should have its own example
    assert content["application/octet-stream"]["example"] == "binary example"
    assert content["text/plain"]["example"] == "text example"


def test_multiple_streambody_with_json_schema_extra() -> None:
    """Each media type should apply its json_schema_extra to its schema."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                json_schema_extra={"maxLength": 1024},
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                json_schema_extra={"maxLength": 2048},
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # Each media type should have its json_schema_extra applied
    assert content["application/octet-stream"]["schema"]["maxLength"] == 1024
    assert content["text/plain"]["schema"]["maxLength"] == 2048


def test_multiple_streambody_with_deprecated() -> None:
    """Each media type should apply its deprecated flag to its schema."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                deprecated=True,
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                deprecated=False,
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # First media type should be deprecated
    assert content["application/octet-stream"]["schema"]["deprecated"] is True
    # Second media type should not have deprecated (it's only added if True)
    assert "deprecated" not in content["text/plain"]["schema"]


def test_multiple_streambody_with_openapi_examples() -> None:
    """Each media type should apply its openapi_examples to its media type object."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                openapi_examples={
                    "binary_small": {"summary": "Small binary", "value": "abc"},
                },
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                openapi_examples={
                    "text_large": {"summary": "Large text", "value": "x" * 100},
                },
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # Each media type should have its openapi_examples
    assert "examples" in content["application/octet-stream"]
    assert content["application/octet-stream"]["examples"]["binary_small"]["summary"] == "Small binary"
    assert "examples" in content["text/plain"]
    assert content["text/plain"]["examples"]["text_large"]["summary"] == "Large text"


def test_multiple_streambody_include_in_schema_false_hides_from_merge() -> None:
    """StreamBody with include_in_schema=False should not appear in merged schema."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                include_in_schema=True,
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                include_in_schema=False,
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    request_body = schema["paths"]["/upload"]["post"]["requestBody"]
    content = request_body["content"]

    # Only the visible StreamBody should be in the schema
    assert "application/octet-stream" in content
    assert "text/plain" not in content


def test_multiple_streambody_all_hidden_from_schema() -> None:
    """When all StreamBody dependencies have include_in_schema=False, no requestBody appears."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream1: Annotated[
            UploadStream,
            StreamBody(
                media_types="application/octet-stream",
                include_in_schema=False,
            ),
        ],
        stream2: Annotated[
            UploadStream,
            StreamBody(
                media_types="text/plain",
                include_in_schema=False,
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    operation = schema["paths"]["/upload"]["post"]

    # No requestBody should be present
    assert "requestBody" not in operation


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


def test_example_field_in_media_type() -> None:
    """Example field should appear in media type object."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(example="sample data"),
        ],
    ) -> None: ...

    schema = app.openapi()
    media_type = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]

    assert media_type["example"] == "sample data"


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


def test_openapi_examples_precedence_over_example() -> None:
    """openapi_examples should take precedence over example field."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(
                example="ignored",
                openapi_examples={"main": {"value": "used"}},
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    media_type = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]

    # openapi_examples should be used, example field should not appear
    assert "examples" in media_type
    assert media_type["examples"] == {"main": {"value": "used"}}
    assert "example" not in media_type


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


def test_empty_examples_list_does_not_override_example() -> None:
    """Empty examples list should not prevent example field from being used."""
    app = FastAPI()
    install_uploadstream_openapi(app)

    @app.post("/upload")
    async def upload(
        stream: Annotated[
            UploadStream,
            StreamBody(
                example="used",
                examples=[],
            ),
        ],
    ) -> None: ...

    schema = app.openapi()
    media_type = schema["paths"]["/upload"]["post"]["requestBody"]["content"]["*/*"]

    # Empty examples list is falsy, so example should be used
    assert media_type["example"] == "used"
    assert "examples" not in media_type
