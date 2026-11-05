from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Iterable, Mapping

from radar.domain.model.entities import AltName, Change, Name, Organization, OrgRelation, Product, ProductVersion
from radar.domain.model.schema import FieldSpec, ModelSchema
from radar.domain.ports.store.docs import Docs
from ..layout import HISTORY, Record, doc_value, read_records, record_of, value_at

Changed = Mapping[str, tuple[Record | None, Record | None]]
NAMES = (Name.__name__, AltName.__name__)

def of_kind(prefix: str | None, ids: Iterable[str]) -> set[str]:
    return {i for i in ids if i.startswith(f"{prefix}_")}

@dataclass(frozen=True, slots=True)
class Neighborhood:
    records: dict[str, Record]
    products: frozenset[str]
    organizations: frozenset[str]

    def after(self, changed: Changed) -> dict[str, Record]:
        merged = {**self.records, **{i: a for i, (_, a) in changed.items() if a is not None}}
        return {i: r for i, r in merged.items() if i not in changed or changed[i][1] is not None}

class _Reach:
    def __init__(self, graph: ReferenceGraph, changed: Changed) -> None:
        self.graph, self.changed = graph, changed
        self.found: dict[str, Record] = {}
        self.inbound: dict[str, list[Record]] = {}
        self.named: set[str] = set()

    def load(self, ids: Iterable[str]) -> None:
        wanted = sorted(set(ids) - self.found.keys() - self.changed.keys())
        self.found.update(read_records(self.graph.docs, self.graph.schema, wanted))
        self.found.update({i: b for i, (b, _) in self.changed.items() if b is not None})

    def refer(self, given: Iterable[str], kinds: Collection[str] | None = None) -> list[Record]:
        ids = sorted(set(given))
        if kinds is None:
            self.inbound.update(self.graph.referrers(set(ids) - self.inbound.keys()))
            found = [r for i in ids for r in self.inbound[i]]
        else:
            found = [r for rs in self.graph.referrers(ids, kinds).values() for r in rs]
        if kinds is None or Name.__name__ in kinds:
            self.named.update(ids)
        self.found.update({r["id"]: r for r in found if r["id"] not in self.changed})
        return found

    def outbound_of(self, records: Iterable[Record]) -> set[str]:
        return {i for r in records for i in self.graph.outbound(r)}

    def around(self, records: Iterable[Record]) -> set[str]:
        return {i for r in records for i in {r["id"], *self.graph.outbound(r)}}

Field = tuple[str, str, str, bool, tuple[str, ...]]

def reference_fields(schema: ModelSchema) -> list[Field]:
    return [(e.name, e.collection, path, f.type == "array", f.refs) for e in schema.entities if e.collection
            for path, f in schema.reference_paths(e.name)]

