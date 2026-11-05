from __future__ import annotations

import dataclasses
import json
import urllib.request
from datetime import date
from typing import Any, Collection, Iterator, Mapping, Sequence

import pytest

from radar.tests.fixtures.fixture_category import FilesCatalogRepository
from radar.adapters.firestore import layout
from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens, FirestoreResearchRuns, RESEARCH, TOKENS
from radar.domain.ports.store.docs import Docs, Fields, Put
from radar.adapters.firestore.repository import (StoreCatalogRepository, StoreChangeLog, StoreRecords,
                                                 StoreVersionStore, proposal_doc)
from radar.domain.validation.context import InvalidChangeset
from radar.domain.ports.history.change_log import ChangeLog, ChangePage
from radar.adapters.storage.memory_change_log import MemoryChangeLog
from radar.domain.model.history.projection import Projection, every_page, plain
from radar.domain.ports.history.version_store import VersionStore
from radar.domain.model.entities import Change, FilesOn, LogEntryView, PatchOp, ProposalAction
from radar.domain.ports.review.research_runs import ResearchRun
from radar.domain.ports.store.blob_store import BlobRef
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.review.proposal_queue import ProposalQueue, Query
from radar.domain.model.history.ids import keyed
from radar.domain.review.agents.tokens import Limits, Scope, issue
from radar.domain.review.proposal import Proposal, content_hash
from radar.tests.store import stores

FX = stores.fixture()

@pytest.fixture(params=("files", "emulator"))
def repository(request: pytest.FixtureRequest) -> CatalogRepository:
    if request.param == "files":
        return FilesCatalogRepository(FX.public, FX.model)
    docs, _ = FX.seeded()
    return StoreCatalogRepository(docs, FX.model)

def test_catalog_repository(repository: CatalogRepository) -> None:
    index = repository.index()
    cards = index.products
    assert [c.slug for c in cards] == sorted(c.slug for c in cards) and len(cards) == index.counts.products
    for card in cards:
        view = repository.product(card.id)
        assert view is not None and repository.product(card.slug) == view and view.slug == card.slug
    assert repository.product("prd_zzzzzzzzzz") is None and repository.product("no-such__product") is None
    ids = [c.id for c in reversed(cards)]
    assert repository.products(ids) == [repository.product(i) for i in ids]
    with pytest.raises(LookupError, match="prd_zzzzzzzzzz"):
        repository.products([*ids[:2], "prd_zzzzzzzzzz"])
    for category in (c for c in index.categories if c.products):
        pages, cursor = [], None
        while page := repository.category_page(category.id, cursor):
            pages.append(page)
            cursor = page.next
            if cursor is None:
                break
        assert len(pages) == category.pages and sum(len(p.products) for p in pages) == category.products
    used = [v for v in repository.products([c.id for c in cards]) if v.hub]
    assert used, "the fixture names products other products use"
    for view in used:
        users = repository.users(view.id)
        assert (view.hub and len(users) == view.hub.users
                and [u.name for u in users] == sorted((u.name for u in users), key=str.lower))
        assert all(any(c.id == view.id for c in repository.product(u.id).components) for u in users)
    versioned = [c.id for c in cards if repository.product(c.id).version > 1]
    assert versioned and all(repository.history(p).entity == p for p in versioned)
    assert repository.history(cards[0].id if cards[0].id not in versioned else "prd_zzzzzzzzzz") is None

def _change(entity: str, n: int, cid: str) -> Change:
    op = (PatchOp(op="add", path="id", value=json.dumps(entity)) if n == 1 else PatchOp(op="remove", path="name")
          if n == 55 else
          PatchOp(op="add" if n == 2 else "replace", path="name", value=json.dumps(f"v{n}")))
    return Change(id=f"chg_{n + (0 if entity.endswith('1') else 500):010d}", entity=entity, version=n,
                  recorded_at=f"2026-10-1{min(n, 8)}T00:00:00Z", actor_kind="human", actor="curator",
                  reason=f"step {n}", patch=(op,), source_refs=(), correlation_id=cid)

