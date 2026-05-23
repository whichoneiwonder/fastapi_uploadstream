# Publish `fastapi_uploadstream` as a library — TODO

## Packaging and metadata
- [ ] Decide and document the stable public API.
  - Keep `UploadStream`, `StreamBody`, and `install_uploadstream_openapi` public.
  - Decide whether `StreamBodyParam` and `size_from_request` should remain exported.
- [x] Remove `uvicorn[standard]` from runtime dependencies in `pyproject.toml`.
  - Move it to a dev/demo dependency group instead.
- [x] Add `anyio` as a direct runtime dependency, since the package imports it directly.
- [x] Revisit `requires-python`.
  - Test whether the library works on Python 3.10+ or 3.11+.
  - Lower the minimum supported version if the test matrix passes.
- [x] Add/complete package metadata in `pyproject.toml`.
  - License metadata
  - Classifiers
  - Keywords
  - Project URLs (Homepage, Repository, Issues, Documentation)
- [x] Add a `LICENSE` file and ensure it matches the README claim.
- [ ] Decide on versioning policy for `0.x` releases and document it.

## API contract and docs
- [ ] Document the runtime contract of `UploadStream`.
  - `read()` semantics
  - EOF behavior
  - `seek()` is forward-only consume-and-discard
  - `iter_chunks()` behavior
  - `close()` behavior
  - `size` comes from `Content-Length` and may be `None`
  - `filename` comes from the `x-filename` header
- [ ] Document the differences from FastAPI `UploadFile`.
  - Raw body streaming vs multipart uploads
  - Not a drop-in replacement for multipart form/file handling
- [ ] Document the OpenAPI installation requirement clearly.
  - Runtime works with `StreamBody`
  - OpenAPI request-body docs require `install_uploadstream_openapi(app)`
- [ ] Decide what to do with partially supported `StreamBody(...)` parameters.
  - `title`
  - `examples`
  - `example`
  - `openapi_examples`
  - `deprecated`
- [ ] Either implement support for those parameters in OpenAPI generation or remove them from the public API.

## Tests to add
git - [x] Add `UploadStream.read()` edge-case tests.
  - `read(0)` returns `b""`
  - `read(-2)` raises `ValueError`
  - repeated `read()` after EOF returns `b""`
  - `read()` after `close()` returns `b""`
- [x] Add `seek()` tests.
  - `seek(0)` no-op
  - `seek(n)` skips bytes correctly
  - seeking past EOF is harmless
  - `seek(-1)` raises `ValueError`
- [x] Add `iter_chunks()` tests.
  - chunk boundaries
  - draining remaining buffered data
  - invalid `chunk_size <= 0` raises `ValueError`
- [x] Add direct media-type matching tests.
  - exact matches
  - wildcard subtype matches like `application/*`
  - `*/*`
  - case-insensitivity
  - content types with parameters like `application/json; charset=utf-8`
- [ ] Add OpenAPI merge/patch tests.
  - routes with existing request bodies
  - multiple `StreamBody` dependencies
  - description propagation
  - behavior for examples-related fields

## Compatibility matrix
- [x] Add CI coverage for supported Python versions.
  - 3.10
  - 3.11
  - 3.12
  - 3.13
  - 3.14
- [x] Test dependencies at both minimum and latest supported versions.
  - FastAPI: min/latest
  - anyio: min/latest if directly bounded
- [x] Decide whether trio is supported.
  - If yes, add tests for `anyio_backend = "trio"`. [x]
  - ~~If no, document asyncio-only support.~~
- [x] Add a package build smoke test.
  - Build wheel and sdist
  - Install built artifact
  - Import `fastapi_uploadstream`
- [x] Add a README example smoke test.

## Release readiness
- [x] Confirm import/install path works cleanly from a fresh virtual environment.
- [ ] Confirm README installation and usage examples still match the released API.
- [ ] Tag the first release only after the compatibility matrix and packaging checks pass.
