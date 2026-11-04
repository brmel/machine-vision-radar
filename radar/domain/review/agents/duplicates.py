from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, Iterator, Mapping

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model import entities as generated
from radar.domain.model.entities import FilesOn, Identifier, Name, Product, ProductOrgRole, Source
from radar.domain.model.history.projection import plain
from radar.domain.model.changeset import Change, Changeset, PutEntity, Retract, without_version
from radar.domain.model.schema import ModelSchema
from radar.domain.review.agents.drafts import References, said, swapped, without
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Changes
from radar.domain.read_model.derived.identity import ProductIdentity
from radar.domain.validation.walk import entities

HELD = {k.__name__: k for k in (Product, Name, Identifier, ProductOrgRole)}
KindOf = Callable[[str], str]
Known = dict[tuple[str, str], set[str]]

def _bare(record: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in without_version(record).items() if k != "id" and v is not None}

def _known(held: Catalog, identity: ProductIdentity) -> Known:
    products = {p.id for p in held.all(Product)}
    known: Known = {}
    for k in (Name, Identifier):
        for r in held.all(k):
            if r.subject in products and (key := identity.called(k.__name__, plain(r))):
                known.setdefault(key, set()).add(r.subject)
    return known

def _makers(puts: Mapping[str, Mapping[str, Any]], held: Catalog, kind_of: KindOf,
            identity: ProductIdentity) -> dict[str, str]:
    return identity.makers(
        [plain(r) for r in held.all(ProductOrgRole)] + [r for i, r in puts.items()
                                                        if kind_of(i) == ProductOrgRole.__name__])

def _answering(product: str, puts: Mapping[str, Mapping[str, Any]], known: Known, maker: Mapping[str, str],
               kind_of: KindOf, identity: ProductIdentity) -> set[str]:
    keys = {identity.called(kind_of(i), r) for i, r in puts.items() if r.get("subject") == product}
    return {h for key in keys if key for h in known.get(key, ()) if maker.get(h) == maker[product]}

def _taken(puts: Mapping[str, Mapping[str, Any]], held: Catalog, known: Known, kind_of: KindOf,
           identity: ProductIdentity) -> dict[str, str]:
    new = {i for i in puts if kind_of(i) == Product.__name__ and held.get(i) is None}
    maker = _makers(puts, held, kind_of, identity)
    answering = {product: _answering(product, puts, known, maker, kind_of, identity) for product in new
                 if product in maker}
    return {product: next(iter(held_ids)) for product, held_ids in answering.items() if len(held_ids) == 1}

def _moved_change(change: Change, taken: Mapping[str, str]) -> Change:
    return (replace(change, action=PutEntity(swapped(dict(change.action.record), taken)))
            if isinstance(change.action, PutEntity) else change)

def _says_only_what_is_held(change: Change, held: Catalog, known: Known, kind_of: KindOf,
                            identity: ProductIdentity) -> bool:
    if not isinstance(change.action, PutEntity):
        return False
    record, kind = change.action.record, kind_of(change.entity)
    if (key := identity.called(kind, record)) and record.get("subject") in known.get(key, ()):
        return True
    return kind in HELD and any(_bare(plain(r)) == _bare(record) for r in held.all(HELD[kind]))

def merged(draft: Changes, held: Catalog, kind_of: KindOf, identity: ProductIdentity) -> Changes:
    puts = {c.entity: c.action.record for c in draft.changeset.changes if isinstance(c.action, PutEntity)}
    known = _known(held, identity)
    taken = _taken(puts, held, known, kind_of, identity)
    moved = (_moved_change(c, taken) for c in draft.changeset.changes if c.entity not in taken)
    kept = tuple(c for c in moved if not _says_only_what_is_held(c, held, known, kind_of, identity))
    if not kept:
        raise ValueError("the catalog holds all this proposes already")
    return _as_edit(replace(draft, changeset=Changeset(kept)), taken, held)

def _as_edit(draft: Changes, taken: Mapping[str, str], held: Catalog) -> Changes:
    subject = taken.get(draft.subject or "", draft.subject)
    edit = draft.files_on == FilesOn.CREATE and subject is not None and held.get(subject) is not None
    reason = (f"{draft.reason} (merged into {', '.join(sorted(set(taken.values())))}, which the catalog holds)" if taken
              else draft.reason)
    return replace(draft, files_on=FilesOn.UPDATE if edit else draft.files_on, subject=subject, reason=reason)

