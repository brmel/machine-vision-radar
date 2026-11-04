from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from radar.domain.ai.grounding import ungrounded
from radar.domain.ports.ai.usage_log import Ended, Outcome
from radar.domain.model.entities import AskAnswer, AskNeed, Citation
from radar.domain.ports.ai.answer_model import AnswerModel, AnswerText, NeedText, Sentence
from radar.domain.ports.search.retriever import Evidence, EvidenceProduct, Retriever

def refusal(reason: str) -> AskAnswer:
    return AskAnswer(answer="", citations=(), refused=True, reason=reason)

def _citations(cites: Sequence[str], evidence: Evidence) -> list[Citation]:
    products = [p for p in evidence.products if p.id in cites]
    ids = {p.id for p in evidence.products}
    out = [Citation(product=_backer(c, products, evidence), source=c) for c in cites if c not in ids]
    return out + [Citation(product=p.id) for p in products if p.id not in {c.product for c in out}]

def _backer(source: str, cited: Sequence[EvidenceProduct], evidence: Evidence) -> str:
    return [p for p in (*cited, *evidence.products) if any(s.id == source for s in p.sources)][0].id

def _cited(sentences: Sequence[Sentence], evidence: Evidence) -> tuple[str, tuple[Citation, ...]]:
    citations: list[Citation] = []
    for sentence in sentences:
        citations += [c for c in _citations(sentence.cites, evidence) if c not in citations]
    return " ".join(s.text.strip() for s in sentences), tuple(citations)

def _need(need: NeedText, evidence: Evidence) -> AskNeed:
    answer, citations = _cited(need.sentences, evidence)
    return AskNeed(need=need.need, answer=answer, citations=citations)

def cited(text: AnswerText, evidence: Evidence) -> AskAnswer:
    if not text.needs:
        answer, citations = _cited(text.sentences, evidence)
        return AskAnswer(answer=answer, citations=citations, refused=False)
    needs = tuple(_need(n, evidence) for n in text.needs)
    every = tuple(dict.fromkeys(c for n in needs for c in n.citations))
    return AskAnswer(answer="", citations=every, needs=needs, refused=False)

@dataclass(frozen=True, slots=True)
class Asked:
    answer: AskAnswer
    text: AnswerText | None
    rejected: str | None = None

    def ended(self) -> Ended | None:
        if self.text is None:
            return None
        return Ended(Outcome.REFUSED if self.answer.refused else Outcome.ANSWERED, self.text.tokens_in,
                     self.text.tokens_out, self.rejected)

class Answerer:
    def __init__(self, retriever: Retriever, model: AnswerModel) -> None:
        self._retriever, self._model = retriever, model

    def ask(self, question: str, locale: str) -> Asked:
        evidence = self._retriever.evidence(question, locale)
        if not evidence.products:
            return Asked(refusal("off_topic"), None)
        text = self._model.answer(question, evidence, locale)
        reason = ungrounded(text.every_sentence(), evidence, question)
        return Asked(refusal("not_enough_evidence"), text, reason) if reason else Asked(cited(text, evidence), text)
