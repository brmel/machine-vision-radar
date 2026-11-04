from __future__ import annotations

import base64
import binascii
from typing import Any, Callable, Mapping, TypeVar

from radar.adapters.console import log
from radar.adapters.web.api import payload
from radar.domain.validation.context import InvalidChangeset
from radar.domain.ports.web.endpoint import Request, Response
from radar.domain.ports.store.records import Records
from radar.domain.ai.meter import Capped
from radar.domain.model.history.projection import plain
from radar.domain.model.entities import ActorKind, AdminModel, FilesOn, ProposalStatus
from radar.domain.ports.review.identity import Identity
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.read_model.history import Histories
from radar.domain.review.agents.tokens import Refused
from radar.domain.review.proposal import findings
from radar.domain.review.requests import Founder, decision_of, draft_of
from radar.domain.review.review import Review
from radar.domain.review.views import bundle_view, outcome_view, page_view, shown_view

Body = Mapping[str, Any]

def text(body: Mapping[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value

def whole(value: Any, key: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} is a whole number") from exc

Figure = TypeVar("Figure", int, float)

def figure(body: Body, key: str, kind: type[Figure]) -> Figure | None:
    value = body.get(key)
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, kind))):
        raise ValueError(f"{key} is {'a whole number' if kind is int else 'a number'}")
    return None if value is None else kind(value)

def cursor(query: Mapping[str, str]) -> str | None:
    return query.get("cursor") or None

Kind = TypeVar("Kind", ProposalStatus, ActorKind, FilesOn)

def _enum(query: Mapping[str, str], key: str, kinds: type[Kind]) -> Kind | None:
    value = query.get(key) or None
    if value is None:
        return None
    if value not in kinds:
        raise ValueError(f"{key} is one of {', '.join(e.value for e in kinds)}")
    return kinds(value)

def _query(query: Mapping[str, str]) -> Query:
    return Query(_enum(query, "status", ProposalStatus), _enum(query, "files_on", FilesOn),
                 _enum(query, "actor_kind", ActorKind), query.get("author") or None, query.get("bundle") or None)

Route = Callable[[str, tuple[str, ...], Mapping[str, str], Body, Founder], Response | None]

class AdminEndpoint:
    def __init__(self, review: Review, identity: Identity, records: Records, histories: Histories,
                 model: AdminModel, correlate: Callable[[str], str], reindex: Callable[[str, str], bool],
                 sections: Mapping[str, Route]) -> None:
        self._review, self._identity, self._records, self._histories, self._model = (
            review, identity, records, histories, model)
        self._correlate, self._reindex, self._sections = correlate, reindex, sections

    def respond(self, request: Request) -> Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not token:
            return Response(401, {"error": "sign in as the admin"})
        admin = self._identity.admin(token)
        if admin is None:
            return Response(403, {"error": "this account is not the admin"})
        founder = Founder(admin.email or admin.uid, self._correlate("admin"))
        try:
            parts = tuple(request.path.removeprefix("/api/admin/").strip("/").split("/"))
            return self._route(request.method, parts, request.query, payload(request), founder)
        except InvalidChangeset as exc:
            return Response(422, {"error": "the change is refused", "findings": list(findings(exc))})
        except Refused as exc:
            return Response(403, {"error": str(exc)})
        except ValueError as exc:
            return Response(400, {"error": str(exc)})
        except LookupError as exc:
            return Response(404, {"error": str(exc)})
        except Capped as exc:
            return Response(429, {"error": f"refused at the cap ({exc})"})

    def _route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
               by: Founder) -> Response:
        routes = {"model": self._model_route, "proposals": self._proposal_route, "decisions": self._decision_route,
                  "bundles": self._bundle_route, "log": self._log_route, "records": self._record_route,
                  "media": self._media_route, **self._sections}
        found = routes[parts[0]](method, parts[1:], query, body, by) if parts[0] in routes else None
        return found or Response(404, {"error": f"no admin route {method} /{'/'.join(parts)}"})

    def _model_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                     by: Founder) -> Response | None:
        return Response(200, plain(self._model)) if (method, parts) == ("GET", ()) else None

    def _proposal_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                        by: Founder) -> Response | None:
        match (method, *parts):
            case ("GET",):
                return Response(200, plain(page_view(self._review.queue(_query(query), by, cursor(query)))))
            case ("POST",):
                return Response(201, plain(shown_view(self._review.submit(draft_of(body), by))))
            case ("GET", pid):
                return Response(200, plain(shown_view(self._review.proposal(pid, by))))
        return None

    def _decision_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                        by: Founder) -> Response | None:
        if (method, parts) != ("POST", ()):
            return None
        outcome = self._review.decide(decision_of(body), by)
        if outcome.changed:
            self._reindex(by.name, by.correlation_id)
        if outcome.refused and not outcome.done:
            return Response(422,
                            {"error": "the change is refused",
                             "findings": [f for r in outcome.refused for f in r.findings]})
        log.info("admin: decided", done=len(outcome.done), refused=len(outcome.refused), held=len(outcome.held))
        return Response(200, plain(outcome_view(outcome)))

    def _bundle_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                      by: Founder) -> Response | None:
        match (method, *parts):
            case ("GET", bundle):
                return Response(200, plain(bundle_view(bundle, self._review.bundle(bundle, by))))
        return None

    def _log_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                   by: Founder) -> Response | None:
        return (Response(200, plain(self._review.log(by, query.get("actor") or None, cursor(query))))
                if (method, parts) == ("GET", ()) else None)

    def _record_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                      by: Founder) -> Response | None:
        match (method, *parts):
            case ("GET",):
                return Response(200,
                                plain(self._records.rows(query.get("kind", ""), query.get("q", ""), cursor(query),
                                                         query.get("category") or None)))
            case ("GET", entity):
                found = self._records.record(entity)
                if found is None:
                    raise LookupError(f"no record {entity}")
                return Response(200, plain(found))
            case ("GET", entity, "history"):
                return Response(200, plain(self._histories.page(entity, cursor(query))))
            case ("GET", entity, "diff"):
                return Response(200,
                                plain(self._histories.diff(entity, whole(query.get("from"), "from"),
                                                           whole(query.get("to"), "to"))))
        return None

    def _media_route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
                     by: Founder) -> Response | None:
        if (method, parts) != ("POST", ()):
            return None
        try:
            content = base64.b64decode(text(body, "content"), validate=True)
        except binascii.Error as exc:
            raise ValueError("content is the file in base64") from exc
        return Response(201, plain(self._records.upload(content, text(body, "mime"))))
