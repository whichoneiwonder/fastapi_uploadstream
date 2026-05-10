# FastAPI UploadStream

Streaming raw request-body helpers for FastAPI that enable efficient handling of large binary uploads without multipart complexity.

## Features

- **Streaming uploads** — Handle large files without loading them entirely into memory
- **Binary body support** — Accept raw binary data directly in request bodies
- **Content-Length aware** — Automatically extract file size from request headers
- **OpenAPI documentation** — Auto-generate schema documentation for streaming endpoints
- **File-like interface** — Use familiar `read()` and `iter_chunks()` methods for consuming streams

## Installation

```bash
pip install fastapi_uploadstream
```

## Quick Start

```python
from typing import Annotated
from fastapi import FastAPI, Depends
from fastapi_uploadstream import UploadStream, StreamBody, install_uploadstream_openapi

app = FastAPI()
install_uploadstream_openapi(app)

@app.post("/upload")
async def upload_file(
    body_content: Annotated[
        UploadStream,
        Depends(
            StreamBody(
                media_types=["application/octet-stream"],
                title="File upload",
            )
        ),
    ],
):
    data = await body_content.read()
    return {
        "size": body_content.size,
        "content_type": body_content.content_type,
    }
```

## When to Use

### ✅ Use UploadStream for:
- Large file uploads (to avoid memory overhead)
- Proxying streaming content to a backend API or storage
- Binary data streams
- Direct binary body requests
- Maintaining compatibility with non-form-based legacy endpoints

### ❌ Use FastAPI's UploadFile for:
- Multipart form uploads
- Multiple files in one request
- Form fields combined with file uploads

## Requirements

- Python 3.10+
- FastAPI 0.116.1+
- anyio (for async streaming primitives)

## License

MIT
