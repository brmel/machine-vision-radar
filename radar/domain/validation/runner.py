from __future__ import annotations

from types import ModuleType
from typing import Sequence

from .context import ValidationContext, ValidationResult
from .rules.catalog import ai_caps, category_and_roles, countries, entity_ids, references, variant_axes, versions
from .rules.claims import claim_profile, claim_values, dates, lifecycle
from .rules import changes, feed, unique
from .rules.registry import no_filler_text, registry_integrity, vocabularies
from .rules.sources import document_integrity, source_integrity, source_preference

ALL_RULES: tuple[ModuleType, ...] = (
    registry_integrity, entity_ids, countries, references, vocabularies, claim_values, claim_profile, dates, versions,
    variant_axes, source_preference, no_filler_text, category_and_roles, source_integrity, document_integrity,
    lifecycle, changes, ai_caps, feed, unique,
)

def validate(ctx: ValidationContext, rules: Sequence[ModuleType] = ALL_RULES) -> ValidationResult:
    res = ValidationResult()
    for rule in rules:
        rule.check(ctx, res)
    return res
