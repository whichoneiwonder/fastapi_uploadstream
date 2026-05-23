"""Unit tests for UploadStream.read(), seek(), iter_chunks(), and media-type matching."""

from __future__ import annotations

import pytest
from anyio import create_memory_object_stream
from starlette.requests import Request

from fastapi_uploadstream import (
    UploadStream,
    _media_type_matches,  # type: ignore[attr-defined]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(headers: dict[str, str] | None = None) -> Request:
    headers = headers or {}
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


async def _make_stream(*chunks: bytes, headers: dict[str, str] | None = None) -> UploadStream:
    """Build an UploadStream pre-loaded with the given chunks."""
    send, recv = create_memory_object_stream[bytes](max_buffer_size=max(len(chunks), 1))
    async with send:
        for chunk in chunks:
            await send.send(chunk)
    return UploadStream(
        request=_make_request(headers),
        receiver=recv,
        cancel_receive=lambda: None,
    )


# ---------------------------------------------------------------------------
# read() edge cases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_read_zero_returns_empty() -> None:
    stream = await _make_stream(b"hello")
    assert await stream.read(0) == b""


@pytest.mark.anyio
async def test_read_negative_two_raises_value_error() -> None:
    stream = await _make_stream(b"hello")
    with pytest.raises(ValueError, match="size must be >= -1"):
        await stream.read(-2)


@pytest.mark.anyio
async def test_repeated_read_after_eof_returns_empty() -> None:
    stream = await _make_stream(b"hello")
    first = await stream.read()
    assert first == b"hello"
    assert await stream.read() == b""
    assert await stream.read() == b""


@pytest.mark.anyio
async def test_read_sized_after_eof_returns_empty() -> None:
    stream = await _make_stream(b"hi")
    await stream.read(2)
    assert await stream.read(1) == b""


@pytest.mark.anyio
async def test_read_after_close_returns_empty() -> None:
    stream = await _make_stream(b"data")
    await stream.close()
    assert await stream.read() == b""
    assert await stream.read(3) == b""


@pytest.mark.anyio
async def test_read_exact_size_consumes_incrementally() -> None:
    stream = await _make_stream(b"abcdef")
    assert await stream.read(3) == b"abc"
    assert await stream.read(3) == b"def"


@pytest.mark.anyio
async def test_read_more_than_available_returns_all() -> None:
    stream = await _make_stream(b"abc")
    assert await stream.read(100) == b"abc"


@pytest.mark.anyio
async def test_read_across_chunk_boundaries() -> None:
    stream = await _make_stream(b"abc", b"def", b"ghi")
    assert await stream.read(5) == b"abcde"
    assert await stream.read() == b"fghi"


# ---------------------------------------------------------------------------
# seek() tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_seek_zero_is_noop() -> None:
    stream = await _make_stream(b"hello")
    await stream.seek(0)
    assert await stream.read() == b"hello"


@pytest.mark.anyio
async def test_seek_skips_bytes() -> None:
    stream = await _make_stream(b"abcdef")
    await stream.seek(3)
    assert await stream.read() == b"def"


@pytest.mark.anyio
async def test_seek_past_eof_is_harmless() -> None:
    stream = await _make_stream(b"abc")
    await stream.seek(1000)
    assert await stream.read() == b""


@pytest.mark.anyio
async def test_seek_negative_raises_value_error() -> None:
    stream = await _make_stream(b"hello")
    with pytest.raises(ValueError, match="Negative seek position"):
        await stream.seek(-1)


@pytest.mark.anyio
async def test_seek_partial_then_read() -> None:
    stream = await _make_stream(b"0123456789")
    await stream.seek(4)
    assert await stream.read(3) == b"456"
    assert await stream.read() == b"789"


# ---------------------------------------------------------------------------
# iter_chunks() tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_iter_chunks_zero_raises_value_error() -> None:
    stream = await _make_stream(b"data")
    with pytest.raises(ValueError, match="chunk_size must be > 0"):
        async for _ in stream.iter_chunks(0):
            pass


@pytest.mark.anyio
async def test_iter_chunks_negative_raises_value_error() -> None:
    stream = await _make_stream(b"data")
    with pytest.raises(ValueError, match="chunk_size must be > 0"):
        async for _ in stream.iter_chunks(-1):
            pass


@pytest.mark.anyio
async def test_iter_chunks_exact_boundaries() -> None:
    stream = await _make_stream(b"abcdef")
    chunks = [c async for c in stream.iter_chunks(3)]
    assert chunks == [b"abc", b"def"]


@pytest.mark.anyio
async def test_iter_chunks_last_chunk_smaller_than_size() -> None:
    stream = await _make_stream(b"abcde")
    chunks = [c async for c in stream.iter_chunks(3)]
    assert chunks == [b"abc", b"de"]


@pytest.mark.anyio
async def test_iter_chunks_drains_remaining_buffer() -> None:
    """Data already pulled into the internal buffer must be yielded by iter_chunks."""
    stream = await _make_stream(b"abcdef")
    partial = await stream.read(2)
    assert partial == b"ab"
    # iter_chunks must drain the leftover buffer before reading more.
    chunks = [c async for c in stream.iter_chunks(4)]
    assert b"".join(chunks) == b"cdef"


@pytest.mark.anyio
async def test_iter_chunks_single_chunk_larger_than_data() -> None:
    stream = await _make_stream(b"hi")
    chunks = [c async for c in stream.iter_chunks(1024)]
    assert chunks == [b"hi"]


@pytest.mark.anyio
async def test_iter_chunks_empty_stream_yields_nothing() -> None:
    stream = await _make_stream()
    chunks = [c async for c in stream.iter_chunks(8)]
    assert chunks == []


@pytest.mark.anyio
async def test_iter_chunks_across_multiple_network_chunks() -> None:
    """chunk_size that crosses incoming network-chunk boundaries assembles correctly."""
    stream = await _make_stream(b"abc", b"def", b"ghi")
    chunks = [c async for c in stream.iter_chunks(4)]
    # 9 bytes with chunk_size=4 → [b"abcd", b"efgh", b"i"]
    assert b"".join(chunks) == b"abcdefghi"
    assert len(chunks[0]) == 4
    assert chunks[-1] == b"i"


# ---------------------------------------------------------------------------
# Media-type matching tests
# ---------------------------------------------------------------------------


def test_media_type_exact_match() -> None:
    assert _media_type_matches("application/json", "application/json")


def test_media_type_exact_no_match() -> None:
    assert not _media_type_matches("application/xml", "application/json")


def test_media_type_wildcard_subtype_matches() -> None:
    assert _media_type_matches("application/json", "application/*")
    assert _media_type_matches("application/octet-stream", "application/*")


def test_media_type_wildcard_subtype_does_not_match_other_type() -> None:
    assert not _media_type_matches("text/plain", "application/*")


def test_media_type_star_star_matches_everything() -> None:
    assert _media_type_matches("application/json", "*/*")
    assert _media_type_matches("text/html", "*/*")
    assert _media_type_matches("image/png", "*/*")


def test_media_type_case_insensitive_content_type() -> None:
    assert _media_type_matches("Application/JSON", "application/json")
    assert _media_type_matches("application/json", "Application/JSON")


def test_media_type_case_insensitive_wildcard() -> None:
    assert _media_type_matches("TEXT/PLAIN", "text/*")


def test_media_type_strips_parameters() -> None:
    assert _media_type_matches("application/json; charset=utf-8", "application/json")
    assert _media_type_matches("text/html; charset=utf-8", "text/*")
    assert _media_type_matches("application/json; charset=utf-8", "*/*")
