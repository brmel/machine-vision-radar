from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from radar.domain.ports.ai.answer_model import Sentence
from radar.domain.ports.search.retriever import Evidence

@dataclass(frozen=True, slots=True)
class ArticleText:
    title: str
    summary: str
    sentences: tuple[Sentence, ...]
    tokens_in: int
    tokens_out: int

class ArticleModel(Protocol):
    def draft(self, subject: Evidence, about: str, locale: str) -> ArticleText:
        ...