def test_the_store_lists_a_collection_past_one_page() -> None:
    docs = stores.fresh()
    for start in range(0, 650, 325):
        docs.commit([Put(f"{layout.CHANGES}/c{n:04d}", {"n": n}) for n in range(start, start + 325)]
                    + [Put(f"{layout.VERSIONS}/e{n:04d}/{layout.SNAPSHOTS}/1", {"n": n})
                       for n in range(start, start + 325)][:175])
    assert [f["n"] for _, f in docs.list(layout.CHANGES)] == list(range(650))
    assert len(list(docs.group(layout.SNAPSHOTS))) == 350
    assert (docs.count(layout.CHANGES) == 650
            and [f["n"] for _, f in docs.after(layout.CHANGES, "n", None)] == list(range(650)))
    assert [f["n"] for _, f in docs.after(layout.CHANGES, "n", (640, "c0640"))] == list(range(641, 650))
    docs.commit([Put("ties/b", {"k": 1}), Put("ties/a", {"k": 1}), Put("ties/c", {"k": 0})])
    assert [p for p, _ in docs.after("ties", "k", None)] == ["ties/c", "ties/a", "ties/b"]
    assert [p for p, _ in docs.after("ties", "k", (1, "a"))] == ["ties/b"]
    assert [p for p, _ in docs.after("ties", "k", (0, ""))] == ["ties/a", "ties/b"]
    docs.commit([Put("nested/a", {"m": {"refs": ["x", "y"], "k": 1}}), Put("nested/b", {"m": {"k": 2}})])
    assert [p for p, _ in docs.where("nested", "m.refs", ["y"], contains=True)] == [
        p for p, _ in docs.where("nested", "m.k", [1])] == ["nested/a"]
    assert [p for p, _ in docs.where("nested", "m.refs", ["x", *map(str, range(40)), "y"],
                                     contains=True)] == ["nested/a"]
    assert sorted(f["n"] for _, f in docs.where(layout.CHANGES, "n", range(0, 650, 10))) == list(range(0, 650, 10))

def _changes(entity: str, other: str) -> list[Change]:
    return [*(_change(entity, n, "cor-a" if n < 3 else "cor-b") for n in range(1, 56)), _change(other, 1, "cor-a")]

@pytest.fixture(params=("projection", "emulator"))
def history(request: pytest.FixtureRequest) -> tuple[ChangeLog, VersionStore]:
    changes = _changes("org_0000000001", "org_0000000002")
    if request.param == "projection":
        log = MemoryChangeLog(changes[::-1])
        return log, Projection(log)
    docs = stores.fresh()
    docs.commit([Put(f"{layout.CHANGES}/{c.id}", plain(c)) for c in changes])
    store_log = StoreChangeLog(docs, FX.model)
    return store_log, StoreVersionStore(docs, store_log)

class CountingDocs:
    def __init__(self, inner: Docs) -> None:
        self._inner, self.docs_read, self.queries = inner, 0, 0

    def get(self, path: str) -> Fields | None:
        doc = self._inner.get(path)
        self.docs_read += 1 if doc is not None else 0
        return doc

    def get_many(self, paths: Sequence[str]) -> dict[str, Fields]:
        docs = self._inner.get_many(paths)
        self.docs_read += len(docs)
        return docs

    def _counted(self, rows: Iterable[tuple[str, Fields]]) -> list[tuple[str, Fields]]:
        items = list(rows)
        self.docs_read += len(items)
        return items

    def list(self, collection: str) -> Iterator[tuple[str, Fields]]:
        return iter(self._counted(self._inner.list(collection)))

    def where(self, collection: str, field: str, values: Collection[Any],
              contains: bool = False) -> list[tuple[str, Fields]]:
        self.queries += 1
        return self._counted(self._inner.where(collection, field, values, contains))

    def page(self, collection: str, cursor: str | None = None, limit: int = 20,
             where: Mapping[str, Any] | None = None) -> list[tuple[str, Fields]]:
        return self._counted(self._inner.page(collection, cursor, limit, where))

    def after(self, collection: str, field: str, start: tuple[Any, str] | None) -> Iterator[tuple[str, Fields]]:
        return iter(self._counted(self._inner.after(collection, field, start)))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

def test_a_second_detect_reads_none_of_the_changes_before_its_cursor() -> None:
    docs = CountingDocs(stores.fresh())
    docs.commit([Put(f"{layout.CHANGES}/{c.id}", plain(c)) for c in _changes("org_0000000001", "org_0000000002")])
    log = StoreChangeLog(docs, FX.model)
    first = log.after()
    assert len(first.changes) == docs.docs_read == 56
    second = log.after(first.cursor)
    assert second == ChangePage((), first.cursor) and docs.docs_read == 56

def test_a_rename_reads_referrers_per_reference_field_not_per_product() -> None:
    docs, files = FX.seeded()
    counted, org = CountingDocs(docs), FX.rows("organizations.jsonl")[0]
    renamed = stores.put({**org, "name": "Halden Imaging"}, "Renamed", [FX.rows("sources.jsonl")[0]["id"]])
    FX.writer(counted, files).check(stores.changeset(renamed))
    fields = sum(1 for e in FX.model.schema.entities if e.collection for _ in FX.model.schema.reference_paths(e.name))
    assert counted.queries <= 3 * fields, (counted.queries, fields)

