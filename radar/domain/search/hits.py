from __future__ import annotations

from typing import Any, Mapping, Sequence

from radar.domain.model.entities import Found, Ranking
from radar.domain.model.registry import Registry
from radar.domain.ports.search.search_engine import Hit

def _hit_json(hit: Hit, spec_labels: Mapping[str, str]) -> dict[str, object]:
    card = hit.card
    why = [{"field": m.field, "terms": list(m.terms),
            **({"key": m.key, "label": spec_labels.get(m.key, m.key)} if m.key else {})} for m in hit.why]
    return {"id": card.id, "slug": card.slug, "name": card.name, "vendor": card.vendor, "vendor_name": card.vendor_name,
            "category": card.category, "score": round(hit.score, 4), "why": why, "rank_sources": dict(hit.ranks)}

def found(hits: Sequence[Hit]) -> Found:
    by_meaning = bool(hits) and hits[0].ranks.keys() == {"semantic"}
    return Found(ranking=Ranking.MEANING if by_meaning else Ranking.WORDS, products=tuple(h.card for h in hits))

def hits_json(hits: Sequence[Hit], registry: Registry) -> list[dict[str, Any]]:
    default_code = registry.default_language.code
    labels = {k: d.label.get(default_code, "") for k, d in registry.spec_definitions.items()}
    return [_hit_json(h, labels) for h in hits]
