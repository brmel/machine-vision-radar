from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import pytest

from radar.adapters.console import log
from radar.adapters.firestore import store
from radar.adapters.firestore.layout import catalog_of
from radar.adapters.firestore.repository import StoreCatalogRepository
from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens
from radar.adapters.web.mcp import PROTOCOLS, SCHEMAS, McpServer, Tool, read_tools
from radar.adapters.wiring.stores import Stores
from radar.domain.ports.web.endpoint import Request
from radar.domain.review.agents.tokens import Limits, Scope, issue
from radar.domain.search.sources import KINDS
from radar.tests.adapters.web.mcp_agent import McpAgent
from radar.tests.store import stores

FX = stores.fixture()
NOW = "2026-10-20T09:00:00Z"
INDEX = FX.index

@dataclass(frozen=True)
class Place:
    tools: dict[str, Tool]
    tokens: FirestoreAgentTokens
    secret: str

    def agent(self, secret: str | None = None, clock: Callable[[], float] = time.monotonic) -> McpAgent:
        return McpAgent(McpServer(self.tools, self.tokens, lambda: NOW, Stores().correlate, clock),
                        self.secret if secret is None else secret)

@pytest.fixture(scope="module")
def place() -> Place:
    docs, _ = FX.seeded()
    tokens = FirestoreAgentTokens(docs)
    token, secret = issue("scout", Scope.READ, date(2027, 1, 1), Limits(), NOW)
    tokens.issue(token)
    sources = catalog_of(FX.model, store.scan(docs, FX.model.schema, KINDS))
    return Place(read_tools(lambda: FX.search_engine, StoreCatalogRepository(docs, FX.model), lambda: sources,
                            FX.model.registry), tokens, secret)

def test_the_protocol_subset(place: Place) -> None:
    agent = place.agent()
    hello = {"protocolVersion": PROTOCOLS[-1], "capabilities": {}, "clientInfo": {"name": "a test", "version": "1"}}
    init = agent.send("initialize", hello).body["result"]
    assert (init["protocolVersion"], init["capabilities"], init["serverInfo"]["name"]) == (
        PROTOCOLS[-1], {"tools": {}}, "mvradar")
    assert agent.send("initialize",
                      {**hello, "protocolVersion": "2024-11-05"}).body["result"]["protocolVersion"] == PROTOCOLS[0]
    initialized = agent.send("notifications/initialized", rid=None)
    assert (initialized.status, initialized.body) == (202, None)
    assert agent.send("ping", rid=7).body == {"jsonrpc": "2.0", "id": 7, "result": {}}
    listed = agent.send("tools/list").body["result"]["tools"]
    assert [t["name"] for t in listed] == ["search_products", "get_product", "search_sources"], (
        "a read token is listed the read tools")
    for tool in SCHEMAS.values():
        assert tool["description"] and tool["inputSchema"]["type"] == tool["outputSchema"]["type"] == "object"
    assert agent.send("resources/list").body["error"]["code"] == -32601
    assert agent.send("tools/call", {"name": "approve_proposal", "arguments": {}}).body["error"]["code"] == -32602
    header = {"authorization": f"Bearer {place.secret}"}
    for body, status, code in ((b"{", 400, -32700), (b"[" * 1_000_000, 400, -32700),
                               (b'[{"jsonrpc": "2.0", "id": 1, "method": "ping"}]', 400, -32600)):
        res = agent.server.respond(Request("POST", "/api/mcp", body, header, "127.0.0.1"))
        assert (res.status, res.body["error"]["code"]) == (status, code)
    assert agent.server.respond(Request("GET", "/api/mcp", b"", header, "127.0.0.1")).status == 405

def test_search_products(place: Place) -> None:
    family = next(v for v in FX.views if v["models"])
    assert place.agent().answer("search_products", {"query": family["name"]})["hits"][0]["id"] == family["id"]
    category = next(c for c in INDEX["categories"] if c["products"] > 2)
    assert len(place.agent().answer("search_products",
                                    {"query": category["label"]["en"], "limit": 2,
                                     "category": category["id"]})["hits"]) == 2
    assert place.agent().refused("search_products", {"limit": 2}) == "'query' is a required property"
    assert place.agent().refused("search_products",
                                 {"query": "widget", "limit": 0}) == "limit: 0 is less than the minimum of 1"

def test_get_product(place: Place) -> None:
    view = next(v for v in FX.views if v["sources"])
    sheet = place.agent().answer("get_product", {"id": view["slug"]})
    assert sheet == {"product": view,
                     "spec_definitions": {c["key"]: INDEX["spec_definitions"][c["key"]]
                                          for c in (*view["core"], *view["detail"])}}
    assert place.agent().refused("get_product", {"id": "no-such-product"}) == "no product 'no-such-product'"
    assert place.agent().refused("get_product", {"id": 7}) == "id: 7 is not of type 'string'"

