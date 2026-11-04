from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

@dataclass(frozen=True, slots=True)
class BlobRef:
    sha256: str
    mime: str

class BlobStore(Protocol):
    def put(self, content: bytes, mime: str, public: bool) -> BlobRef:
        ...

    def get(self, ref: BlobRef) -> Iterator[bytes]:
        ...

    def url(self, ref: BlobRef, public: bool) -> str:
        ...

    def has(self, ref: BlobRef) -> bool:
        ...

    def publish(self, ref: BlobRef, public: bool) -> None:
        ...

    def remove(self, ref: BlobRef) -> None:
        ...
