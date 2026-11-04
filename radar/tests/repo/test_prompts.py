from __future__ import annotations

import ast
import json
import re
import string

from radar import paths
from radar.adapters.files.prompts import parse_prompt

RADAR = paths.DEV / "radar"
INSTRUCTION_ARGS = {"instruction", "static_instruction", "system_instruction"}

def inline_instructions(source: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.keyword) and node.arg in INSTRUCTION_ARGS
                and not (isinstance(node.value, ast.Attribute) and node.value.attr == "instruction")):
            lines.append(node.value.lineno)
        named = isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
                                                     and ("PROMPT" in t.id or "INSTRUCTION" in t.id)
                                                     for t in node.targets)
        if named and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            lines.append(node.lineno)
    return lines

def test_every_prompt_fills_its_inputs_and_returns_a_json_schema() -> None:
    prompts = [parse_prompt(p.read_text(encoding="utf-8"), p.stem) for p in sorted(paths.PROMPTS.glob("*.md"))]
    assert prompts, "the registry holds the ask prompt at least"
    for p in prompts:
        assert {name for _, name, _, _ in string.Formatter().parse(p.message) if name} == set(p.inputs), p.id
        assert p.instruction.strip() and json.loads(p.output_schema)["type"] == "object", p.id
        assert p.render(**{name: name for name in p.inputs})

def test_each_prompt_is_one_file_named_by_its_use_alone() -> None:
    found = [p.relative_to(paths.PROMPTS).as_posix() for p in sorted(paths.PROMPTS.rglob("*"))]
    assert [f for f in found if not re.fullmatch(r"[a-z_]+\.md", f)] == []

def test_a_prompt_written_in_code_is_found_on_a_fixture() -> None:
    fixture = ('INSTRUCTION = """Answer briefly."""\n'
               'agent = LlmAgent(static_instruction="Be terse.")\n'
               'agent = LlmAgent(static_instruction=INSTRUCTION)\n'
               'agent = LlmAgent(static_instruction=prompt.instruction)\n')
    assert inline_instructions(fixture) == [1, 2, 3]

def test_no_model_instruction_is_written_in_code() -> None:
    found = [f"{p.relative_to(paths.DEV)}:{n}" for p in sorted(RADAR.rglob("*.py")) if "tests" not in p.parts
             for n in inline_instructions(p.read_text(encoding="utf-8"))]
    assert found == []
