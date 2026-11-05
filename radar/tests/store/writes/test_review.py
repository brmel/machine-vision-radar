from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from radar.adapters.firestore import layout, store
from radar.domain.model.history.changeset import Retract, parse_changeset
from radar.domain.model.entities import FilesOn, ProposalStatus, Risk
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.ports.store.docs import Put
from radar.domain.review.agents.tokens import Limits, Refused, Scope, issue
from radar.domain.review.proposal import AlreadyProposed, Filed, ProposalError
from radar.domain.review.requests import (Agent, Approval, Bundle, Bundled, Changes, Enactment, Founder, Job, Picked,
                                          Reader, Rejection, Report, Retraction, Revision, Rollback, Withdrawal)
from radar.domain.validation.context import Part
from radar.domain.validation.verdict import InvalidChangeset
from radar.tests.store import stores

FX = stores.fixture()
FOUNDER, SCOUT = Founder("founder", "review-founder"), Job("scout", "review-scout")

def _agent(name: str) -> Agent:
    return Agent(issue(name, Scope.PROPOSE, date(2026, 10, 19), Limits(), stores.NOW)[0], f"{name}-run")

def _changes(files_on: FilesOn, reason: str, subject: str, *records: tuple[dict[str, Any], list[str]]) -> Changes:
    return Changes(files_on, reason, subject,
                   parse_changeset({"changes": [stores.put(r, reason, refs) for r, refs in records]}))

def _claim_draft(add: float) -> Changes:
    _, claim = FX.revised_claim(add)
    return _changes(FilesOn.UPDATE, "Datasheet revision B", claim["subject"], (claim, claim["source_refs"]))

def test_a_proposal_changes_the_catalog_only_once_approved_and_retracting_it_undoes_it() -> None:
    docs, files = FX.seeded()
    review, claim = FX.review(docs, files), FX.rows("claims.jsonl")[0]
    filed = review.submit(_claim_draft(40), SCOUT)
    assert (filed.proposal.status, filed.proposal.files_on, filed.proposal.actor_kind) == (
        "suggested", FilesOn.UPDATE, "agent")
    assert FX.stored(docs, claim["id"])["value"] == claim["value"], "an agent's proposal waits for the founder"
    [change] = filed.changes
    assert (change.entity, change.after["value"]["range"]["max"]) == (claim["id"], claim["value"]["range"]["max"] + 40)
    with pytest.raises(ProposalError, match="note"):
        review.decide(Approval(Picked((filed.proposal.id, filed.proposal.id)), " "), FOUNDER)
    [approved] = review.decide(Approval(Picked((filed.proposal.id, filed.proposal.id)), "Checked against revision B"),
                               FOUNDER).done
    assert (FX.stored(docs, claim["id"])["value"]["range"]["max"] == claim["value"]["range"]["max"] + 40
            and len(approved.applied) == 1)
    event = FX.stored(docs, approved.applied[0].change)
    assert (event["proposal"], event["actor"], event["correlation_id"], approved.reviewer) == (
        filed.proposal.id, "scout", FOUNDER.correlation_id, "founder")
    retracted = review.decide(Retraction(Picked((filed.proposal.id,)), "Revision B was withdrawn"), FOUNDER)
    assert (retracted.changed and retracted.one().status == "retracted"
            and FX.stored(docs, claim["id"])["value"] == claim["value"])
    assert [v.version for v in FX.versions(docs).history(claim["id"]).versions] == [3, 2, 1]
    log = review.log(FOUNDER)
    assert [(e.action, e.actor) for e in log.entries] == [("retract", "founder"), ("approve", "founder"),
                                                          ("submit", "scout")]
    assert log.entries[1].changes == (event["id"],) and log.entries[1].correlation_id == FOUNDER.correlation_id

