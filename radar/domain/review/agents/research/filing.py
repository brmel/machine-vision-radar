from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Mapping

from radar.domain.model.history.changeset import Change, Changeset, PutEntity, without_version
from radar.domain.model.entities import Claim, Document, FilesOn, Source
from radar.domain.model.history.ids import keyed
from radar.domain.model.history.projection import plain
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.catalog.held_records import HeldRecords
from radar.domain.ports.ai.research_agent import ProposalDraft, RecordsDraft
from radar.domain.ports.review.proposing import Proposing
from radar.domain.ports.review.research_runs import ResearchRun, Step
from radar.domain.ports.web.page_fetcher import Page
from radar.domain.review.agents.drafts import PROVENANCE
from radar.domain.review.proposal import AlreadyProposed, Filed, Unfiled
from radar.domain.review.requests import Agent, Bundle, Changes

RESEARCHER = "research"
Log = Callable[[ResearchRun, Step, str], ResearchRun]

def as_put(entity: Document | Source | Claim) -> dict[str, Any]:
    return without_version(plain(entity))

class Filing:
    def __init__(self, review: Proposing, schema: ModelSchema, held: HeldRecords, log: Log) -> None:
        self._review, self._schema, self._held, self._log = review, schema, held, log
        self._citing = frozenset(e.name for e in schema.entities if any(f.name == "source_refs" for f in e.fields))

    def read(self, page: Page, page_type: str) -> Change:
        held = self._held.matching(Source, "url", page.url)
        source = (replace(held[0], retrieved_at=page.retrieved_at) if held
                  else Source(id=keyed("src", page.url), version=1, type=page_type, url=page.url,
                              title=page.title or None, retrieved_at=page.retrieved_at))
        return Change(PutEntity(as_put(source)), f"Read on {page.url}", "agent", RESEARCHER, (source.id,))

    def cited(self, draft: RecordsDraft, source: str) -> tuple[Change, ...]:
        cited = ({**r, "source_refs": [source]} if self._schema.kind_of(r["id"]) in self._citing else r
                 for r in draft.records)
        return tuple(Change(PutEntity(put), draft.reason, "agent", RESEARCHER, (source,))
                     for put in map(self._over_held, cited) if put)

    def _over_held(self, record: Mapping[str, Any]) -> dict[str, Any] | None:
        held = without_version(self._held.held(record["id"]))
        put = {**held, **record}
        return None if held and all(put[k] == held.get(k) for k in put.keys() - set(PROVENANCE)) else put

    def filed(self, run: ResearchRun, step: Step, draft: ProposalDraft, reason: str, changes: tuple[Change, ...],
              by: Agent, source_url: str | None = None) -> ResearchRun:
        [filing] = self._review.file(Bundle(run.id,
                                            (Changes(FilesOn(draft.files_on), reason, draft.subject, Changeset(changes),
                                                     source_url),)), by)
        for refusal in filing.refusals:
            run = self._log(run, Step.REJECTED, f"{reason}: {refusal}")
        match filing:
            case Filed(proposal):
                return self._log(run, step, proposal.id)
            case AlreadyProposed():
                return self._log(run, Step.SKIPPED, f"{reason}: an open proposal holds it")
            case Unfiled():
                return run
