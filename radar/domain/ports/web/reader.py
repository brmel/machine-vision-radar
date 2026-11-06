from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from radar.domain.model.entities import Instant

@dataclass(frozen=True, slots=True)
class Link:
    address: str
    site: str

    def within(self, sites: Iterable[str]) -> bool:
        return any(self.site == site or self.site.endswith(f".{site}") for site in sites)

@dataclass(frozen=True, slots=True)
class Page:
    link: Link
    title: str
    text: str
    links: tuple[Link, ...]
    images: tuple[Link, ...]
    retrieved_at: Instant

@dataclass(frozen=True, slots=True)
class File:
    link: Link
    mime: str
    content: bytes
    retrieved_at: Instant

@dataclass(frozen=True, slots=True)
class Unread:
    address: str
    reason: str

class Reader(Protocol):
    def link(self, address: str) -> Link | Unread:
        ...

    def page(self, link: Link, by: Instant) -> Page | Unread:
        ...

    def file(self, link: Link, by: Instant) -> File | Unread:
        ...

    def sitemap(self, site: Link, by: Instant) -> tuple[Link, ...] | Unread:
        ...
