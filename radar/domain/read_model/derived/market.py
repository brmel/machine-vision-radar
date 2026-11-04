from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from radar.domain.model.dates import start_of
from radar.domain.model.entities import OrgRelation
from radar.domain.model.registry import Registry

View = dict[str, Any]

def _categories(cards: Sequence[View]) -> list[View]:
    products = Counter(c["category"] for c in cards)
    vendors = Counter(category for category, _ in {(c["category"], c["vendor"]) for c in cards})
    return [{"category": c, "products": n, "vendors": vendors[c]}
            for c, n in sorted(products.items(), key=lambda i: (-i[1], i[0]))]

def _vendors(cards: Sequence[View], briefs: Sequence[View]) -> list[View]:
    products = Counter(c["vendor"] for c in cards)
    categories = Counter(vendor for vendor, _ in {(c["vendor"], c["category"]) for c in cards})
    made = [b for b in briefs if b["slug"] in products]
    return [{"organization": b, "products": products[b["slug"]], "categories": categories[b["slug"]]}
            for b in sorted(made, key=lambda b: (-products[b["slug"]], b["name"].lower(), b["slug"]))]

def _countries(cards: Sequence[View], briefs: Sequence[View]) -> list[View]:
    located = {b["slug"]: b["country"] for b in briefs if b.get("country")}
    organizations = Counter(located.values())
    products = Counter(located[c["vendor"]] for c in cards if c["vendor"] in located)
    return [{"country": c, "organizations": n, "products": products[c]}
            for c, n in sorted(organizations.items(), key=lambda i: (-products[i[0]], -i[1], i[0]))]

def _newest_first(r: OrgRelation) -> tuple[int, str]:
    return -(start_of(r.valid_from).toordinal() if r.valid_from else 0), r.id

def _consolidation(relations: Sequence[OrgRelation], briefs: Sequence[View], registry: Registry) -> list[View]:
    types = registry.vocabularies["org_relation_types"]
    by_id = {b["id"]: b for b in briefs}
    owning = [r for r in relations if r.type in registry.marked("org_relation_types", lambda t: t.owns)]
    return [{"type": {"id": r.type, "label": dict(types[r.type].label)}, "organization": by_id[r.from_org],
             "owner": by_id[r.to_org], **({"year": start_of(r.valid_from).year} if r.valid_from else {})}
            for r in sorted(owning, key=_newest_first)]

def market(cards: Sequence[View], briefs: Sequence[View], relations: Sequence[OrgRelation], registry: Registry) -> View:
    return {"categories": _categories(cards), "vendors": _vendors(cards, briefs),
            "countries": _countries(cards, briefs), "consolidation": _consolidation(relations, briefs, registry),
            "organizations": len(briefs)}
