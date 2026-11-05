from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radar.adapters.firestore.ledgers.ai import CALLS
from radar.domain.ai.budget import Use
from radar.domain.ai.meter import cost
from radar.adapters.storage.blobs import StorageBlobStore
from radar.domain.model.history.projection import plain
from radar.domain.review.requests import Reader, Report
from radar.tests.store import stores

FX = stores.fixture()
DATASHEETS = Path(__file__).parents[2] / "fixtures" / "datasheets.json"
PROBLEMS = {"eval_queries": [
    {"id": f"evq_00000000p{n}", "version": 1, "query": query, "language": language, "targets": ["prd_0000000002"]}
    for n, (query, language) in enumerate((("a glossy finish; a long reach", "en"),
                                           ("une finition brillante ; une grande portée", "fr")), 1)]}

def test_each_ai_use_s_eval_runs_on_the_scripted_models_under_its_caps(tmp_path: Path) -> None:
    place = FX.loaded(("index", "rebuild"))
    queries, languages = len(FX.rows("eval_queries.jsonl")), {q["language"] for q in FX.rows("eval_queries.jsonl")}
    for use, cases in (("ask", queries * len(languages)), ("draft", queries)):
        assert FX.json(place, "eval", "run", use, "--floor", "1") == {
            "use": use, "cases": cases, "passed": cases, "rate": 1.0, "failures": []}
    assert FX.json(place, "eval", "run", "solve", "--cases", stores.file(tmp_path, "problems.json", PROBLEMS),
                   "--floor", "1") == {"use": "solve", "cases": 2, "passed": 2, "rate": 1.0, "failures": []}
    sheets = json.loads(DATASHEETS.read_text(encoding="utf-8"))
    assert FX.json(place, "eval", "run", "datasheet", "--cases", str(DATASHEETS), "--floor",
                   "1")["passed"] == len(sheets["cases"])
    case, claim = sheets["cases"][0], sheets["cases"][0]["expected"]["claims"][0]
    claim["value"]["quantity"]["value"] += 1
    run = stores.cli(FX, place, "eval", "run", "datasheet", "--cases", stores.file(tmp_path, "wrong.json", sheets),
                     "--floor", "1", "--json", check=False)
    assert (run.returncode == 1
            and json.loads(run.stdout)["failures"] == [{"case": case["id"], "why": f"missed {claim['spec_key']}"}])

def test_the_ai_caps_from_the_cli() -> None:
    place = FX.loaded()

    def ask() -> dict[str, Any]:
        return next(r for r in FX.json(place, "ai-caps", "get")["uses"] if r["use"] == Use.ASK.value)

    before = ask()
    assert [r["use"] for r in FX.json(place, "ai-caps", "get")["uses"]] == [u.value for u in Use]
    paused = FX.json(place, "ai-caps", "set", Use.ASK.value, "--day-calls", "0", "--reason", "Ask paused for a test")
    assert paused["status"] == "approved" and ask()["day_calls"] == 0
    refused = stores.cli(FX, place, "catalog", "ask", "glossy widget", check=False)
    assert refused.returncode == 1 and f"{Use.ASK.value}: 0 calls a day, made" in refused.stderr
    assert FX.json(place, "ai-caps", "history", Use.ASK.value)["versions"][0]["proposal"] == paused["id"]
    assert [e["action"] for e in FX.json(place, "proposal", "log")["entries"]
            if e["proposal"] == paused["id"]] == ["approve", "submit"]
    stores.cli(FX, place, "proposal", "retract", paused["id"], "--note", "Ask back on")
    assert ask() == before

    other = next(m for m in FX.model.registry.ai.models if m.id != before["model"])
    FX.json(place, "ai-caps", "set", Use.ASK.value, "--model", other.id, "--reason", "Ask on another model")
    assert (ask()["model"], ask()["day_calls"]) == (other.id, before["day_calls"])
    stores.cli(FX, place, "catalog", "ask", "glossy widget")
    [call] = [f for _, f in stores.fresh_at(place[0]).list(CALLS) if f["outcome"] == "answered"]
    spent = cost(FX.model.registry.ai, other, call["tokens_in"], call["tokens_out"])
    assert (call["model"], call["cad"]) == (other.id, round(spent, 8))
    assert call["tokens_in"] and ask()["cad_month"] == round(spent, 6)

