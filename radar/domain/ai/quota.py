from __future__ import annotations

import hashlib
import re
import urllib.parse

from radar.domain.ai.answerer import Answerer, Asked, refusal
from radar.domain.ai.meter import Capped, Meter
from radar.domain.model.entities import AskAnswer
from radar.domain.ports.search.ask_ledger import AskLedger
from radar.domain.ports.search.search_engine import SearchEngine
from radar.domain.search.terms import words

ASSISTANTS = {"chatgpt.com": "chatgpt", "chat.openai.com": "chatgpt", "perplexity.ai": "perplexity",
              "www.perplexity.ai": "perplexity", "claude.ai": "claude", "gemini.google.com": "gemini",
              "copilot.microsoft.com": "copilot"}

def counters(event: str, referrer: str) -> dict[str, int]:
    host = (urllib.parse.urlsplit(referrer).hostname or "").lower()
    assistant = ASSISTANTS.get(host)
    site = re.sub(r"[^a-z0-9.-]", "", host.removeprefix("www."))[:60]
    return {event: 1, **({f"from_{assistant}": 1} if assistant else {f"ref_{site}": 1} if site else {})}

def _client(day: str, address: str) -> str:
    return "c" + hashlib.sha256(f"{day} {address}".encode()).hexdigest()[:16]

class Quota:
    def __init__(self, ledger: AskLedger, meter: Meter[Answerer], engine: SearchEngine, release: str) -> None:
        self._ledger, self._meter, self._engine, self._release = ledger, meter, engine, release

    def _asked(self, answerer: Answerer, question: str, locale: str) -> Asked:
        key = hashlib.sha256(f"{locale} {' '.join(words(question))} {self._engine.last_indexed().version} "
                             f"{self._release}".encode()).hexdigest()
        cached = self._ledger.cached(key)
        if cached is not None:
            return Asked(cached, None)
        asked = answerer.ask(question, locale)
        self._ledger.remember(key, asked.answer)
        return asked

    def ask(self, question: str, locale: str, day: str, address: str) -> tuple[AskAnswer, float]:
        try:
            asked, cad = self._meter.call(day, lambda answerer: self._asked(answerer, question, locale),
                                          _client(day, address))
        except Capped:
            return refusal("limit"), 0.0
        self._ledger.count(day, {"refusal" if asked.answer.refused else "answer": 1})
        return asked.answer, cad
