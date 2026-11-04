from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from radar.domain.ports.search.retriever import Evidence

@dataclass(frozen=True, slots=True)
class Sentence:
    text: str
    cites: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class NeedText:
    need: str
    sentences: tuple[Sentence, ...]

@dataclass(frozen=True, slots=True)
class AnswerText:
    sentences: tuple[Sentence, ...]
    tokens_in: int
    tokens_out: int
    needs: tuple[NeedText, ...] = ()

    def every_sentence(self) -> tuple[Sentence, ...]:
        return (*self.sentences, *(s for n in self.needs for s in n.sentences))

class AnswerModel(Protocol):
    def answer(self, question: str, evidence: Evidence, locale: str) -> AnswerText:
        ...