def test_the_review_queue_from_the_cli(tmp_path: Path) -> None:
    place = FX.loaded()
    claim, changed = FX.revised_claim(40)
    edit = FX.json(place, "product", "edit",
                   stores.changes_file(tmp_path, "edit.json", stores.put(changed, "Revision B")), "--reason",
                 "Revision B", "--actor", "scout")
    assert (edit["status"], edit["subject"], edit["author"]) == ("suggested", claim["subject"], "scout")
    assert [p["id"] for p in FX.json(place, "proposal", "list", "--status", "suggested")["proposals"]] == [edit["id"]]
    [shown] = FX.json(place, "proposal", "show", edit["id"])["changes"]
    assert (json.loads(shown["after"])["value"] == changed["value"]
            and json.loads(shown["before"])["value"] == claim["value"])
    FX.json(place, "proposal", "approve", edit["id"], "--note", "Checked")
    history = FX.json(place, "record", "history", claim["id"])
    assert history["versions"][0]["proposal"] == edit["id"]
    assert FX.json(place, "proposal", "retract", edit["id"], "--note", "Withdrawn")["done"][0]["status"] == "retracted"
    org = {**FX.rows("organizations.jsonl")[0], "id": "org_00000000zz", "name": "Halden Optics",
           "slug": "halden-optics"}
    added = FX.json(place, "org", "add", stores.changes_file(tmp_path, "org.json", stores.put(org, "New maker")),
                    "--reason", "New maker", "--source", FX.rows("sources.jsonl")[0]["id"])
    assert FX.json(place, "proposal", "reject", added["id"], "--note",
                   "Not a maker yet")["done"][0]["status"] == "rejected"
    document = {k: v for k, v in FX.rows("documents.jsonl")[0].items()
                if k not in ("version", "sha256", "mime", "bytes")}
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% a fictional manual\n")
    media = FX.json(place, "media", "add", str(pdf),
                    stores.file(tmp_path, "doc.json", {**document, "id": "doc_00000000zz"}), "--reason", "Manual")
    FX.json(place, "proposal", "approve", media["id"], "--note", "Our own manual")
    gone = FX.json(place, "media", "retract", "doc_00000000zz", "--reason", "Taken down")
    sha = json.loads(FX.json(place, "proposal", "show", media["id"])["changes"][0]["after"])["sha256"]
    assert any(sha[2:] in o for o in stores.objects(place[1]))
    FX.json(place, "proposal", "approve", gone["id"], "--note", "Takedown")
    assert not any(sha[2:] in o for o in stores.objects(place[1]))
    actions = [(e["action"], e["proposal"]) for e in FX.json(place, "proposal", "log")["entries"]]
    assert actions[:2] == [("approve", gone["id"]), ("submit", gone["id"])] and ("retract", edit["id"]) in actions
    assert {e["actor"] for e in FX.json(place, "proposal", "log", "--actor", "scout")["entries"]} == {"scout"}
    assert FX.json(place, "proposal", "log") == plain(FX.queue(stores.fresh_at(place[0])).log())
    product = next(p for p in FX.rows("products.jsonl") if p.get("parent"))
    name, role = (next(r for r in FX.rows(f) if r.get(k) == product["id"])
                  for f, k in (("names.jsonl", "subject"), ("product_org_roles.jsonl", "product")))
    new = {**product, "id": f"{product['id'][:-1]}z", "slug": f"{product['slug']}-bare"}
    bare = [stores.put(new, "New model"),
            stores.put({**name, "id": f"{name['id'][:-1]}z", "subject": new["id"], "value": "Widget Bare"},
                       "New model"),
            stores.put({**role, "id": f"{role['id'][:-1]}z", "product": new["id"]}, "New model")]
    added = FX.json(place, "product", "add", stores.changes_file(tmp_path, "bare.json", *bare), "--reason", "New model",
                    "--source", role["source_refs"][0])
    FX.json(place, "proposal", "approve", added["id"], "--note", "Listed by the maker")
    quality = FX.json(place, "quality", "report", "--file")
    assert new["id"] in {r["id"] for r in quality["records"] if r["weak"]} and len(quality["filed"]) == quality["weak"]
    assert {p["files_on"]
            for p in FX.json(place, "proposal", "list", "--author", "radar quality report")["proposals"]} == {"quality"}
    assert stores.cli(FX, place, "proposal", "submit",
                      stores.file(tmp_path, "draft.json",
                                  {"files_on": "report", "reason": "A report", "subject": claim["subject"]}),
                      check=False).returncode == 1, "a report is a reader's"
    review = FX.review(stores.fresh_at(place[0]), StorageBlobStore(f"http://{stores.STORAGE}", place[1]))
    report = review.submit(Report(claim["subject"], "The datasheet says otherwise"), Reader("test")).proposal
    [fixed] = FX.json(place, "proposal", "edit", report.id,
                      stores.changes_file(tmp_path, "fix.json", stores.put(changed, "Fixed")), "--note",
                      "Sourced")["done"]
    assert [e["note"] for e in fixed["edits"]] == ["Sourced"]

