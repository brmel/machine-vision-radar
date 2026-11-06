from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from radar.domain.model.entities import (CategoryEntry, CategoryPage, FeedBrief, IndexCounts, IndexView, OrgBrief,
                                         ProductCard, ProductView, RegistryView, SpecCell, SpecLabel,
                                         TermEntry, TermRef, ViewValue)
from radar.domain.model.history.projection import plain
from radar.domain.model.registry import Registry
from .facets import compute_category_facets

PAGE_SIZE = 20
CARD_SPECS = 3

def _card_specs(view: ProductView, keys: tuple[str, ...]) -> dict[str, ViewValue]:
    cells = {c.key: c.value for c in (*view.core, *view.detail) if c.value is not None}
    return {k: cells[k] for k in keys if k in cells}

def parse_card(c: Mapping[str, Any]) -> ProductCard:
    return ProductCard(id=c["id"], slug=c["slug"], name=c["name"], kind=c["kind"],
                       vendor=c["vendor"], vendor_name=c["vendor_name"], category=c["category"],
                       summary=c.get("summary"), status=TermRef(**c["status"]) if c.get("status") else None,
                       tags=tuple(c["tags"]), specs=c["specs"],
                       thumbnail_url=c.get("thumbnail_url"))

def card(view: ProductView, keys: tuple[str, ...]) -> ProductCard:
    return ProductCard(id=view.id, slug=view.slug, name=view.name, kind=view.kind, vendor=view.vendor.slug,
                       vendor_name=view.vendor.name, category=view.category,
                       summary=dict(view.summary) if view.summary else None,
                       status=view.status.term if view.status else None, tags=tuple(t.id for t in view.tags),
                       specs=_card_specs(view, keys), thumbnail_url=view.thumbnail_url)

def index_card(view: ProductView) -> ProductCard:
    return card(view, tuple([c.key for c in view.core if c.value is not None][:CARD_SPECS]))

def listing_card(registry: Registry, view: ProductView) -> ProductCard:
    profile = registry.profile(view.category)
    return card(view, tuple(dict.fromkeys((*profile.sections.core, *(f.field for f in profile.facets)))))

def paginate(registry: Registry, category: str, cards: Sequence[ProductCard]) -> list[CategoryPage]:
    profile = registry.profile(category)
    sorted_cards = sorted(cards, key=lambda c: (c.name.lower(), c.id))
    ordered = [plain(c) for c in sorted_cards]
    facets = compute_category_facets(registry, profile, ordered)
    pages = max(1, math.ceil(len(ordered) / PAGE_SIZE))
    return [CategoryPage(category=category, page=n, pages=pages, next=str(n + 1) if n < pages else None,
                         facets=facets, products=tuple(sorted_cards[(n - 1) * PAGE_SIZE:n * PAGE_SIZE]))
            for n in range(1, pages + 1)]

@dataclass(frozen=True, slots=True)
class Tally:
    days: Counter[str] = field(default_factory=Counter)

    @staticmethod
    def of(view: ProductView) -> Tally:
        return Tally(Counter(s.retrieved_at[:10] for s in view.sources))

    def __add__(self, other: Tally) -> Tally:
        return Tally(self.days + other.days)

    def __sub__(self, other: Tally) -> Tally:
        return Tally(self.days - other.days)

    def plain(self) -> dict[str, Any]:
        return {"days": sorted([d, n] for d, n in self.days.items())}

    @staticmethod
    def parse(raw: Mapping[str, Any]) -> Tally:
        return Tally(Counter({d: n for d, n in raw["days"]}))

def _category_entries(registry: Registry, counted: Counter[str],
                      pages: Mapping[str, int]) -> tuple[CategoryEntry, ...]:
    profiles = {p.category_id: p for p in registry.profiles}
    return tuple(CategoryEntry(id=c.id, label=dict(c.label), description=dict(c.description), domain=c.domain,
                               pipeline=c.pipeline, glyph=c.glyph,
                               core=profiles[c.id].sections.core,
                               products=counted[c.id], pages=pages.get(c.id, 0),
                               component_hub=c.component_hub.path if c.component_hub else None)
                 for c in registry.categories.values())

def _spec_defs(registry: Registry) -> dict[str, SpecLabel]:
    symbol = {s.id: registry.units[s.unit].symbol for s in registry.spec_definitions.values() if s.unit}
    return {s.id: SpecLabel(label=dict(s.label), unit=symbol.get(s.id) or None, better=s.better or None)
            for s in registry.spec_definitions.values()}

def _described(registry: Registry, vocab: str) -> tuple[TermEntry, ...]:
    return tuple(TermEntry(id=t.id, label=dict(t.label), description=dict(t.description))
                 for t in registry.vocabularies[vocab].values())

def index(registry: Registry, cards: Sequence[ProductCard], orgs: Sequence[OrgBrief], pages: Mapping[str, int],
          tally: Tally, news: Sequence[FeedBrief]) -> IndexView:
    return IndexView(
        data_as_of=max(tally.days, default=None),
        counts=IndexCounts(products=len(cards), organizations=len(orgs), categories=len(registry.categories)),
        pipeline_stages=_described(registry, "pipeline_stages"), domains=_described(registry, "domains"),
        categories=_category_entries(registry, Counter(c.category for c in cards), pages),
        spec_definitions=_spec_defs(registry),
        spec_groups={g.id: dict(g.label) for g in registry.spec_groups.values()},
        tags=tuple(TermRef(id=t.id, label=dict(t.label)) for t in registry.vocabularies["tags"].values()),
        search=registry.search, news=tuple(news[:registry.feed.teaser]), organizations=tuple(orgs),
        products=tuple(sorted(cards, key=lambda c: c.slug)))

def republished(registry: Registry, stored: RegistryView) -> RegistryView:
    fresh = index(registry, (), (), {}, Tally(), ())
    counted = Counter({c.id: c.products for c in stored.categories})
    return replace(stored, pipeline_stages=fresh.pipeline_stages, domains=fresh.domains,
                   categories=_category_entries(registry, counted, {c.id: c.pages for c in stored.categories}),
                   spec_definitions=fresh.spec_definitions, spec_groups=fresh.spec_groups, tags=fresh.tags,
                   search=fresh.search)

def comparison(index: IndexView, views: list[ProductView]) -> dict[str, Any]:
    return {"products": [{"id": p.id, "name": p.name, "vendor": p.vendor.slug, "category": p.category} for p in views],
            "specs": _rows(index, views)}

def _rows(index: IndexView, views: list[ProductView]) -> list[dict[str, Any]]:
    core = [c.key for v in views for c in v.core]
    detail = [c.key for v in views for c in v.detail if c.key not in core]
    rows = [_compared(key, section, views, index) for section, keys in (("core", core), ("detail", detail))
            for key in dict.fromkeys(keys)]
    return [r for r in rows if r is not None]

def _compared(key: str, section: str, views: list[ProductView], index: IndexView) -> dict[str, Any] | None:
    cells = {v.id: next((c for c in (*v.core, *v.detail) if c.key == key), SpecCell(key=key)) for v in views}
    if all(c.value is None for c in cells.values()):
        return None
    seen = {json.dumps(plain(c.value), sort_keys=True, ensure_ascii=False) for c in cells.values()}
    spec = index.spec_definitions[key]
    return {"key": key, "section": section, "label": plain(spec.label), "unit": spec.unit,
            "values": {pid: {"value": plain(c.value), "source": c.source} for pid, c in cells.items()},
            "diff": len(seen) > 1}
