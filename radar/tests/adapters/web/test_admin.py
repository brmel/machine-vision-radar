from __future__ import annotations

import base64
import json
from typing import Any

from radar.adapters.firestore.layout import catalog_of, read_records
from radar.adapters.firestore.repository import StoreCatalogRepository, StoreRecords
from radar.adapters.web.admin.agents import AgentsAdmin
from radar.adapters.web.admin.endpoint import AdminEndpoint
from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens, TOKENS
from radar.domain.ports.web.endpoint import Request
from radar.domain.ports.review.identity import Admin
from radar.domain.ports.store.docs import Docs
from radar.domain.read_model.history import Histories
from radar.domain.read_model.products.values import Terms
from radar.domain.review.requests import Founder
from radar.tests.store import stores

FX = stores.fixture()

class Tokens:
    def admin(self, id_token: str) -> Admin | None:
        return Admin("uid-founder", "founder@example.com") if id_token == "founder" else None

def _admin() -> tuple[AdminEndpoint, list[bool], Docs]:
    docs, files = FX.seeded()
    reindexed: list[bool] = []
    histories = Histories(FX.versions(docs), StoreCatalogRepository(docs, FX.model),
                          lambda ids: catalog_of(FX.model, read_records(docs, FX.model.schema, ids).values()),
                          Terms(FX.model.registry).source_view)
    endpoint = AdminEndpoint(FX.review(docs, files), Tokens(), StoreRecords(docs, FX.model, files),
                             histories, FX.model,
                             lambda job: f"{job}-test", lambda actor, cid: reindexed.append(True) or True,
                             {"agents": AgentsAdmin(FirestoreAgentTokens(docs), lambda: "2026-10-20T09:00:00Z").route})
    return endpoint, reindexed, docs

def _call(endpoint: AdminEndpoint, method: str, path: str, body: Any = None, token: str = "founder",
          **query: str) -> Any:
    response = endpoint.respond(Request(method, f"/api/admin/{path}",
                                        json.dumps(body).encode() if body is not None else b"",
                                        {"authorization": f"Bearer {token}"} if token else {}, "127.0.0.1", query))
    return response.status, response.body

def test_the_admin_api_answers_the_founder_only_and_files_everything_as_proposals() -> None:
    endpoint, reindexed, _ = _admin()
    assert (_call(endpoint, "GET", "proposals", token="")[0] == 401
            and _call(endpoint, "GET", "proposals", token="reader")[0] == 403)
    status, model = _call(endpoint, "GET", "model")
    assert status == 200 and {e["id"] for e in model["entities"]} >= {"Product", "Organization", "Document"}
    assert {k["files_on"] for k in model["kinds"]} == set(FX.model.registry.proposal_kinds())
    claim = FX.rows("claims.jsonl")[0]
    changed = {k: v for k, v in claim.items() if k != "version"} | {
        "value": {"range": {**claim["value"]["range"], "max": 999.0}}}
    draft = {"files_on": "update", "reason": "Revision B", "subject": claim["subject"], "changeset": {"changes": [
        {"op": "put", "entity": changed, "reason": "Revision B", "actor_kind": "agent", "actor": "someone else",
         "source_refs": claim["source_refs"]}]}}
    status, filed = _call(endpoint, "POST", "proposals", draft)
    assert (status == 201
            and (filed["status"], filed["author"],
                 filed["actor_kind"]) == ("suggested", "founder@example.com", "human"))
    assert json.loads(filed["changes"][0]["after"])["value"]["range"]["max"] == 999.0 and not reindexed
    assert [p["id"] for p in _call(endpoint, "GET", "proposals", status="suggested")[1]["proposals"]] == [filed["id"]]
    assert _call(endpoint, "POST", "decisions",
                 {"decision": "approve", "proposals": [filed["id"]], "note": " "})[0] == 400
    status, approved = _call(endpoint, "POST", "decisions",
                             {"decision": "approve", "proposals": [filed["id"]], "note": "Checked"})
    assert status == 200 and approved["done"][0]["status"] == "approved" and reindexed == [True]
    history = _call(endpoint, "GET", f"records/{claim['id']}/history")[1]
    assert (history["versions"][0]["proposal"] == filed["id"]
            and history["versions"][0]["correlation_id"] == "admin-test")
    assert [c["path"]
            for c in _call(endpoint, "GET", f"records/{claim['id']}/diff",
                           **{"from": "1", "to": "2"})[1]["changes"]] == ["value.range.max"]
    status, rollback = _call(endpoint, "POST", "proposals",
                             {"files_on": "rollback", "subject": claim["id"], "to": 1,
                              "reason": "Revision B withdrawn"})
    assert status == 201 and rollback["status"] == "suggested"
    assert _call(endpoint, "POST", "decisions",
                 {"decision": "retract", "proposals": [filed["id"]],
                  "note": "Withdrawn"})[1]["done"][0]["status"] == "retracted"
    assert [e["action"] for e in _call(endpoint, "GET", "log")[1]["entries"]] == [
        "retract", "submit", "approve", "submit"]
    bad = {**draft,
           "changeset": {"changes": [{**draft["changeset"]["changes"][0],
                                      "entity": {**changed, "source_refs": ["src_zzzzzzzzzz"]}}]}}
    status, refused = _call(endpoint, "POST", "proposals", bad)
    assert status == 422 and refused["findings"]
    withdrawal = _call(endpoint, "POST", "proposals",
                       {"files_on": "retract", "subject": claim["id"], "reason": "Not on the datasheet"})[1]
    _call(endpoint, "POST", "decisions", {"decision": "approve", "proposals": [withdrawal["id"]], "note": "Checked"})
    history = _call(endpoint, "GET", f"records/{claim['id']}/history")[1]
    assert (_call(endpoint, "GET", f"records/{claim['id']}")[0] == 404
            and [v["version"] for v in history["versions"]] == [4, 3, 2, 1])
    assert history["versions"][0]["reason"] == "Not on the datasheet"

