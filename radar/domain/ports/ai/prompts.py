from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from radar.domain.ai.prompts import Prompt

class PromptRegistry(Protocol):
    def prompt(self, prompt_id: str) -> Prompt:
        ...

@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    tokens_in: int
    tokens_out: int
    prompt: str

class ModelRunner(Protocol):
    def reply(self, agent: str, prompt: Prompt, request: str, max_tokens: int,
              file: tuple[bytes, str] | None = None) -> Reply:
        ...
