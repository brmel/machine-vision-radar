from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Page:
    url: str
    title: str
    text: str
    links: tuple[str, ...]
    retrieved_at: str
    images: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class File:
    url: str
    mime: str
    content: bytes
    retrieved_at: str

class Unfetchable(Exception):
    ...

class PageFetcher(Protocol):
    def fetch(self, url: str, within: float) -> Page:
        ...

    def file(self, url: str, within: float) -> File:
        ...
