from __future__ import annotations

from radar.domain.validation.context import ValidationContext, ValidationResult

NAME = "profile_facets"

ALLOWED_DATATYPES = frozenset({"quantity", "term", "term_set", "boolean"})

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    for profile in ctx.registry.profiles:
        for facet in profile.facets:
            spec = ctx.registry.spec_definitions.get(facet.field)
            if spec is None:
                res.error(NAME, profile.category_id, f"facet '{facet.field}' has no SpecDefinition")
            elif spec.datatype not in ALLOWED_DATATYPES:
                res.error(
                    NAME,
                    profile.category_id,
                    f"facet '{facet.field}' points to '{spec.datatype}' spec; facets must be Term, Quantity or boolean",
                )
