from __future__ import annotations

import re
from typing import Iterator

from radar.domain.ai.budget import Use
from radar.domain.model import versions
from radar.domain.model.entities import CategoryProfile, FilesOn, LocalizedText, SpecDefinition
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "registry_integrity"
RESERVED = frozenset({"product", "vendor", "category", "browse", "search", "compare", "about", "admin", "api", "assets",
                      "read-model", "ort", "news"})
HUB_PATH = re.compile(r"[a-z][a-z0-9-]*")

def _specs(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    for s in reg.spec_definitions.values():
        unit = reg.units.get(s.unit or "")
        if s.datatype != "quantity":
            if s.dimension is not None or s.unit is not None or s.better is not None:
                yield s.id, f"a {s.datatype} spec takes no dimension, unit or better direction"
        elif s.dimension not in reg.dimensions:
            yield s.id, f"quantity spec needs a known dimension, got {s.dimension!r}"
        elif unit is None or unit.dimension != s.dimension:
            yield s.id, f"unit {s.unit!r} is not a {s.dimension} unit"
        yield from _vocabulary(ctx, s)

def _measures(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    for s in ctx.registry.spec_definitions.values():
        if s.datatype != "quantity" and (s.bounds is not None or s.precision is not None):
            yield s.id, f"a {s.datatype} spec takes no bounds or precision"
        elif s.bounds is not None and s.bounds.min >= s.bounds.max:
            yield s.id, f"bounds run from {s.bounds.min} down to {s.bounds.max}"

def _vocabulary(ctx: ValidationContext, s: SpecDefinition) -> Iterator[tuple[str, str]]:
    if s.datatype not in ("term", "term_set"):
        if s.vocabulary:
            yield s.id, f"a {s.datatype} spec takes no vocabulary"
    elif not s.vocabulary or not ctx.registry.has(s.vocabulary):
        yield s.id, f"a {s.datatype} spec needs a known vocabulary, got {s.vocabulary!r}"

def _units(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    for u in reg.units.values():
        if u.dimension not in reg.dimensions:
            yield u.id, f"unknown dimension '{u.dimension}'"

def _dimensions(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    for d in reg.dimensions.values():
        canonical = reg.units.get(d.canonical_unit)
        if canonical is None or canonical.dimension != d.id:
            yield d.id, f"canonical unit {d.canonical_unit!r} is not a {d.id} unit"
        elif canonical.factor != 1:
            yield d.id, f"canonical unit {d.canonical_unit!r} has factor {canonical.factor}, not 1"
        codes = [u.ucum for u in reg.units.values() if u.dimension == d.id]
        for code in sorted({c for c in codes if codes.count(c) > 1}):
            yield d.id, f"two units share the UCUM code {code!r}"

def _profiles(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg, schema = ctx.registry, ctx.schema
    specs = set(reg.spec_definitions)
    allowed = {
        "core": specs, "detail": specs,
        "versions": {f.name for f in schema.types["ProductVersion"].fields},
        "offerings": {f.name for f in schema.types["Offering"].fields},
    }
    seen: set[str] = set()
    for p in reg.profiles:
        cid = p.category_id
        if cid not in reg.categories:
            yield cid, "profile for an unknown category"
        if cid in seen:
            yield cid, "more than one profile"
        seen.add(cid)
        keyed = {**{s: getattr(p.sections, s) for s in allowed},
                 "required": p.required, "axis_dependent_keys": p.axis_dependent_keys}
        for section, keys in keyed.items():
            for key in sorted(set(keys) - allowed.get(section, specs)):
                yield cid, f"{section}: '{key}' is not a valid key here"
        yield from _facets(ctx, p)

def _facets(ctx: ValidationContext, p: CategoryProfile) -> Iterator[tuple[str, str]]:
    for f in p.facets:
        spec = ctx.registry.spec_definitions.get(f.field)
        if spec is None:
            yield p.category_id, f"facet '{f.field}' is not a spec"
        elif spec.datatype not in ("quantity", "term", "term_set", "boolean"):
            yield p.category_id, (f"facet '{f.field}' points to a {spec.datatype} spec; facets must be Term, Quantity "
                                  "or boolean")

def _coverage(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    for cid in sorted(set(reg.categories) - {p.category_id for p in reg.profiles}):
        yield cid, "category has no profile"
    profiled = {k for p in reg.profiles for k in (*p.sections.core, *p.sections.detail)}
    for spec_id in sorted(set(reg.spec_definitions) - profiled):
        yield spec_id, "spec is in no profile's core or detail"
    for p in reg.profiles:
        if not p.sections.core:
            yield p.category_id, "profile has no core spec"

def _bindings(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    bound = ctx.schema.vocabularies() | {s.vocabulary for s in reg.spec_definitions.values() if s.vocabulary}
    for name in sorted(bound):
        if not reg.has(name):
            yield name, "vocabulary is bound in the model but missing from the registry"
    for name in sorted(set(reg.vocabularies) - bound):
        yield name, "vocabulary is not used by any field or spec"
    schemes = set(reg.vocabularies.get("version_schemes", {}))
    if schemes != versions.SCHEMES:
        yield "version_schemes", f"terms {sorted(schemes)} must equal the orderable schemes {sorted(versions.SCHEMES)}"

def _references(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    records = [("Category", reg.categories), ("Unit", reg.units), ("Dimension", reg.dimensions),
               ("SpecDefinition", reg.spec_definitions), *(("Term", terms) for terms in reg.vocabularies.values())]
    for type_name, items in records:
        bound = [f for f in ctx.schema.types[type_name].fields if f.vocabulary]
        for item in items.values():
            for f in bound:
                for term_id in _ids(getattr(item, f.name)):
                    if not reg.has(f.vocabulary) or term_id not in reg.items(f.vocabulary):
                        yield item.id, f"{f.name} '{term_id}' is not in '{f.vocabulary}'"

def _ids(value: tuple[str, ...] | str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return value if isinstance(value, tuple) else (value,)

def _hubs(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    reg = ctx.registry
    taken: dict[str, str] = {}
    for c in reg.categories.values():
        hub = c.component_hub
        if hub is None:
            continue
        if not HUB_PATH.fullmatch(hub.path) or hub.path in RESERVED or hub.path in taken:
            yield c.id, (f"component_hub path '{hub.path}' must be lowercase letters, digits and dashes, not a route "
                         "of the site, and one category's")
        if hub.relation not in reg.items("relation_types"):
            yield c.id, f"component_hub relation '{hub.relation}' is not in 'relation_types'"
        taken[hub.path] = c.id

def _synonyms(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    for name, terms in ctx.registry.vocabularies.items():
        named: dict[str, str] = {}
        for t in terms.values():
            for text in {*t.label.values(), *(t.aliases or ())}:
                other = named.setdefault(text.casefold(), t.id)
                if other != t.id:
                    yield t.id, f"'{name}' term shares '{text}' with '{other}'"

def _uniform(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    for name, terms in ctx.registry.vocabularies.items():
        described = any(t.description for t in terms.values())
        for t in terms.values():
            if described and not _multilingual(t.description, [l.code for l in ctx.registry.languages]):
                yield t.id, f"'{name}' terms carry a description; this one has none in all languages"

def _sides(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    for name, terms in ctx.registry.vocabularies.items():
        if any(t.from_side or t.to_side for t in terms.values()):
            yield from ((t.id, f"'{name}' terms read from both sides; this one lacks one") for t in terms.values()
                        if not (t.from_side and t.to_side))

def _multilingual(text: LocalizedText | None, codes: list[str]) -> bool:
    return bool(text and all(text.get(c) for c in codes))

def _filings(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    events = tuple(e.value for e in FilesOn)
    for name, terms in ctx.registry.vocabularies.items():
        if any(t.files_on for t in terms.values()):
            for event in events:
                named = [t.id for t in terms.values() if t.files_on == event]
                if len(named) != 1:
                    yield name, f"'{event}' files {len(named)} kinds; each event files one"

def _ai(ctx: ValidationContext) -> Iterator[tuple[str, str]]:
    ai, uses = ctx.registry.ai, [u.value for u in Use]
    if sorted(u.use for u in ai.uses) != sorted(uses):
        yield "ai.json", f"sets each AI use once: {', '.join(uses)}"
    models = {m.id for m in ai.models}
    for u in ai.uses:
        if (u.use == Use.ALL.value) != (u.model is None) or (u.model and u.model not in models):
            yield "ai.json", f"'{u.use}' runs {u.model!r}: all uses together run none, and each use one of the models"

def check(ctx: ValidationContext) -> Findings:
    for part in (_specs, _measures, _units, _dimensions, _profiles, _coverage, _bindings, _references, _hubs, _uniform,
                 _sides, _synonyms, _filings, _ai):
        for item_id, message in part(ctx):
            yield Finding(NAME, item_id, message)
