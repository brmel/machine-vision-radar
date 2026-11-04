from __future__ import annotations

import re
from typing import Iterable, Sequence

from radar.domain.ports.ai.answer_model import Sentence
from radar.domain.ports.search.retriever import Evidence

NUMBER = re.compile(r"\d+(?:[.,   ]\d+)*")

def _numbers(text: str) -> list[tuple[str, tuple[str, ...]]]:
    found = [m.group() for m in NUMBER.finditer(text)]
    return [("".join(re.findall(r"\d+", n)), tuple(re.findall(r"\d+", n))) for n in found]

def _texts(evidence: Evidence) -> Iterable[str]:
    for p in evidence.products:
        yield from (p.id, p.name, p.vendor, p.category, p.summary)
        yield from (t for f in p.facts for t in (f.label, f.value))
        yield from (s.title for s in p.sources)

def _unbacked(sentence: Sentence, ids: frozenset[str], known: set[str]) -> str | None:
    foreign = [c for c in sentence.cites if c not in ids]
    unknown = [joined for joined, parts in _numbers(sentence.text) if joined not in known and not set(parts) <= known]
    if not sentence.cites:
        return "cites nothing"
    if foreign:
        return f"cites {foreign[0]}, which is not in the evidence"
    return f"states {unknown[0]}, which is not in the evidence" if unknown else None

def ungrounded(sentences: Sequence[Sentence], evidence: Evidence, given: str = "") -> str | None:
    if not sentences:
        return "no sentence"
    known = {part for text in (*_texts(evidence), given) for joined, parts in _numbers(text)
             for part in (joined, *parts)}
    reasons = ((n, _unbacked(s, evidence.ids(), known)) for n, s in enumerate(sentences, 1))
    return next((f"sentence {n} {reason}" for n, reason in reasons if reason), None)
