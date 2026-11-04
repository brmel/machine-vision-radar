from __future__ import annotations

import re
from collections import defaultdict

from radar.domain.model.entities import Identifier
from radar.domain.validation.context import ValidationContext, ValidationResult
from radar.domain.validation.walk import entities, repeated

NAME = "entity_ids"

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    prefixes = {e.name: e.prefix for e in ctx.schema.entities}
    for e in entities(ctx.catalog, ctx.schema):
        prefix = prefixes[type(e).__name__]
        if not e.id.startswith(f"{prefix}_"):
            res.error(NAME, e.id, f"{type(e).__name__} id must start with '{prefix}_'")
    for entity_id, n in repeated(e.id for e in entities(ctx.catalog, ctx.schema)):
        res.error(NAME, entity_id, f"id used by {n} entities")
    for (scheme, issuer, value), n in repeated((i.scheme, i.issuer, i.value) for i in ctx.catalog.all(Identifier)):
        res.error(NAME, value, f"identifier {scheme}/{issuer or '-'}/{value} is used {n} times")
    _unique_slugs(ctx, res)
    for i in ctx.catalog.all(Identifier):
        _identifier(ctx, res, i)

def _gs1(digits: str) -> bool:
    body = [int(d) for d in reversed(digits[:-1])]
    return (sum(d * (3 if n % 2 == 0 else 1) for n, d in enumerate(body)) + int(digits[-1])) % 10 == 0

def _identifier(ctx: ValidationContext, res: ValidationResult, i: Identifier) -> None:
    scheme = ctx.registry.vocabularies["identifier_schemes"].get(i.scheme)
    if scheme is None:
        return
    kind = ctx.schema.kind_of(i.subject)
    if scheme.pattern and not re.fullmatch(scheme.pattern, i.value):
        res.error(NAME, i.id, f"{i.scheme} '{i.value}' is not the whole of {scheme.pattern}")
    elif scheme.gs1_check and not _gs1(i.value):
        res.error(NAME, i.id, f"{i.scheme} '{i.value}' fails its GS1 check digit")
    if scheme.subjects and kind not in scheme.subjects:
        res.error(NAME, i.id, f"{i.scheme} identifies {', '.join(scheme.subjects)}, not a {kind}")

def _unique_slugs(ctx: ValidationContext, res: ValidationResult) -> None:
    slugged = {k.name for k in ctx.schema.entities if any(f.name == "slug" for f in k.fields)}
    owners: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for e in entities(ctx.catalog, ctx.schema):
        if type(e).__name__ in slugged:
            owners[type(e).__name__, e.slug].append(e.id)
    for (kind, slug), ids in owners.items():
        if len(ids) > 1:
            res.error(NAME, slug, f"{kind} slug '{slug}' is used by {', '.join(ids)}")
