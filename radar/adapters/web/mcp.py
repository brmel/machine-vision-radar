from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from typing import Any, Callable, Mapping

import jsonschema

from radar import paths
from radar.adapters.console import log
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.history.projection import plain
from radar.domain.model.model import Model
from radar.domain.model.registry import Registry
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.model.entities import ProposalStatus
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.ports.review.proposing import Proposing
from radar.domain.ports.review.agent_tokens import AgentTokens
from radar.domain.ports.search.search_engine import SearchEngine, SearchRequest
from radar.domain.ports.web.endpoint import Request, Response
from radar.domain.read_model.products.views import product_sheet
from radar.domain.review.agents.tokens import AgentToken, Refused, Scope, Throttled, admit, digest, throttle
from radar.domain.review.requests import Agent, Draft, draft_of
from radar.domain.review.views import page_view, shown_view
from radar.domain.search.hits import hits_json
from radar.domain.search.sources import SourceQuery

GENERATED = paths.GENERATED_MCP_TOOLS.read_bytes()
SCHEMAS = {t["name"]: t for t in json.loads(GENERATED)["tools"]}
CHECKS = {name: jsonschema.Draft202012Validator(t["inputSchema"],
                                                format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
          for name, t in SCHEMAS.items()}
PROTOCOLS = ("2025-11-25", "2025-06-18")
SERVER = {"name": "mvradar", "title": "Machine Vision Radar", "version": hashlib.sha256(GENERATED).hexdigest()[:12]}
PARSE, INVALID, NO_METHOD, BAD_PARAMS, REFUSED, LIMITED = -32700, -32600, -32601, -32602, -32001, -32002
PROPOSING = ("submit_proposal", "list_my_proposals", "get_proposal_status")

Tool = Callable[[Mapping[str, Any], Agent], Mapping[str, Any]]
Message = dict[str, Any]

def _reply(rid: Any, answer: Message) -> Message:
    return {"jsonrpc": "2.0", "id": rid, **answer}

def _error(code: int, message: str) -> Message:
    return {"error": {"code": code, "message": message}}

def read_tools(engine: Callable[[], SearchEngine], repository: CatalogRepository, sources: Callable[[], Catalog],
               registry: Registry) -> dict[str, Tool]:
    return {
        "search_products": lambda a, _: {
            "hits": hits_json(engine().search(SearchRequest(a["query"], a["limit"], a["semantic"], a.get("category"),
                                                            a.get("tag"))), registry)},
        "get_product": lambda a, _: plain(product_sheet(repository, a["id"])),
        "search_sources": lambda a, _: SourceQuery(**{**a,
                                                      **{k: date.fromisoformat(a[k]) for k in ("since", "until")
                                                         if k in a}}).found(sources(), registry),
    }

def _draft(arguments: Mapping[str, Any], model: Model) -> Draft:
    try:
        raw = json.loads(arguments["changeset"])
    except ValueError as exc:
        raise ValueError(f"changeset is not JSON: {exc}") from exc
    return draft_of({**arguments, "changeset": raw}, model)

def _mine(arguments: Mapping[str, Any]) -> Query:
    return Query(ProposalStatus(arguments["status"]) if "status" in arguments else None)

def proposal_tools(review: Proposing, model: Model) -> dict[str, Tool]:
    submit, mine, status = PROPOSING
    return {submit: lambda a, agent: plain(shown_view(review.submit(_draft(a, model), agent))),
            mine: lambda a, agent: plain(page_view(review.queue(_mine(a), agent, a.get("cursor")))),
            status: lambda a, agent: plain(shown_view(review.proposal(a["id"], agent)))}

def _scope(tool: str | None) -> Scope:
    return Scope.PROPOSE if tool in PROPOSING else Scope.READ

def _refused(message: Message, exc: Refused) -> Response:
    match exc:
        case Throttled(retry_after=seconds):
            status, headers = 429, {"retry-after": str(seconds)}
            error = {"code": LIMITED, "message": f"the agent token is over its limits: {exc}",
                     "data": {"retry_after": seconds}}
        case _:
            log.warn("mcp: refused", reason=str(exc))
            status, headers, error = 401, {}, _error(REFUSED, f"the agent token is refused: {exc}")["error"]
    return Response(status, _reply(message["id"], {"error": error}) if "id" in message else None, headers)

def _checked(name: str, arguments: Any) -> Mapping[str, Any]:
    error = jsonschema.exceptions.best_match(CHECKS[name].iter_errors(arguments))
    if error is not None:
        field = ".".join(map(str, error.absolute_path))
        raise ValueError(f"{field}: {error.message}" if field else error.message)
    return {**{k: p["default"] for k, p in SCHEMAS[name]["inputSchema"]["properties"].items() if "default" in p},
            **arguments}

class McpServer:
    def __init__(self, tools: Mapping[str, Tool], tokens: AgentTokens, now: Callable[[], str],
                 correlate: Callable[[str], str], clock: Callable[[], float] = time.monotonic) -> None:
        self._tools, self._tokens, self._now, self._correlate, self._clock = tools, tokens, now, correlate, clock

    def respond(self, request: Request) -> Response:
        if request.method != "POST":
            return Response(405, {"error": "POST one JSON-RPC message: this server opens no stream"})
        return self.handle(request.headers.get("authorization", "").removeprefix("Bearer ").strip(), request.body)

    def handle(self, secret: str, body: bytes) -> Response:
        correlation_id = self._correlate("mcp")
        try:
            message = json.loads(body)
        except (ValueError, RecursionError):
            return Response(400, _reply(None, _error(PARSE, "the message is not JSON")))
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str)):
            return Response(400,
                            _reply(message.get("id") if isinstance(message, dict) else None,
                                   _error(INVALID, "send one JSON-RPC 2.0 request or notification")))
        try:
            token = self._admitted(secret, message)
        except Refused as exc:
            return _refused(message, exc)
        if "id" not in message:
            return Response(202)
        return Response(200,
                        _reply(message["id"],
                               self._answer(message["method"], message.get("params"), Agent(token, correlation_id))))

    def _admitted(self, secret: str, message: Message) -> AgentToken:
        now, params = self._now(), message.get("params")
        tool = params.get("name") if message["method"] == "tools/call" and isinstance(params, dict) else None
        agent = admit(self._tokens.by_digest(digest(secret)), _scope(tool), date.fromisoformat(now[:10]))
        try:
            throttle(agent, self._tokens.count(agent.id, now[:16], tool == PROPOSING[0]), now)
        except Throttled as exc:
            log.warn("mcp: throttled", agent=agent.name, reason=str(exc), retry_after=exc.retry_after)
            raise
        return agent

    def _answer(self, method: str, params: Any, agent: Agent) -> Message:
        params = params if isinstance(params, dict) else {}
        match method:
            case "initialize":
                asked = params.get("protocolVersion")
                return {"result": {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                                   "capabilities": {"tools": {}}, "serverInfo": SERVER}}
            case "ping":
                return {"result": {}}
            case "tools/list":
                return {"result": {"tools": [SCHEMAS[name] for name in self._tools
                                             if agent.token.scope.covers(_scope(name))]}}
            case "tools/call":
                return self._call(params, agent)
        return _error(NO_METHOD, f"no method {method}")

    def _call(self, params: Mapping[str, Any], agent: Agent) -> Message:
        name = params.get("name")
        if not isinstance(name, str) or name not in self._tools:
            return _error(BAD_PARAMS, f"no tool {name}: tools/list names them")
        started = self._clock()
        try:
            answer = self._tools[name](_checked(name, params.get("arguments", {})), agent)
            result, outcome = {"content": [{"type": "text", "text": json.dumps(answer, ensure_ascii=False)}],
                               "structuredContent": answer}, {"outcome": "ok"}
        except (LookupError, ValueError, OSError, RuntimeError) as exc:
            result, outcome = ({"content": [{"type": "text", "text": str(exc)}], "isError": True},
                               {"outcome": "error", "reason": str(exc)})
        log.info("mcp: tools/call", agent=agent.name, tool=name, **outcome,
                 latency_ms=round((self._clock() - started) * 1000, 1))
        return {"result": result}
