from __future__ import annotations

from typing import Mapping, Protocol

from radar.domain.model.entities import AskAnswer

class AskLedger(Protocol):
    def cached(self, key: str) -> AskAnswer | None:
        ...

    def remember(self, key: str, answer: AskAnswer) -> None:
        ...

    def count(self, day: str, events: Mapping[str, int]) -> None:
        ...

    def counted(self, day: str) -> Mapping[str, int]:
        ...
