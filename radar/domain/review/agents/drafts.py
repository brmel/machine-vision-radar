from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Callable, Iterator, Mapping

from radar.domain.model.history.changeset import Change
from radar.domain.model.entities import Claim, Name, Product, ProductOrgRole, ProductVersion, Source, SpecDefinition
from radar.domain.model.history.ids import keyed
from radar.domain.model.registry import Registry
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.ai.research_agent import RecordsDraft, Terms

PROPOSED = (Product, Name, ProductOrgRole, ProductVersion, Claim)
SET_BY_RUN = ("version", "source_refs")
PROVENANCE = ("source_refs", "recorded_at", "method", "fetched_at")
References = Mapping[str, list[tuple[str, str]]]
Words = Mapping[str, Mapping[str, str]]

def terms(schema: ModelSchema, registry: Registry) -> Terms:
    return {kind.__name__: {f.name + ("" if f.optional else "*"): tuple(registry.items(v))
                            if (v := f.vocabulary or f.key_vocabulary) else ()
                            for f in schema.types[kind.__name__].fields if f.name not in SET_BY_RUN}
            for kind in PROPOSED}

def references(schema: ModelSchema) -> References:
    return {e.prefix: [(f"{e.name}.{path}", path) for path, f in schema.reference_paths(e.name)
                       if f.refs != (Source.__name__,)]
            for e in schema.entities if e.prefix}

def at(record: Mapping[str, Any], path: str) -> list[str]:
    value: Any = record
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]

def naming(record: Mapping[str, Any], refs: References) -> list[tuple[str, str]]:
    return [(w, ref) for w, p in refs.get(record["id"].partition("_")[0], ()) for ref in at(record, p)]

def without(changes: tuple[Change, ...], refused: set[str], refs: References) -> tuple[Change, ...]:
    kept = tuple(c for c in changes if c.entity not in refused)
    named = {c.entity for c in kept if {ref for _, ref in naming(c.action.record, refs)} & refused}
    return without(kept, refused | named, refs) if named else kept

def said(record: Mapping[str, Any]) -> str:
    return json.dumps({k: v for k, v in record.items() if k not in ("id", "version", *PROVENANCE)}, sort_keys=True)

def swapped(value: Any, ids: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return ids.get(value, value)
    if isinstance(value, list):
        out = [swapped(v, ids) for v in value]
        return [v for n, v in enumerate(out) if not (v in ids.values() and v in out[:n])]
    return {k: swapped(v, ids) for k, v in value.items()} if isinstance(value, dict) else value

def corrected(draft: RecordsDraft, first: Callable[[Mapping[str, Any]], str | None]) -> RecordsDraft:
    ids = {r["id"]: held for r in draft.records if (held := first(r)) and held != r["id"]}
    return replace(draft, records=tuple(swapped(dict(r), ids) for r in draft.records)) if ids else draft

def _key(word: str) -> str:
    return "".join(ch for ch in word.casefold() if ch.isalnum())

def _spellings(spec: SpecDefinition, registry: Registry) -> Iterator[tuple[str, str]]:
    for unit in registry.units.values():
        if spec.datatype == "quantity" and unit.dimension == spec.dimension:
            yield from ((unit.id, unit.id), (unit.symbol, unit.id))
    for term in registry.vocabularies.get(spec.vocabulary or "", {}).values():
        yield from ((said, term.id) for said in (term.id, *term.label.values()))

def _unique(spellings: Iterator[tuple[str, str]]) -> dict[str, str]:
    found: dict[str, set[str]] = {}
    for said, held in spellings:
        found.setdefault(_key(said), set()).add(held)
    return {key: next(iter(ids)) for key, ids in found.items() if key and len(ids) == 1}

def words(registry: Registry) -> Words:
    return {spec.id: _unique(_spellings(spec, registry)) for spec in registry.spec_definitions.values()}

def _held(said: Mapping[str, str], word: object) -> object:
    return said.get(_key(word), word) if isinstance(word, str) else word

def _value(value: object, datatype: str, said: Mapping[str, str]) -> object:
    match value:
        case {"quantity": {"unit": unit} as measure}:
            return {"quantity": {**measure, "unit": _held(said, unit)}}
        case {"range": {"unit": unit} as span}:
            return {"range": {**span, "unit": _held(said, unit)}}
        case {"term": str(term)} | {"terms": [str(term)]} if datatype in ("term", "term_set"):
            return {"terms": [_held(said, term)]} if datatype == "term_set" else {"term": _held(said, term)}
        case {"terms": list(terms)}:
            return {"terms": [_held(said, t) for t in terms]}
    return value

def resolved(draft: RecordsDraft, specs: Mapping[str, SpecDefinition], said: Words) -> RecordsDraft:
    return replace(draft, records=tuple(
        {**r, "value": _value(r["value"], spec.datatype, said[spec.id])}
        if "value" in r and (spec := specs.get(str(r.get("spec_key")))) else r for r in draft.records))

def minted(draft: RecordsDraft, run_id: str, holds: Callable[[str], bool]) -> RecordsDraft:
    ids = {r["id"]: keyed(r["id"].partition("_")[0], f"{run_id}:{r['id']}") for r in draft.records
           if not holds(r["id"])}
    return replace(draft, records=tuple(swapped(dict(r), ids) for r in draft.records),
                   subject=ids.get(draft.subject or "", draft.subject)) if ids else draft