def test_the_admin_reads_records_and_takes_files() -> None:
    endpoint, _, _ = _admin()
    product = FX.rows("products.jsonl")[0]
    rows = _call(endpoint, "GET", "records", kind="Product", q=product["id"])[1]["records"]
    assert product["id"] in {r["id"] for r in rows}
    found = _call(endpoint, "GET", f"records/{product['id']}")[1]
    related = [json.loads(r) for r in found["related"]]
    assert json.loads(found["record"])["id"] == product["id"]
    assert {r["id"] for r in related} >= {c["id"] for c in FX.rows("claims.jsonl") if c["subject"] == product["id"]}
    assert {r["id"] for r in related} >= {s for c in FX.rows("claims.jsonl") if c["subject"] == product["id"]
                                          for s in c["source_refs"]}
    assert (_call(endpoint, "GET", "records", kind="Claim")[0] == 400
            and _call(endpoint, "GET", "records/prd_zzzzzzzzzz")[0] == 404)
    status, stored = _call(endpoint, "POST", "media",
                           {"mime": "application/pdf", "content": base64.b64encode(b"%PDF-1.4 fictional").decode()})
    assert status == 201 and stored["bytes"] == 18 and len(stored["sha256"]) == 64
    assert _call(endpoint, "POST", "media", {"mime": "application/pdf", "content": "not base64!"})[0] == 400
    assert _call(endpoint, "GET", "no-such-route")[0] == 404

def test_the_founder_issues_lists_and_revokes_agent_tokens() -> None:
    endpoint, _, docs = _admin()
    assert _call(endpoint, "GET", "agents") == (200,
                                                {"tokens": [],
                                                 "limits": {"requests_per_minute": 60, "proposals_per_day": 50},
                                                 "total": 0})
    asked = {"name": "Muse", "scope": "propose", "expires": "2026-12-31", "proposals_per_day": 5}
    status, issued = _call(endpoint, "POST", "agents", asked)
    assert (status == 201 and issued["token"].startswith("mvr_")
            and issued["agent"]["limits"] == {"requests_per_minute": 60, "proposals_per_day": 5})
    status, listed = _call(endpoint, "GET", "agents")
    assert (listed["tokens"] == [issued["agent"]] and issued["agent"]["status"] == "active"
            and issued["token"] not in json.dumps(listed))
    stored = json.dumps(list(docs.list(TOKENS)))
    assert issued["token"] not in stored and issued["agent"]["id"] in stored
    for bad, why in (({**asked, "scope": "admin"}, "scope is one of read, propose"),
                     ({**asked, "expires": "2026-10-20"}, "expires after today"),
                     ({**asked, "proposals_per_day": True}, "proposals_per_day is a whole number"),
                     ({**asked, "requests_per_minute": 0}, "a whole number from 1"),
                     ({**asked, "name": ""}, "name is required")):
        status, refused = _call(endpoint, "POST", "agents", bad)
        assert status == 400 and why in refused["error"]
    on_expiry = AgentsAdmin(FirestoreAgentTokens(docs), lambda: "2026-12-31T00:00:00Z").route
    listed = on_expiry("GET", (), {}, {}, Founder("founder", "expiry"))
    assert listed is not None and [t["status"] for t in listed.body["tokens"]] == ["expired"]
    status, revoked = _call(endpoint, "POST", f"agents/{issued['agent']['id']}/revoke")
    assert status == 200 and (revoked["status"], revoked["revoked_at"]) == ("revoked", "2026-10-20T09:00:00Z")
    assert FirestoreAgentTokens(docs).revoke(revoked["id"], "2026-10-22T08:00:00Z").revoked_at == revoked["revoked_at"]
    assert _call(endpoint, "POST", "agents/agt_zzzzzzzzzz/revoke")[0] == 404
