import sys

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict


class ASGIVersions(TypedDict):
    """ASGI version information."""

    spec_version: str
    version: str


class HTTPRequestMessage(TypedDict):
    """ASGI HTTP request body message."""

    type: str
    body: bytes
    more_body: bool


class HTTPDisconnectMessage(TypedDict):
    """ASGI HTTP disconnect message."""

    type: str


class HTTPResponseStartMessage(TypedDict):
    """ASGI HTTP response start message."""

    type: str
    status: int
    headers: NotRequired[list[tuple[bytes, bytes]]]


class HTTPResponseBodyMessage(TypedDict):
    """ASGI HTTP response body message."""

    type: str
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class HTTPScope(TypedDict):
    """ASGI HTTP scope."""

    type: str
    asgi: ASGIVersions
    http_version: str
    method: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: list[tuple[bytes, bytes]]
    client: tuple[str, int]
    server: tuple[str, int]


ASGIMessage = HTTPRequestMessage | HTTPDisconnectMessage | HTTPResponseStartMessage | HTTPResponseBodyMessage
