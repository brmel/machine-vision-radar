from __future__ import annotations

from collections.abc import Sequence

from .context import ValidationContext
from .rule import Rule
from .rules.catalog import ai_caps, category_and_roles, countries, entity_ids, references, variant_axes, versions
from .rules.claims import claim_profile, claim_values, dates, lifecycle
from .rules import changes, feed, unique
from .rules.registry import no_filler_text, registry_integrity, vocabularies
from .rules.sources import document_integrity, source_integrity, source_preference
from .verdict import Verdict

RULES: tuple[Rule, ...] = (
    registry_integrity.check, entity_ids.check, countries.check, references.check, vocabularies.check,
    claim_values.check, claim_profile.check, dates.check, versions.check, variant_axes.check, source_preference.check,
    no_filler_text.check, category_and_roles.check, source_integrity.check, document_integrity.check, lifecycle.check,
    changes.check, ai_caps.check, feed.check, unique.check,
)

def check(ctx: ValidationContext, rules: Sequence[Rule] = RULES) -> Verdict:
    return Verdict(tuple(f for rule in rules for f in rule(ctx)))
