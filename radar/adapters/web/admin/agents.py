from __future__ import annotations

from datetime import date
from typing import Callable, Mapping

from radar.adapters.web.admin.endpoint import Body, cursor, figure, text
from radar.domain.model.entities import IssuedToken
from radar.domain.model.history.projection import plain
from radar.domain.ports.review.agent_tokens import AgentTokens
from radar.domain.ports.web.endpoint import Response
from radar.domain.review.agents.tokens import Limits, Scope, issue, token_view, tokens_view
from radar.domain.review.requests import Founder

class AgentsAdmin:
    def __init__(self, tokens: AgentTokens, now: Callable[[], str]) -> None:
        self._tokens, self._now = tokens, now

    def route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
              by: Founder) -> Response | None:
        now = self._now()
        today = date.fromisoformat(now[:10])
        match (method, *parts):
            case ("GET",):
                tokens, after, total = self._tokens.page(cursor(query))
                return Response(200, plain(tokens_view(tokens, today, after, total)))
            case ("POST",):
                given = {key: figure(body, key, int) for key in ("requests_per_minute", "proposals_per_day")}
                limits = Limits(**{key: n for key, n in given.items() if n is not None})
                if (scope := text(body, "scope")) not in {s.value for s in Scope}:
                    raise ValueError(f"scope is one of {', '.join(s.value for s in Scope)}")
                expires = date.fromisoformat(text(body, "expires"))
                token, secret = issue(text(body, "name"), Scope(scope), expires, limits, now)
                self._tokens.issue(token)
                return Response(201, plain(IssuedToken(agent=token_view(token, today), token=secret)))
            case ("POST", token_id, "revoke"):
                return Response(200, plain(token_view(self._tokens.revoke(token_id, now), today)))
        return None
