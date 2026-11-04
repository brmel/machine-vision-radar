from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

@dataclass(frozen=True, slots=True)
class Request:
    method: str
    path: str
    body: bytes
    headers: Mapping[str, str]
    address: str
    query: Mapping[str, str] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: Mapping[str, Any] | None = None
    headers: Mapping[str, str] = field(default_factory=dict)

class Endpoint(Protocol):
    def respond(self, request: Request) -> Response:
        ...
