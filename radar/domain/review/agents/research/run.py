from __future__ import annotations

import time
from dataclasses import replace
from datetime import date, timedelta
from typing import Callable
from urllib.parse import urlsplit

from radar.domain.ai.meter import Capped, Meter
from radar.domain.model.history.changeset import Change
from radar.domain.model.entities import ResearchMeasures
from radar.domain.model.model import Model
from radar.domain.ports.ai.image_judge import ImageJudge
from radar.domain.ports.ai.research_agent import FileDraft, ProposalDraft, Reading, RecordsDraft, ResearchAgent
from radar.domain.ports.ai.usage_log import Unparsed
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.catalog.held_records import HeldRecords
from radar.domain.ports.review.agent_tokens import AgentTokens
from radar.domain.ports.review.proposing import Proposing
from radar.domain.ports.review.research_runs import (Ending, Line, Outcome, ResearchRun, ResearchRunLog, RunPage,
                                                     Status, Step)
from radar.domain.ports.web.page_fetcher import Page, PageFetcher, Unfetchable
from radar.domain.review.agents.drafts import corrected, minted, naming, references, resolved, terms, words
from radar.domain.review.agents.files import Files
from radar.domain.review.agents.research.filing import RESEARCHER, Filing
from radar.domain.review.agents.research.media import Media
from radar.domain.review.agents.research.sites import RunScope, Site, sites_of
from radar.domain.review.agents.runs import Measure
from radar.domain.review.agents.tokens import Limits, Scope, issue
from radar.domain.review.requests import Agent, Founder, Job

PAGES, SECONDS, FOLLOW = 8, 40.0, 5

def _followed(site: Site, page: Page, follow: tuple[str, ...], seen: set[str]) -> list[tuple[Site, str]]:
    host = urlsplit(site.url).netloc
    return [(site, link) for link in dict.fromkeys(follow) if link in page.links and urlsplit(link).netloc == host
            and link not in seen][:FOLLOW]

def _read_through(run: ResearchRun) -> tuple[Ending, str]:
    return ((Status.DONE, "every page in reach is read") if run.said(Step.READ)
            else (Status.BLOCKED, "no page in reach could be read"))

