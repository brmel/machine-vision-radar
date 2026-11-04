from __future__ import annotations

from typing import Any, Callable

from radar.domain.model.entities import CategoryProfile, FacetOption, FacetView
from radar.domain.model.registry import Language, Registry

Option = tuple[str, dict[str, str], float | None]

def js_number(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else repr(float(x))

def _number(text: str, sort_key: float, languages: tuple[Language, ...]) -> Option:
    return (text, {l.code: text.replace(".", l.decimal) for l in languages}, sort_key)

KINDS = {"term": "enum", "term_set": "multi", "quantity": "number", "boolean": "boolean"}

def value_options(val: dict[str, Any], langs: tuple[Language, ...]) -> list[Option]:
    match val:
        case {"terms": terms}:
            return [(t["id"].lower(), t["label"], None) for t in terms]
        case {"term": t}:
            return [(t["id"].lower(), t["label"], None)]
        case {"boolean": b}:
            return [("true" if b else "false", {l.code: l.yes if b else l.no for l in langs}, None)]
        case {"range": r}:
            return [_number(f"{js_number(r['min'])}–{js_number(r['max'])}", float(r["min"]), langs)]
        case {"quantity": q}:
            return [_number(js_number(q["value"]), float(q["value"]), langs)]
    return []

def _counted(cards: list[dict[str, Any]], key: str, registry: Registry) -> tuple[
        dict[str, int], dict[str, tuple[dict[str, str], float | None]]]:
    counts: dict[str, int] = {}
    meta: dict[str, tuple[dict[str, str], float | None]] = {}
    for c in (c for c in cards if key in c["specs"]):
        for oid, label, sort_key in {o[0]: o for o in value_options(c["specs"][key], registry.languages)}.values():
            counts[oid] = counts.get(oid, 0) + 1
            meta[oid] = (label, sort_key)
    return counts, meta

def _ranked(order: list[str], meta: dict[str, tuple[dict[str, str], float | None]]) -> Callable[
        [str], tuple[int, float, str]]:
    def rank(oid: str) -> tuple[int, float, str]:
        if oid in order:
            return (0, float(order.index(oid)), oid)
        sort_key = meta[oid][1]
        return (1, sort_key if sort_key is not None else 0.0, oid)
    return rank

def _publishing(cards: list[dict[str, Any]], key: str) -> int:
    return sum(1 for c in cards if key in c["specs"] and "none" not in c["specs"][key])

def compute_category_facets(registry: Registry, profile: CategoryProfile,
                            cards: list[dict[str, Any]]) -> tuple[FacetView, ...]:
    computed: list[FacetView] = []
    for f in profile.facets:
        spec = registry.spec_definitions[f.field]
        counts, meta = _counted(cards, f.field, registry)
        if not counts:
            continue
        rank = _ranked(list(registry.vocabularies.get(spec.vocabulary or "", {})), meta)
        symbol = registry.units[spec.unit].symbol if spec.unit else ""
        computed.append(FacetView(id=f.field, spec_key=f.field, label=dict(spec.label),
                                  description=dict(spec.description) if spec.description else None,
                                  kind=KINDS[spec.datatype], count=_publishing(cards, f.field), unit=symbol or None,
                                  **_span(cards, f.field),
                                  options=tuple(FacetOption(id=o, label=meta[o][0], count=counts[o])
                                                for o in sorted(counts, key=rank))))
    return tuple(sorted(computed, key=lambda f: -f.count))

def _bounds(value: dict[str, Any]) -> tuple[float, float] | None:
    match value:
        case {"quantity": q}:
            return q["value"], q["value"]
        case {"range": r}:
            return r["min"], r["max"]
    return None

def _span(cards: list[dict[str, Any]], key: str) -> dict[str, float]:
    bounds = [b for c in cards if key in c["specs"] and (b := _bounds(c["specs"][key]))]
    return {"min": min(b[0] for b in bounds), "max": max(b[1] for b in bounds)} if bounds else {}
