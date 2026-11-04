from __future__ import annotations

from typing import Protocol

from radar.domain.ai.prompts import Prompt

class PromptRegistry(Protocol):
    def prompt(self, prompt_id: str) -> Prompt:
        ...
