from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from radar.adapters.console import log
from radar.domain.ai.answerer import refusal
from radar.domain.model.history.projection import plain
from radar.domain.model.history.ids import ENTITY_ID
from radar.domain.ports.search.ask_ledger import AskLedger
from radar.domain.ports.web.attestation import Attestation, Verdict
from radar.domain.ports.web.endpoint import Endpoint, Request, Response
from radar.domain.ports.search.search_engine import NoIndex, SearchEngine, SearchRequest
from radar.domain.ai.quota import Quota, counters
from radar.domain.review.requests import Reader, Report
from radar.domain.review.review import Review
from radar.domain.search.hits import found

EVENTS = ("search", "zero_result", "result_click")
MAX_QUESTION = 300
MAX_MESSAGE, MAX_SOURCE = 2000, 500
NOT_FILED = {"error": "the report was not filed: try again later"}

def _is_language(locale: object) -> bool:
    return (isinstance(locale, str) and 2 <= len(locale) <= 3 and locale.isascii() and locale.isalpha()
            and locale.islower())

def payload(request: Request) -> dict[str, Any]:
    body = json.loads(request.body or b"{}") if request.method == "POST" else {}
    if not isinstance(body, dict):
        raise ValueError("the body is a JSON object")
    return body

def wire(response: Response) -> str:
    return "" if response.body is None else json.dumps(response.body, ensure_ascii=False)

def client_address(request: Request) -> str:
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",")]
    return hops[-2] if len(hops) > 1 else request.address

class AskEndpoint:
    def __init__(self, quota: Quota, ledger: AskLedger,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 correlate: Callable[[str], str] = lambda job: job) -> None:
        self._quota, self._ledger, self._now, self._correlate = quota, ledger, now, correlate

    def respond(self, request: Request) -> Response:
        self._correlate("ask" if request.path.endswith("/ask") else "count")
        if request.method != "POST":
            return Response(405, {"error": "POST a JSON object"})
        try:
            body = payload(request)
        except ValueError:
            return Response(400, {"error": "POST a JSON object"})
        if request.path.endswith("/count"):
            return self._count(body)
        if request.path.endswith("/ask"):
            return self._ask(body, request)
        return Response(404, {"error": f"no route {request.path}"})

    def _count(self, body: Mapping[str, Any]) -> Response:
        if body.get("event") not in EVENTS:
            return Response(400, {"error": f"event is one of {', '.join(EVENTS)}"})
        self._ledger.count(self._now().strftime("%Y-%m-%d"), counters(str(body["event"]), str(body.get("from") or "")))
        return Response(204)

    def _ask(self, body: Mapping[str, Any], request: Request) -> Response:
        question, locale = body.get("question"), body.get("locale")
        if (not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION
                or not _is_language(locale)):
            return Response(400, {"error": f"question is 1 to {MAX_QUESTION} characters and locale is a language code"})
        try:
            answer, cad = self._quota.ask(question, locale, self._now().strftime("%Y-%m-%d"), client_address(request))
        except (NoIndex, OSError, ValueError, RuntimeError) as exc:
            log.error(f"ask: no answer: {exc}")
            return Response(503, plain(refusal("unavailable")))
        log.info("ask: answered", refused=answer.refused, reason=answer.reason, cad=round(cad, 6))
        return Response(429 if answer.reason == "limit" else 200, plain(answer))

class FindEndpoint:
    def __init__(self, engine: SearchEngine, correlate: Callable[[str], str]) -> None:
        self._engine, self._correlate = engine, correlate

    def respond(self, request: Request) -> Response:
        self._correlate("find")
        try:
            words = payload(request).get("words")
        except ValueError:
            words = None
        if not isinstance(words, str) or not words.strip() or len(words) > MAX_QUESTION:
            return Response(400, {"error": f"POST words, 1 to {MAX_QUESTION} characters"})
        try:
            listed = found(self._engine.search(SearchRequest(words, None)))
        except (NoIndex, OSError, ValueError, RuntimeError) as exc:
            log.error(f"find: no result: {exc}")
            return Response(503, {"error": "search is unavailable: try again later"})
        return Response(200, plain(listed))

def _address(value: str) -> bool:
    url = urllib.parse.urlsplit(value)
    return len(value) <= MAX_SOURCE and url.scheme in ("http", "https") and bool(url.netloc)

def _report(body: Mapping[str, Any]) -> Report | None:
    subject, message, source = body.get("subject"), body.get("message"), body.get("source_url")
    if (not isinstance(subject, str) or not ENTITY_ID.fullmatch(subject) or not isinstance(message, str)
            or not message.strip() or len(message) > MAX_MESSAGE
            or (source is not None and (not isinstance(source, str) or not _address(source)))):
        return None
    return Report(subject, message, source)

class ReportEndpoint:
    def __init__(self, review: Review, attestation: Attestation, correlate: Callable[[str], str]) -> None:
        self._review, self._attestation, self._correlate = review, attestation, correlate

    def respond(self, request: Request) -> Response:
        try:
            report = _report(payload(request))
        except ValueError:
            report = None
        if report is None:
            return Response(400,
                            {"error": f"POST subject (a record id), message (1 to {MAX_MESSAGE} characters) and an "
                                      "optional source_url "
                                      f"(an http(s) address of at most {MAX_SOURCE})"})
        try:
            match self._attestation.check(request.headers.get("x-firebase-appcheck", "")):
                case Verdict.REFUSED:
                    log.warn("report: refused, the request does not attest")
                    return Response(401,
                                    {"error": "the report is not from the site's form: reload the page and send it "
                                              "again"})
                case Verdict.UNAVAILABLE:
                    log.error("report: not filed, App Check is unavailable")
                    return Response(503, NOT_FILED)
                case Verdict.ATTESTS:
                    filed = self._review.submit(report, Reader(self._correlate("report"))).proposal
        except (OSError, ValueError) as exc:
            log.error(f"report: not filed: {exc}")
            return Response(503, NOT_FILED)
        log.info("report: filed", proposal=filed.id, reports=filed.reports)
        return Response(201, {"report": "filed"}) if filed.reports == 1 else Response(200, {"report": "counted"})

class Api:
    def __init__(self, ask: Endpoint, admin: Endpoint, mcp: Endpoint, report: Endpoint, find: Endpoint) -> None:
        self._ask, self._admin, self._mcp, self._report, self._find = ask, admin, mcp, report, find

    def respond(self, request: Request) -> Response:
        exact = {"/api/mcp": self._mcp, "/api/report": self._report, "/api/find": self._find}.get(request.path)
        return (exact or (self._admin if request.path.startswith("/api/admin/") else self._ask)).respond(request)

class Served:
    def __init__(self, build: Callable[[], Endpoint], ttl: float = 1800,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._build, self._ttl, self._clock = build, ttl, clock
        self._endpoint: Endpoint | None = None
        self._until = 0.0

    def __call__(self, request: Request) -> Response:
        if self._endpoint is None or self._clock() >= self._until:
            self._endpoint, self._until = self._build(), self._clock() + self._ttl
        return self._endpoint.respond(request)
