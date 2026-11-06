from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import Claim, Product
from radar.domain.model.registry import Registry

@dataclass(frozen=True, slots=True)
class Coverage:
    products: int
    no_category: tuple[str, ...]
    untagged: tuple[str, ...]
    thin: tuple[str, ...]

    @staticmethod
    def of(catalog: Catalog, registry: Registry, thin: Collection[str]) -> Coverage:
        products = catalog.all(Product)
        return Coverage(
            products=len(products),
            no_category=tuple(sorted(p.id for p in products if p.category not in registry.categories)),
            untagged=tuple(sorted(p.id for p in products if not p.tags)),
            thin=tuple(sorted(thin)),
        )

@dataclass(frozen=True, slots=True)
class SpecShare:
    key: str
    products: int
    share: float

@dataclass(frozen=True, slots=True)
class CategoryCoverage:
    category: str
    products: int
    missing_required: int
    specs: tuple[SpecShare, ...]

def _shares(members: list[Product], keys: tuple[str, ...], claimed: dict[str, set[str]]) -> tuple[SpecShare, ...]:
    counts = [(k, sum(1 for p in members if k in claimed.get(p.id, ()))) for k in keys]
    return tuple(SpecShare(k, n, round(n / len(members), 3)) for k, n in sorted(counts, key=lambda kn: (-kn[1], kn[0])))

def _category(cid: str, members: list[Product], registry: Registry, claimed: dict[str, set[str]]) -> CategoryCoverage:
    sections = registry.profile(cid).sections
    return CategoryCoverage(cid, len(members), sum(1 for p in members if registry.unstated(p, claimed.get(p.id, ()))),
                            _shares(members, (*sections.core, *sections.detail), claimed))

def spec_shares(catalog: Catalog, registry: Registry, category: str | None = None) -> tuple[CategoryCoverage, ...]:
    products = [p for p in catalog.all(Product) if category in (None, p.category)]
    claimed: dict[str, set[str]] = {}
    for c in catalog.all(Claim):
        claimed.setdefault(c.subject, set()).add(c.spec_key)
    by_category: dict[str, list[Product]] = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p)
    return tuple(_category(cid, members, registry, claimed) for cid, members in sorted(by_category.items()))
