from __future__ import annotations

import json
import socket
import sys
from typing import Any
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from radar import paths
from radar.adapters.console import log
from radar.adapters.firestore.docs import FirestoreDocs
from radar.domain.ports.store.docs import Increment
from radar.adapters.web.api import AskEndpoint, HealthEndpoint, ReportEndpoint, Served
from radar.adapters.web.app_check import AppCheck
from radar.domain.model.entities import FilesOn
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.ports.web.attestation import Verdict
from radar.domain.ports.web.endpoint import Request
from radar.adapters.firestore.ledgers.ai import (CALLS, FirestoreAskLedger, FirestoreBudget, FirestoreUsageLog, METRICS,
                                                 usage_collection)
from radar.adapters.wiring.root import Wiring
from radar.adapters.ai.prompted.answer_model import PromptedAnswerModel
from radar.adapters.ai.runners.chat_completions import ChatCompletionsRunner
from radar.adapters.ai.scripted import ScriptedAnswerModel
from radar.adapters.files.prompts import FilesPromptRegistry
from radar.domain.ai.answerer import Answerer
from radar.domain.ai.budget import Use, caps_of, model_of
from radar.domain.ai.meter import Meter
from radar.domain.ports.ai.usage_log import ModelCall, Outcome
from radar.domain.ai.quota import Quota
from radar.domain.ports.ai.answer_model import AnswerModel
from radar.tests.adapters.stub_server import meta_saying, serving
from radar.tests.store import stores

FX = stores.fixture()
NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
DAY, MONTH = "2026-10-19", "2026-10"
HOSTING = "35.191.0.9"
USAGE, CAP, ASKS_ON = (usage_collection(Use.ASK), caps_of(FX.model.registry.ai, [])[Use.ASK],
                       model_of(FX.model.registry.ai, Use.ASK, None).id)

@pytest.fixture(scope="module")
def place() -> tuple[str, str]:
    return FX.loaded(("index", "rebuild"))

@pytest.fixture
def ledger() -> FirestoreDocs:
    return stores.fresh_at(stores.place()[0])

def _endpoint(ledger: FirestoreDocs, release: str, model: AnswerModel = ScriptedAnswerModel()) -> AskEndpoint:
    wiring = Wiring()
    engine, asks = wiring.search_engine(), FirestoreAskLedger(ledger)
    answerer = Answerer(wiring.retriever(engine), model)
    meter = Meter(FirestoreBudget(ledger, FX.model), FirestoreUsageLog(ledger, now=lambda: NOW),
                  FX.model.registry.ai, Use.ASK, "scripted", lambda model: answerer)
    quota = Quota(asks, meter, engine, release)
    return AskEndpoint(quota, asks, now=lambda: NOW, correlate=wiring.correlate)

@pytest.fixture
def endpoint(place: tuple[str, str], ledger: FirestoreDocs, monkeypatch: pytest.MonkeyPatch) -> AskEndpoint:
    FX.wire(place, monkeypatch)
    return _endpoint(ledger, "api-00001")

def _spent(ledger: FirestoreDocs) -> float:
    return (ledger.get(f"{USAGE}/{MONTH}") or {})["cad"]

def _ask(endpoint: AskEndpoint, question: str, address: str = "203.0.113.7", locale: str = "en",
         forged: str = "198.51.100.1"):
    headers = {"x-forwarded-for": f"{forged}, {address}, {HOSTING}"}
    return endpoint.respond(Request("POST", "/api/ask", json.dumps({"question": question, "locale": locale}).encode(),
                                    headers, "169.254.1.1"))

@pytest.mark.parametrize("locale", ["en", "de"])
def test_an_answer_cites_the_catalog_and_its_cost_is_counted(endpoint: AskEndpoint, ledger: FirestoreDocs,
                                                             locale: str) -> None:
    res = _ask(endpoint, "glossy widget", locale=locale)
    assert res.status == 200 and not res.body["refused"] and res.body["citations"]
    assert set(res.body) == {"answer", "citations", "refused"}
    today = ledger.get(f"{USAGE}/{DAY}") or {}
    assert today["calls"] == 1 and list(today["clients"].values()) == [1] and "203.0.113.7" not in json.dumps(today)
    assert _spent(ledger) > 0

def test_a_repeated_question_is_served_from_the_cache_at_no_cost(endpoint: AskEndpoint, ledger: FirestoreDocs) -> None:
    first = _ask(endpoint, "glossy widget")
    spent = _spent(ledger)
    assert _ask(endpoint, "Glossy  widget?", address="198.51.100.4").body == first.body and _spent(ledger) == spent

