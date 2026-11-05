from __future__ import annotations

from radar.domain.model.entities import Claim, Product
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "versions"

def check(ctx: ValidationContext) -> Findings:
    for p in ctx.catalog.all(Product):
        try:
            ctx.catalog.versions_of(p.id)
        except ValueError as exc:
            yield Finding(NAME, p.id, str(exc))
    for c in ctx.catalog.all(Claim):
        vrange = c.applies_to_versions
        if vrange is None:
            continue
        if vrange.product != c.subject:
            yield Finding(NAME, c.id,
                          f"applies_to_versions.product '{vrange.product}' is not the subject '{c.subject}'")
            continue
        try:
            if not ctx.catalog.resolve(vrange):
                yield Finding(NAME, c.id, "applies_to_versions matches no version")
        except ValueError as exc:
            yield Finding(NAME, c.id, str(exc))
