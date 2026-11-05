from __future__ import annotations

from radar.domain.validation.context import ValidationContext, Whole
from radar.domain.validation.verdict import Finding, Findings, Severity
from radar.domain.model.entities import Organization, Product, ProductOrgRole

NAME = "category_and_roles"

def _makers(ctx: ValidationContext) -> dict[str, set[str]]:
    slugs = {o.id: o.slug for o in ctx.catalog.all(Organization)}
    makers: dict[str, set[str]] = {}
    for role in ctx.catalog.all(ProductOrgRole):
        makers.setdefault(role.product, set()).add(slugs.get(role.org, role.org))
    return makers

def _twice(ctx: ValidationContext) -> Findings:
    seen: dict[tuple[str, str, str], str] = {}
    for role in ctx.catalog.all(ProductOrgRole):
        if (first := seen.setdefault((role.product, role.org, role.role), role.id)) != role.id:
            yield Finding(NAME, role.id,
                          f"'{role.product}' names '{role.org}' as '{role.role}' twice: {first} and {role.id}")

def check(ctx: ValidationContext) -> Findings:
    products, makers = ctx.catalog.all(Product), _makers(ctx)
    yield from _twice(ctx)
    for prod in products:
        maker, _, own = prod.slug.partition("__")
        if prod.id not in makers:
            yield Finding(NAME, prod.id, f"product '{prod.id}' has no associated ProductOrgRole")
        elif not (maker and own):
            expected = ", ".join(sorted(makers[prod.id]))
            yield Finding(NAME, prod.id,
                          f"slug '{prod.slug}' is not '<maker>__<product>', the maker part from its maker's slug: "
                          f"{expected}")
    if not isinstance(ctx.scope, Whole):
        return
    populated = {p.category for p in products}
    for cat_id in ctx.registry.categories:
        if cat_id not in populated:
            yield Finding(NAME, cat_id, f"category '{cat_id}' is empty (zero products)", Severity.WARNING)
