from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens, USAGE
from radar.adapters.web.mcp import PROPOSING, McpServer, proposal_tools
from radar.adapters.wiring.stores import Stores
from radar.domain.model.history.ids import keyed
from radar.domain.ports.store.docs import Docs
from radar.domain.model.entities import FilesOn
from radar.domain.review.agents.tokens import Limits, Scope, issue
from radar.tests.adapters.web.mcp_agent import McpAgent
from radar.tests.store import stores

FX = stores.fixture()
SOURCE = FX.rows("sources.jsonl")[0]["id"]
HELD_PRODUCT = next(p for p in FX.rows("products.jsonl") if p["id"] == "prd_0000000003")
HELD_ROLE = next(r for r in FX.rows("product_org_roles.jsonl") if r["product"] == HELD_PRODUCT["id"])

@dataclass
class Place:
    docs: Docs
    server: McpServer
    tokens: FirestoreAgentTokens
    now: list[str]

    def token(self, name: str, scope: Scope = Scope.PROPOSE, limits: Limits = Limits()) -> tuple[str, McpAgent]:
        token, secret = issue(name, scope, date(2027, 1, 1), limits, self.now[0])
        self.tokens.issue(token)
        return token.id, McpAgent(self.server, secret)

@pytest.fixture
def place() -> Place:
    docs, files = FX.seeded()
    now = ["2026-10-20T09:00:00Z"]
    tokens = FirestoreAgentTokens(docs)
    return Place(docs, McpServer(proposal_tools(FX.review(docs, files)), tokens, lambda: now[0], Stores().correlate),
                 tokens, now)

def _draft(files_on: str, subject: str, *records: dict[str, Any], refs: list[str]) -> dict[str, Any]:
    changes = [{"op": "put", "entity": r, "reason": "From the maker's datasheet",
                **({"source_refs": refs} if refs else {})} for r in records]
    return {"files_on": files_on, "reason": "Seen on the maker's site", "subject": subject,
            "changeset": json.dumps({"changes": changes})}

def _new(key: str, record: dict[str, Any], org: str = HELD_ROLE["org"]) -> dict[str, Any]:
    product = {**{k: v for k, v in HELD_PRODUCT.items() if k != "version"}, "id": keyed("prd", key),
               "slug": f"agent__{key}"}
    made = {**{k: v for k, v in HELD_ROLE.items() if k != "version"}, "id": keyed("por", key), "product": product["id"],
            "org": org}
    alias = {"id": keyed("aln", key), "subject": product["id"], "value": f"Alias {key}"}
    return _draft("create", product["id"], product, made, {**record, "subject": product["id"]}, alias, refs=[SOURCE])

def _revision(add: float) -> dict[str, Any]:
    claim, changed = FX.revised_claim(add)
    return _draft("update", claim["subject"], {k: v for k, v in changed.items() if k != "version"},
                  refs=claim["source_refs"])

def test_an_agent_files_through_review_and_sees_its_own_only(place: Place) -> None:
    grok_id, grok = place.token("Grok Bot")
    _, muse = place.token("Muse")
    claim = FX.rows("claims.jsonl")[0]
    filed = grok.answer("submit_proposal", _revision(5.0))
    assert (filed["status"], filed["files_on"], filed["actor_kind"], filed["author"], filed["token_id"]) == (
        "suggested", FilesOn.UPDATE, "agent", "Grok Bot", grok_id)
    assert filed["sources"] == claim["source_refs"] and [c["entity"] for c in filed["changes"]] == [claim["id"]]
    assert json.loads(filed["changes"][0]["after"])["value"]["range"]["max"] == claim["value"]["range"]["max"] + 5.0
    entry = FX.queue(place.docs).log().entries[0]
    assert ((entry.proposal, entry.actor, entry.actor_kind) == (filed["id"], "Grok Bot", "agent")
            and entry.correlation_id.startswith("mcp-"))
    claim, changed = FX.revised_claim(5.0)
    again = _draft("update", claim["subject"],
                   {k: v for k, v in changed.items() if k != "version"} | {"id": keyed("clm", "again")},
                   refs=claim["source_refs"])
    assert grok.refused("submit_proposal", again) == f"your open proposals put all this already: {filed['id']}", (
        "the same values, under any id")

    assert [p["id"] for p in grok.answer("list_my_proposals", {})["proposals"]] == [filed["id"]]
    assert grok.answer("list_my_proposals", {"status": "approved"})["proposals"] == []
    assert grok.answer("get_proposal_status", {"id": filed["id"]})["changes"] == filed["changes"]
    assert muse.answer("list_my_proposals", {})["proposals"] == []
    assert muse.refused("get_proposal_status", {"id": filed["id"]}) == f"{filed['id']} is not a proposal of Muse's"

def test_sources_are_required_and_bad_input_is_refused_naming_the_field(place: Place) -> None:
    _, agent = place.token("Grok Bot")
    alias = {"id": keyed("aln", "agent"), "subject": "prd_0000000001", "value": "W1"}
    assert agent.refused("submit_proposal", _draft("update", "prd_0000000001", alias, refs=[])) == \
        "changeset: changes[0]: source_refs names at least one source the change rests on"
    assert agent.refused("submit_proposal",
                         {**_draft("update", "prd_0000000001", alias, refs=[SOURCE]), "changeset": "{"}).startswith(
"changeset is not JSON:")
    assert agent.refused("submit_proposal",
                         {"files_on": "update", "changeset": "{}"}) == "'reason' is a required property"
    assert agent.refused("submit_proposal",
                         {**_draft("update", "prd_0000000001", alias, refs=[SOURCE]), "files_on": "approve"}) == \
        ("files_on: 'approve' is not one of ['create', 'update', 'merge', 'retract', 'report', 'quality', 'feed', "
         "'rollback']")
    assert agent.refused("submit_proposal",
                         _draft("update", "prd_0000000001", {**alias, "subject": "prd_nowhere000"}, refs=[SOURCE]))
    assert agent.refused("get_proposal_status", {}) == "'id' is a required property"