def test_a_change_citing_no_source_is_refused_whoever_proposes_it_but_a_provenance_records() -> None:
    docs, files = FX.seeded()
    review, name, source = FX.review(docs, files), FX.rows("names.jsonl")[0], FX.rows("sources.jsonl")[0]
    renamed = _changes(FilesOn.UPDATE, "Renamed", name["id"], ({**name, "value": "Widget One B"}, []))
    for by in (FOUNDER, SCOUT):
        with pytest.raises(ProposalError, match=r"changes\[0\]: source_refs names at least one source"):
            review.submit(renamed, by)
    page = _changes(FilesOn.CREATE, "A page", "src_00000000zy",
                    ({**source, "id": "src_00000000zy", "url": "https://example.com/page"}, []))
    assert review.submit(page, FOUNDER).proposal.status == "suggested"
    with pytest.raises(Refused):
        review.submit(Report(name["subject"], "Wrong name"), FOUNDER)
    org = FX.rows("organizations.jsonl")[0]
    review.decide(Enactment(_changes(FilesOn.UPDATE, "Renamed", org["id"],
                                     ({**org, "name": "Halden Imaging"}, [source["id"]]))), FOUNDER)
    rolled = review.submit(Rollback(org["id"], 1, "The old name stands"), FOUNDER).proposal
    assert (rolled.files_on == FilesOn.ROLLBACK
            and review.decide(Approval(Picked((rolled.id,)), "Checked"), FOUNDER).changed)
    assert FX.stored(docs, org["id"])["name"] == org["name"]

def test_retracting_a_proposal_that_added_a_source_returns_the_catalog_to_before_it() -> None:
    docs, files = FX.seeded()
    review = FX.review(docs, files)
    source, product, name, role = (FX.rows(f)[0]
                                   for f in ("sources.jsonl", "products.jsonl", "names.jsonl",
                                             "product_org_roles.jsonl"))
    cited = ["src_000000000z"]
    added = [{**source, "id": cited[0], "url": "https://example.com/widget-nine.pdf"},
             {**product, "id": "prd_000000000z", "slug": f"{product['slug']}-nine"},
             {**name, "id": "nam_000000000z", "subject": "prd_000000000z", "value": "Widget Nine"},
             {**role, "id": "por_000000000z", "product": "prd_000000000z", "source_refs": cited}]
    approved = review.decide(Enactment(_changes(FilesOn.CREATE, "New model", "prd_000000000z",
                                                *((r, cited) for r in added))), FOUNDER).one()
    review.decide(Retraction(Picked((approved.id,)), "Never sold"), FOUNDER)
    versions = FX.versions(docs)
    for r in added:
        assert docs.get(layout.canonical(FX.model.schema, r["id"])) is None
        assert [v.version for v in versions.history(r["id"]).versions] == [2, 1]
    today, records = date.fromisoformat(stores.NOW[:10]), list(store.scan(docs, FX.model.schema))
    assert FX.model.check(layout.catalog_of(FX.model, records), Part(), today).errors == ()
    review.decide(Enactment(_changes(FilesOn.CREATE, "A page", "src_00000000zz",
                                     ({**added[0], "id": "src_00000000zz"}, ["src_00000000zz"]))), FOUNDER)
    review.decide(Enactment(Withdrawal("src_00000000zz", "Gone")), FOUNDER)
    assert docs.get(layout.canonical(FX.model.schema, "src_00000000zz")) is None, (
        "a source its Change events cite is withdrawn; they keep it")
    records = list(store.scan(docs, FX.model.schema))
    for moved in ("2026-10-18T23:00:00Z",
                  "2026-01-01T00:00:00Z"):
        events = [{**r, "recorded_at": moved} if r["id"] == approved.applied[-1].change else r for r in records]
        [finding] = FX.model.check(layout.catalog_of(FX.model, events), Part(), today).errors
        assert finding.message == f"Change.source_refs: '{cited[0]}' does not exist", (
            "history cites a source that existed when it was recorded")

