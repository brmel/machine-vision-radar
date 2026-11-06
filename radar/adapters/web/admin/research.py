from __future__ import annotations

from typing import Any, Callable, Mapping

from radar.domain.model.entities import RunScope, RunScopeKind
from radar.domain.model.history.projection import plain
from radar.domain.ports.web.endpoint import Response
from radar.domain.review.agents.research.run import Researcher
from radar.domain.review.agents.runs import run_view, runs_view
from radar.domain.review.requests import Founder

def _scope(body: Mapping[str, Any]) -> RunScope:
    kind, key = next(iter(body.items()), ("", ""))
    if len(body) != 1 or kind not in {k.value for k in RunScopeKind} or not isinstance(key, str) or not key.strip():
        raise ValueError("a run's scope is one of product, maker or category, with its id or slug")
    return RunScope(kind=RunScopeKind(kind), key=key.strip())

class ResearchAdmin:
    def __init__(self, research: Callable[[], Researcher], correlate: Callable[[str], str]) -> None:
        self._research, self._correlate = research, correlate

    def route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Mapping[str, Any],
              by: Founder) -> Response | None:
        match (method, *parts):
            case ("GET",):
                return Response(200, plain(runs_view(self._research().runs(query.get("cursor") or None))))
            case ("POST",):
                research = self._research()
                run = research.start(_scope(body), Founder(by.name, self._correlate("research")))
                return Response(201, plain(run_view(research.status(run))))
            case ("GET", run_id):
                return Response(200, plain(run_view(self._research().status(run_id))))
            case ("POST", run_id, "cancel"):
                return Response(200, plain(run_view(self._research().cancel(run_id))))
        return None