def test_a_new_release_answers_again_what_the_last_one_cached(endpoint: AskEndpoint, ledger: FirestoreDocs) -> None:
    _ask(endpoint, "glossy widget")
    spent = _spent(ledger)
    _ask(_endpoint(ledger, "api-00002"), "glossy widget")
    assert _spent(ledger) > spent

def test_a_client_past_its_asks_of_the_day_is_refused_whatever_header_it_forges(endpoint: AskEndpoint) -> None:
    for n in range(CAP.client_calls or 0):
        assert _ask(endpoint, f"widget {n}", forged=f"198.51.100.{n + 10}").status == 200
    limited = _ask(endpoint, "one more widget")
    assert (limited.status, limited.body["refused"], limited.body["reason"]) == (429, True, "limit")
    assert _ask(endpoint, "one more widget", address="198.51.100.9").status == 200

def test_the_site_cap_refuses_past_its_limit(endpoint: AskEndpoint, ledger: FirestoreDocs) -> None:
    ledger.commit([Increment(f"{USAGE}/{DAY}", {"calls": CAP.day_calls})])
    res = _ask(endpoint, "glossy widget")
    assert (res.status, res.body["reason"]) == (429, "limit")

def test_every_model_call_and_every_capped_one_is_recorded_without_the_question(
        endpoint: AskEndpoint, ledger: FirestoreDocs, capsys: pytest.CaptureFixture[str]) -> None:
    log.configure(json_mode=True)
    capsys.readouterr()
    _ask(endpoint, "glossy widget")
    ledger.commit([Increment(f"{USAGE}/{MONTH}", {"cad": CAP.month_cad})])
    _ask(endpoint, "matte widget")
    calls = sorted((f for _, f in ledger.list(CALLS)), key=lambda c: c["outcome"])
    assert [(c["use"], c["prompt"], c["model"], c["outcome"]) for c in calls] == [
        ("ask", "scripted", ASKS_ON, "answered"), ("ask", "scripted", ASKS_ON, "capped")]
    assert (calls[0]["tokens_in"] > 0 and calls[0]["cad"] > 0 and calls[0]["latency_ms"] >= 0
            and calls[0]["correlation_id"].startswith("ask-"))
    assert calls[1]["reason"].startswith("ask: CAD") and "widget" not in json.dumps(calls)
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines() if '"model call"' in line]
    assert ([line["outcome"] for line in lines] == ["answered", "capped"]
            and all("widget" not in json.dumps(line) for line in lines))

@pytest.mark.parametrize("said", ['{"sentences": [{"words": "Widget Two is glossy."}]}',
                                  '{"sentences": [{"text": "Widget Two is'])
def test_a_reply_out_of_shape_is_unavailable_and_charged_as_billed(
        place: tuple[str, str], ledger: FirestoreDocs, monkeypatch: pytest.MonkeyPatch, said: str) -> None:
    FX.wire(place, monkeypatch)
    model = model_of(FX.model.registry.ai, Use.ASK, None)
    with serving(meta_saying(said, []), keep_alive=True) as url:
        runner = ChatCompletionsRunner(model.id, f"{url}/v1", "recorded")
        model = PromptedAnswerModel(FilesPromptRegistry(paths.PROMPTS).prompt("ask"), runner)
        res = _ask(_endpoint(ledger, "api-00001", model), "glossy widget")
    [call] = [f for _, f in ledger.list(CALLS)]
    assert (res.status, res.body["reason"], call["outcome"], call["reason"]) == (
        503, "unavailable", "error", "Unparsed")
    assert call["tokens_in"] > 0 and call["cad"] > 0 and _spent(ledger) == pytest.approx(call["cad"], abs=1e-8)

def test_a_usage_record_never_holds_a_credential(ledger: FirestoreDocs, capsys: pytest.CaptureFixture[str]) -> None:
    log.configure(json_mode=True)
    capsys.readouterr()
    FirestoreUsageLog(ledger, now=lambda: NOW).record(ModelCall(Use.ASK, "answer/v1", "ya29.a0secretvalue", 1, 1, 0.0,
                                                                1, Outcome.ERROR, "Bearer abc.def"))
    stored = json.dumps([f for _, f in ledger.list(CALLS)]) + capsys.readouterr().err
    assert "ya29.a0secretvalue" not in stored and "abc.def" not in stored and "[redacted]" in stored

