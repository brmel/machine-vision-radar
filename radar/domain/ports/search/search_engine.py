from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from radar.domain.model.entities import EmbedderModel, ProductCard
from radar.domain.ports.search.index_runs import Action

class IndexMismatch(ValueError):
    ...

class NoIndex(LookupError):
    ...

@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    limit: int | None
    semantic: bool = False
    category: str | None = None
    tag: str | None = None

@dataclass(frozen=True, slots=True)
class Match:
    field: str
    terms: tuple[str, ...]
    key: str | None = None

@dataclass(frozen=True, slots=True)
class Hit:
    card: ProductCard
    score: float
    why: tuple[Match, ...] = ()
    ranks: Mapping[str, int] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class Built:
    version: str
    embedded: tuple[str, ...]
    removed: tuple[str, ...]
    products: int

@dataclass(frozen=True, slots=True)
class IndexState:
    version: str
    model: EmbedderModel
    products: int

class SearchEngine(Protocol):
    def index(self, action: Action) -> Built:
        ...

    def last_indexed(self) -> IndexState:
        ...

    def search(self, request: SearchRequest) -> list[Hit]:
        ...
