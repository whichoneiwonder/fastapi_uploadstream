# /// script
# requires-python = ">=3.13"
# dependencies = ["faststream"]
# ///


from faststream import StreamBody, BinaryUploadFile
from fastapi import FastAPI, UploadFile, File, Depends


app = FastAPI()


@app.post("/binary")
async def upload_binary_content(
    field: BinaryUploadFile = StreamBody(title="body content"),
) -> dict[str, str]:
    return {
        "message": "Item created",
        "content-type": field.content_type or '',
        "body": (await field.read(1024)).hex(),
    }

@app.post("/multipart")
async def upload_multipart_file(
    field: UploadFile = File(title="body content"),
) -> dict[str, str]:
    return {
        "message": "Item created",
        "content-type": field.content_type or '',
        "body": (await field.read(1024)).hex(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        # reload=True,
        # reload_delay=1,
    )
