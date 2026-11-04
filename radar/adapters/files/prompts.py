from __future__ import annotations

from pathlib import Path

from radar.domain.ai.prompts import Prompt

def _sections(text: str) -> dict[str, str]:
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = out.setdefault(line[3:].strip(), [])
        elif current is not None:
            current.append(line)
    return {name: "\n".join(lines).strip("\n") for name, lines in out.items()}

def parse_prompt(text: str, prompt_id: str) -> Prompt:
    sections = _sections(text)
    inputs = tuple(line.split("`")[1] for line in sections["Inputs"].splitlines() if line.startswith("- `"))
    schema = sections["Output"].removeprefix("```json").removesuffix("```").strip()
    return Prompt(prompt_id, inputs, schema, sections["Instruction"], sections["Message"])

class FilesPromptRegistry:
    def __init__(self, root: Path) -> None:
        self._root = root

    def prompt(self, prompt_id: str) -> Prompt:
        path = self._root / f"{prompt_id}.md"
        if not path.is_file():
            raise LookupError(f"no prompt {prompt_id} in {self._root}")
        return parse_prompt(path.read_text(encoding="utf-8"), prompt_id)