def test_a_new_product_the_catalog_holds_merges_into_it_by_name_part_number_or_id(place: Place) -> None:
    _, agent = place.token("Grok Bot")
    held = HELD_PRODUCT
    name = next(n["value"] for n in FX.rows("names.jsonl") if n["subject"] == held["id"])
    number = next(i["value"] for i in FX.rows("identifiers.jsonl") if i["subject"] == held["id"])
    by_name = agent.answer("submit_proposal",
                           _new("named",
                                {"id": keyed("nam", "named"), "value": f"  {name.upper()} ", "is_primary": True}))
    by_number = agent.answer("submit_proposal",
                             _new("numbered",
                                  {"id": keyed("idn", "numbered"), "scheme": "part_number", "value": number.lower()}))
    for merged, key in ((by_name, "named"), (by_number, "numbered")):
        assert (merged["subject"], merged["files_on"]) == (held["id"], FilesOn.UPDATE)
        assert merged["reason"] == f"Seen on the maker's site (merged into {held['id']}, which the catalog holds)"
        assert [(c["entity"], json.loads(c["after"])["subject"]) for c in merged["changes"]] == [
            (keyed("aln", key), held["id"])]
    by_id = agent.answer("submit_proposal",
                         _draft("create", held["id"], {"id": keyed("aln", "id"), "subject": held["id"], "value": "WOS"},
                                refs=[SOURCE]))
    assert (by_id["subject"], by_id["files_on"], by_id["reason"]) == (
        held["id"], FilesOn.UPDATE, "Seen on the maker's site")
    primary = next(n for n in FX.rows("names.jsonl") if n["subject"] == held["id"])
    assert agent.refused("submit_proposal",
                         _draft("update", held["id"], {k: v for k, v in primary.items() if k != "version"},
                                refs=[SOURCE])) == \
        "the catalog holds all this proposes already"

@pytest.mark.parametrize(("org", "twin"), [("org_0000000002", False), (HELD_ROLE["org"], True)],
                         ids=["another maker", "two held products"])
def test_a_new_product_stays_new_unless_one_held_product_of_its_maker_answers(
        place: Place, org: str, twin: bool) -> None:
    _, agent = place.token("Grok Bot")
    name = next(n for n in FX.rows("names.jsonl") if n["subject"] == HELD_PRODUCT["id"])
    if twin:
        FX.apply(place.docs, None, "twin",
                 stores.put({**name, "id": keyed("nam", "twin"), "subject": "prd_0000000001", "is_primary": False},
                            "A second name", [SOURCE]))
    filed = agent.answer("submit_proposal",
                         _new("same-name",
                              {"id": keyed("nam", "same-name"), "value": name["value"], "is_primary": True}, org))
    assert (filed["subject"], filed["files_on"], filed["reason"]) == (
        keyed("prd", "same-name"), FilesOn.CREATE, "Seen on the maker's site")

def test_a_read_token_reads_and_cannot_propose(place: Place) -> None:
    _, reader = place.token("Scout", Scope.READ)
    _, proposer = place.token("Grok Bot")
    assert reader.send("tools/list").body["result"]["tools"] == []
    assert [t["name"] for t in proposer.send("tools/list").body["result"]["tools"]] == list(PROPOSING)
    refused = reader.send("tools/call", {"name": "list_my_proposals", "arguments": {}})
    assert (refused.status, refused.body["error"]["message"]) == (
        401, "the agent token is refused: its scope is read; this needs propose")

def test_requests_a_minute_are_limited_until_the_next_minute(place: Place) -> None:
    token, agent = place.token("Grok Bot", limits=Limits(requests_per_minute=2))
    place.now[0] = "2026-10-20T09:00:45Z"
    assert [agent.send("ping").status for _ in range(2)] == [200, 200]
    over = agent.send("ping", rid=3)
    assert (over.status, over.headers) == (429, {"retry-after": "15"})
    assert over.body == {"jsonrpc": "2.0", "id": 3,
                         "error": {"code": -32002,
                                   "message": "the agent token is over its limits: over its 2 requests a minute",
                                   "data": {"retry_after": 15}}}
    notified = agent.send("notifications/initialized", rid=None)
    assert (notified.status, notified.body, notified.headers) == (429, None, {"retry-after": "15"})
    assert place.docs.get(f"{USAGE}/{token}-2026-10-20") == {"requests": {"m0900": 4}}
    place.now[0] = "2026-10-20T09:01:00Z"
    assert agent.send("ping").status == 200

def test_proposals_a_day_are_limited_until_the_next_day(place: Place) -> None:
    token, agent = place.token("Grok Bot", limits=Limits(proposals_per_day=1))
    place.now[0] = "2026-10-20T23:59:30Z"
    agent.answer("submit_proposal", _revision(1.0))
    over = agent.send("tools/call", {"name": "submit_proposal", "arguments": _revision(2.0)})
    assert (over.status, over.headers["retry-after"], over.body["error"]["data"]) == (429, "30", {"retry_after": 30})
    assert over.body["error"]["message"] == "the agent token is over its limits: over its 1 proposals a day"
    assert len(agent.answer("list_my_proposals", {})["proposals"]) == 1, "only a proposal counts against the day's"
    assert place.docs.get(f"{USAGE}/{token}-2026-10-20")["proposals"] == 2
    place.now[0] = "2026-10-21T00:00:10Z"
    assert agent.answer("submit_proposal", _revision(2.0))["status"] == "suggested"
