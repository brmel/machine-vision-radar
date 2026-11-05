from __future__ import annotations

from typing import Protocol

from .context import ValidationContext
from .verdict import Findings

class Rule(Protocol):
    def __call__(self, ctx: ValidationContext) -> Findings:
        ...
