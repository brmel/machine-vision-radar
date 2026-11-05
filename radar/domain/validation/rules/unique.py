from __future__ import annotations

from collections import defaultdict

from radar.domain.model.entities import Change
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings
from radar.domain.validation.walk import visits

NAME, PERMANENT = "unique", "permanent"

def _shared(ctx: ValidationContext) -> Findings:
    holders: defaultdict[tuple[str, object], list[str]] = defaultdict(list)
    for v in visits(ctx):
        if v.spec.unique and v.value != "":
            holders[v.path, v.value].append(v.entity.id)
    for (path, value), ids in holders.items():
        if len(ids) > 1:
            for holder in sorted(ids):
                others = ", ".join(sorted(i for i in ids if i != holder))
                yield Finding(NAME, holder, f"{path} '{value}' is also held by {others}")

def _replaced(ctx: ValidationContext) -> Findings:
    permanent = {e.name: {f.name for f in e.fields if f.permanent} for e in ctx.schema.entities}
    for c in ctx.catalog.all(Change):
        kind = ctx.schema.kind_of(c.entity) or ""
        for op in c.patch:
            if op.op == "replace" and op.path in permanent.get(kind, ()):
                yield Finding(PERMANENT, c.entity,
                              f"{kind}.{op.path} never changes once set; version {c.version} sets it to {op.value}")

def check(ctx: ValidationContext) -> Findings:
    yield from _shared(ctx)
    yield from _replaced(ctx)
