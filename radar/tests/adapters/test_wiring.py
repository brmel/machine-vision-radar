from __future__ import annotations

import http.client
import io
import urllib.request
from types import SimpleNamespace
from typing import Callable

import pytest

from radar import paths
from radar.domain.ports.store.docs import Put
from radar.adapters.wiring.root import Wiring
from radar.adapters.wiring.stores import TEST_ONLY, NoStore
from radar.domain.ports.web.attestation import Verdict

PROJECT = paths.firebase_project()

@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    for variable in TEST_ONLY:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("MVR_ACCESS_TOKEN", "token-1")
    requests: list[urllib.request.Request] = []

    def urlopen(req: urllib.request.Request, timeout: float) -> io.BytesIO:
        assert timeout > 0, "every request has a time limit"
        requests.append(req)
        return io.BytesIO(b"{}")

    class Connection:
        sock = None

        def __init__(self, host: str, timeout: float) -> None:
            assert timeout > 0, "every request has a time limit"
            self._host = host

        def request(self, method: str, target: str, body: bytes | None, headers: dict[str, str]) -> None:
            requests.append(urllib.request.Request(f"https://{self._host}{target}", body, headers, method=method))

        def getresponse(self) -> SimpleNamespace:
            return SimpleNamespace(status=200, read=lambda: b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(http.client, "HTTPSConnection", Connection)
    return requests

def test_the_project_is_read_with_the_token(sent: list[urllib.request.Request]) -> None:
    Wiring(PROJECT).store().get("products/prd_1")
    assert sent[0].full_url == (f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/"
                                "products/prd_1")
    assert sent[0].get_header("Authorization") == "Bearer token-1"

def test_a_report_on_the_project_is_attested_by_app_check_with_the_token(sent: list[urllib.request.Request]) -> None:
    assert Wiring(PROJECT, yes=True).attestation().check("limited-1") is Verdict.ATTESTS
    assert sent[0].full_url == f"https://firebaseappcheck.googleapis.com/v1beta/projects/{PROJECT}:verifyAppCheckToken"
    assert (sent[0].get_header("Authorization"), sent[0].get_header("X-goog-user-project")) == (
        "Bearer token-1", PROJECT)

def test_a_write_to_the_project_needs_yes(sent: list[urllib.request.Request]) -> None:
    with pytest.raises(PermissionError, match="--yes"):
        Wiring(PROJECT).store().commit([Put("products/prd_1", {"id": "prd_1"})])
    with pytest.raises(PermissionError, match="--yes"):
        Wiring(PROJECT).blobs().write("media/00/file.pdf", b"%PDF", "application/pdf")
    assert sent == []
    Wiring(PROJECT, yes=True).store().commit([Put("products/prd_1", {"id": "prd_1"})])
    assert [r.full_url.rsplit("/", 1)[1] for r in sent] == ["documents:commit"]

@pytest.mark.parametrize(("reach", "why"), [
    (lambda: Wiring(f"{PROJECT}-other").store(), PROJECT),
    (lambda: Wiring().repository(), "no store"),
    (lambda: Wiring().blobs(), "no store"),
])
def test_no_store_says_why_before_anything_is_sent(reach: Callable[[], object], why: str,
                                                   sent: list[urllib.request.Request]) -> None:
    with pytest.raises(NoStore, match=why):
        reach()
    assert sent == []

def test_a_model_opens_on_the_project_only_with_yes(sent: list[urllib.request.Request]) -> None:
    ask = Wiring(PROJECT).ask_meter(Wiring(PROJECT).search_engine())
    for build in (Wiring(PROJECT).research_meter, Wiring(PROJECT).datasheet_meter, Wiring(PROJECT).draft_meter):
        build()
    assert sent == []
    with pytest.raises(NoStore, match="--yes"):
        ask.call("2026-10-30", lambda model: model)
    assert sent and [r.full_url for r in sent if r.get_method() != "GET"] == []

def test_muse_spark_on_the_meta_model_api_needs_its_key_before_anything_is_sent(
        sent: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    ask = Wiring(PROJECT, yes=True).ask_meter(Wiring(PROJECT).search_engine())
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        ask.call("2026-10-30", lambda model: model)
    assert [r.full_url for r in sent if "meta.ai" in r.full_url] == []

def test_no_token_no_project(sent: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MVR_ACCESS_TOKEN")
    with pytest.raises(NoStore, match="MVR_ACCESS_TOKEN"):
        Wiring(PROJECT).blobs()

@pytest.mark.parametrize("variable", TEST_ONLY)
def test_never_the_project_beside_an_emulator_or_fixture_setting(variable: str, sent: list[urllib.request.Request],
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(variable, "leftover")
    with pytest.raises(NoStore, match=variable):
        Wiring(PROJECT).store()
