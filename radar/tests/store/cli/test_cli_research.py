from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from radar.adapters.web.admin.research import ResearchAdmin
from radar.adapters.wiring.root import Wiring
from radar.domain.review.requests import Founder
from radar.tests.adapters.stub_server import serving
from radar.tests.fixtures.fixture_category import recorded_page
from radar.tests.store import stores

FX = stores.fixture()

def test_research_from_the_cli_and_the_admin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    where = FX.loaded()
    FX.wire(where, monkeypatch)
    with serving(pages=recorded_page) as site:
        monkeypatch.setenv("MVR_WEB_BASE", site)
        run = FX.json(where, "research", "run", "--maker",
                      next(o for o in FX.rows("organizations.jsonl") if o["website"] == "https://example.com")["slug"])
    assert run["status"] == "done" and run["filed"]
    row = {k: run[k] for k in ("id", "scope", "actor", "started_at", "ended_at", "status", "cad")} | {
        k: len(run[k]) for k in ("pages", "filed", "rejected")}
    assert (FX.json(where, "research", "list") == {"runs": [row], "total": 1}
            and FX.json(where, "research", "log", run["id"]) == run)
    refused = {detail.split(": ", 1)[1]: 1 for detail in run["rejected"]}
    measured = {"since": run["started_at"], "runs": 1, "pages": 3, "filed": 7, "refused": refused, "values": 5,
                "filter_values": 3, "cad": run["cad"],
                "skipped": {"169.254.169.254 is not a public address": 1, "the store holds it": 1,
"robots.txt disallows it": 1, "not public: it asks for a sign-in": 1, "not a page: HTTP 200, application/pdf": 1,
"it redirects off its site, to https://elsewhere.example.org/": 1}}
    cells = {"cells": 126, "before": 64, "now": 64}
    assert FX.json(where, "research", "measure", "--since", run["started_at"]) == {
        **measured, "statuses": {"suggested": 5}, "published": 0, "cells": {"fixture_domain.widgets": cells}}
    bundle = FX.json(where, "proposal", "list", "--bundle", run["id"])["proposals"]
    FX.json(where, "proposal", "approve", *(p["id"] for p in bundle if p["subject"] == "prd_0000000002"), "--note",
            "Checked on the maker's page")
    reach = next(c for c in FX.rows("claims.jsonl") if c["subject"] == "prd_0000000002"
                 and c["spec_key"] == "fixture_reach")
    stores.cli(FX, where, "change", "apply",
               stores.changes_file(tmp_path, "reach.json", stores.put(reach, "The catalogue's reach")))
    assert FX.json(where, "research", "measure", "--since", run["started_at"]) == {
        **measured, "statuses": {"approved": 3, "suggested": 2}, "published": 2,
        "cells": {"fixture_domain.widgets": {**cells, "now": 65}}}
    later = (datetime.fromisoformat(run["started_at"]) + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    assert FX.json(where, "research", "measure", "--since", later)["runs"] == 0
    ended = stores.cli(FX, where, "research", "cancel", run["id"], check=False)
    assert ended.returncode == 1 and "only a running run is cancelled" in ended.stderr

    wiring = Wiring()
    admin = ResearchAdmin(wiring.researcher, wiring.correlate)
    founder = Founder("founder@example.com", "admin-test")
    listed, shown = admin.route("GET", (), {}, {}, founder), admin.route("GET", (run["id"],), {}, {}, founder)
    assert listed is not None and shown is not None and (listed.body, shown.body) == ({"runs": [row], "total": 1}, run)
    for body in ({"scope": "acme"}, {"maker": "acme", "category": "lighting"}, {"maker": " "}):
        with pytest.raises(ValueError, match="one of product, maker or category"):
            admin.route("POST", (), {}, body, founder)
    for kind in ("product", "category"):
        refused = stores.cli(FX, where, "research", "run", f"--{kind}", "nothing", check=False)
        assert refused.returncode == 1 and f"no {kind} nothing" in refused.stderr
        with pytest.raises(LookupError, match=f"no {kind} nothing"):
            admin.route("POST", (), {}, {kind: "nothing"}, founder)