def test_product_edit_thumbnail_from_cli(tmp_path: Path) -> None:
    place = FX.loaded()
    prod = FX.rows("products.jsonl")[0]
    doc = {k: v for k, v in FX.rows("documents.jsonl")[0].items() if k not in ("version", "sha256", "mime", "bytes")}
    png = tmp_path / "thumb.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n fictional image\n")
    media = FX.json(place, "media", "add", str(png), stores.file(tmp_path, "thumb_doc.json", {
        **doc, "id": "doc_00000000th", "kind": "image", "rights": "own", "subjects": [prod["id"]],
    }), "--reason", "Product photo")
    FX.json(place, "proposal", "approve", media["id"], "--note", "Photo approved")

    unknown = stores.cli(FX, place, "product", "edit", "prd_0000000099", "--thumbnail", "doc_00000000th", "--reason",
                         "Set thumbnail", check=False)
    assert (unknown.returncode == 1 and "no product 'prd_0000000099'" in unknown.stderr
            and "Traceback" not in unknown.stderr)
    assert stores.cli(FX, place, "product", "edit", prod["id"], "--thumbnail", "doc_00000000th", "--reason",
                      "Set thumbnail", check=False).returncode == 2
    role = next(r for r in FX.rows("product_org_roles.jsonl") if r["product"] == prod["id"])
    edit = FX.json(place, "product", "edit", prod["id"], "--thumbnail", "doc_00000000th", "--reason", "Set thumbnail",
                   "--source", role["source_refs"][0])
    assert edit["status"] == "suggested"
    FX.json(place, "proposal", "approve", edit["id"], "--note", "Thumbnail approved")

    updated = FX.json(place, "product", "get", prod["id"])
    assert updated["product"]["thumbnail_url"] is not None

def test_product_documents_manual_and_release_notes_from_cli(tmp_path: Path) -> None:
    place = FX.loaded()
    prod = next(p for p in FX.rows("products.jsonl") if p["id"] == "prd_0000000002")
    ver = next(v for v in FX.rows("product_versions.jsonl") if v["product"] == prod["id"])
    doc_tmpl = {k: v for k, v in FX.rows("documents.jsonl")[0].items()
                if k not in ("version", "sha256", "mime", "bytes")}
    notes_file = tmp_path / "notes.txt"
    notes_file.write_bytes(b"Release notes v1.0\n")
    notes = FX.json(place, "media", "add", str(notes_file), stores.file(tmp_path, "notes.json", {
        **doc_tmpl, "id": "doc_00000000rn", "kind": "release_notes", "rights": "open_licence", "subjects": [ver["id"]],
    }), "--reason", "Version notes")
    FX.json(place, "proposal", "approve", notes["id"], "--note", "Notes approved")
    updated = FX.json(place, "product", "get", prod["id"])
    assert any(m["kind"]["id"] == "release_notes" and m.get("version") == ver["label"]
               for m in updated["product"]["media"])

def test_dedupe_keeps_the_earliest_then_the_lowest_id_and_its_proposals_approve_in_any_order() -> None:
    datasheet, website = (next(s for s in FX.rows("sources.jsonl") if s["type"] == t) for t in ("datasheet", "website"))
    claim = FX.rows("claims.jsonl")[0]
    tie = {**datasheet, "id": "src_000000000z"}
    earlier = {**website, "id": "src_000000000y", "retrieved_at": "2026-10-01T00:00:00Z"}
    records = [{**r, "source_refs": [tie["id"]]} if r["id"] == claim["id"] else r for r in FX.records]
    place = FX.holding([*records, tie, earlier])
    citing = sorted(r["id"] for r in FX.rows("claims.jsonl") if website["id"] in r["source_refs"])
    groups = [{"url": website["url"], "kept": earlier["id"], "extras": [website["id"]], "repoint": citing},
              {"url": datasheet["url"], "kept": datasheet["id"], "extras": [tie["id"]], "repoint": [claim["id"]]}]
    assert FX.json(place, "source", "dedupe")["groups"] == groups
    filed = FX.json(place, "source", "dedupe", "--file")
    assert len(filed["filed"]) == 2 and filed["refusals"] == []
    for proposal in reversed(filed["filed"]):
        stores.cli(FX, place, "proposal", "approve", proposal, "--note", "One URL, one Source")
    assert FX.json(place, "source", "dedupe")["groups"] == []
    validated = FX.json(place, "store", "validate")
    assert validated["ok"] and [w for w in validated["warnings"] if w["rule"] == "unique"] == []