def test_change_log_and_version_store(history: tuple[ChangeLog, VersionStore]) -> None:
    log, versions = history
    entity = "org_0000000001"
    first = log.for_entity(entity)
    rest = log.for_entity(entity, first.cursor)
    assert [c.version for c in first.changes + rest.changes] == list(range(1, 56)) and rest.cursor is None
    assert versions.get(entity, 3) == {"id": entity, "name": "v3"} and versions.get(entity, 99) is None
    page = versions.history(entity)
    assert [v.version for v in page.versions] == list(range(55, 35, -1)) and page.total == 55
    assert [v.version for v in versions.history(entity, page.cursor).versions][0] == 35
    assert [(c.path, c.before, c.after) for c in versions.diff(entity, 2, 4)] == [("name", "v2", "v4")]
    assert [(c.path, c.before, c.after) for c in versions.diff(entity, 54, 55)] == [("name", "v54", None)]

def test_blob_store() -> None:
    blob_store = stores.blobs()
    content = b"%PDF-1.4\n% a fictional datasheet\n"
    ref = blob_store.put(content, "application/pdf", True)
    assert blob_store.put(content, "application/pdf", True) == ref and blob_store.has(ref)
    assert b"".join(blob_store.get(ref)) == content and not blob_store.has(BlobRef("0" * 64, "application/pdf"))
    with urllib.request.urlopen(blob_store.url(ref, True)) as res:
        assert res.read() == content
    with pytest.raises(PermissionError):
        blob_store.url(blob_store.put(b"vendor bytes", "application/pdf", False), False)
    blob_store.write(f"media/{ref.sha256[:2]}/{ref.sha256[2:]}.pdf", b"tampered", "application/pdf", True)
    with pytest.raises(ValueError, match="hashes to"):
        b"".join(blob_store.get(ref))

def test_catalog_writer() -> None:
    writer = FX.writer(*FX.seeded())
    _, changed = FX.revised_claim(10.0)
    applied = writer.apply(stores.changeset(stores.put(changed, "Datasheet revision B")), "change-1")
    [event] = applied.events
    assert set(event) == {"id", "entity", "version", "recorded_at", "actor_kind", "actor", "reason", "patch",
                          "source_refs", "correlation_id"}
    assert ((event["version"], event["correlation_id"], event["actor_kind"]) == (2, "change-1", "human")
            and applied.writes > 3)
    assert writer.apply(stores.changeset(stores.put(changed, "Datasheet revision B")), "change-2").writes == 0
    before = writer.docs.get_many([p for c in writer.docs.collections() for p, _ in writer.docs.list(c)])
    with pytest.raises(InvalidChangeset):
        writer.apply(stores.changeset(stores.put({**changed, "source_refs": ["src_zzzzzzzzzz"]}, "Datasheet revision C",
                                                 changed["source_refs"])), "change-3")
    assert writer.docs.get_many(list(before)) == before

def _proposal(n: int, author: str, files_on: FilesOn, at: str) -> Proposal:
    digest = content_hash(author, f"prd_{n:010d}", f"report {n}", None, None)
    return Proposal(keyed("prp", digest), files_on, "suggested", None, f"prd_{n:010d}", f"reason {n}",
                    "agent" if author != "founder" else "human", author, at, digest, f"report {n}")

def _entry(p: Proposal, action: ProposalAction, at: str, actor: str = "founder") -> LogEntryView:
    return LogEntryView(at=at, action=action, proposal=p.id, actor=actor, actor_kind="human",
                        note=None if action == "submit" else f"{action} note", changes=(),
                        correlation_id=f"test-{action}")