class Proposed(ValueError):
    ...

def _holders(mine: Iterable[Proposal]) -> dict[str, str]:
    return {said(c.action.record): p.id for p in mine if p.changeset for c in p.changeset.changes
            if isinstance(c.action, PutEntity)}

def unproposed(draft: Changes, mine: Iterable[Proposal], kind_of: KindOf, refs: References) -> Changes:
    holders, changes = _holders(mine), draft.changeset.changes
    stated = {c.entity: said(c.action.record) for c in changes if isinstance(c.action, PutEntity)
              and kind_of(c.entity) != Source.__name__}
    held = {entity: holders[s] for entity, s in stated.items() if s in holders}
    kept = without(changes, set(held), refs)
    if held and all(kind_of(c.entity) == Source.__name__ for c in kept):
        raise Proposed(f"your open proposals put all this already: {', '.join(sorted(set(held.values())))}")
    return replace(draft, changeset=Changeset(kept))

@dataclass(frozen=True, slots=True)
class SourceGroup:
    url: str
    kept: str
    extras: tuple[str, ...]
    repoint: tuple[str, ...]

Naming = tuple[Mapping[str, object], frozenset[str]]

def _named(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, dict)):
        for v in value.values() if isinstance(value, dict) else value:
            yield from _named(v)

def _joined(sets: Iterable[set[str]]) -> list[set[str]]:
    parts: list[set[str]] = []
    for s in sets:
        touching = [p for p in parts if p & s]
        parts = [p for p in parts if not p & s] + [s.union(*touching)]
    return sorted(parts, key=min)

def _held(sources: Iterable[Source]) -> dict[str, list[Source]]:
    at: defaultdict[str, list[Source]] = defaultdict(list)
    for s in sources:
        if s.url:
            at[s.url].append(s)
    return {url: sorted(found, key=lambda s: (s.retrieved_at, s.id)) for url, found in sorted(at.items())
            if len(found) > 1}

def _naming(catalog: Catalog, schema: ModelSchema, url_of: Mapping[str, str]) -> list[Naming]:
    records = (without_version(plain(e)) for e in entities(catalog, schema)
               if not isinstance(e, (Source, generated.Change)))
    found = ((r, frozenset(url_of[x] for x in _named(r) if x in url_of)) for r in records)
    return sorted(((r, urls) for r, urls in found if urls), key=lambda pair: str(pair[0]["id"]))

def _draft(groups: list[SourceGroup], naming: list[Naming]) -> Changes:
    into, kept = {extra: g.kept for g in groups for extra in g.extras}, {g.url: g.kept for g in groups}
    reason = "One URL, one Source: " + "; ".join(f"{', '.join(g.extras)} merged into {g.kept} ({g.url})"
                                                  for g in groups)
    repoints = (Change(PutEntity(swapped(r, into)), reason, source_refs=tuple(sorted({kept[u] for u in urls})))
                for r, urls in naming)
    retracts = (Change(Retract(extra), reason) for g in groups for extra in g.extras)
    return Changes(FilesOn.MERGE, reason, groups[0].kept, Changeset((*repoints, *retracts)))

def _drafts(groups: tuple[SourceGroup, ...], naming: list[Naming]) -> tuple[Changes, ...]:
    parts = _joined([*({g.url} for g in groups), *(set(urls) for _, urls in naming)])
    return tuple(_draft([g for g in groups if g.url in part], [n for n in naming if min(n[1]) in part])
                 for part in parts)

@dataclass(frozen=True, slots=True)
class SourceMerge:
    groups: tuple[SourceGroup, ...]
    drafts: tuple[Changes, ...]

    @staticmethod
    def kinds(schema: ModelSchema) -> tuple[str, ...]:
        return tuple(e.name for e in schema.entities if e.name != generated.Change.__name__)

    @classmethod
    def of(cls, catalog: Catalog, schema: ModelSchema) -> SourceMerge:
        held = _held(catalog.all(Source))
        url_of = {extra.id: url for url, (_, *extras) in held.items() for extra in extras}
        naming = _naming(catalog, schema, url_of)
        groups = tuple(SourceGroup(url, kept.id, tuple(e.id for e in extras),
                                   tuple(str(r["id"]) for r, urls in naming if url in urls))
                       for url, (kept, *extras) in held.items())
        return cls(groups, _drafts(groups, naming))
