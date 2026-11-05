from __future__ import annotations

from radar.domain.model.entities import Claim, Product
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "claim_profile"

def check(ctx: ValidationContext) -> Findings:
    for c in ctx.catalog.all(Claim):
        product = ctx.catalog.get(c.subject)
        if (isinstance(product, Product) and product.category in ctx.registry.categories
                and c.spec_key not in ctx.registry.keys(product)):
            yield Finding(NAME, c.id,
                          f"'{c.spec_key}' is not in the profile of {product.category} nor in a spec group the product "
                          "takes")
