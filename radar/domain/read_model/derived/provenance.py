from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import CategoryProfile, Claim, LifecycleEvent, Product, Source
from radar.domain.model.registry import Registry
from radar.domain.model.dates import start_of

def _cited(catalog: Catalog, claims: list[Claim]) -> dict[str, Source]:
    return {s.id: s for s in (catalog.get(r) for c in claims for r in c.source_refs) if isinstance(s, Source)}

def _backed(claims: list[Claim], cited: dict[str, Source], vendor: frozenset[str]) -> int:
    return sum(1 for c in claims if any(cited[r].type in vendor for r in c.source_refs if r in cited))

def _against(profile: CategoryProfile | None, claims: list[Claim]) -> tuple[tuple[str, ...], int]:
    if profile is None:
        return (), 0
    keys = {c.spec_key for c in claims}
    return (tuple(k for k in profile.required_at_publish if k not in keys),
            sum(1 for c in claims if c.spec_key in profile.sections.core))

def _gaps(claims: list[Claim]) -> tuple[str, ...]:
    by_key: dict[str, list[Claim]] = {}
    for c in claims:
        by_key.setdefault(c.spec_key, []).append(c)
    out = []
    for key, group in sorted(by_key.items()):
        spans = sorted(((start_of(c.valid_from), start_of(c.valid_to) if c.valid_to else None) for c in group
                        if c.valid_from), key=lambda s: s[0])
        if any(end is not None and end < start for (_, end), (start, _) in zip(spans, spans[1:])):
            out.append(key)
    return tuple(out)

@dataclass(frozen=True, slots=True)
class Provenance:
    product: str
    category: str
    claims: int
    sources_per_claim: float
    source_types: dict[str, int]
    vendor_backed: int
    undated_sources: tuple[str, ...]
    valid_time_gaps: tuple[str, ...]
    overdue_events: tuple[str, ...]
    missing_required: tuple[str, ...]
    core_specs: int

    @property
    def weak(self) -> tuple[str, ...]:
        reasons = []
        if self.claims and self.vendor_backed * 2 < self.claims:
            reasons.append(f"{self.vendor_backed} of {self.claims} claims rest on a vendor document")
        if not self.core_specs:
            reasons.append("no core spec")
        return tuple(reasons)

    def report(self) -> dict[str, Any]:
        return {"id": self.product, "category": self.category, "claims": self.claims,
                "sources_per_claim": self.sources_per_claim, "source_types": self.source_types,
                "vendor_backed": self.vendor_backed, "undated_sources": list(self.undated_sources),
                "valid_time_gaps": list(self.valid_time_gaps), "overdue_events": list(self.overdue_events),
                "missing_required": list(self.missing_required), "core_specs": self.core_specs,
                "weak": list(self.weak)}

    @staticmethod
    def of(catalog: Catalog, registry: Registry, today: date) -> list[Provenance]:
        claims: dict[str, list[Claim]] = {}
        for c in catalog.all(Claim):
            claims.setdefault(c.subject, []).append(c)
        overdue: dict[str, list[str]] = {}
        expected = registry.marked("lifecycle_event_states", lambda t: t.expected)
        for e in catalog.all(LifecycleEvent):
            if e.state in expected and start_of(e.date) < today:
                overdue.setdefault(e.product, []).append(e.id)
        profiles = {p.category_id: p for p in registry.profiles}
        vendor = registry.marked("source_types", lambda t: t.vendor_document)
        return [Provenance._one(catalog, p, claims.get(p.id, []), profiles.get(p.category), overdue.get(p.id, []),
                                vendor)
                for p in sorted(catalog.all(Product), key=lambda p: p.id)]

    @staticmethod
    def _one(catalog: Catalog, product: Product, claims: list[Claim], profile: CategoryProfile | None,
             overdue: list[str], vendor: frozenset[str]) -> Provenance:
        cited = _cited(catalog, claims)
        missing, core = _against(profile, claims)
        return Provenance(
            product=product.id, category=product.category, claims=len(claims),
            sources_per_claim=round(sum(len(c.source_refs) for c in claims) / len(claims), 2) if claims else 0.0,
            source_types=dict(sorted(Counter(s.type for s in cited.values()).items())),
            vendor_backed=_backed(claims, cited, vendor),
            undated_sources=tuple(sorted(i for i, s in cited.items() if s.published_at is None)),
            valid_time_gaps=_gaps(claims), overdue_events=tuple(sorted(overdue)), missing_required=missing,
            core_specs=core,
        )