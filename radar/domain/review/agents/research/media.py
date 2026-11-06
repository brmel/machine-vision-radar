from __future__ import annotations

from dataclasses import replace
from typing import Callable
from urllib.parse import urlsplit

from radar.domain.ai.meter import Capped, Meter
from radar.domain.model.history.changeset import Change, PutEntity
from radar.domain.model.entities import ProductCard
from radar.domain.ports.ai.image_judge import CandidateImage, ImageEvaluation, ImageJudge
from radar.domain.ports.ai.research_agent import FileDraft
from radar.domain.ports.ai.usage_log import Unparsed
from radar.domain.ports.review.research_runs import ResearchRun, Step
from radar.domain.ports.web.page_fetcher import File, Page, PageFetcher, Unfetchable
from radar.domain.review.agents.files import Files, Staged
from radar.domain.review.agents.research.filing import RESEARCHER, Filing, Log
from radar.domain.review.requests import Agent

IMAGES = (".png", ".jpg", ".jpeg", ".webp")

def _best_photo(evaluation: ImageEvaluation) -> str | None:
    photos = [j for j in evaluation.judged if j.kind == "photo"]
    return max(photos, key=lambda j: j.confidence).url if photos else None

def _candidate_urls(page: Page) -> tuple[str, ...]:
    return tuple(u for u in dict.fromkeys((*page.images, *page.links)) if urlsplit(u).path.lower().endswith(IMAGES))[:3]

class Media:
    def __init__(self, fetcher: PageFetcher, files: Files, judge: Meter[ImageJudge], filing: Filing, log: Log,
                 now: Callable[[], str]) -> None:
        self._fetcher, self._files, self._judge, self._filing, self._log, self._now = (
            fetcher, files, judge, filing, log, now)

    def photo(self, run: ResearchRun, product: ProductCard, page: Page, read: Change, by: Agent,
              left: Callable[[], float]) -> tuple[ResearchRun, str | None]:
        files, run = self._candidates(_candidate_urls(page), run, left)
        if not files:
            return self._log(run, Step.SKIPPED, f"{page.url}: no candidate images found"), None
        try:
            candidates = tuple(CandidateImage(f.url, f.content, f.mime) for f in files.values())
            judged, cad = self._judge.call(self._now()[:10], lambda j: j.judge(product.name, candidates))
        except Capped as exc:
            return run, str(exc)
        except Unparsed as exc:
            return (self._log(replace(run, cad=run.cad + exc.cad), Step.REJECTED, f"{page.url}: judge error: {exc}"),
                    None)
        run = replace(run, cad=run.cad + cad)
        best_url = _best_photo(judged)
        if not best_url or best_url not in files:
            return self._log(run, Step.SKIPPED, f"{page.url}: no suitable product photo"), None
        best = files[best_url]
        draft = FileDraft("update", f"The maker's page shows a photo of {product.name}", product.id, best.url)
        document = Change(PutEntity(self._files.staged(best, product.id).document), draft.reason, "agent",
                          RESEARCHER, read.source_refs)
        return self._filing.filed(run, Step.FILED, draft, draft.reason, (read, document), by, best.url), None

    def _candidates(self, urls: tuple[str, ...], run: ResearchRun, left: Callable[[], float]) -> tuple[
            dict[str, File], ResearchRun]:
        files: dict[str, File] = {}
        for url in urls:
            if left() < 0:
                break
            try:
                files[url] = self._fetcher.file(url, left())
            except Unfetchable as exc:
                run = self._log(run, Step.SKIPPED, f"{url}: {exc}")
        return files, run

    def linked(self, run: ResearchRun, draft: FileDraft, cards: set[str], page: Page, read: Change, by: Agent,
               left: Callable[[], float]) -> ResearchRun:
        if draft.url not in page.links:
            return self._log(run, Step.REJECTED, f"{draft.url}: not one of the page's links")
        if draft.subject not in cards:
            return self._log(run, Step.REJECTED, f"{draft.url}: the file is for none of the cards' products")
        try:
            file = self._fetcher.file(draft.url, left())
        except Unfetchable as exc:
            return self._log(run, Step.SKIPPED, f"{draft.url}: {exc}")
        staged = self._files.staged(file, draft.subject)
        document = Change(PutEntity(staged.document), draft.reason, "agent", RESEARCHER, read.source_refs)
        return self._datasheet(self._filing.filed(run, Step.MEDIA, draft, draft.reason, (read, document), by, file.url),
                               draft, staged, by)

    def _datasheet(self, run: ResearchRun, draft: FileDraft, staged: Staged, by: Agent) -> ResearchRun:
        try:
            stated = self._files.stated(staged, self._now()[:10])
        except Capped as exc:
            return self._log(run, Step.REJECTED, f"{staged.file.url}: {exc}")
        except Unparsed as exc:
            return self._log(replace(run, cad=run.cad + exc.cad), Step.REJECTED, f"{staged.file.url}: {exc}")
        if stated is None or not stated.claims:
            return (self._log(run, Step.SKIPPED, f"{staged.file.url}: the datasheet states no value under a spec key")
                    if stated else run)
        reason = f"Values stated in the datasheet {staged.file.url}"
        changes = tuple(Change(PutEntity(r), reason, "agent", RESEARCHER, (stated.source.id,))
                        for r in (stated.source, *stated.claims))
        return self._filing.filed(replace(run, cad=run.cad + stated.cad), Step.DATASHEET, draft, reason, changes, by,
                                  staged.file.url)
