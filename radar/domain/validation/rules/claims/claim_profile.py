from __future__ import annotations

from radar.domain.model.entities import Claim, Product
from radar.domain.validation.context import ValidationContext, Whole
from radar.domain.validation.verdict import Finding, Findings, Severity

NAME = "claim_profile"

def _missing(ctx: ValidationContext) -> Findings:
    stated: dict[str, set[str]] = {}
    for c in ctx.catalog.all(Claim):
        stated.setdefault(c.subject, set()).add(c.spec_key)
    for p in ctx.catalog.all(Product):
        if p.category in ctx.registry.categories:
            if missing := ctx.registry.unstated(p, stated.get(p.id, ())):
                yield Finding(NAME, p.id, f"states no {', '.join(missing)}, required in {p.category}", Severity.WARNING)

def check(ctx: ValidationContext) -> Findings:
    for c in ctx.catalog.all(Claim):
        product = ctx.catalog.get(c.subject)
        if (isinstance(product, Product) and product.category in ctx.registry.categories
                and c.spec_key not in ctx.registry.keys(product)):
            yield Finding(NAME, c.id,
                          f"'{c.spec_key}' is not in the profile of {product.category} nor in a spec group the product "
                          "takes")
    if isinstance(ctx.scope, Whole):
        yield from _missing(ctx)
