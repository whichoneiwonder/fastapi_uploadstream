# Usage Guide

## Installation

Install the package from PyPI:

```bash
pip install fastapi_uploadstream
```

For the full FastAPI standard extras (Uvicorn, etc.):

```bash
pip install "fastapi[standard]"
```

---

## StreamBody Dependency

`StreamBody` is a factory function that returns a FastAPI-compatible dependency.
Annotate your endpoint signature to receive an [`UploadStream`][fastapi_uploadstream.UploadStream].

```python
from typing import Annotated
from fastapi import FastAPI
from fastapi_uploadstream import StreamBody, UploadStream, install_uploadstream_openapi

app = FastAPI()
install_uploadstream_openapi(app)


@app.post("/upload")
async def upload(body: Annotated[UploadStream, StreamBody(media_types=["application/octet-stream"])]):
    data = await body.read()
    return {"bytes": len(data)}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `media_types` | `str \| list[str]` | `"*/*"` | Accepted content types. Supports wildcards like `"image/*"`. |
| `title` | `str \| None` | `None` | OpenAPI request body title. |
| `description` | `str \| None` | `None` | OpenAPI request body description. |
| `include_in_schema` | `bool` | `True` | Whether to include the body in the generated OpenAPI schema. |
| `json_schema_extra` | `dict \| None` | `None` | Extra fields merged into the OpenAPI binary schema. |
| `channel_buffer_size` | `int` | `2048` | Number of bytes buffered in the in-process stream channel. |

---

## UploadStream Object

`UploadStream` provides a file-like interface over the raw HTTP request body.
It is yielded by the `StreamBody` dependency and should not be constructed directly.

### Metadata attributes

```python
body.filename  # Value of the x-filename request header, or None
body.size  # Value of Content-Length as int, or None if absent
body.content_type  # Content-Type header value
body.request  # The underlying Starlette Request
```

### Reading data

```python
# Read all remaining bytes at once
all_bytes: bytes = await body.read()

# Read up to N bytes
chunk: bytes = await body.read(4096)

# Iterate in fixed-size chunks (default 64 KB)
async for chunk in body.iter_chunks(chunk_size=65536):
    process(chunk)

# Discard N bytes from the current position
await body.seek(1024)

# Explicitly close (also called automatically on dependency teardown)
await body.close()
```

---

## OpenAPI Integration

Call `install_uploadstream_openapi()` once on your `FastAPI` application to patch
the OpenAPI generator so that endpoints using `StreamBody` show correct binary
`requestBody` definitions in the schema:

```python
from fastapi import FastAPI
from fastapi_uploadstream import install_uploadstream_openapi

app = FastAPI()
install_uploadstream_openapi(app)
```

This must be called **before** any request triggers schema generation
(i.e. before the first call to `/openapi.json` or `/docs`).

---

## Multiple Content Types

You can accept several content types on a single endpoint:

```python
StreamBody(media_types=["application/octet-stream", "image/png", "image/jpeg"])
```

Wildcard sub-types are also supported:

```python
StreamBody(media_types=["image/*"])  # accepts any image/* content type
StreamBody(media_types=["*/*"])  # accepts anything (the default)
```

If the client sends a content type not in the list, the dependency raises
`HTTP 415 Unsupported Media Type` automatically.

---

## Example: Large File Upload with Progress Tracking

```python
@app.post("/upload-large")
async def upload_large_file(body: Annotated[UploadStream, StreamBody()]):
    bytes_received = 0

    async for chunk in body.iter_chunks(chunk_size=65536):
        bytes_received += len(chunk)
        # process chunk …

    return {"total_bytes": bytes_received}
```

---

## Example: Proxy to Object Storage

```python
import httpx


@app.put("/proxy-upload")
async def proxy_upload(body: Annotated[UploadStream, StreamBody(media_types=["application/octet-stream"])]):
    async with httpx.AsyncClient() as client:

        async def stream_body():
            async for chunk in body.iter_chunks():
                yield chunk

        response = await client.put(
            "https://storage.example.com/bucket/object",
            content=stream_body(),
            headers={"Content-Type": body.content_type},
        )
    return {"status": response.status_code}
```
