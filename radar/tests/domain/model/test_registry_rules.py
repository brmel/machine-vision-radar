from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any, Callable

import pytest

from radar.adapters.files.json_parser import parse_catalog
from radar.domain.model.entities import Bounds
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.rules.registry import registry_integrity
from radar.domain.validation.runner import validate
from radar.tests.fixtures.corpus import CORPUS, REGISTRY, SCHEMA

SPECS = sorted(REGISTRY.spec_definitions.values(), key=lambda s: s.id)
QUANTITY, TERM, STRING = (next(s.id for s in SPECS if s.datatype == d) for d in ("quantity", "term", "string"))

def _registry(**changes) -> Any:
    return dataclasses.replace(REGISTRY, **changes)

def _spec(spec_id: str, **changes) -> Any:
    return _registry(spec_definitions={**REGISTRY.spec_definitions,
                                       spec_id: dataclasses.replace(REGISTRY.spec_definitions[spec_id], **changes)})

def _category(**changes) -> Any:
    cat = next(c for c in REGISTRY.categories.values() if c.component_hub)
    hub = {k: changes.pop(k) for k in ("path", "relation") if k in changes}
    changed = dataclasses.replace(cat, component_hub=dataclasses.replace(cat.component_hub, **hub), **changes)
    return _registry(categories={**REGISTRY.categories, cat.id: changed})

def _term(has: Callable[[Any], Any], **changes) -> tuple[Any, str]:
    name, terms = next((n, t) for n, t in REGISTRY.vocabularies.items() if any(has(x) for x in t.values())
                       and len(t) > 1)
    first, second = list(terms.values())[:2]
    changes = {k: v(first) if callable(v) else v for k, v in changes.items()}
    return _registry(vocabularies={**REGISTRY.vocabularies,
                                   name: {**terms, second.id: dataclasses.replace(second, **changes)}}), name

def _ai(**changes) -> Any:
    return _registry(ai=dataclasses.replace(REGISTRY.ai, **changes))

def _ai_use(**changes) -> Any:
    return _ai(uses=(*REGISTRY.ai.uses[:-1], dataclasses.replace(REGISTRY.ai.uses[-1], **changes)))

_SHARED = next(d for d in REGISTRY.dimensions.values() if sum(u.dimension == d.id for u in REGISTRY.units.values()) > 1)
_CANONICAL = REGISTRY.units[_SHARED.canonical_unit]
_SIBLING = next(u for u in REGISTRY.units.values() if u.dimension == _SHARED.id and u.id != _CANONICAL.id)

def _dimension(change: Callable[[Any, Any], Any], same: bool = False) -> Any:
    other = _SIBLING if same else next(u for u in REGISTRY.units.values() if u.dimension != _SHARED.id)
    return _registry(dimensions={**REGISTRY.dimensions, _SHARED.id: change(_SHARED, other)})

