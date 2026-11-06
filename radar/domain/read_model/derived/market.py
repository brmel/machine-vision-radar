from __future__ import annotations

from collections import Counter
from typing import Sequence

from radar.domain.model.dates import start_of
from radar.domain.model.entities import (ConsolidationEvent, CountryCount, MarketCategory, MarketVendor, MarketView,
                                         OrgBrief, OrgRelation, ProductCard, TermRef)
from radar.domain.model.registry import Registry

def _categories(cards: Sequence[ProductCard]) -> tuple[MarketCategory, ...]:
    products = Counter(c.category for c in cards)
    vendors = Counter(category for category, _ in {(c.category, c.vendor) for c in cards})
    return tuple(MarketCategory(category=c, products=n, vendors=vendors[c])
                 for c, n in sorted(products.items(), key=lambda i: (-i[1], i[0])))

def _vendors(cards: Sequence[ProductCard], briefs: Sequence[OrgBrief]) -> tuple[MarketVendor, ...]:
    products = Counter(c.vendor for c in cards)
    categories = Counter(vendor for vendor, _ in {(c.vendor, c.category) for c in cards})
    made = [b for b in briefs if b.slug in products]
    return tuple(MarketVendor(organization=b, products=products[b.slug], categories=categories[b.slug])
                 for b in sorted(made, key=lambda b: (-products[b.slug], b.name.lower(), b.slug)))

def _countries(cards: Sequence[ProductCard], briefs: Sequence[OrgBrief]) -> tuple[CountryCount, ...]:
    located = {b.slug: b.country for b in briefs if b.country}
    organizations = Counter(located.values())
    products = Counter(located[c.vendor] for c in cards if c.vendor in located)
    return tuple(CountryCount(country=c, organizations=n, products=products[c])
                 for c, n in sorted(organizations.items(), key=lambda i: (-products[i[0]], -i[1], i[0])))

def _newest_first(r: OrgRelation) -> tuple[int, str]:
    return -(start_of(r.valid_from).toordinal() if r.valid_from else 0), r.id

def _consolidation(relations: Sequence[OrgRelation], briefs: Sequence[OrgBrief],
                   registry: Registry) -> tuple[ConsolidationEvent, ...]:
    types = registry.vocabularies["org_relation_types"]
    by_id = {b.id: b for b in briefs}
    owning = [r for r in relations if r.type in registry.marked("org_relation_types", lambda t: t.owns)]
    return tuple(ConsolidationEvent(type=TermRef(id=r.type, label=types[r.type].label), organization=by_id[r.from_org],
                                    owner=by_id[r.to_org], year=start_of(r.valid_from).year if r.valid_from else None)
                 for r in sorted(owning, key=_newest_first))

def market(cards: Sequence[ProductCard], briefs: Sequence[OrgBrief], relations: Sequence[OrgRelation],
           registry: Registry) -> MarketView:
    return MarketView(categories=_categories(cards), vendors=_vendors(cards, briefs),
                      countries=_countries(cards, briefs), consolidation=_consolidation(relations, briefs, registry),
                      organizations=len(briefs))
