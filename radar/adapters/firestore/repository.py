from __future__ import annotations

import json
from dataclasses import asdict, fields, replace
from typing import Any, Iterable, Mapping, Sequence

from radar.adapters.files.json_parser import Checker, ModelParser
from radar.adapters.files.model_json import DEFAULT_LANGUAGE
from radar.domain.model.entities import (ActorKind, AdminRecord, CategoryPage, Change, Claim, Document, FilesOn,
                                         HistoryView, IndexView, LogEntryView, LogPage, MarketView, Name, Organization,
                                         Product, ProductCard, ProductView, ProposalStatus, RecordRow, RecordRows,
                                         Source, StoredFile)
from radar.domain.model.history.projection import Projection, json_text, later, page_of, paged, plain
from radar.domain.model.schema import ModelSchema
from radar.domain.model.changeset import changeset_json, parse_changeset
from radar.domain.ports.history.change_log import ChangePage
from radar.domain.ports.review.proposal_queue import Query, QueuePage
from radar.domain.model.history.ids import ENTITY_ID, keyed
from radar.domain.review.proposal import AppliedChange, Edit, Proposal
from radar.domain.ports.store.blob_store import BlobStore
from radar.domain.ports.store.docs import Docs, Fields, Increment, Put
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.catalog.held_records import T
from radar.domain.ports.store.records import LISTED
from .docs import list_page
from . import layout
from .layout import (CHANGES, FACETS, FEED_STATE, HISTORY, INDEX, LOG, PAGES, PRODUCTS, PROPOSALS, canonical, doc_value,
                     newest_first, read_records, record_of, version)
from .projection.neighborhood import ReferenceGraph
from .store import scan

class StoreCatalogRepository:
    def __init__(self, docs: Docs, schema: ModelSchema) -> None:
        self._docs, self._views = docs, Checker(schema)

    def index(self) -> IndexView:
        reg = self._docs.get(f"{INDEX}/registry")
        if reg is None:
            raise LookupError("the store has no read model; run `radar store load` first")
        cards = [c for n in range(1, reg["cards"] + 1) for c in doc_value(self._docs.get(f"{INDEX}/cards-{n}"))]
        raw = {**doc_value(reg), "organizations": doc_value(self._docs.get(f"{INDEX}/organizations")),
               "products": cards}
        return self._views.parse(raw, IndexView, INDEX)

    def product(self, key: str) -> ProductView | None:
        if ENTITY_ID.fullmatch(key):
            raw = doc_value(self._docs.get(f"{PRODUCTS}/{key}"))
        else:
            found = self._docs.where(PRODUCTS, "slug", [key])
            raw = doc_value(found[0][1]) if found else None
        return None if raw is None else self._views.parse(raw, ProductView, key)

    def products(self, ids: Sequence[str]) -> list[ProductView]:
        found = self._docs.get_many([f"{PRODUCTS}/{i}" for i in ids])
        missing = [i for i in ids if f"{PRODUCTS}/{i}" not in found]
        if missing:
            raise LookupError(f"no product view for {missing[0]}")
        return [self._views.parse(doc_value(found[f"{PRODUCTS}/{i}"]), ProductView, i) for i in ids]

    def category_page(self, category: str, cursor: str | None = None) -> CategoryPage | None:
        facets, page = (self._docs.get(f"{FACETS}/{category}"),
                        doc_value(self._docs.get(f"{FACETS}/{category}/{PAGES}/{cursor or 1}")))
        if facets is None or page is None:
            return None
        return self._views.parse({**page, "facets": doc_value(facets)}, CategoryPage, category)

    def users(self, product: str) -> list[ProductCard]:
        found = self._docs.where(PRODUCTS, "uses", [product], contains=True)
        cards = [self._views.parse(json.loads(f["card"]), ProductCard, p) for p, f in found]
        return sorted(cards, key=lambda c: (c.name.lower(), c.id))

    def history(self, entity: str) -> HistoryView | None:
        raw = doc_value(self._docs.get(f"{HISTORY}/{entity}"))
        return None if raw is None else self._views.parse(raw, HistoryView, entity)

    def market(self) -> MarketView:
        raw = doc_value(self._docs.get(f"{INDEX}/market"))
        if raw is None:
            raise LookupError("no market view in the store: run `radar store reproject`")
        return self._views.parse(raw, MarketView, "market")

class StoreChangeLog:
    def __init__(self, docs: Docs, schema: ModelSchema) -> None:
        self._docs, self._parser, self._type = docs, ModelParser(schema), schema.types[Change.__name__]

    def _parsed(self, rows: Iterable[tuple[str, Fields]]) -> list[Change]:
        return [self._parser.record(f, self._type, p) for p, f in rows]

    def for_entity(self, entity: str, cursor: str | None = None) -> ChangePage:
        return paged(self._parsed(self._docs.where(CHANGES, "entity", [entity])), cursor)

    def after(self, cursor: str | None = None) -> ChangePage:
        recorded, _, change = (cursor or "").partition("|")
        return later(self._parsed(self._docs.after(CHANGES, "recorded_at", (recorded, change) if cursor else None)),
                     cursor)

