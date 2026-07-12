# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fastapi_uploadstream",
#     "fastapi",
#     "uvicorn",
#     "python-multipart",
# ]
#
# [tool.uv.sources]
# fastapi_uploadstream = { path = ".", editable = true }
# ///


from typing import Annotated

from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

try:
    import uvicorn  # pyright: ignore[reportMissingImports]

    __uvicorn_import_error__ = None
except ImportError as ie:
    uvicorn = None  # type: ignore[assignment, misc]
    __uvicorn_import_error__ = ie


class DemoResponse(BaseModel):
    message: str
    content_type: str
    body: str


app = FastAPI()
install_uploadstream_openapi(app)


@app.post("/image-or-text", description="Endpoint that accepts either image/jpeg or text/plain content types")
async def upload_image_or_text(
    body_content: Annotated[
        UploadStream,
        StreamBody(
            media_types=["image/jpeg", "text/plain"],
            title="body content",
        ),
    ],
) -> DemoResponse:
    return DemoResponse(
        message="Item created",
        content_type=body_content.content_type or "",
        body=(await body_content.read(1024)).hex(),
    )


@app.post("/binary")
async def upload_binary_content(
    body_content: Annotated[
        UploadStream,
        StreamBody(
            title="body content",
        ),
    ],
) -> DemoResponse:
    return DemoResponse(
        message="Item created",
        content_type=body_content.content_type or "",
        body=(await body_content.read(1024)).hex(),
    )


# This endpoint is only available if the multipart library is installed,
# which is an optional dependency of fastapi

try:
    import multipart  # noqa: F401
except ImportError:
    pass
else:

    @app.post("/multipart", description="Comparison endpoint for multipart file uploads")
    async def upload_multipart_file(
        body_content: Annotated[UploadFile, File(title="body content")],
    ) -> DemoResponse:
        return DemoResponse(
            message="Item created",
            content_type=body_content.content_type or "",
            body=(await body_content.read(1024)).hex(),
        )


def run_demo() -> None:
    # This test just exists to make sure the example code in the README actually works
    # and is type correct. It doesn't need to assert anything, if it runs without error
    # then the example code is working as intended.
    from fastapi import testclient

    client = testclient.TestClient(app)
    response = client.post(
        "/binary",
        content=b"hello world",
        headers={"Content-Type": "text/plain"},
    )
    if not response.status_code == 200:
        raise RuntimeError(f"Expected status code 200, got {response.status_code}")
    print("Ok")  # noqa: T201


if __name__ == "__main__":
    if not uvicorn:
        raise RuntimeError("Uvicorn is not installed. consider installing it via pip") from __uvicorn_import_error__
    uvicorn.run(app, port=8000)