class Researcher:
    def __init__(self, meter: Meter[ResearchAgent], judge: Meter[ImageJudge], fetcher: PageFetcher, files: Files,
                 review: Proposing, runs: ResearchRunLog, tokens: AgentTokens, read: CatalogRepository,
                 held: HeldRecords, model: Model, now: Callable[[], str],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._meter, self._fetcher, self._runs, self._tokens, self._read, self._held = (
            meter, fetcher, runs, tokens, read, held)
        self._now, self._clock = now, clock
        registry = model.registry
        self._page_type = next(k for k, t in registry.vocabularies["source_types"].items() if t.research)
        self._terms, self._refs = terms(model), references(model.schema)
        self._specs, self._words = registry.spec_definitions, words(registry)
        self._filing = Filing(review, model.schema, held, self._log)
        self._media = Media(fetcher, files, judge, self._filing, self._log, now)
        self._measure = Measure(runs, review, read, held, model)

    def start(self, scope: RunScope, by: Founder | Job) -> str:
        sites = sites_of(scope, self._held.organizations(), self._read)
        now = self._now()
        token, _ = issue(RESEARCHER, Scope.PROPOSE, date.fromisoformat(now[:10]) + timedelta(days=1), Limits(), now)
        self._tokens.issue(token)
        run = ResearchRun(by.correlation_id, scope.key, by.name, now, token.id)
        self._runs.save(run)
        try:
            self._loop(run, sites, Agent(token, run.id))
        except Exception as exc:
            self._end(self._runs.get(run.id), Status.FAILED, f"{type(exc).__name__}: {exc}")
            raise
        finally:
            self._tokens.revoke(token.id, self._now())
        return run.id

    def status(self, run: str) -> ResearchRun:
        return self._runs.get(run)

    def cancel(self, run: str) -> ResearchRun:
        found = self._runs.get(run)
        if found.outcome:
            raise ValueError(f"{run} is {found.outcome.status.value}: only a running run is cancelled")
        self._runs.cancel(run, self._now())
        return self._runs.get(run)

    def runs(self, cursor: str | None = None) -> RunPage:
        return self._runs.page(cursor)

    def measure(self, since: str, by: Founder) -> ResearchMeasures:
        return self._measure.since(since, by)

    def _loop(self, run: ResearchRun, sites: tuple[Site, ...], by: Agent) -> ResearchRun:
        started, reach, seen = self._clock(), [(s, s.url) for s in sites], set()
        left = lambda: SECONDS - (self._clock() - started)
        while reach:
            site, url = reach.pop(0)
            if url in seen:
                continue
            if stop := self._stop(run, left()):
                return self._end(run, *stop)
            seen.add(url)
            try:
                page = self._fetcher.fetch(url, left())
            except Unfetchable as exc:
                run = self._log(run, Step.SKIPPED, f"{url}: {exc}")
                continue
            run, read = self._log(run, Step.READ, page.url), self._filing.read(page, self._page_type)
            seen.add(page.url)
            if site.target_product and url == site.url:
                run, capped = self._media.photo(run, site.products[0], page, read, by, left)
                if capped:
                    return self._end(run, Status.CAPPED, capped)
            run, capped, follow = self._research(run, Reading(page, site.org, site.products, self._terms), read, by,
                                                 left)
            if capped:
                return self._end(run, Status.CAPPED, capped)
            reach += _followed(site, page, follow, seen)
        return self._end(run, *_read_through(run))

    def _stop(self, run: ResearchRun, left: float) -> tuple[Ending, str] | None:
        stored = self._runs.get(run.id).outcome
        if stored and stored.status is Status.CANCELLED:
            return Status.CANCELLED, stored.reason
        if len(run.said(Step.READ)) >= PAGES:
            return Status.PARTIAL, f"its budget of {PAGES} pages is read"
        return (Status.PARTIAL, f"its {SECONDS:g} s are spent") if left < 0 else None

    def _research(self, run: ResearchRun, reading: Reading, read: Change, by: Agent,
                  left: Callable[[], float]) -> tuple[ResearchRun, str | None, tuple[str, ...]]:
        try:
            findings, cad = self._meter.call(self._now()[:10], lambda agent: agent.research(reading))
        except Capped as exc:
            return run, str(exc), ()
        except Unparsed as exc:
            return self._log(replace(run, cad=run.cad + exc.cad), Step.REJECTED,
                             f"{reading.page.url}: the model's answer is refused: {exc}"), None, ()
        run = replace(run, cad=run.cad + cad)
        for draft in findings.proposals:
            if left() < 0:
                return self._log(run, Step.SKIPPED,
                                 f"{draft.url if isinstance(draft, FileDraft) else draft.reason}: its {SECONDS:g} s "
                                 "are spent"), None, ()
            run = self._filed(run, draft, reading, read, by, left)
        return run, None, findings.follow

    def _filed(self, run: ResearchRun, draft: ProposalDraft, reading: Reading, read: Change, by: Agent,
               left: Callable[[], float]) -> ResearchRun:
        match draft:
            case FileDraft():
                return self._media.linked(run, draft, {card.id for card in reading.known}, reading.page, read, by, left)
            case RecordsDraft():
                draft = minted(corrected(resolved(draft, self._specs, self._words), self._held.ranked_first), run.id,
                               lambda i: self._held.held(i) is not None)
                if stray := self._stray(draft, reading):
                    return self._log(run, Step.REJECTED, f"{draft.reason}: {stray}")
                cited = self._filing.cited(draft, read.entity)
                return (self._filing.filed(run, Step.FILED, draft, draft.reason, (read, *cited), by) if cited
                        else self._log(run, Step.SKIPPED, f"{draft.reason}: the store holds it"))

    def _stray(self, draft: RecordsDraft, reading: Reading) -> str | None:
        given = {card.id for card in reading.known} | {reading.maker} | {r["id"] for r in draft.records}
        named = [("subject", draft.subject)] + [ref for r in draft.records for ref in naming(r, self._refs)]
        return next((f"{w}: {ref} is none of the cards, the maker or the records of the proposal" for w, ref in named
                     if ref and ref not in given), None)

    def _log(self, run: ResearchRun, step: Step, detail: str) -> ResearchRun:
        logged = run.logged(Line(self._now(), step, detail))
        self._runs.save(logged)
        return logged

    def _end(self, run: ResearchRun, status: Ending, why: str) -> ResearchRun:
        now = self._now()
        ended = replace(run.logged(Line(now, Step.ENDED, why)), outcome=Outcome(status, why, now))
        self._runs.save(ended)
        return ended