def test_a_question_off_the_catalog_is_refused_and_counted(endpoint: AskEndpoint, ledger: FirestoreDocs) -> None:
    res = _ask(endpoint, "What is the capital of Australia?", locale="fr")
    assert (res.status, res.body["refused"], res.body["reason"]) == (200, True, "off_topic")
    assert (ledger.get(f"{METRICS}/{DAY}") or {}) == {"refusal": 1}

@pytest.mark.parametrize("body",
                         [{"question": "", "locale": "en"}, {"question": "x" * 301, "locale": "en"},
                          {"question": "widget", "locale": "english"}, {"question": "widget", "locale": "../"},
                          ["widget"]])
def test_a_bad_request_is_refused(endpoint: AskEndpoint, body: object) -> None:
    assert endpoint.respond(Request("POST", "/api/ask", json.dumps(body).encode(), {}, "203.0.113.7")).status == 400

def test_counters_are_added_server_side_with_nothing_of_the_asker(endpoint: AskEndpoint, ledger: FirestoreDocs) -> None:
    def count(body: dict) -> int:
        return endpoint.respond(Request("POST", "/api/count", json.dumps(body).encode(), {}, "203.0.113.7")).status
    assert count({"event": "search", "from": "https://chatgpt.com/c/abc"}) == 204
    assert count({"event": "zero_result", "from": "https://www.perplexity.ai/search?q=x"}) == 204
    assert count({"event": "result_click", "from": "https://example.com/"}) == 204
    assert count({"event": "page_view", "from": "https://www.linkedin.com/feed/update/1?x=y"}) == 204
    assert count({"event": "page_view"}) == 204
    assert count({"event": "anything"}) == 400
    assert (ledger.get(f"{METRICS}/{DAY}") or {}) == {"search": 1, "zero_result": 1, "result_click": 1, "page_view": 2,
                                                      "from_chatgpt": 1, "from_perplexity": 1, "ref_example_com": 1,
                                                      "ref_linkedin_com": 1}

def test_every_log_line_of_an_ask_carries_its_correlation_id(endpoint: AskEndpoint,
                                                             capsys: pytest.CaptureFixture[str]) -> None:
    log.configure(json_mode=True)
    capsys.readouterr()
    _ask(endpoint, "glossy widget")
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert lines and len({line["correlation_id"] for line in lines}) == 1
    assert lines[0]["correlation_id"].startswith("ask-")

class _FlaskRequest:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self.method, self.path, self.headers, self.remote_addr, self._body = (
            "POST", "/api/ask", headers, "169.254.1.1", body)
        self.args: dict[str, str] = {}

    def get_data(self) -> bytes:
        return self._body

def test_the_cloud_function_runs_in_us_central1_scaled_to_zero_and_serves_the_endpoint(
        endpoint: AskEndpoint, monkeypatch: pytest.MonkeyPatch) -> None:
    deployed: dict[str, object] = {}
    https_fn = SimpleNamespace(on_request=lambda **settings: deployed.update(settings) or (lambda fn: fn),
                               Response=lambda text, status, headers, content_type: (
                                   status, content_type, headers, json.loads(text)), Request=object)
    monkeypatch.setitem(sys.modules, "firebase_functions",
                        SimpleNamespace(https_fn=https_fn,
                                        options=SimpleNamespace(MemoryOption=SimpleNamespace(GB_2="2GiB"))))
    monkeypatch.delitem(sys.modules, "radar.adapters.web.function", raising=False)
    from radar.adapters.web import function
    log.configure()
    api = function.entry(Served(lambda: endpoint))
    status, mime, headers, body = api(_FlaskRequest(json.dumps({"question": "glossy widget", "locale": "en"}).encode(),
                                                    {"Content-Type": "application/json",
                                                     "X-Forwarded-For": f"203.0.113.7, {HOSTING}"}))
    assert (deployed["region"], deployed["min_instances"]) == ("us-central1", 0)
    assert (status, mime, headers, body["refused"]) == (200, "application/json", {}, False) and body["citations"]