def test_review_refuses_what_it_cannot_apply() -> None:
    docs, files = FX.seeded()
    review, claim = FX.review(docs, files), FX.rows("claims.jsonl")[0]
    unsourced = parse_changeset(
        {"changes": [stores.put({**claim, "source_refs": ["src_zzzzzzzzzz"]}, "No such source")]})
    good, other = (review.submit(_claim_draft(add), FOUNDER).proposal for add in (40, 50))
    review.decide(Rejection(Picked((other.id,)), "Revision C is not out"), FOUNDER)
    with pytest.raises(ProposalError, match="rejected"):
        review.decide(Approval(Picked((good.id, other.id)), "Both"), FOUNDER)
    assert (review.proposal(good.id, FOUNDER).proposal.status == "suggested"
            and FX.stored(docs, claim["id"])["value"] == claim["value"])
    report = review.submit(Report(claim["subject"], "The max is wrong."), Reader("review-reader")).proposal
    assert (report.files_on, report.author) == (FilesOn.REPORT, "public")
    with pytest.raises(ProposalError, match="no change"):
        review.decide(Approval(Picked((report.id,)), "Fix"), FOUNDER)
    with pytest.raises(InvalidChangeset):
        review.decide(Revision(report.id, unsourced, "Sourced"), FOUNDER)
    edited = review.decide(Revision(report.id, _claim_draft(60).changeset, "Checked the datasheet"), FOUNDER).one()
    assert ([e.note for e in edited.edits] == ["Checked the datasheet"]
            and review.decide(Approval(Picked((edited.id,)), "Fixed"), FOUNDER).changed)
    review.decide(Approval(Picked((good.id,)), "Revision B"), FOUNDER)
    [refused] = review.decide(Retraction(Picked((report.id,)), "Wrong after all"), FOUNDER).refused
    assert "changed after" in refused.findings[0].message
    rollback = review.submit(Rollback(claim["id"], 1, "Back to the first datasheet"), FOUNDER).proposal
    review.decide(Approval(Picked((rollback.id,)), "Back to v1"), FOUNDER)
    assert FX.stored(docs, claim["id"])["value"] == claim["value"]
    assert review.queue(Query(ProposalStatus.SUGGESTED), FOUNDER).proposals == ()

def test_a_withdrawal_lets_go_of_the_record_everywhere_and_never_leaves_a_reference_inside_a_value() -> None:
    docs, files = FX.seeded()
    review = FX.review(docs, files)
    shared = next(d for d in FX.rows("documents.jsonl") if d["subjects"])
    product, last = shared["subjects"][0], FX.rows("products.jsonl")[-1]["id"]
    if len(shared["subjects"]) == 1:
        docs.commit([Put(layout.canonical(FX.model.schema, shared["id"]),
                         {**FX.stored(docs, shared["id"]), "subjects": [product, last]})])
    filed = review.submit(Withdrawal(product, "Never sold"), FOUNDER).proposal
    retracted = ({c.entity for c in filed.changeset.changes if isinstance(c.action, Retract)} if filed.changeset
                 else set())
    needing = {r["id"] for f in ("names.jsonl", "claims.jsonl") for r in FX.rows(f) if r["subject"] == product}
    assert {product} | needing <= retracted and shared["id"] not in retracted
    review.decide(Approval(Picked((filed.id,)), "Checked"), FOUNDER)
    assert (docs.get(layout.canonical(FX.model.schema, product)) is None
            and product not in FX.stored(docs, shared["id"])["subjects"])
    assert FX.versions(docs).history(product).versions
    claim = next(c for c in FX.rows("claims.jsonl") if c["subject"] not in (product, last))
    docs.commit([Put(layout.canonical(FX.model.schema, claim["id"]),
                     {**FX.stored(docs, claim["id"]), "applies_to_versions": {"product": last}})])
    with pytest.raises(InvalidChangeset, match=f"applies_to_versions.product: '{last}' does not exist"):
        review.decide(Enactment(Withdrawal(last, "Never sold")), FOUNDER)
    assert docs.get(layout.canonical(FX.model.schema, last)) is not None

