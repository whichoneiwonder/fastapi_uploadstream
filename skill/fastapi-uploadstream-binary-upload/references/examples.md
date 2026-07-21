# Binary Upload Recipes

## Accept Multiple Content Types

```python
from typing import Annotated

from fastapi import FastAPI
from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

app = FastAPI()
install_uploadstream_openapi(app)


@app.post("/ingest")
async def ingest(
    body: Annotated[
        UploadStream,
        StreamBody(media_types=["application/octet-stream", "image/png", "image/jpeg"]),
    ],
):
    # copy input stream to an output stream
    with open('output-file.bin', 'wb') as output:
        async for data in body.iter_chunks():
            output.write(data)
```

## Skip Prefix Bytes Then Process Remaining Stream

```python
@app.post("/parse-with-header")
async def parse_with_header(
    body: Annotated[UploadStream, StreamBody(media_types=["application/octet-stream"])],
):
    await body.seek(16)
    payload = await body.read()
    return {"payload_bytes": len(payload)}
```

## Proxy Streaming Bytes to Storage in Chunks

```python
@app.post("/store")
async def store(
    body: Annotated[UploadStream, StreamBody(media_types=["application/octet-stream"])],
):
    total = 0
    async for chunk in body.iter_chunks(chunk_size=1024 * 1024):
        total += len(chunk)
        # write chunk to object storage or downstream service
    return {"stored_bytes": total}
```

## Troubleshooting Checklist

- 415 response: verify request `Content-Type` is in `StreamBody(media_types=...)`.
- Missing schema in docs: ensure `install_uploadstream_openapi(app)` runs before OpenAPI generation.
- Empty upload unexpectedly: verify the client actually sent a request body.
- Validation or docs conflicts: ensure the endpoint has only one `StreamBody` and no `Body`/`Form`/`File` params.