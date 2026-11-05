from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from radar.adapters.web.admin.search import SearchAdmin
from radar.adapters.wiring.root import Wiring
from radar.domain.ai.budget import Use
from radar.domain.model.history.projection import plain
from radar.domain.review.requests import Founder
from radar.tests.store import stores

FX = stores.fixture()
FOUNDER = Founder("founder@example.com", "admin-test")

@pytest.fixture
def place(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    where = FX.loaded(("index", "rebuild"))
    FX.wire(where, monkeypatch)
    return where

def _admin() -> SearchAdmin:
    wiring = Wiring()
    return wiring.search_admin(wiring.review(), wiring.histories())

def _route(admin: SearchAdmin, method: str, *parts: str, body: dict[str, Any] | None = None,
           **query: str) -> tuple[int, Any]:
    response = admin.route(method, parts, query, body or {}, FOUNDER)
    assert response is not None, f"no route {method} {'/'.join(parts)}"
    return response.status, response.body

def test_each_search_screen_answers_what_its_command_prints(place: tuple[str, str]) -> None:
    admin = _admin()
    assert _route(admin, "GET", "status") == (200, FX.json(place, "index", "status"))
    assert _route(admin, "GET", "caps") == (200, FX.json(place, "ai-caps", "get"))
    assert _route(admin, "GET", "query", q="widget") == (200, {"hits": FX.json(place, "product", "search", "widget")})
    Wiring().ask_ledger().count(Wiring().now()[:10], {"search": 2, "zero_result": 1})
    assert _route(admin, "GET", "weekly") == (200, FX.json(place, "metrics", "weekly"))
    assert _route(admin, "GET", "weekly")[1]["weeks"][0]["counts"] == {"search": 2, "zero_result": 1}

def test_an_update_is_recorded_and_the_settings_name_the_registry_s_one_model(place: tuple[str, str]) -> None:
    admin = _admin()
    status, view = _route(admin, "POST", "update")
    assert status == 200 and (view["runs"][0]["action"], view["runs"][0]["actor"]) == ("update", FOUNDER.name)
    settings = _route(admin, "GET", "settings")[1]
    assert (settings["current"]["model_id"] == settings["search"]["model"]
            and settings["search"] == plain(FX.model.registry.search))
    assert admin.route("POST", ("model",), {}, {"model": "no/such-model"}, FOUNDER) is None
    with pytest.raises(ValueError, match="day_calls: must be at least 0, got -1"):
        _route(admin, "POST", "caps", body={"use": Use.ASK.value, "day_calls": -1, "reason": "a mistake"})
    with pytest.raises(ValueError, match="model is required"):
        _route(admin, "POST", "caps", body={"use": Use.ASK.value, "model": "", "reason": "a mistake"})

def test_a_failed_rebuild_is_answered_with_its_error_and_recorded(
        place: tuple[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path))
    status, body = _route(_admin(), "POST", "rebuild")
    error = _route(_admin(), "GET", "status")[1]["runs"][0]["error"]
    assert (status, body) == (500, {"error": f"the index rebuild failed: {error}"})
    assert error.startswith(f"fastembed could not load {FX.model.registry.search.model}")
