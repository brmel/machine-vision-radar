from __future__ import annotations

from collections import defaultdict

from radar.domain.model.entities import Claim, Source
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "source_preference"
# Data-driven exception: the rule weighs the two kinds of evidence it names, as a claim method and as a source type.
DATASHEET, INHERITED = "datasheet", "inherited_record_source"

def _source_types(ctx: ValidationContext, c: Claim) -> set[str]:
    return {s.type for s in map(ctx.catalog.get, c.source_refs) if isinstance(s, Source)}

def check(ctx: ValidationContext) -> Findings:
    groups: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for c in ctx.catalog.all(Claim):
        spec = ctx.registry.spec_definitions.get(c.spec_key)
        if spec is not None and spec.datatype == "quantity":
            groups[(c.subject, c.spec_key)].append(c)
    for claims in groups.values():
        yield from _check_group(ctx, claims)

def _check_group(ctx: ValidationContext, claims: list[Claim]) -> Findings:
    datasheet = [c.rank for c in claims if c.method == DATASHEET or DATASHEET in _source_types(ctx, c)]
    if not datasheet:
        return
    for c in claims:
        if (c.method == INHERITED or _source_types(ctx, c) == {INHERITED}) and c.rank <= min(datasheet):
            yield Finding(NAME, c.id,
                          f"inherited claim for '{c.spec_key}' ranks {c.rank}, above the datasheet claim at "
                          f"{min(datasheet)}")
