---
name: fastapi-uploadstream-binary-upload
description: "Guide for handling HTTP uploads of binary data in FastAPI using fastapi_uploadstream. Use when users ask about how to upload raw http bodies to a fastapi app without multipart encoding. Describes StreamBody, UploadStream, content-type validation, chunked reads, or OpenAPI binary requestBody setup."
argument-hint: "endpoint shape, accepted media types, and whether OpenAPI docs are needed"
user-invocable: true
---

# FastAPI UploadStream Binary Uploads

Use this skill when you need to implement or explain raw HTTP binary uploads in FastAPI with `fastapi_uploadstream`.

## What This Skill Covers

- Installing and importing the library
- Defining a streaming endpoint with `StreamBody`
- Reading upload bytes safely with `UploadStream`
- Restricting accepted `Content-Type` values
- Publishing correct OpenAPI `requestBody` schema for binary bodies

## Core Pattern

Use `Annotated[UploadStream, StreamBody(...)]` on a single endpoint parameter.
Call `install_uploadstream_openapi(app)` once during app setup.

```python
from typing import Annotated

from fastapi import FastAPI
from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

import hashlib  # For demo only - not required.

app = FastAPI()
install_uploadstream_openapi(app)


@app.post("/upload")
async def upload_binary(
    body: Annotated[
        UploadStream,
        StreamBody(
            media_types=["application/octet-stream"],
            title="Binary upload",
            description="Raw binary request body to hash and return metadata",
        ),
    ],
):
    # Calculate SHA-256 hash of the uploaded data (for demo purposes)
    sha256 = hashlib.sha256()
    async for chunk in body.iter_chunks():
        sha256.update(chunk)
    return {
        "bytes": body.size,
        "content_type": body.content_type,
        "filename": body.filename,
        "size": body.size,
        "sha256": sha256.hexdigest(),
    }
```

## Practical Guidance

1. Prefer `read(size)` or `iter_chunks()` for large payloads.
2. Set `media_types` to explicit values like `application/octet-stream` or `image/*`.
3. Expect HTTP 415 when the request `Content-Type` is not allowed.
4. Use only one `StreamBody(...)` per endpoint.
5. Do not mix `StreamBody` with `Body`, `Form`, `File`, or `UploadFile` on the same endpoint.

## Streaming Large Files

```python
@app.post("/upload-large")
async def upload_large(
    body: Annotated[UploadStream, StreamBody(media_types=["application/octet-stream"])],
):
    total = 0
    async for chunk in body.iter_chunks(chunk_size=64 * 1024):
        total += len(chunk)
        # Process each chunk here.
    return {"bytes": total}
```

## Ingesting whole file in memory (only small files)

You can also read the entire upload into memory for small files:
But beware that this can lead to high memory usage for large uploads, and should be avoided.
```python
@app.post("/upload-small")
async def upload_small(
    body: Annotated[UploadStream, StreamBody(media_types=["application/octet-stream"])],
):
    total = 0
    # watch out! this loads the entire request body!
    data = await body.read()
    total = len(data)
    return {"bytes": total}
```

## Client Example

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "content-type: application/octet-stream" \
  -H "x-filename: payload.bin" \
  --data-binary @payload.bin
```

## Request Handling Notes

- `body.filename` comes from the `x-filename` header when present.
- `body.size` is derived from `Content-Length` when available.
- `body.content_type` is the incoming request content type.
- `read(-1)` reads all remaining bytes.

## More Examples

See [reference examples](./references/examples.md) for common endpoint variants.