def test_search_sources(place: Place) -> None:
    sources, documents, orgs = FX.rows("sources.jsonl"), FX.rows("documents.jsonl"), FX.rows("organizations.jsonl")
    newest = sorted(sources, key=lambda s: (s["retrieved_at"], s["id"]), reverse=True)
    newest_files = sorted(documents, key=lambda d: (d["fetched_at"], d["id"]), reverse=True)

    def found(**arguments: Any) -> tuple[list[str], list[str]]:
        answer = place.agent().answer("search_sources", arguments)
        return [s["id"] for s in answer["sources"]], [d["id"] for d in answer["documents"]]

    def ids(rows: list[dict[str, Any]], keep: Callable[[dict[str, Any]], bool]) -> list[str]:
        return [r["id"] for r in rows if keep(r)]

    datasheet, kind, day = sources[0], newest[0]["type"], newest[0]["retrieved_at"][:10]
    assert found(url=datasheet["url"].upper()) == ([datasheet["id"]],
                                                   ids(newest_files, lambda d: d["source_url"] == datasheet["url"]))
    sited = [o for o in orgs if o.get("website")]
    vendor = next(o for o in sited if datasheet["url"].startswith(o["website"]))
    other = next(o for o in sited if not datasheet["url"].startswith(o["website"]))
    assert found(vendor=vendor["slug"]) == (ids(newest, bool), ids(newest_files, bool))
    assert found(vendor=other["id"]) == ([], [])
    assert found(type=kind) == (ids(newest, lambda s: s["type"] == kind),
                                ids(newest_files, lambda d: d["kind"] == kind))
    assert found(since=day) == (ids(newest, lambda s: s["retrieved_at"][:10] >= day),
                                ids(newest_files, lambda d: d["fetched_at"][:10] >= day))
    assert found(until=day, limit=1) == ([newest[0]["id"]], [newest_files[0]["id"]])
    assert place.agent().refused("search_sources", {"vendor": "no-such-vendor"}) == "no organization 'no-such-vendor'"
    unsited = next(o for o in orgs if not o.get("website"))
    assert place.agent().refused("search_sources", {"vendor": unsited["slug"]}) == (
        f"{unsited['name']} has no website to find its sources on")
    assert place.agent().refused("search_sources",
                                 {"type": "no_such_type"}) == ("type 'no_such_type' is neither a source type nor a "
                                                               "document kind")
    assert place.agent().refused("search_sources", {"since": "2026-13-01"}) == "since: '2026-13-01' is not a 'date'"
    assert place.agent().refused("search_sources",
                                 {"colour": "red"}) == "Additional properties are not allowed ('colour' was unexpected)"

def test_a_missing_token_is_refused_with_the_reason(place: Place) -> None:
    missing = place.agent("").send("tools/list")
    assert (missing.status, missing.body["error"]) == (401,
                                                       {"code": -32001,
                                                        "message": "the agent token is refused: no such token"})
    unanswered = place.agent("").send("notifications/initialized", rid=None)
    assert (unanswered.status, unanswered.body) == (401, None)

def test_each_call_logs_its_agent_tool_correlation_id_outcome_and_latency_never_the_token(
        place: Place, capsys: pytest.CaptureFixture[str]) -> None:
    ticks = iter([10.0, 10.25, 20.0, 20.5])
    agent = place.agent(clock=lambda: next(ticks))
    log.configure(json_mode=True)
    for key in (INDEX["products"][0]["slug"], "no-such-product"):
        agent.send("tools/call", {"name": "get_product", "arguments": {"id": key}})
    place.agent(f"mvr_{'0' * 32}").send("tools/list")
    err = capsys.readouterr().err
    log.configure()
    lines = [json.loads(line) for line in err.splitlines()]
    calls = [line for line in lines if line["event"] == "mcp: tools/call"]
    assert [(c["agent"], c["tool"], c["outcome"], c["latency_ms"]) for c in calls] == [
        ("scout", "get_product", "ok", 250.0), ("scout", "get_product", "error", 500.0)]
    assert calls[1]["reason"] == "no product 'no-such-product'"
    assert len({c["correlation_id"] for c in calls}) == 2 and all(c["correlation_id"].startswith("mcp-") for c in calls)
    assert [line["reason"] for line in lines if line["event"] == "mcp: refused"] == ["no such token"]
    assert place.secret not in err and "mvr_" not in err
