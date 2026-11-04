from __future__ import annotations

from typing import Iterable, Sequence, TypeVar

from radar.domain.model import versions
from radar.domain.model.entities import Claim, ProductVersion, VersionRange
from radar.domain.ports.catalog.catalog import Catalog

T = TypeVar("T")

class MemoryCatalog(Catalog):
    def __init__(self, entities: Iterable[object] = ()) -> None:
        self._by_kind: dict[type, list[object]] = {}
        self._by_id: dict[str, object] = {}
        for e in entities:
            self._by_kind.setdefault(type(e), []).append(e)
            self._by_id.setdefault(getattr(e, "id"), e)

    def all(self, kind: type[T]) -> Sequence[T]:
        return tuple(self._by_kind.get(kind, ()))

    def get(self, entity_id: str) -> object | None:
        return self._by_id.get(entity_id)

    def versions_of(self, product: str) -> Sequence[ProductVersion]:
        return versions.order([v for v in self.all(ProductVersion) if v.product == product])

    def resolve(self, vrange: VersionRange) -> Sequence[ProductVersion]:
        ordered = self.versions_of(vrange.product)
        exclude = vrange.exclude or ()
        labels = {v.label for v in ordered}
        unknown = [x for x in (vrange.min, vrange.max, *(vrange.include or ()), *exclude) if x is not None
                   and x not in labels]
        if unknown:
            raise ValueError(f"version '{unknown[0]}' is not a version of {vrange.product}")
        return [v for v in _chosen(ordered, vrange) if v.label not in exclude]

    def claims_for(self, subject: str) -> Sequence[Claim]:
        return [c for c in self.all(Claim) if c.subject == subject and c.applies_to_versions is None]

def _chosen(ordered: Sequence[ProductVersion], vrange: VersionRange) -> list[ProductVersion]:
    at: dict[str, int] = {}
    for n, v in enumerate(ordered):
        at.setdefault(v.label, n)
    span = vrange.min or vrange.max or not vrange.include
    inside = list(ordered[at.get(vrange.min, 0):at.get(vrange.max, len(ordered) - 1) + 1]) if span else []
    return inside + [v for v in ordered if v.label in (vrange.include or ()) and v not in inside]
