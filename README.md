# FastStreamBody

Streaming raw request-body helpers for FastAPI that enable efficient handling of large binary uploads without multipart complexity.

## Features

- **Streaming uploads** - Handle large files without loading them entirely into memory
- **Binary body support** - Accept raw binary data directly in request bodies
- **Content-Length aware** - Automatically extract file size from request headers
- **OpenAPI documentation** - Auto-generate schema documentation for streaming endpoints
- **File-like interface** - Use familiar `read()` methods for consuming streams

## Installation

```bash
pip install faststreambody
```

## Quick Start

```python
from typing import Annotated
from fastapi import FastAPI, Depends
from faststreambody import BinaryUploadFile, StreamBody, install_streambody_openapi

app = FastAPI()
install_streambody_openapi(app)

@app.post("/upload")
async def upload_file(
    body_content: Annotated[
        BinaryUploadFile,
        Depends(
            StreamBody(
                media_types=["application/octet-stream"],
                title="File upload",
            )
        ),
    ],
):
    # Read the streamed content
    data = await body_content.read()
    return {
        "size": body_content.size,
        "content_type": body_content.content_type,
    }
```

## Usage

### StreamBody Dependency

The `StreamBody` dependency configures how your endpoint accepts streaming uploads:

```python
StreamBody(
    media_types=["application/octet-stream", "text/plain"],  # Accepted content types
    include_in_schema=True,  # Include in OpenAPI schema
    title="Upload content",  # OpenAPI title
)
```

### BinaryUploadFile Object

Once received, you interact with the stream through `BinaryUploadFile`:

```python
@app.post("/upload")
async def handle_upload(
    body: Annotated[BinaryUploadFile, Depends(StreamBody(media_types=["*/*"]))]
):
    # Access file metadata
    print(f"Size: {body.size}")  # From Content-Length header
    print(f"Type: {body.content_type}")
    print(f"Name: {body.filename}")  # From x-filename header
    
    # Read the stream in chunks
    chunk = await body.read(1024)  # Read up to 1024 bytes
    
    # Read remaining data at once
    remaining = await body.read()  # Read all remaining data
    
    # Read everything (resets on first call)
    all_data = await body.read(-1)  # Read all from beginning
```

### OpenAPI Documentation

Call `install_streambody_openapi()` to add automatic schema documentation:

```python
app = FastAPI()
install_streambody_openapi(app)
```

This adds proper OpenAPI definitions for binary request bodies on your streaming endpoints.

## When to Use

### ✅ Use FastStreamBody for:
- Large file uploads (to avoid memory overhead)
- Binary data streams
- Streaming content without multipart complexity
- Direct binary body requests

### ❌ Use FastAPI's UploadFile for:
- Multipart form uploads
- Multiple files in one request
- Form fields + file combinations

## Example: File Upload with Size Tracking

```python
@app.post("/upload-large")
async def upload_large_file(
    body: Annotated[
        BinaryUploadFile,
        Depends(StreamBody(media_types=["application/octet-stream"]))
    ]
):
    bytes_received = 0
    chunk_size = 65536  # 64KB chunks
    
    while True:
        chunk = await body.read(chunk_size)
        if not chunk:
            break
        bytes_received += len(chunk)
        # Process chunk...
    
    return {"total_bytes": bytes_received}
```

## Requirements

- Python 3.13+
- FastAPI 0.116.1+
- anyio (for async streaming primitives)

## License

MIT
