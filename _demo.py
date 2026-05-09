# /// script
# requires-python = ">=3.13"
# dependencies = ["faststreambody", "fastapi", "uvicorn"]
# ///


from typing import Annotated

from fastapi import Depends, FastAPI, File, UploadFile
from pydantic import BaseModel

from faststreambody import BinaryUploadFile, StreamBody, install_streambody_openapi


class DemoResponse(BaseModel):
    message: str
    content_type: str
    body: str

app = FastAPI()
install_streambody_openapi(app)


@app.post("/binary")
async def upload_binary_content(
    body_content: Annotated[
        BinaryUploadFile,
        Depends(
            StreamBody(
                media_types=["application/octet-stream", "text/plain"],
                title="body content",
            )
        ),
    ],
) -> DemoResponse:
    return DemoResponse(
        message="Item created",
        content_type=body_content.content_type or "",
        body=(await body_content.read(1024)).hex(),
    )


@app.post("/multipart")
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

    uvicorn.run(
        "_demo:app",
        reload=True,
        reload_delay=1,
    )