def _run_drafts() -> dict[str, Changes]:
    source, product, name, role = (FX.rows(f)[0]
                                   for f in ("sources.jsonl", "products.jsonl", "names.jsonl",
                                             "product_org_roles.jsonl"))
    claims, (held, revised) = FX.rows("claims.jsonl"), FX.revised_claim(40)
    *_, other, last = sorted({c["subject"] for c in claims} - {held["subject"]})
    gone, claim = (next(c for c in claims if c["subject"] == subject) for subject in (last, other))
    page = ({**source, "id": "src_00000000p1", "url": "https://example.com/widget-nine"}, [])
    cited, made = ["src_00000000p1"], "prd_000000000z"
    new = ({**product, "id": made, "slug": f"{product['slug']}-nine"},
           {**name, "id": "nam_000000000z", "subject": made, "value": "Widget Nine"},
           {**role, "id": "por_000000000z", "product": made})
    own = {**next(p for p in FX.rows("products.jsonl") if p["id"] == claim["subject"]),
           "website_url": "https://example.com/widget"}
    value = {**claim, "id": "clm_00000000v1"}
    return {"a": _changes(FilesOn.CREATE, "Widget Nine", made, page, *((r, cited) for r in new)),
            "c": _changes(FilesOn.UPDATE, "Its own page", claim["subject"], page, (own, cited)),
            "b": _changes(FilesOn.UPDATE, "Its value", claim["subject"], page, (value, cited),
                          ({**claim, "id": "clm_00000000v2", "spec_key": "no_such_spec"}, cited)),
            "r": _changes(FilesOn.UPDATE, "Datasheet revision B", held["subject"], page, (revised, cited)),
            "s": _changes(FilesOn.UPDATE, "Recorded again", gone["subject"], page,
                          ({**gone, "recorded_at": "2026-10-18T12:00:00Z"}, cited)),
            "again": _changes(FilesOn.UPDATE, "Its value", claim["subject"], page, (value, cited)),
            "d": _changes(FilesOn.UPDATE, "Widget Nine's value", made, page,
                          ({**claim, "id": "clm_00000000v3", "subject": made}, cited))}

def test_a_runs_bundle_is_filed_salvaged_and_read_in_dependency_order_the_riskiest_first() -> None:
    docs, files = FX.seeded()
    review, run, drafts = FX.review(docs, files), _agent("research"), _run_drafts()
    filings = review.file(Bundle(run.correlation_id, tuple(drafts[k] for k in "acbrs")), run)
    assert [(type(f), len(f.refusals)) for f in filings] == [(Filed, 0), (Filed, 0), (Filed, 1), (Filed, 0), (Filed, 0)]
    a, c, b, r, s = (f.proposal for f in filings if isinstance(f, Filed))
    assert b.changeset is not None and [ch.entity for ch in b.changeset.changes] == ["src_00000000p1", "clm_00000000v1"]
    assert review.file(Bundle(run.correlation_id, (drafts["again"],)), run) == (AlreadyProposed(),)
    members = review.bundle(run.correlation_id, FOUNDER)
    assert [(m.proposal.id, m.risk, m.after) for m in members] == [
        (c.id, Risk.CHANGES, ()), (r.id, Risk.CHANGES, ()), (s.id, Risk.CHANGES, ()), (a.id, Risk.ADDS, ()),
        (b.id, Risk.ADDS, (c.id,))]
    other = _agent("other")
    assert review.queue(Query(), other).total == 0 and review.queue(Query(bundle=run.correlation_id), run).total == 5
    with pytest.raises(Refused):
        review.proposal(b.id, other)

def test_approving_a_bundle_applies_each_on_its_own_and_holds_only_what_needs_a_member_not_approved() -> None:
    docs, files = FX.seeded()
    review, run, drafts = FX.review(docs, files), _agent("research"), _run_drafts()
    a, c, b, r, s = (f.proposal for f in review.file(Bundle(run.correlation_id, tuple(drafts[k] for k in "acbrs")), run)
                     if isinstance(f, Filed))
    review.decide(Rejection(Picked((c.id,)), "Not its own page"), FOUNDER)
    gone = drafts["s"].subject or ""
    review.decide(Enactment(Withdrawal(gone, "Never sold")), FOUNDER)
    whole = Approval(Bundled(run.correlation_id), "Checked on the maker's page")
    outcome = review.decide(whole, FOUNDER)
    assert ([p.id for p in outcome.done] == [a.id, b.id, r.id] and [x.proposal.id for x in outcome.refused] == [s.id]
            and outcome.held == ())
    [d] = review.file(Bundle(run.correlation_id, (drafts["d"],)), run)
    assert isinstance(d, Filed)
    review.decide(Retraction(Picked((a.id,)), "Not this maker's product"), FOUNDER)
    again = review.decide(whole, FOUNDER)
    assert again.done == () and [(h.proposal.id, h.waits_on) for h in again.held] == [(d.proposal.id, (a.id,))]
    assert {m.proposal.id: m.risk for m in review.bundle(run.correlation_id, FOUNDER) if m.risk is None} == {
        a.id: None, b.id: None, c.id: None, r.id: None}
