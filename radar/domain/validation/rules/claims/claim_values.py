from __future__ import annotations

from collections import defaultdict

from radar.domain.model.entities import (Claim, ClaimValue, ClaimValueBoolean, ClaimValueNone, ClaimValueQuantity,
                                         ClaimValueRange, ClaimValueString, ClaimValueTerm, ClaimValueTerms, Relation,
                                         SpecDefinition)
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "claim_values"

VARIANTS: dict[str, tuple[type, ...]] = {"quantity": (ClaimValueQuantity, ClaimValueRange, ClaimValueNone),
                                        "term": (ClaimValueTerm, ClaimValueNone), "term_set": (ClaimValueTerms,),
                                        "boolean": (ClaimValueBoolean, ClaimValueNone),
                                        "string": (ClaimValueString, ClaimValueNone)}

def _measured(ctx: ValidationContext, numbers: tuple[float, ...], unit: str, spec: SpecDefinition) -> list[str]:
    measured = ctx.registry.units.get(unit)
    if measured is None:
        return []
    if measured.dimension != spec.dimension:
        return [f"unit '{unit}' measures {measured.dimension}, expected {spec.dimension}"]
    bounds = spec.bounds
    outside = [n for n in numbers if bounds
               and not bounds.min <= ctx.registry.converted(n, unit, spec.unit or unit) <= bounds.max]
    return [f"{n} {unit} is outside the bounds {bounds.min}–{bounds.max} {spec.unit}" for n in outside if bounds]

def _terms(ctx: ValidationContext, terms: tuple[str, ...], spec: SpecDefinition) -> list[str]:
    vocab = ctx.registry.items(spec.vocabulary or "")
    unknown = [f"'{t}' is not in registry '{spec.vocabulary}'" for t in terms if t not in vocab]
    return unknown + ([f"terms repeat: {list(terms)}"] if len(set(terms)) < len(terms) else [])

def _errors(ctx: ValidationContext, value: ClaimValue, spec: SpecDefinition) -> list[str]:
    if not isinstance(value, VARIANTS[spec.datatype]):
        return [f"'{spec.id}' is a {spec.datatype}, not a {type(value).__name__.removeprefix('ClaimValue').lower()}"]
    match value:
        case ClaimValueQuantity(quantity=q):
            return _measured(ctx, (q.value,), q.unit, spec)
        case ClaimValueRange(range=r):
            return _measured(ctx, (r.min, r.max), r.unit, spec) + (
                [f"range runs from {r.min} down to {r.max}"] if r.min > r.max else [])
        case ClaimValueTerm(term=t):
            return _terms(ctx, (t,), spec)
        case ClaimValueTerms(terms=ts):
            return _terms(ctx, ts, spec)
    return []

def check(ctx: ValidationContext) -> Findings:
    first: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for c in ctx.catalog.all(Claim):
        spec = ctx.registry.spec_definitions.get(c.spec_key)
        if spec is None:
            continue
        for message in _errors(ctx, c.value, spec):
            yield Finding(NAME, c.id, f"{c.spec_key}: {message}")
        if c.rank == 1 and spec.datatype != "term_set":
            first[(c.subject, c.spec_key)].append(c)
    for (subject, key), claims in first.items():
        if len({repr(c.value) for c in claims}) > 1:
            yield Finding(NAME, claims[-1].id, f"{key}: {subject} has {len(claims)} different values ranked first")
    yield from _qualifiers(ctx)

def _qualifiers(ctx: ValidationContext) -> Findings:
    for r in ctx.catalog.all(Relation):
        for key, value in (r.qualifiers or {}).items():
            spec = ctx.registry.spec_definitions.get(key)
            for message in _errors(ctx, value, spec) if spec else [f"'{key}' is not a spec"]:
                yield Finding(NAME, r.id, f"qualifier {key}: {message}")