class ReferenceGraph:
    def __init__(self, docs: Docs, schema: ModelSchema) -> None:
        self.docs, self.schema = docs, schema
        self.product, self.organization, self.version = (schema.types[t.__name__].prefix
                                                         for t in (Product, Organization, ProductVersion))
        self.fields = reference_fields(schema)
        self.own = frozenset(e.name for e in schema.entities) - {Product.__name__}
        self.unique = [(e.name, e.collection, f.name) for e in schema.entities if e.collection for f in e.fields
                       if f.unique]

    def outbound(self, record: Record) -> set[str]:
        kind = self.schema.kind_of(record["id"])
        found = (value_at(record, path) for path, _ in self.schema.reference_paths(kind or ""))
        return {i for value in found if value is not None for i in (value if isinstance(value, list) else [value])}

    def referrers(self, ids: Collection[str], kinds: Collection[str] | None = None) -> dict[str, list[Record]]:
        found: dict[str, Record] = {}
        for _, collection, path, many, refs in self._fields(kinds):
            if named := sorted(i for i in ids if not refs or self.schema.kind_of(i) in refs):
                found.update((r["id"], record_of(r))
                             for _, r in self.docs.where(collection, path, named, contains=many))
        filed: dict[str, list[Record]] = {i: [] for i in ids}
        for r in found.values():
            for i in self.outbound(r) & filed.keys():
                filed[i].append(r)
        return filed

    def _fields(self, kinds: Collection[str] | None) -> list[Field]:
        return self.fields if kinds is None else [f for f in self.fields if f[0] in kinds]

    def naming(self, entity_id: str) -> list[tuple[FieldSpec, Record]]:
        kind = self.schema.kind_of(entity_id)
        return [(f, record_of(r)) for e in self.schema.entities if e.name != Change.__name__ for f in e.fields
                if kind in f.refs
                for _, r in self.docs.where(e.collection or "", f.name, [entity_id], contains=f.type == "array")]

    def neighborhood(self, changed: Changed) -> Neighborhood:
        reach = _Reach(self, changed)
        records = [r for pair in changed.values() for r in pair if r is not None]
        reach.load(changed)
        products = self._products(reach, records)
        organizations = self._organizations(reach, records)
        reach.refer(self._listed(products) - products)
        reach.refer(of_kind(self.version, reach.found))
        for _ in range(2):
            reach.load(reach.outbound_of([*reach.found.values(), *records]))
        self._names(reach)
        self._holders(reach, records)
        return Neighborhood(reach.found, frozenset(products), frozenset(organizations))

    def _products(self, reach: _Reach, records: list[Record]) -> set[str]:
        changed = reach.changed
        others = [i for i in changed if not i.startswith(f"{self.product}_")]
        facts = [r for r in records if not r["id"].startswith(f"{self.product}_")]
        products = of_kind(self.product, set(changed) | reach.outbound_of(facts) | reach.around(reach.refer(others)))
        named = {r["subject"] for r in records if self.schema.kind_of(r["id"]) in NAMES}
        shown = of_kind(self.product, changed.keys() | named)
        products |= of_kind(self.product, reach.around(reach.refer(shown)))
        products |= of_kind(self.product, reach.outbound_of(reach.refer(of_kind(self.organization, named))))
        reach.load(products)
        products |= self._parents(reach, products)
        reach.load(products)
        reach.refer(products - reach.inbound.keys(), self.own)
        return products

    @staticmethod
    def _parents(reach: _Reach, products: set[str]) -> set[str]:
        return {r["parent"] for p in products for r in (reach.found.get(p), *reach.changed.get(p, ()))
                if r and r.get("parent")}

    def _organizations(self, reach: _Reach, records: list[Record]) -> set[str]:
        relation = OrgRelation.__name__
        others = [i for i in reach.changed if not i.startswith((f"{self.product}_", f"{self.organization}_"))]
        owning = [r for r in (*records, *reach.refer(others)) if self.schema.kind_of(r["id"]) == relation]
        organizations: set[str] = set()
        grown = of_kind(self.organization, reach.changed.keys() | reach.outbound_of(owning))
        while grown:
            organizations |= grown
            grown = of_kind(self.organization, reach.outbound_of(reach.refer(grown, {relation}))) - organizations
        return organizations

    def _listed(self, products: set[str]) -> set[str]:
        stored = self.docs.get_many([f"{HISTORY}/{p}" for p in sorted(products)]).values()
        return {v["entity"] for f in stored for v in doc_value(f)["versions"]}

    def _names(self, reach: _Reach) -> None:
        subjects = sorted(
            (of_kind(self.product, reach.found) | of_kind(self.organization, reach.found)) - reach.named)
        for kind in NAMES:
            found = self.docs.where(self.schema.types[kind].collection or "", "subject", subjects)
            reach.found.update({r["id"]: record_of(r) for _, r in found if r["id"] not in reach.changed})

    def _holders(self, reach: _Reach, records: list[Record]) -> None:
        for kind, collection, name in self.unique:
            values = sorted({r[name] for r in records
                             if self.schema.kind_of(r["id"]) == kind and r.get(name) not in (None, "")})
            reach.found.update((h["id"], record_of(h)) for _, h in self.docs.where(collection, name, values))
