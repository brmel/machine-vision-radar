from __future__ import annotations

import json
from typing import Any

from radar.domain.ai.prompts import Prompt
from radar.adapters.ai.prompted.reply import read
from radar.domain.ports.ai.prompts import ModelRunner
from radar.adapters.files.model_json import LANGUAGES as CONTRACT_LANGUAGES
from radar.domain.ports.ai.answer_model import AnswerText, NeedText, Sentence
from radar.domain.ports.search.retriever import Evidence

LANGUAGES = {l.code: l.name for l in CONTRACT_LANGUAGES}
MAX_TOKENS = 800

def evidence_json(evidence: Evidence) -> str:
    return json.dumps([{"id": p.id, "name": p.name, "vendor": p.vendor, "category": p.category, "summary": p.summary,
                        "values": [{"spec": f.label, "value": f.value, **({"source": f.source} if f.source else {})}
                                   for f in p.facts],
                        "sources": [{"id": s.id, "title": s.title} for s in p.sources]} for p in evidence.products],
                      ensure_ascii=False)

def sentences_of(raw: Any) -> tuple[Sentence, ...]:
    return tuple(Sentence(s["text"], tuple(s["cites"])) for s in raw["sentences"])

def _text(raw: Any, tokens_in: int, tokens_out: int) -> AnswerText:
    needs = tuple(NeedText(n["need"], sentences_of(n)) for n in raw.get("needs", ()))
    return AnswerText(() if needs else sentences_of(raw), tokens_in, tokens_out, needs)

class PromptedAnswerModel:
    def __init__(self, prompt: Prompt, runner: ModelRunner) -> None:
        self._prompt, self._runner = prompt, runner

    def answer(self, question: str, evidence: Evidence, locale: str) -> AnswerText:
        request = self._prompt.render(language=LANGUAGES.get(locale, locale), evidence=evidence_json(evidence),
                                      question=question)
        reply = self._runner.reply("catalog_answerer", self._prompt, request, MAX_TOKENS)
        return read(reply, lambda raw: _text(raw, reply.tokens_in, reply.tokens_out))
