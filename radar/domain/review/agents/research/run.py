from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Callable

from radar.domain.ai.meter import Capped, Meter
from radar.domain.model.history.changeset import Change, as_record
from radar.domain.model.history.projection import every_page
from radar.domain.model.entities import (FrontierView, Instant, OrgRelation, ResearchMeasures, RunScope, RunScopeKind,
                                         Standing)
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
from radar.domain.ports.web.crawl_records import CrawlRecords
from radar.domain.ports.web.reader import Page, Reader, Unread
from radar.domain.review.agents.drafts import corrected, minted, naming, references, resolved, terms, words
from radar.domain.review.agents.files import Files
from radar.domain.review.agents.research.filing import RESEARCHER, Filing
from radar.domain.review.agents.research.frontier import Frontier, Reach, Site, SourceTypes, sites_of
from radar.domain.review.agents.research.media import Media
from radar.domain.review.agents.research.tables import Tables, named_card
from radar.domain.review.agents.runs import Measure
from radar.domain.review.agents.tokens import AgentToken, Limits, Scope, Throttled, issue
from radar.domain.review.requests import Agent, Founder, Job

PAGES, SECONDS, ENOUGH = 8, 40.0, 3
DEAD_AFTER = SECONDS + 60

def _deadline(now: Instant) -> Instant:
    return (datetime.fromisoformat(now) + timedelta(seconds=SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")

def _read_through(run: ResearchRun) -> tuple[Ending, str]:
    return ((Status.DONE, "every page in reach is read") if run.said(Step.READ)
            else (Status.BLOCKED, "no page in reach could be read"))

class Researcher:
    def __init__(self, meter: Meter[ResearchAgent], judge: Meter[ImageJudge], reader: Reader, files: Files,
                 review: Proposing, runs: ResearchRunLog, tokens: AgentTokens, read: CatalogRepository,
                 held: HeldRecords, crawl: CrawlRecords, model: Model, now: Callable[[], str]) -> None:
        self._meter, self._reader, self._runs, self._tokens, self._read, self._held, self._crawl, self._now = (
            meter, reader, runs, tokens, read, held, crawl, now)
        registry = model.registry
        self._owning = registry.marked("org_relation_types", lambda t: t.owns)
        self._terms, self._refs = terms(model), references(model.schema)
        self._specs, self._words = registry.spec_definitions, words(registry)
        self._filing = Filing(review, model, held, self._log, tokens, now)
        self._types = SourceTypes(registry.vocabularies["source_types"])
        self._media = Media(reader, files, judge, self._filing, self._types, self._log, now)
        self._tables = Tables(registry, self._words)
        self._methods = registry.vocabularies["claim_methods"]
        self._language = registry.default_language.code
        self._measure = Measure(runs, review, read, held, model)

    def start(self, scope: RunScope, by: Founder | Job) -> str:
        owning = tuple(r for t in sorted(self._owning) for r in self._held.matching(OrgRelation, "type", t))
        sites = sites_of(scope, self._held.organizations(), owning, self._read)
        now = self._now()
        self._settle(now)
        token = self._day_token(now)
        run = ResearchRun(by.correlation_id, scope, by.name, now, token.id)
        self._runs.save(run)
        try:
            self._loop(run, self._frontier(sites), Agent(token, run.id))
        except Exception as exc:
            self._end(self._runs.get(run.id), Status.FAILED, f"{type(exc).__name__}: {exc}")
            raise
        return run.id

    def _frontier(self, sites: tuple[Site, ...]) -> Frontier:
        return Frontier(self._reader, sites, self._crawl, self._language, self._now)

    def due_makers(self) -> tuple[RunScope, ...]:
        return tuple(RunScope(kind=RunScopeKind.MAKER, key=org) for org in self._crawl.due(self._now()))

    def frontier(self, org: str, seed: bool) -> FrontierView:
        scope = RunScope(kind=RunScopeKind.MAKER, key=org)
        owning = tuple(r for t in sorted(self._owning) for r in self._held.matching(OrgRelation, "type", t))
        [site] = sites_of(scope, self._held.organizations(), owning, self._read)
        frontier = self._frontier((site,))
        if seed:
            reach = frontier.next()
            if isinstance(reach, Reach) and (unread := frontier.seed(reach, _deadline(self._now()))):
                raise ValueError(f"{unread.address}: {unread.reason}")
        return frontier.view(site.org)

    def _settle(self, now: Instant) -> None:
        unended = [run for page in every_page(self._runs.page) for run in page.runs if not run.outcome]
        read = [run.as_of(now, DEAD_AFTER) for run in unended]
        live = {run.token for run in read if not run.outcome}
        for run in filter(lambda r: r.outcome, read):
            self._runs.save(run)
            if run.token not in live:
                self._tokens.revoke(run.token, now)

    def _day_token(self, now: str) -> AgentToken:
        today = date.fromisoformat(now[:10])
        for held in self._tokens.page()[0]:
            if held.name == RESEARCHER and held.standing(today) is Standing.ACTIVE:
                return held
        token, _ = issue(RESEARCHER, Scope.PROPOSE, today + timedelta(days=1), Limits(), now)
        self._tokens.issue(token)
        return token

    def status(self, run: str) -> ResearchRun:
        return self._runs.get(run).as_of(self._now(), DEAD_AFTER)

    def cancel(self, run: str) -> ResearchRun:
        found = self._runs.get(run)
        if found.outcome:
            raise ValueError(f"{run} is {found.outcome.status.value}: only a running run is cancelled")
        self._runs.cancel(run, self._now())
        return self._runs.get(run)

    def runs(self, cursor: str | None = None) -> RunPage:
        page = self._runs.page(cursor)
        return replace(page, runs=tuple(run.as_of(self._now(), DEAD_AFTER) for run in page.runs))

    def measure(self, since: str, by: Founder) -> ResearchMeasures:
        return self._measure.since(since, by)

    def _loop(self, run: ResearchRun, frontier: Frontier, by: Agent) -> ResearchRun:
        deadline = _deadline(self._now())
        while (reach := frontier.next()) is not None:
            if stop := self._stop(run, deadline):
                return self._end(run, *stop)
            match reach:
                case Unread():
                    run = self._skipped(run, reach)
                case Reach():
                    try:
                        run, capped = self._visit(run, frontier, reach, by, deadline)
                    except Throttled as exc:
                        return self._end(self._runs.get(run.id), Status.CAPPED, f"the research token is {exc}")
                    if capped:
                        return self._end(run, Status.CAPPED, capped)
        return self._end(run, *_read_through(run))

    def _stop(self, run: ResearchRun, deadline: Instant) -> tuple[Ending, str] | None:
        stored = self._runs.get(run.id).outcome
        if stored and stored.status is Status.CANCELLED:
            return Status.CANCELLED, stored.reason
        if len(run.said(Step.READ)) >= PAGES:
            return Status.PARTIAL, f"its budget of {PAGES} pages is read"
        return (Status.PARTIAL, f"its {SECONDS:g} s are spent") if self._now() > deadline else None

    def _visit(self, run: ResearchRun, frontier: Frontier, reach: Reach, by: Agent,
               deadline: Instant) -> tuple[ResearchRun, str | None]:
        if unmapped := frontier.mapped(reach, deadline):
            run = self._skipped(run, unmapped)
        page = self._reader.page(reach.link, deadline)
        if isinstance(page, Unread):
            frontier.unread(reach, page)
            return self._skipped(run, page), None
        run = self._log(run, Step.READ, page.link.address)
        if frontier.unchanged(reach, page):
            frontier.read(reach, page, ())
            return self._log(run, Step.SKIPPED, f"{page.link.address}: unchanged since it was last read"), None
        read = self._filing.read(page, self._types.of(page.link, reach.own))
        if reach.home and reach.site.one_product:
            run, capped = self._media.photo(run, reach.site.products[0], page, read, by, deadline)
            if capped:
                return run, capped
        run, capped, follow = self._research(run, reach, page, read, by, deadline)
        frontier.read(reach, page, follow)
        return run, capped

    def _tabled(self, run: ResearchRun, reach: Reach, page: Page, read: Change, by: Agent,
                deadline: Instant) -> ResearchRun | None:
        card = named_card(page, reach.site.products) if self._method(read) in self._methods else None
        table = self._tables.read(page, card) if card else None
        if not card or not table or len(table.claims) < ENOUGH:
            return None
        address = page.link.address
        records = tuple({"id": f"clm_{card.id}_{key}", "subject": card.id, "spec_key": key, "value": value}
                        for key, value in table.claims)
        draft = RecordsDraft("update", f"The maker's table on {address} states {len(records)} of its values", card.id,
                             records)
        run = self._filed(run, draft, reach, page, read, by, deadline)
        if table.unmatched:
            run = self._log(run, Step.SKIPPED, f"{address}: labels no spec names: {', '.join(table.unmatched)}")
        return run

    def _research(self, run: ResearchRun, reach: Reach, page: Page, read: Change, by: Agent,
                  deadline: Instant) -> tuple[ResearchRun, str | None, tuple[str, ...]]:
        if (tabled := self._tabled(run, reach, page, read, by, deadline)) is not None:
            return tabled, None, ()
        reading = Reading(page, reach.site.org, reach.site.products, self._terms)
        try:
            findings, cad = self._meter.call(self._now()[:10], lambda agent: agent.research(reading))
        except Capped as exc:
            return run, str(exc), ()
        except Unparsed as exc:
            return self._log(replace(run, cad=run.cad + exc.cad), Step.REJECTED,
                             f"{page.link.address}: the model's answer is refused: {exc}"), None, ()
        run = replace(run, cad=run.cad + cad)
        for draft in findings.proposals:
            if self._now() > deadline:
                return self._log(run, Step.SKIPPED,
                                 f"{draft.url if isinstance(draft, FileDraft) else draft.reason}: its {SECONDS:g} s "
                                 "are spent"), None, ()
            run = self._filed(run, draft, reach, page, read, by, deadline)
        return run, None, findings.follow

    def _filed(self, run: ResearchRun, draft: ProposalDraft, reach: Reach, page: Page, read: Change, by: Agent,
               deadline: Instant) -> ResearchRun:
        match draft:
            case FileDraft():
                return self._media.linked(run, draft, reach, page, read, by, deadline)
            case RecordsDraft():
                draft = minted(corrected(self._stamped(resolved(draft, self._specs, self._words), page, read),
                                         self._held.ranked_first), run.id, lambda i: self._held.held(i) is not None)
                if stray := self._stray(draft, reach):
                    return self._log(run, Step.REJECTED, f"{draft.reason}: {stray}")
                cited, refused = self._filing.cited(draft, read.entity)
                if refused:
                    run = self._log(run, Step.REJECTED, f"{draft.reason}: {refused}")
                if cited:
                    return self._filing.filed(run, Step.FILED, draft, draft.reason, (read, *cited), by)
                return run if refused else self._log(run, Step.SKIPPED, f"{draft.reason}: the store holds it")

    def _method(self, read: Change) -> str:
        return str(as_record(read.action.entity)["type"])

    def _stamped(self, draft: RecordsDraft, page: Page, read: Change) -> RecordsDraft:
        stamp = {"method": self._method(read), "recorded_at": page.retrieved_at, "rank": 1}
        return replace(draft, records=tuple({**r, **stamp} if "spec_key" in r else r for r in draft.records))

    def _stray(self, draft: RecordsDraft, reach: Reach) -> str | None:
        given = {card.id for card in reach.site.products} | {reach.site.org} | {r["id"] for r in draft.records}
        named = [("subject", draft.subject)] + [ref for r in draft.records for ref in naming(r, self._refs)]
        return next((f"{w}: {ref} is none of the cards, the maker or the records of the proposal" for w, ref in named
                     if ref and ref not in given), None)

    def _skipped(self, run: ResearchRun, unread: Unread) -> ResearchRun:
        return self._log(run, Step.SKIPPED, f"{unread.address}: {unread.reason}")

    def _log(self, run: ResearchRun, step: Step, detail: str) -> ResearchRun:
        logged = run.logged(Line(self._now(), step, detail))
        self._runs.save(logged)
        return logged

    def _end(self, run: ResearchRun, status: Ending, why: str) -> ResearchRun:
        now = self._now()
        ended = replace(run.logged(Line(now, Step.ENDED, why)), outcome=Outcome(status, why, now))
        self._runs.save(ended)
        return ended
