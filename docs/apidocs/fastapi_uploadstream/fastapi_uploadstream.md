# {py:mod}`fastapi_uploadstream`

```{py:module} fastapi_uploadstream
```

```{autodoc2-docstring} fastapi_uploadstream
:allowtitles:
```

## Package Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`UploadStream <fastapi_uploadstream.UploadStream>`
  - ```{autodoc2-docstring} fastapi_uploadstream.UploadStream
    :summary:
    ```
* - {py:obj}`StreamBodyParam <fastapi_uploadstream.StreamBodyParam>`
  - ```{autodoc2-docstring} fastapi_uploadstream.StreamBodyParam
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`size_from_request <fastapi_uploadstream.size_from_request>`
  - ```{autodoc2-docstring} fastapi_uploadstream.size_from_request
    :summary:
    ```
* - {py:obj}`StreamBody <fastapi_uploadstream.StreamBody>`
  - ```{autodoc2-docstring} fastapi_uploadstream.StreamBody
    :summary:
    ```
* - {py:obj}`install_uploadstream_openapi <fastapi_uploadstream.install_uploadstream_openapi>`
  - ```{autodoc2-docstring} fastapi_uploadstream.install_uploadstream_openapi
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <fastapi_uploadstream.__all__>`
  - ```{autodoc2-docstring} fastapi_uploadstream.__all__
    :summary:
    ```
````

### API

````{py:function} size_from_request(request: fastapi.Request) -> int | None
:canonical: fastapi_uploadstream.size_from_request

```{autodoc2-docstring} fastapi_uploadstream.size_from_request
```
````

`````{py:class} UploadStream(request: fastapi.Request, receiver: anyio.streams.memory.MemoryObjectReceiveStream[bytes | starlette.requests.ClientDisconnect], cancel_receive: collections.abc.Callable[[], object])
:canonical: fastapi_uploadstream.UploadStream

```{autodoc2-docstring} fastapi_uploadstream.UploadStream
```

```{rubric} Initialization
```

```{autodoc2-docstring} fastapi_uploadstream.UploadStream.__init__
```

````{py:method} read(size: int = -1) -> bytes
:canonical: fastapi_uploadstream.UploadStream.read
:async:

```{autodoc2-docstring} fastapi_uploadstream.UploadStream.read
```

````

````{py:method} seek(offset: int) -> None
:canonical: fastapi_uploadstream.UploadStream.seek
:async:

```{autodoc2-docstring} fastapi_uploadstream.UploadStream.seek
```

````

````{py:method} iter_chunks(chunk_size: int = 64 * 1024) -> collections.abc.AsyncIterator[bytes]
:canonical: fastapi_uploadstream.UploadStream.iter_chunks
:async:

```{autodoc2-docstring} fastapi_uploadstream.UploadStream.iter_chunks
```

````

````{py:method} close() -> None
:canonical: fastapi_uploadstream.UploadStream.close
:async:

```{autodoc2-docstring} fastapi_uploadstream.UploadStream.close
```

````

`````

`````{py:class} StreamBodyParam(*, media_types: str | collections.abc.Iterable[str] = '*/*', title: str | None = None, description: str | None = None, examples: list[typing.Any] | None = None, openapi_examples: dict[str, typing.Any] | None = None, deprecated: bool | str | None = None, include_in_schema: bool = True, json_schema_extra: dict[str, typing.Any] | collections.abc.Callable[[dict[str, typing.Any]], None] | None = None, channel_buffer_size: int = 2048, client_disconnect: typing.Literal[eof, raise] = 'raise')
:canonical: fastapi_uploadstream.StreamBodyParam

Bases: {py:obj}`fastapi.params.Body`

```{autodoc2-docstring} fastapi_uploadstream.StreamBodyParam
```

```{rubric} Initialization
```

```{autodoc2-docstring} fastapi_uploadstream.StreamBodyParam.__init__
```

````{py:method} __call__(request: fastapi.Request) -> collections.abc.AsyncIterator[fastapi_uploadstream.UploadStream]
:canonical: fastapi_uploadstream.StreamBodyParam.__call__
:async:

```{autodoc2-docstring} fastapi_uploadstream.StreamBodyParam.__call__
```

````

````{py:method} openapi_request_body() -> dict[str, typing.Any]
:canonical: fastapi_uploadstream.StreamBodyParam.openapi_request_body

```{autodoc2-docstring} fastapi_uploadstream.StreamBodyParam.openapi_request_body
```

````

`````

````{py:function} StreamBody(*, media_types: str | list[str] = '*/*', title: str | None = None, description: str | None = None, examples: list[typing.Any] | None = None, openapi_examples: dict[str, typing.Any] | None = None, deprecated: bool | str | None = None, include_in_schema: bool = True, json_schema_extra: dict[str, typing.Any] | collections.abc.Callable[[dict[str, typing.Any]], None] | None = None, channel_buffer_size: int = 2048, client_disconnect: typing.Literal[eof, raise] = 'raise') -> fastapi_uploadstream.StreamBodyParam
:canonical: fastapi_uploadstream.StreamBody

```{autodoc2-docstring} fastapi_uploadstream.StreamBody
```
````

````{py:function} install_uploadstream_openapi(app: fastapi.FastAPI) -> fastapi.FastAPI
:canonical: fastapi_uploadstream.install_uploadstream_openapi

```{autodoc2-docstring} fastapi_uploadstream.install_uploadstream_openapi
```
````

````{py:data} __all__
:canonical: fastapi_uploadstream.__all__
:value: >
   ['StreamBody', 'StreamBodyParam', 'UploadStream', 'install_uploadstream_openapi', 'size_from_request...

```{autodoc2-docstring} fastapi_uploadstream.__all__
```

````