class StoreVersionStore(Projection):
    def __init__(self, docs: Docs, log: StoreChangeLog) -> None:
        super().__init__(log)
        self._docs = docs

    def get(self, entity: str, n: int) -> dict[str, Any] | None:
        snapshot = self._docs.get(version(entity, n))
        return doc_value(snapshot) if snapshot else super().get(entity, n)

SLOTS = 8

def proposal_doc(p: Proposal, kind: str) -> Fields:
    doc = {**{f.name: getattr(p, f.name) for f in fields(p) if f.name != "files_on"}, "kind": kind,
           "changeset": json.dumps(changeset_json(p.changeset), ensure_ascii=False) if p.changeset else None,
           **{k: [asdict(x) for x in getattr(p, k)] for k in ("edits", "applied", "undone")}}
    return {k: v for k, v in doc.items() if v is not None}

class StoreProposalQueue:
    def __init__(self, docs: Docs, kinds: Mapping[str, str]) -> None:
        self._docs, self._kinds = docs, kinds
        self._events = {kind: FilesOn(event) for event, kind in kinds.items()}

    def _proposal(self, f: Fields) -> Proposal:
        def applied(key: str) -> tuple[AppliedChange, ...]:
            return tuple(AppliedChange(a["change"], a["entity"], int(a["version"])) for a in f[key])
        return Proposal(f["id"], self._events[f["kind"]], ProposalStatus(f["status"]),
                        parse_changeset(json.loads(f["changeset"])) if "changeset" in f else None, f.get("subject"),
                        f["reason"], ActorKind(f["actor_kind"]), f["author"], f["created_at"], f["content_hash"],
                        f.get("message"), f.get("source_url"), int(f["reports"]), f.get("reviewer"), f.get("note"),
                        f.get("decided_at"), tuple(Edit(e["at"], e["actor"], e["note"]) for e in f["edits"]),
                        applied("applied"), applied("undone"), f.get("token"), f.get("bundle"))

    def _entry(self, entry: LogEntryView) -> Put:
        return Put(f"{LOG}/{newest_first(entry.at)}-{entry.proposal}-{entry.action}-{entry.correlation_id}",
                   plain(entry))

    def submit(self, proposal: Proposal, entry: LogEntryView) -> Proposal:
        for n in range(SLOTS):
            filed = proposal if n == 0 else replace(proposal, id=keyed("prp", f"{proposal.content_hash}:{n}"))
            path = f"{PROPOSALS}/{filed.id}"
            stored = self._docs.get(path)
            if stored is None:
                self._docs.commit([Put(path, proposal_doc(filed, self._kinds[filed.files_on]), create=True),
                                   self._entry(replace(entry, proposal=filed.id))])
                return filed
            if stored["content_hash"] == proposal.content_hash and stored["status"] == ProposalStatus.SUGGESTED:
                self._docs.commit([Increment(path, {"reports": 1}), self._entry(replace(entry, proposal=filed.id))])
                return self._proposal({**stored, "reports": int(stored["reports"]) + 1})
        raise ValueError(f"{SLOTS} proposal ids of {proposal.id} are taken by other content or decided proposals")

    def get(self, proposal_id: str) -> Proposal | None:
        found = self._docs.get(f"{PROPOSALS}/{proposal_id}")
        return self._proposal(found) if found else None

    def list(self, query: Query, cursor: str | None = None) -> QueuePage:
        where = {"status": query.status, "kind": self._kinds[query.files_on] if query.files_on else None,
                 "actor_kind": query.actor_kind, "author": query.author, "bundle": query.bundle}
        filters = {k: v for k, v in where.items() if v is not None}
        rows, after, total = list_page(self._docs, PROPOSALS, cursor, filters or None)
        return QueuePage(tuple(self._proposal(f) for _, f in rows), after, total)

    def record(self, proposal: Proposal, entry: LogEntryView) -> Proposal:
        self._docs.commit([Put(f"{PROPOSALS}/{proposal.id}", proposal_doc(proposal, self._kinds[proposal.files_on])),
                           self._entry(entry)])
        return proposal

    def log(self, actor: str | None = None, cursor: str | None = None) -> LogPage:
        where = {"actor": actor} if actor else None
        rows, after, total = list_page(self._docs, LOG, cursor, where)
        entries = tuple(LogEntryView(at=f["at"], action=f["action"], proposal=f["proposal"], actor=f["actor"],
                                     actor_kind=f["actor_kind"], changes=tuple(f["changes"]),
                                     correlation_id=f["correlation_id"], note=f.get("note")) for _, f in rows)
        return LogPage(entries=entries, next=after, total=total)

