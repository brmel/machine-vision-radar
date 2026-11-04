from __future__ import annotations

import ast
import json

import pytest

from radar import paths
from radar.adapters.console import log

CONSOLE = {paths.DEV / "radar" / "adapters" / "console" / name for name in ("log.py", "output.py")}

def offences(source: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name == "print" or name.startswith(("sys.stdout.", "sys.stderr.")) or name == "traceback.print_exc":
                lines.append(node.lineno)
        if isinstance(node, ast.ExceptHandler) and all(isinstance(statement, ast.Pass) for statement in node.body):
            lines.append(node.lineno)
    return sorted(lines)

def test_the_rule_fires_on_a_fixture() -> None:
    fixture = "\n".join([
        "print('x')",
        "sys.stdout.write('x')",
        "sys.stderr.buffer.write(b'x')",
        "traceback.print_exc()",
        "try:\n    a()\nexcept ValueError:\n    pass",
        "log.info('fine')",
        "try:\n    a()\nexcept ValueError as exc:\n    log.error(str(exc))",
    ])
    assert offences(fixture) == [1, 2, 3, 4, 7]

def test_no_module_prints_or_swallows_an_error() -> None:
    files = [f for f in (paths.DEV / "radar").rglob("*.py") if "tests" not in f.relative_to(paths.DEV).parts
             and f not in CONSOLE]
    hits = [f"{f.relative_to(paths.DEV)}:{line}" for f in files for line in offences(f.read_text(encoding="utf-8"))]
    assert hits == []

def test_a_json_line_carries_the_shared_fields_and_no_secret(capsys: pytest.CaptureFixture[str]) -> None:
    secrets = {"token": "s3cr3t-token-value", "Authorization": "Bearer abc.def.ghi", "cookie": "session=abc123",
               "api_key": "AIzaSyA1234567890abcdefghijklmnopqrstuv", "agent_token": "mvr_0123456789abcdefghijklmnop"}
    log.configure(json_mode=True)
    log.bind(correlation_id="job-1")
    log.warn("an ask failed with Bearer ya29.a0AfH6SMBx and eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM", **secrets,
             product="prd_0001")
    err = capsys.readouterr().err
    log.configure()
    line = json.loads(err)
    fields = json.loads((paths.CONTRACTS / "logging.json").read_text(encoding="utf-8"))["fields"]
    assert list(line)[:4] == fields and line["correlation_id"] == "job-1" and line["product"] == "prd_0001"
    assert line["time"].endswith("Z")
    for secret in [*secrets.values(), "ya29.a0AfH6SMBx", "eyJhbGciOi"]:
        assert secret not in err
