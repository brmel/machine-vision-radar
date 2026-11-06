"""The in-memory catalog and its ProductVersion ordering per version scheme. Data-driven exception: each scheme is an
ordering of its own, which the catalog applies with no registry; registry_integrity holds the version_schemes vocabulary
to these."""
from __future__ import annotations

import re
from typing import Callable, Iterable, Iterator, Mapping, Sequence, TypeVar

from ..ports.catalog.catalog import Catalog
from .entities import Claim, Entity, ProductVersion, VersionRange

T = TypeVar("T")

def _numeric(v: ProductVersion) -> tuple[int, ...]:
    parts = re.findall(r"\d+", v.label)
    if not parts:
        raise ValueError(f"version '{v.label}' of {v.product} has no numeric part for scheme '{v.scheme}'")
    return tuple(int(p) for p in parts)

def _released(v: ProductVersion) -> str:
    if v.released is None:
        raise ValueError(f"version '{v.label}' of {v.product} uses scheme 'continuous' but has no released date")
    return v.released.value

def _supersedes_chain(versions: Sequence[ProductVersion]) -> list[ProductVersion]:
    by_id = {v.id: v for v in versions}
    successors = {v.supersedes: v for v in versions if v.supersedes in by_id}
    roots = [v for v in versions if v.supersedes not in by_id]
    if len(roots) != 1:
        raise ValueError(f"vendor scheme needs one supersedes chain, found {len(roots)} roots")
    chain = [roots[0]]
    while chain[-1].id in successors:
        chain.append(successors[chain[-1].id])
    if len(chain) != len(versions):
        raise ValueError("vendor scheme: supersedes chain does not cover every version")
    return chain

_ORDERS: dict[str, Callable[[Sequence[ProductVersion]], list[ProductVersion]]] = {
    "semver": lambda vs: sorted(vs, key=_numeric),
    "calver": lambda vs: sorted(vs, key=_numeric),
    "continuous": lambda vs: sorted(vs, key=_released),
    "vendor": _supersedes_chain,
}

def order(versions: Sequence[ProductVersion]) -> list[ProductVersion]:
    if not versions:
        return []
    schemes = {v.scheme for v in versions}
    if len(schemes) != 1:
        raise ValueError(f"versions of {versions[0].product} mix schemes {sorted(schemes)}")
    scheme = schemes.pop()
    if scheme not in _ORDERS:
        raise ValueError(f"no ordering for version scheme '{scheme}'")
    return _ORDERS[scheme](versions)

SCHEMES = frozenset(_ORDERS)

class MemoryCatalog(Catalog):
    def __init__(self, entities: Iterable[Entity] = ()) -> None:
        self._by_kind: dict[type, list[Entity]] = {}
        self._by_id: dict[str, Entity] = {}
        for e in entities:
            self._by_kind.setdefault(type(e), []).append(e)
            self._by_id.setdefault(e.id, e)

    def __iter__(self) -> Iterator[Entity]:
        return iter(self._by_id.values())

    def changed(self, after: Mapping[str, Entity | None]) -> MemoryCatalog:
        kept = [e for e in self if e.id not in after]
        return MemoryCatalog(sorted([*kept, *(e for e in after.values() if e is not None)], key=lambda e: e.id))

    def all(self, kind: type[T]) -> Sequence[T]:
        return tuple(self._by_kind.get(kind, ()))

    def get(self, entity_id: str) -> Entity | None:
        return self._by_id.get(entity_id)

    def versions_of(self, product: str) -> Sequence[ProductVersion]:
        return order([v for v in self.all(ProductVersion) if v.product == product])

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