class StoreFeedReads:
    def __init__(self, docs: Docs, schema: ModelSchema, repository: CatalogRepository) -> None:
        self._docs, self._schema, self._repository = docs, schema, repository

    def records(self, ids: Sequence[str]) -> dict[str, dict[str, Any]]:
        return read_records(self._docs, self._schema, ids)

    def name_of(self, subject: str) -> str:
        names = self._schema.collection(Name.__name__)
        primary = next((f["value"] for _, f in self._docs.where(names, "subject", [subject]) if f.get("is_primary")),
                       None)
        return str(primary or self.records([subject]).get(subject, {}).get("name", subject))

    def counts(self) -> dict[str, int]:
        index = self._repository.index()
        return {"products": len(index.products), "organizations": len(index.organizations),
                "sources": self._docs.count(self._schema.collection(Source.__name__))}

    def examples(self) -> list[str]:
        return [c.id for c in sorted(self._repository.index().products, key=lambda c: c.slug)[:3]]

    def cursor(self) -> str | None:
        found = self._docs.get(f"{FEED_STATE}/detector")
        return str(found["cursor"]) if found else None

    def advance(self, cursor: str) -> None:
        self._docs.commit([Put(f"{FEED_STATE}/detector", {"cursor": cursor})])

class StoreHeldRecords:
    def __init__(self, docs: Docs, schema: ModelSchema) -> None:
        self._docs, self._schema = docs, schema

    def organizations(self) -> tuple[Organization, ...]:
        return tuple(
            layout.catalog_of(self._schema, scan(self._docs, self._schema, (Organization.__name__,))).all(Organization))

    def held(self, record_id: str) -> Mapping[str, Any] | None:
        return layout.held(self._docs, self._schema, record_id)

    def matching(self, kind: type[T], field: str, value: str) -> tuple[T, ...]:
        found = (record_of(f) for _, f in self._docs.where(self._schema.collection(kind.__name__), field, [value]))
        return tuple(layout.catalog_of(self._schema, found).all(kind))

    def ranked_first(self, claim: Mapping[str, Any]) -> str | None:
        return layout.ranked_first(self._docs, self._schema, dict(claim))

    def claims(self) -> tuple[Claim, ...]:
        return tuple(layout.catalog_of(self._schema, scan(self._docs, self._schema, (Claim.__name__,))).all(Claim))

    def created_since(self, instant: str) -> frozenset[str]:
        return frozenset(f["entity"] for _, f in self._docs.after(CHANGES, "recorded_at", (instant, ""))
                         if f["version"] == 1)

Row = dict[str, Any]

def _row(r: Row) -> RecordRow:
    return RecordRow(id=r["id"], label=r.get("title", {}).get(DEFAULT_LANGUAGE.code) or r["id"],
                     detail=" · ".join(str(v) for v in (r.get("kind"), r.get("rights"), *r.get("subjects", [])) if v))

class StoreRecords:
    def __init__(self, docs: Docs, schema: ModelSchema, blobs: BlobStore) -> None:
        self._docs, self._schema, self._blobs = docs, schema, blobs
        self._graph, self._read = ReferenceGraph(docs, schema), StoreCatalogRepository(docs, schema)

    def _all(self, kind: str, category: str | None) -> list[RecordRow]:
        if kind == Product.__name__:
            return [RecordRow(id=c.id, label=c.name, detail=c.vendor_name) for c in self._read.index().products
                    if category in (None, c.category)]
        if kind == Organization.__name__:
            return [RecordRow(id=o.id, label=o.name, detail=o.country) for o in self._read.index().organizations]
        return [_row(r) for _, r in self._docs.list(self._schema.collection(kind))]

    def _page_docs(self, kind: str, cursor: str | None) -> RecordRows:
        rows, after, total = list_page(self._docs, self._schema.collection(kind), cursor)
        return RecordRows(records=tuple(_row(r) for _, r in rows), total=total, next=after)

    def rows(self, kind: str, query: str = "", cursor: str | None = None,
             category: str | None = None) -> RecordRows:
        if kind not in LISTED:
            raise ValueError(f"kind is one of {', '.join(LISTED)}")
        if kind == Document.__name__ and not query:
            return self._page_docs(kind, cursor)
        hits = sorted((r for r in self._all(kind, category) if query.lower() in f"{r.label} {r.id}".lower()),
                      key=lambda r: (r.label.lower(), r.id))
        page, after = page_of(hits, cursor)
        return RecordRows(records=page, total=len(hits), next=after)

    def record(self, entity: str) -> AdminRecord | None:
        found = self._docs.get(canonical(self._schema, entity))
        if found is None:
            return None
        related = [r for _, r in self._graph.naming(entity)]
        cited = sorted({s for r in (found, *related) for s in r.get("source_refs", [])} - {r["id"] for r in related})
        sources = list(read_records(self._docs, self._schema, cited).values())
        return AdminRecord(record=json_text(record_of(found)),
                           related=tuple(json_text(r) for r in (*related, *sources)))

    def upload(self, content: bytes, mime: str) -> StoredFile:
        ref = self._blobs.put(content, mime, False)
        return StoredFile(sha256=ref.sha256, mime=ref.mime, bytes=len(content))
