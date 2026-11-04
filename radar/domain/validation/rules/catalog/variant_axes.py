from __future__ import annotations

from radar.domain.model.entities import Claim, ClaimValue, Product
from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "variant_axes"

def _values(ctx: ValidationContext, subject: str) -> dict[str, ClaimValue]:
    return {c.spec_key: c.value for c in ctx.catalog.all(Claim) if c.subject == subject and c.rank == 1}

def _check_variant(ctx: ValidationContext, res: ValidationResult, p: Product, axis_keys: set[str]) -> None:
    parent = ctx.catalog.get(p.parent) if p.parent else None
    if not isinstance(parent, Product):
        res.error(NAME, p.id, "a variant needs a parent product")
        return
    allowed = axis_keys | set(p.variant_axes or {}) | set(parent.variant_axes or {})
    mine, theirs = _values(ctx, p.id), _values(ctx, parent.id)
    for key, value in mine.items():
        if key not in allowed and theirs.get(key, value) != value:
            res.error(NAME, p.id, f"'{key}' differs from parent {parent.id} but is not a variant axis")
        elif key not in allowed and key not in theirs:
            res.error(NAME, p.id, f"'{key}' is not on parent {parent.id} and is not a variant axis")

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    axis_keys = {p.category_id: set(p.axis_dependent_keys) for p in ctx.registry.profiles}
    for p in ctx.catalog.all(Product):
        # Data-driven exception: a variant is the product tree's lowest level, not a kind the registry may add.
        if p.kind == "variant":
            _check_variant(ctx, res, p, axis_keys.get(p.category, set()))
