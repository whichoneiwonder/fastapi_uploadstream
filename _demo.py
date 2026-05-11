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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000)