def test_health_answers_the_release_the_commit_and_the_index_version_to_a_get(
        place: tuple[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    FX.wire(place, monkeypatch)
    engine = Wiring().search_engine()
    health = HealthEndpoint(engine, "api-00007", "abc1234")
    assert health.respond(Request("POST", "/api/health", b"{}", {}, "127.0.0.1")).status == 405
    response = health.respond(Request("GET", "/api/health", b"", {}, "127.0.0.1"))
    assert (response.status, response.headers) == (200, {"cache-control": "no-store"})
    assert response.body == {"release": "api-00007", "commit": "abc1234", "index": engine.last_indexed().version}

def test_radar_metrics_sums_the_days_counters_and_reads_the_kpis() -> None:
    where = stores.place()
    ledger = FirestoreAskLedger(stores.fresh_at(where[0]))
    ledger.count(DAY, {"search": 3, "zero_result": 1, "result_click": 2})
    ledger.count("2026-10-17", {"search": 1, "answer": 3, "refusal": 1})
    ledger.count("2026-10-01", {"search": 100})
    out = FX.json(where, "metrics", "show", "--to", DAY)
    assert out["counts"] == {"answer": 3, "refusal": 1, "result_click": 2, "search": 4, "zero_result": 1}
    assert out["kpis"] == {"click_through": 0.5, "zero_result": 0.25, "ask_refusal": 0.25}

class Once:
    def __init__(self) -> None:
        self._used: set[str] = set()

    def check(self, token: str) -> Verdict:
        if token == "outage":
            return Verdict.UNAVAILABLE
        fresh = token.startswith("minted-") and token not in self._used
        self._used.add(token)
        return Verdict.ATTESTS if fresh else Verdict.REFUSED

def test_a_reader_files_a_report_counted_once_more_when_repeated_and_only_from_the_form() -> None:
    docs, files = FX.seeded()
    endpoint, queue = ReportEndpoint(FX.review(docs, files), Once(), lambda job: f"{job}-test"), FX.queue(docs)

    def send(body: Any, token: str = "") -> tuple[int, Any]:
        response = endpoint.respond(Request("POST", "/api/report",
                                            body if isinstance(body, bytes) else json.dumps(body).encode(),
                                            {"x-firebase-appcheck": token} if token else {}, "127.0.0.1"))
        return response.status, response.body

    subject = FX.rows("products.jsonl")[0]["id"]
    report = {"subject": subject, "message": "The frame rate is 120 fps on the datasheet.",
              "source_url": "https://example.com/datasheet.pdf"}
    assert send(report)[0] == 401 and send(report, "forged")[0] == 401
    assert send(report, "outage") == (503, {"error": "the report was not filed: try again later"}), (
        "an outage is no refusal")
    assert send(report, "minted-1") == (201, {"report": "filed"})
    assert send(report, "minted-1")[0] == 401, "a token attests once"
    assert send(report, "minted-2") == (200, {"report": "counted"})
    [filed] = queue.list(Query()).proposals
    assert (filed.status, filed.files_on, filed.author, filed.actor_kind, filed.reports) == (
        "suggested", FilesOn.REPORT, "public", "human", 2)
    assert (filed.subject, filed.message, filed.source_url, filed.changeset) == (
        subject, report["message"], report["source_url"], None)
    assert [(e.action, e.actor, e.correlation_id)
            for e in queue.log().entries] == [("submit", "public", "report-test")] * 2
    for n, bad in enumerate([b"not json", [report], {**report, "message": " "}, {**report, "message": "x" * 2001},
                             {**report, "subject": "Kamera 9"}, {**report, "source_url": "javascript:alert(1)"},
                             {**report, "source_url": "https://example.com/" + "x" * 500}]):
        assert send(bad, f"minted-bad-{n}")[0] == 400, bad
    assert queue.list(Query()).proposals == (filed,)

@pytest.mark.parametrize(("status", "answer", "verdict"),
                         [(200, {}, Verdict.ATTESTS), (200, {"alreadyConsumed": True}, Verdict.REFUSED),
                          (403, {"error": {"code": 403}}, Verdict.REFUSED), (429, {}, Verdict.UNAVAILABLE),
                          (500, {}, Verdict.UNAVAILABLE)])
def test_app_check_attests_a_token_it_has_not_seen_and_says_when_it_is_down(
        status: int, answer: dict[str, Any], verdict: Verdict) -> None:
    heard: list[tuple[str, Any]] = []

    def verify(path: str, sent: bytes) -> tuple[int, bytes]:
        heard.append((path, json.loads(sent)))
        return status, json.dumps(answer).encode()

    with serving(verify) as root:
        app_check = AppCheck("demo-mvradar", "server-token", root)
        assert app_check.check("limited-1") is verdict and app_check.check("") is Verdict.REFUSED
    assert heard == [("/projects/demo-mvradar:verifyAppCheckToken", {"appCheckToken": "limited-1"})]

def test_app_check_out_of_reach_is_an_outage() -> None:
    with socket.socket() as gone:
        gone.bind(("127.0.0.1", 0))
        port = gone.getsockname()[1]
    assert AppCheck("demo-mvradar", "server-token",
                    f"http://127.0.0.1:{port}").check("limited-1") is Verdict.UNAVAILABLE
