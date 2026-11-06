from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping

from radar.adapters.console import log
from radar.adapters.web.admin.endpoint import Body, cursor, figure, text
from radar.domain.ai.answerer import Answerer, refusal
from radar.domain.ai.budget import Use, cap_draft
from radar.domain.ai.meter import Capped, Meter, caps_today
from radar.domain.model.registry import Registry
from radar.domain.model.history.ids import keyed
from radar.domain.ports.ai.prompts import PromptRegistry
from radar.domain.ports.ai.usage_log import Budget
from radar.domain.ports.search.ask_ledger import AskLedger
from radar.domain.ports.search.index_runs import Action
from radar.domain.ports.search.search_engine import SearchEngine, SearchRequest
from radar.domain.ports.web.endpoint import Response
from radar.domain.read_model.history import Histories
from radar.domain.review.requests import Enactment, Founder
from radar.domain.review.review import Review
from radar.domain.model.history.projection import plain
from radar.domain.review.views import proposal_view
from radar.domain.search.eval import Traffic
from radar.domain.search.hits import hits_json
from radar.domain.search.indexing import Indexer

HITS, WEEKS = 10, 8

class SearchAdmin:
    def __init__(self, indexer: Callable[[], Indexer], engine: Callable[[], SearchEngine],
                 meter: Callable[[], Meter[Answerer]], budget: Budget, prompts: PromptRegistry, ledger: AskLedger,
                 review: Review, histories: Histories, registry: Registry, today: Callable[[], str]) -> None:
        self._indexer, self._engine, self._meter, self._budget, self._prompts = indexer, engine, meter, budget, prompts
        self._ledger, self._review, self._histories, self._registry, self._today = (
            ledger, review, histories, registry, today)

    def _run(self, action: Action, by: Founder) -> Response:
        try:
            self._indexer().run(action, by.name, by.correlation_id)
        except (OSError, ValueError, RuntimeError) as exc:
            log.error(f"admin: the index {action} failed: {exc}")
            return Response(500, {"error": f"the index {action} failed: {exc}"})
        return Response(200, plain(self._indexer().status()))

    def _ask(self, body: Body) -> dict[str, Any]:
        question, locale = text(body, "question"), text(body, "locale")
        try:
            return plain(self._meter().call(self._today(), lambda answerer: answerer.ask(question, locale))[0].answer)
        except Capped as exc:
            log.warn(f"admin: the test question is refused at the cap, {exc}")
            return plain(refusal("limit"))

    def _set_cap(self, body: Body, by: Founder) -> dict[str, Any]:
        use, model = Use(text(body, "use")), text(body, "model") if "model" in body else None
        cap = self._budget.caps()[use].changed(figure(body, "month_cad", float), figure(body, "day_calls", int),
                                               figure(body, "client_calls", int), model)
        return plain(proposal_view(self._review.decide(Enactment(cap_draft(use, cap, text(body, "reason"), by.name)),
                                                       by).one()))

    def route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
              by: Founder) -> Response | None:
        return self._index_route(method, parts, query, body, by) or self._ai_route(method, parts, query, body, by)

    def _index_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                     by: Founder) -> Response | None:
        match (method, *parts):
            case ("GET", "status"):
                return Response(200, plain(self._indexer().status()))
            case ("POST", "update" | "rebuild" as action):
                return self._run(action, by)
            case ("GET", "settings"):
                return Response(200, plain(self._indexer().settings()))
            case ("GET", "query"):
                hits = self._engine().search(SearchRequest(text(query, "q"), HITS, query.get("semantic") == "true"))
                return Response(200, {"hits": hits_json(hits, self._registry)})
            case ("GET", "weekly"):
                return Response(200, plain(Traffic(self._ledger).weeks(date.fromisoformat(self._today()), WEEKS)))
        return None

    def _ai_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                  by: Founder) -> Response | None:
        match (method, *parts):
            case ("POST", "ask"):
                return Response(200, self._ask(body))
            case ("GET", "caps"):
                return Response(200, plain(caps_today(self._budget, self._registry.ai, self._prompts, self._today())))
            case ("POST", "caps"):
                return Response(201, self._set_cap(body, by))
            case ("GET", "caps", use, "history"):
                return Response(200, plain(self._histories.page(keyed("cap", Use(use).value), cursor(query))))
        return None
