from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from radar.domain.model.entities import ClaimValue, Source
from radar.domain.ports.ai.usage_log import Ended, Outcome

@dataclass(frozen=True, slots=True)
class Datasheet:
    product: str
    content: bytes
    mime: str
    source: Source

@dataclass(frozen=True, slots=True)
class SpecValue:
    spec_key: str
    value: ClaimValue

@dataclass(frozen=True, slots=True)
class Extraction:
    values: tuple[SpecValue, ...]
    tokens_in: int
    tokens_out: int

    def ended(self) -> Ended:
        return Ended(Outcome.ANSWERED, self.tokens_in, self.tokens_out)

class DatasheetExtractor(Protocol):
    def extract(self, datasheet: Datasheet) -> Extraction:
        ...