_PROFILE = REGISTRY.profiles[0]
_UNDESCRIBED, _DESCRIBED = _term(lambda t: t.description, description={"en": "English only."})
_TWINS = next(t for t in REGISTRY.vocabularies.values() if len(t) > 1)
_FIRST = next(iter(_TWINS.values()))
REGISTRY_BREAKS: dict[str, tuple[Any, Any, str]] = {
    "quantity_without_dimension": (registry_integrity, _spec(QUANTITY, dimension=None), ""),
    "unit_wrong_dimension": (registry_integrity, _spec(QUANTITY, unit=next(
        u for u, x in REGISTRY.units.items() if x.dimension != REGISTRY.spec_definitions[QUANTITY].dimension)), ""),
    "canonical_unit_other_dimension": (registry_integrity,
                                       _dimension(lambda d, other: dataclasses.replace(d, canonical_unit=other.id)),
                                       "is not a"),
    "canonical_unit_factor": (registry_integrity,
                              _dimension(lambda d, sibling: dataclasses.replace(d, canonical_unit=sibling.id),
                                         same=True), "not 1"),
    "ucum_twice": (registry_integrity,
                   _registry(units={**REGISTRY.units,
                                    _SIBLING.id: dataclasses.replace(_SIBLING, ucum=_CANONICAL.ucum)}),
                   f"share the UCUM code '{_CANONICAL.ucum}'"),
    "term_without_vocabulary": (registry_integrity, _spec(TERM, vocabulary=None), ""),
    "better_on_term": (registry_integrity, _spec(TERM, better="higher"), ""),
    "bounds_on_term": (registry_integrity, _spec(TERM, bounds=Bounds(min=0, max=1)), "takes no bounds or precision"),
    "bounds_backwards": (registry_integrity, _spec(QUANTITY, bounds=Bounds(min=2, max=1)),
                         "bounds run from 2 down to 1"),
    "string_with_unit": (registry_integrity, _spec(STRING, dimension="length", unit="m"), ""),
    "profile_unknown_key": (registry_integrity,
                            _registry(profiles=(dataclasses.replace(_PROFILE, required_at_publish=("not_a_spec",)),
                                                *REGISTRY.profiles[1:])), ""),
    "profile_wrong_version_field": (registry_integrity, _registry(profiles=(dataclasses.replace(
        _PROFILE, sections=dataclasses.replace(_PROFILE.sections,
                                               versions=("version_label",))), *REGISTRY.profiles[1:])), ""),
    "missing_profile": (registry_integrity, _registry(profiles=REGISTRY.profiles[1:]), ""),
    "profile_without_core": (registry_integrity,
                             _registry(profiles=(dataclasses.replace(_PROFILE, sections=dataclasses.replace(
_PROFILE.sections, core=(), detail=(*_PROFILE.sections.core, *_PROFILE.sections.detail))), *REGISTRY.profiles[1:])),
                             ""),
    "orphan_vocabulary": (registry_integrity, _registry(vocabularies={**REGISTRY.vocabularies, "orphan": {}}), ""),
    "unknown_stage": (registry_integrity, _category(pipeline=("no_such_stage",)),
                      "pipeline 'no_such_stage' is not in 'pipeline_stages'"),
    "unknown_glyph": (registry_integrity, _category(glyph="no_such_glyph"), "glyph 'no_such_glyph' is not in 'glyphs'"),
    "term_without_fr_description": (registry_integrity, _UNDESCRIBED,
                                    f"'{_DESCRIBED}' terms carry a description; this one has none in all languages"),
    "twin_label": (registry_integrity, _term(lambda t: True, label=lambda f: {**f.label, "en": f.label["en"]})[0],
                   f"with '{_FIRST.id}'"),
    "twin_alias": (registry_integrity, _term(lambda t: True, aliases=lambda f: (f.label["en"].upper(),))[0],
                   f"with '{_FIRST.id}'"),
    "hub_on_a_site_route": (registry_integrity, _category(path="product"), "component_hub path 'product' must be"),
    "hub_unknown_relation": (registry_integrity, _category(relation="no_such_relation"),
                             "component_hub relation 'no_such_relation' is not in 'relation_types'"),
    "two_kinds_one_event": (registry_integrity, _term(lambda t: t.files_on, files_on=lambda f: f.files_on)[0],
                            "kinds; each event files one"),
    "string_facet": (registry_integrity, _spec(next(f.field for p in REGISTRY.profiles for f in p.facets
                                                    if REGISTRY.spec_definitions[f.field].datatype == "boolean"),
                                               datatype="string"),
                     "facets must be Term, Quantity or boolean"),
    "ai_use_twice": (registry_integrity, _ai(uses=(*REGISTRY.ai.uses, REGISTRY.ai.uses[-1])), "sets each AI use once"),
    "ai_use_without_model": (registry_integrity, _ai_use(model=None), "each use one of the models"),
    "ai_use_unlisted_model": (registry_integrity, _ai_use(model="no-such-model"), "each use one of the models"),
    "ai_all_with_model": (registry_integrity,
                          _ai(uses=(dataclasses.replace(REGISTRY.ai.uses[0], model=REGISTRY.ai.models[0].id),
                                    *REGISTRY.ai.uses[1:])), "all uses together run none"),
}

@pytest.mark.parametrize("name", sorted(REGISTRY_BREAKS))
def test_registry_break_fails_its_rule(name: str) -> None:
    rule, registry, message = REGISTRY_BREAKS[name]
    errors = [e.message
              for e in validate(ValidationContext(parse_catalog(CORPUS, SCHEMA), registry, SCHEMA, date(2026, 10, 17)),
                                [rule]).errors]
    assert errors and all(message in e for e in errors), errors

def test_registry_entries_carry_no_status() -> None:
    registry_types = ("Category", "CategoryProfile", "SpecDefinition", "Unit", "Dimension", "Term")
    assert [t for t in registry_types if any(f.name == "status" for f in SCHEMA.types[t].fields)] == []
