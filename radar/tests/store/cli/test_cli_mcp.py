from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import jsonschema
import pytest

from radar import paths
from radar.tests.store import stores

FX = stores.fixture()

@pytest.fixture(scope="module")
def place() -> tuple[str, str]:
    return FX.loaded(("index", "rebuild"))

def _call(rid: int, tool: str, **arguments: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}

def _serve(place: tuple[str, str], secret: str, messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    run = subprocess.run([sys.executable, "-m", "radar", "--json", "mcp", "serve"], cwd=paths.DEV,
                         env={**FX.env(place), "MVR_AGENT_TOKEN": secret}, capture_output=True, text=True, check=True,
                         input="".join(json.dumps(m) + "\n" for m in messages))
    return [json.loads(line) for line in run.stdout.splitlines()], run.stderr

def test_stdio_answers_what_the_cli_prints(place: tuple[str, str]) -> None:
    run = stores.cli(FX, place, "-v", "agent-token", "create", "scout", "--scope", "read", "--expires", "2099-01-01")
    secret, listed = json.loads(run.stdout)["token"], stores.cli(FX, place, "agent-token", "list")
    assert run.stdout.count(secret) == 1 and secret not in run.stderr + listed.stdout + listed.stderr
    product, url = FX.rows("products.jsonl")[0], FX.rows("sources.jsonl")[0]["url"]
    name = next(n["value"] for n in FX.rows("names.jsonl") if n["subject"] == product["id"])
    messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "a test", "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                _call(2, "search_products", query=name), _call(3, "get_product", id=product["slug"]),
                _call(4, "search_sources", url=url)]
    answers, err = _serve(place, secret, messages)
    for answer in answers:
        jsonschema.validate(answer, stores.OUTPUTS["mcp serve"])
    assert [a["id"] for a in answers] == [1, 2, 3, 4] and answers[0]["result"]["protocolVersion"] == "2025-06-18"
    assert answers[1]["result"]["structuredContent"] == {"hits": FX.json(place, "product", "search", name)}
    assert answers[2]["result"]["structuredContent"] == FX.json(place, "product", "get", product["slug"])
    assert answers[3]["result"]["structuredContent"] == FX.json(place, "source", "search", "--url", url)
    assert secret not in err
    tokenless = stores.cli(FX, place, "mcp", "serve", check=False)
    assert tokenless.returncode == 2 and "MVR_AGENT_TOKEN" in tokenless.stderr

def test_stdio_files_a_proposal_as_the_cli_shows_it_and_refuses_one_over_the_day(place: tuple[str, str]) -> None:
    secret = FX.json(place, "agent-token", "create", "Grok Bot", "--scope", "propose", "--expires", "2099-01-01",
                     "--proposals-per-day", "1")["token"]
    claim, changed = FX.revised_claim(7.0)

    def draft(reason: str) -> dict[str, Any]:
        change = {"op": "put", "entity": {k: v for k, v in changed.items() if k != "version"}, "reason": reason,
                  "source_refs": claim["source_refs"]}
        return {"files_on": "update", "reason": reason, "subject": claim["subject"],
                "changeset": json.dumps({"changes": [change]})}

    answers, _ = _serve(place, secret,
                        [_call(1, "submit_proposal", **draft("Revision C")), _call(2, "list_my_proposals"),
                         _call(3, "submit_proposal", **draft("Revision D"))])
    filed = answers[0]["result"]["structuredContent"]
    assert ((filed["actor_kind"], filed["author"]) == ("agent", "Grok Bot")
            and filed == FX.json(place, "proposal", "show", filed["id"]))
    assert answers[1]["result"]["structuredContent"] == FX.json(place, "proposal", "list", "--actor-kind", "agent",
                                                                "--author", "Grok Bot")
    over = answers[2]["error"]
    assert (over["code"], over["message"]) == (-32002, "the agent token is over its limits: over its 1 proposals a day")
    assert 0 < over["data"]["retry_after"] <= 86_400
