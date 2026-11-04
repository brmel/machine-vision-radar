from __future__ import annotations

import json
from typing import Any

from radar.adapters.ai.adk.runner import AdkRunner
from radar.adapters.ai.adk.specs import specs_json
from radar.domain.ai.prompts import Prompt
from radar.domain.model.entities import ProductCard
from radar.domain.model.history.projection import plain
from radar.domain.model.registry import Registry
from radar.domain.ports.ai.research_agent import FileDraft, Findings, ProposalDraft, Reading, RecordsDraft

MAX_TOKENS, PAGE = 8000, 20_000

def _draft(proposal: dict[str, Any]) -> ProposalDraft:
    files_on, reason, subject = proposal["files_on"], proposal["reason"], proposal["subject"] or None
    if proposal.get("media"):
        return FileDraft(files_on, reason, subject, proposal["media"])
    records = json.loads(proposal["records"] or "[]")
    if not isinstance(records, list) or not all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in records):
        raise ValueError("records is a JSON list of records, each with its id")
    return RecordsDraft(files_on, reason, subject, tuple(records))

def _read_against(registry: Registry, known: tuple[ProductCard, ...]) -> tuple[str, str]:
    categories = {card.category for card in known} or set(registry.categories)
    profiles = [p for p in registry.profiles if p.category_id in categories]
    keys = {k for p in profiles for k in (*p.sections.core, *p.sections.detail)}
    by_category = {p.category_id: {"specs": [*p.sections.core, *p.sections.detail],
                                   "filters": [f.field for f in p.facets]} for p in profiles}
    return specs_json(registry, keys), json.dumps(by_category, ensure_ascii=False)

class AdkResearchAgent:
    def __init__(self, prompt: Prompt, runner: AdkRunner, registry: Registry) -> None:
        self._prompt, self._runner, self._registry = prompt, runner, registry

    def research(self, reading: Reading) -> Findings:
        known = json.dumps([plain(card) for card in reading.known], ensure_ascii=False)
        specs, profiles = _read_against(self._registry, reading.known)
        request = self._prompt.render(maker=reading.maker, url=reading.page.url, retrieved_at=reading.page.retrieved_at,
                                      known=known, terms=json.dumps(reading.terms, ensure_ascii=False), specs=specs,
                                      profiles=profiles, page=reading.page.text[:PAGE],
                                      links="\n".join(reading.page.links))
        reply = self._runner.run("research_agent", self._prompt, request, MAX_TOKENS)
        return reply.read(lambda raw: Findings(tuple(_draft(p) for p in raw["proposals"]), tuple(raw["follow"]),
                                               reply.tokens_in, reply.tokens_out))
