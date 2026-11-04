from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Prompt:
    id: str
    inputs: tuple[str, ...]
    output_schema: str
    instruction: str
    message: str

    def render(self, **values: str) -> str:
        if set(values) != set(self.inputs):
            raise ValueError(f"prompt {self.id} takes {sorted(self.inputs)}, not {sorted(values)}")
        return self.message.format(**values)
