from __future__ import annotations

import argparse
import json

import jsonschema
import pytest

from radar import paths
from radar.adapters.web.mcp import SCHEMAS
from radar.cli import build_parser, main

OPERATIONS = json.loads((paths.CONTRACTS / "operations.json").read_text(encoding="utf-8"))["operations"]

def _verbs() -> dict[str, argparse.ArgumentParser]:
    nouns = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction)).choices
    return {f"{noun} {verb}": vp for noun, np in nouns.items()
            for a in np._actions if isinstance(a, argparse._SubParsersAction) for verb, vp in a.choices.items()}

def test_the_registry_lists_exactly_the_cli_commands_and_every_screen_or_tool_has_one() -> None:
    assert sorted(op["cli"] for op in OPERATIONS) == sorted(_verbs())
    assert len({op["id"] for op in OPERATIONS}) == len(OPERATIONS)
    assert [op["id"] for op in OPERATIONS if (op["admin"] or op["mcp"]) and op["cli"] not in _verbs()] == []
    assert sorted(op["mcp"] for op in OPERATIONS if op["mcp"]) == sorted(SCHEMAS)

def test_every_output_is_a_json_schema() -> None:
    for op in OPERATIONS:
        jsonschema.Draft202012Validator.check_schema(op["output"])

def test_every_noun_verb_argument_and_flag_has_help() -> None:
    parser = build_parser()
    nouns = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    missing = [f"radar {a.dest}" for a in parser._actions if not a.help]
    missing += [f"radar {noun}" for noun in nouns.choices
                if not next(c.help for c in nouns._choices_actions if c.dest == noun)]
    missing += [f"radar {noun} {a.dest}" for noun, np in nouns.choices.items() for a in np._actions if not a.help]
    for command, verb in _verbs().items():
        missing += [f"radar {command} {a.dest}" for a in verb._actions if not a.help]
    assert missing == []

@pytest.mark.parametrize("command", sorted(_verbs()))
def test_a_usage_error_exits_2_with_a_json_error(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        main(["--json", *command.split(), "--no-such-flag"])
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert exited.value.code == 2 and line["level"] == "error" and line["code"] == 2

def test_a_command_with_no_store_exits_2_and_says_so(monkeypatch: pytest.MonkeyPatch,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    assert main(["--json", "catalog", "ask", "a question"]) == 2
    assert json.loads(capsys.readouterr().err.strip().splitlines()[-1])["code"] == 2

def test_model_commands_answer_json_in_their_shape(capsys: pytest.CaptureFixture[str]) -> None:
    outputs = {op["cli"]: op["output"] for op in OPERATIONS}
    for command in (["model", "validate"], ["model", "generate", "--check"]):
        assert main(["--json", *command]) == 0
        jsonschema.validate(json.loads(capsys.readouterr().out), outputs[" ".join(command[:2])])
