from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from radar.domain.ports.ai.usage_log import Ended, Outcome

ImageKind = Literal["photo", "logo", "banner", "diagram", "other_product", "unrelated"]

@dataclass(frozen=True, slots=True)
class CandidateImage:
    url: str
    content: bytes
    mime: str

@dataclass(frozen=True, slots=True)
class JudgedImage:
    url: str
    kind: ImageKind
    confidence: float
    reason: str

@dataclass(frozen=True, slots=True)
class ImageEvaluation:
    judged: tuple[JudgedImage, ...]
    tokens_in: int
    tokens_out: int

    def ended(self) -> Ended:
        return Ended(Outcome.ANSWERED, self.tokens_in, self.tokens_out)

class ImageJudge(Protocol):
    def judge(self, product_name: str, candidates: tuple[CandidateImage, ...]) -> ImageEvaluation:
        ...