def test_proposal_queue() -> None:
    proposals: ProposalQueue = FX.queue(stores.fresh())
    made = [_proposal(n, "scout" if n % 2 else "founder", FilesOn.UPDATE if n % 3 else FilesOn.MERGE,
                      f"2026-10-18T{10 + n // 60}:{n % 60:02d}:00Z")
            for n in range(55)]
    for p in made:
        assert proposals.submit(p, _entry(p, "submit", p.created_at, p.author)) == p
    again = proposals.submit(made[0], _entry(made[0], "submit", "2026-10-18T11:30:00Z", "scout"))
    assert (again.id, again.reports) == (made[0].id, 2) and proposals.get(made[0].id) == again
    taken = proposals.submit(dataclasses.replace(made[1], content_hash="0" * 64),
                             _entry(made[1], "submit", "2026-10-18T11:00:00Z"))
    assert taken.id not in {p.id for p in made} and proposals.get(made[1].id) == made[1], "a taken id goes to the next"
    pages = [proposals.list(Query("suggested"))]
    while pages[-1].cursor:
        pages.append(proposals.list(Query("suggested"), pages[-1].cursor))
    by_key = sorted([*made, taken], key=lambda p: p.id)
    assert ([p.id for page in pages for p in page.proposals] == [p.id for p in by_key] and len(pages) == 3
            and pages[0].total == 56)
    assert {p.id for p in proposals.list(Query(files_on=FilesOn.MERGE, actor_kind="agent")).proposals} == {
        p.id for p in made if p.files_on == FilesOn.MERGE and p.author == "scout"}
    rejected = made[3].decided("reject", "founder", "not sourced", "2026-10-18T12:00:00Z")
    assert proposals.record(rejected, _entry(rejected, "reject", "2026-10-18T12:00:00Z")) == rejected
    assert (proposals.get(made[3].id) == rejected
            and [p.id for p in proposals.list(Query("rejected")).proposals] == [made[3].id])
    again = proposals.submit(made[3], _entry(made[3], "submit", "2026-10-18T12:30:00Z"))
    assert again.id != made[3].id and again.status == "suggested", "the same content after a decision is a new proposal"
    log = proposals.log()
    assert [(e.action, e.proposal) for e in log.entries[:3]] == [
        ("submit", again.id), ("reject", made[3].id), ("submit", made[0].id)]
    every = [e for page in every_page(lambda cursor: proposals.log(cursor=cursor)) for e in page.entries]
    assert (len(every) == log.total == 59 and len(log.entries) == 20
            and [e.at for e in every] == sorted((e.at for e in every), reverse=True))
    scout = [e for page in every_page(lambda cursor: proposals.log("scout", cursor)) for e in page.entries]
    assert scout == [e for e in every if e.actor == "scout"] and len(scout) == proposals.log("scout").total > 20

def test_admin_lists_read_at_most_one_page_of_documents() -> None:
    inner = stores.fresh()
    docs = CountingDocs(inner)
    queue, blobs = FX.queue(docs), stores.blobs()
    made = [_proposal(n, "scout", FilesOn.UPDATE, f"2026-10-18T10:{n:02d}:00Z") for n in range(25)]
    inner.commit([Put(f"{layout.PROPOSALS}/{p.id}", proposal_doc(p, FX.model.registry.proposal_kinds()[p.files_on]))
                  for p in made]
                 + [Put(f"{layout.LOG}/{layout.newest_first(p.created_at)}-{p.id}-s-c",
                        plain(_entry(p, "submit", p.created_at))) for p in made])

    tokens, runs, records = (FirestoreAgentTokens(docs), FirestoreResearchRuns(docs),
                             StoreRecords(docs, FX.model, blobs))
    docs.commit([Put(f"{TOKENS}/{t.id}",
                     {**dataclasses.asdict(t), "scope": t.scope.value, "expires": t.expires.isoformat()})
                 for t, _ in [issue(f"agt-{n}", Scope.READ, date(2026, 12, 31), Limits(), "2026-10-20T09:00:00Z")
                              for n in range(25)]]
                + [Put(f"{RESEARCH}/res_{n:04d}",
                       {**dataclasses.asdict(ResearchRun(f"res_{n:04d}", "acme", "founder", "2026-10-20T09:00:00Z",
                                                         "agt", 1.0)), "outcome": "running", "lines": []})
                   for n in range(25)]
                + [Put(f"documents/doc_{n:010d}",
                       {"id": f"doc_{n:010d}", "version": 1, "kind": "photo", "mime": "image/jpeg",
                       "bytes": 1024, "sha256": f"{n:064x}", "subjects": ["prd_0000000001"],
                       "rights": "editorial_press"}) for n in range(25)])
    cases = [
        (lambda c=None: queue.list(Query(), cursor=c), lambda r: r.proposals, lambda r: r.cursor, lambda r: r.total),
        (lambda c=None: queue.log(cursor=c), lambda r: r.entries, lambda r: r.cursor, lambda r: r.total),
        (lambda c=None: tokens.page(cursor=c), lambda r: r[0], lambda r: r[1], lambda r: r[2]),
        (lambda c=None: runs.page(cursor=c), lambda r: r.runs, lambda r: r.cursor, lambda r: r.total),
        (lambda c=None: records.rows("Document", cursor=c), lambda r: r.records, lambda r: r.cursor, lambda r: r.total),
    ]
    for fetch, get_items, get_cursor, get_total in cases:
        docs.docs_read = 0
        p1 = fetch(None)
        assert len(get_items(p1)) == 20 and docs.docs_read <= 20 and get_total(p1) == 25 and get_cursor(p1)
        docs.docs_read = 0
        assert len(get_items(fetch(get_cursor(p1)))) == 5 and docs.docs_read <= 20
