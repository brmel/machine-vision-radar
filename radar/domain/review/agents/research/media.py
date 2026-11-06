from __future__ import annotations

from dataclasses import replace
from typing import Callable

from radar.domain.ai.meter import Capped, Meter
from radar.domain.model.entities import Instant, ProductCard
from radar.domain.model.history.changeset import Change, PutEntity
from radar.domain.ports.ai.image_judge import CandidateImage, ImageJudge
from radar.domain.ports.ai.research_agent import FileDraft
from radar.domain.ports.ai.usage_log import Unparsed
from radar.domain.ports.review.research_runs import ResearchRun, Step
from radar.domain.ports.web.reader import File, Link, Page, Reader, Unread
from radar.domain.review.agents.files import Files, Staged
from radar.domain.review.agents.research.filing import RESEARCHER, Filing, Log
from radar.domain.review.agents.research.frontier import Reach, SourceTypes
from radar.domain.review.requests import Agent

PHOTOS = 3

def _squeezed(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())

def _likeliest(images: tuple[Link, ...], name: str) -> list[Link]:
    return sorted(images, key=lambda i: _squeezed(name) not in _squeezed(i.address.rpartition("/")[2]))

class Media:
    def __init__(self, reader: Reader, files: Files, judge: Meter[ImageJudge], filing: Filing, types: SourceTypes,
                 log: Log, now: Callable[[], str]) -> None:
        self._reader, self._files, self._judge, self._filing, self._types, self._log, self._now = (
            reader, files, judge, filing, types, log, now)

    def photo(self, run: ResearchRun, product: ProductCard, page: Page, read: Change, by: Agent,
              deadline: Instant) -> tuple[ResearchRun, str | None]:
        address = page.link.address
        files, run = self._candidates(_likeliest(page.images, product.name)[:PHOTOS], run, deadline)
        if not files:
            return self._log(run, Step.SKIPPED, f"{address}: no candidate images found"), None
        try:
            candidates = tuple(CandidateImage(a, f.content, f.mime) for a, f in files.items())
            judged, cad = self._judge.call(self._now()[:10], lambda j: j.judge(product.name, candidates))
        except Capped as exc:
            return run, str(exc)
        except Unparsed as exc:
            return (self._log(replace(run, cad=run.cad + exc.cad), Step.REJECTED, f"{address}: judge error: {exc}"),
                    None)
        run = replace(run, cad=run.cad + cad)
        best_url = judged.best_photo()
        if not best_url or best_url not in files:
            return self._log(run, Step.SKIPPED, f"{address}: no suitable product photo"), None
        best = files[best_url]
        draft = FileDraft("update", f"The maker's page shows a photo of {product.name}", product.id, best.link.address)
        document = Change(PutEntity(self._files.staged(best, product.id).document), draft.reason, "agent",
                          RESEARCHER, read.source_refs)
        return self._filing.filed(run, Step.FILED, draft, draft.reason, (read, document), by, best.link.address), None

    def _candidates(self, links: tuple[Link, ...], run: ResearchRun, deadline: Instant) -> tuple[
            dict[str, File], ResearchRun]:
        files: dict[str, File] = {}
        for link in links:
            if self._now() > deadline:
                break
            match self._reader.file(link, deadline):
                case File() as file:
                    files[link.address] = file
                case Unread(address, reason):
                    run = self._log(run, Step.SKIPPED, f"{address}: {reason}")
        return files, run

    def linked(self, run: ResearchRun, draft: FileDraft, reach: Reach, page: Page, read: Change, by: Agent,
               deadline: Instant) -> ResearchRun:
        link = next((link for link in page.links if link.address == draft.url), None)
        if link is None:
            return self._log(run, Step.REJECTED, f"{draft.url}: not one of the page's links")
        if draft.subject not in {card.id for card in reach.site.products}:
            return self._log(run, Step.REJECTED, f"{draft.url}: the file is for none of the cards' products")
        file = self._reader.file(link, deadline)
        if isinstance(file, Unread):
            return self._log(run, Step.SKIPPED, f"{file.address}: {file.reason}")
        staged = self._files.staged(file, draft.subject)
        document = Change(PutEntity(staged.document), draft.reason, "agent", RESEARCHER, read.source_refs)
        filed = self._filing.filed(run, Step.MEDIA, draft, draft.reason, (read, document), by, file.link.address)
        return self._datasheet(filed, draft, staged, self._types.of(file.link, reach.own, staged.document.kind), by)

    def _datasheet(self, run: ResearchRun, draft: FileDraft, staged: Staged, source_type: str,
                   by: Agent) -> ResearchRun:
        address = staged.file.link.address
        try:
            stated = self._files.stated(staged, source_type, self._now()[:10])
        except Capped as exc:
            return self._log(run, Step.REJECTED, f"{address}: {exc}")
        except Unparsed as exc:
            return self._log(replace(run, cad=run.cad + exc.cad), Step.REJECTED, f"{address}: {exc}")
        if stated is None or not stated.claims:
            return (self._log(run, Step.SKIPPED, f"{address}: the datasheet states no value under a spec key")
                    if stated else run)
        reason = f"Values stated in the datasheet {address}"
        changes = tuple(Change(PutEntity(r), reason, "agent", RESEARCHER, (stated.source.id,))
                        for r in (stated.source, *stated.claims))
        return self._filing.filed(replace(run, cad=run.cad + stated.cad), Step.DATASHEET, draft, reason, changes, by,
                                  address)
