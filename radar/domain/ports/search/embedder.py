from __future__ import annotations

from typing import Protocol, Sequence

from radar.domain.model.entities import EmbedderModel

class Embedder(Protocol):
    @property
    def model(self) -> EmbedderModel:
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...
