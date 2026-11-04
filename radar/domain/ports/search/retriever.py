from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Fact:
    label: str
    value: str
    source: str | None

@dataclass(frozen=True, slots=True)
class SourceRef:
    id: str
    title: str
    url: str | None

@dataclass(frozen=True, slots=True)
class EvidenceProduct:
    id: str
    name: str
    vendor: str
    category: str
    summary: str
    facts: tuple[Fact, ...]
    sources: tuple[SourceRef, ...]

@dataclass(frozen=True, slots=True)
class Evidence:
    products: tuple[EvidenceProduct, ...]

    def ids(self) -> frozenset[str]:
        return frozenset(i for p in self.products for i in (p.id, *(s.id for s in p.sources)))

class Retriever(Protocol):
    def evidence(self, question: str, locale: str) -> Evidence:
        ...

    def about(self, products: tuple[str, ...], locale: str) -> Evidence:
        ...
