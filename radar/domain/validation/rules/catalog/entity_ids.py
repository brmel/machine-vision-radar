from __future__ import annotations

import re

from radar.domain.model.entities import Identifier
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings
from radar.domain.validation.walk import entities, repeated

NAME = "entity_ids"

def check(ctx: ValidationContext) -> Findings:
    prefixes = {e.name: e.prefix for e in ctx.schema.entities}
    for e in entities(ctx.catalog, ctx.schema):
        prefix = prefixes[type(e).__name__]
        if not e.id.startswith(f"{prefix}_"):
            yield Finding(NAME, e.id, f"{type(e).__name__} id must start with '{prefix}_'")
    for entity_id, n in repeated(e.id for e in entities(ctx.catalog, ctx.schema)):
        yield Finding(NAME, entity_id, f"id used by {n} entities")
    for (scheme, issuer, value), n in repeated((i.scheme, i.issuer, i.value) for i in ctx.catalog.all(Identifier)):
        yield Finding(NAME, value, f"identifier {scheme}/{issuer or '-'}/{value} is used {n} times")
    for i in ctx.catalog.all(Identifier):
        yield from _identifier(ctx, i)

def _gs1(digits: str) -> bool:
    body = [int(d) for d in reversed(digits[:-1])]
    return (sum(d * (3 if n % 2 == 0 else 1) for n, d in enumerate(body)) + int(digits[-1])) % 10 == 0

def _identifier(ctx: ValidationContext, i: Identifier) -> Findings:
    scheme = ctx.registry.vocabularies["identifier_schemes"].get(i.scheme)
    if scheme is None:
        return
    kind = ctx.schema.kind_of(i.subject)
    if scheme.pattern and not re.fullmatch(scheme.pattern, i.value):
        yield Finding(NAME, i.id, f"{i.scheme} '{i.value}' is not the whole of {scheme.pattern}")
    elif scheme.gs1_check and not _gs1(i.value):
        yield Finding(NAME, i.id, f"{i.scheme} '{i.value}' fails its GS1 check digit")
    if scheme.subjects and kind not in scheme.subjects:
        yield Finding(NAME, i.id, f"{i.scheme} identifies {', '.join(scheme.subjects)}, not a {kind}")
