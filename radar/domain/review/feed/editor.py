from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from radar.domain.model.entities import (FeedDesk, FeedDeskRow, FeedItem, FeedSentence, FilesOn, PartialDate,
                                         ProposalStatus)
from radar.domain.model.history.ids import keyed
from radar.domain.model.history.projection import every_page, page_of, plain
from radar.domain.model.registry import Registry
from radar.domain.model.changeset import Change, Changeset, PutEntity
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.review.feed.news import published
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Approval, Changes, Enactment, Founder, Job, Picked, Revision, Withdrawal
from radar.domain.review.review import Review

Parse = Callable[[Mapping[str, Any]], FeedItem]

@dataclass(frozen=True, slots=True)
class Article:
    title: Mapping[str, str]
    summary: Mapping[str, str]
    body: tuple[FeedSentence, ...]
    event_date: PartialDate | None = None
    event_source: str | None = None

@dataclass(frozen=True, slots=True)
class Pending:
    proposal: Proposal
    item: FeedItem

def _text(raw: Any, key: str) -> dict[str, str]:
    if (not isinstance(raw, dict) or not all(isinstance(v, str) for v in raw.values())
            or not any(v.strip() for v in raw.values())):
        raise ValueError(f"{key} is text with its localized versions")
    return {k: v.strip() for k, v in raw.items() if v.strip()}

def _sentence(raw: Any, n: int) -> FeedSentence:
    cites = raw.get("cites") if isinstance(raw, dict) else None
    if not isinstance(cites, list) or not cites or not all(isinstance(c, str) for c in cites):
        raise ValueError(f"body[{n}] cites a product, an organization or a source, by id")
    return FeedSentence(text=_text(raw.get("text"), f"body[{n}].text"), cites=tuple(cites))

def article_of(raw: Any) -> Article:
    if not isinstance(raw, dict) or not isinstance(raw.get("body"), list) or not raw["body"]:
        raise ValueError("an article is {title, summary, body: [{text, cites}]} with at least one sentence")
    date = raw.get("event_date")
    return Article(_text(raw.get("title"), "title"), _text(raw.get("summary"), "summary"),
                   tuple(_sentence(s, n) for n, s in enumerate(raw["body"])),
                   PartialDate(**date) if isinstance(date, dict) else None, raw.get("event_source"))

def _slug_of(title: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-") or "article"
    return next(s for s in (base, *(f"{base}-{n}" for n in range(2, len(taken) + 3))) if s not in taken)

def share_view(item: FeedItem, locale: str, origin: str) -> dict[str, str]:
    url = f"{origin.rstrip('/')}/news/{item.slug}"
    title = item.title.get(locale) or next(iter(item.title.values()), "")
    summary = item.summary.get(locale) or next(iter(item.summary.values()), "")
    return {"locale": locale, "url": url, "text": "\n".join([title, summary, url])}

def _row(item: FeedItem, proposal: Proposal | None = None) -> FeedDeskRow:
    return FeedDeskRow(id=item.id, slug=item.slug, kind=item.kind, authorship=item.authorship, position=item.position,
                       title=item.title, summary=item.summary, body=item.body, published_at=item.published_at,
                       event_date=item.event_date, event_source=item.event_source,
                       proposal=proposal.id if proposal else None)

def _cites(body: Sequence[FeedSentence]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(c for s in body for c in s.cites))

class Feed:
    def __init__(self, review: Review, desk: Job, published: Callable[[], Sequence[FeedItem]], parse: Parse,
                 registry: Registry, clock: Callable[[], str]) -> None:
        self._review, self._desk, self._published, self._parse, self._registry, self._clock = (
            review, desk, published, parse, registry, clock)

    def _pending(self, status: ProposalStatus | None) -> list[Pending]:
        pages = every_page(lambda cursor: self._review.queue(Query(status, FilesOn.FEED), self._desk, cursor))
        return [Pending(p, self._parse(p.changeset.changes[0].action.record)) for page in pages for p in page.proposals
                if p.changeset and isinstance(p.changeset.changes[0].action, PutEntity)]

    def drafts(self) -> list[Pending]:
        return sorted(self._pending(ProposalStatus.SUGGESTED), key=lambda d: (d.item.position, d.item.id))

    def items(self) -> list[FeedItem]:
        return published(self._published())

    def _slugs(self) -> set[str]:
        return {i.slug for i in self.items()} | {d.item.slug for d in self._pending(None)}

    def _change(self, item: FeedItem, reason: str, by: Founder | Job) -> Changeset:
        return Changeset((Change(PutEntity(plain(replace(item, version=1))), reason, by.kind, by.name, ()),))

    def write(self, article: Article, by: Founder | Job, kind: str | None = None,
              authorship: str = "human") -> Proposal:
        drafts, items = self.drafts(), self.items()
        main_title = next(iter(article.title.values()))
        slug = _slug_of(main_title, self._slugs())
        position = max((i.position for i in [*items, *(d.item for d in drafts)]), default=0) + 1
        item = FeedItem(id=keyed("nws", slug), version=1, slug=slug, kind=kind or self._registry.feed.article,
                        authorship=authorship, byline=self._registry.feed.byline, title=article.title,
                        summary=article.summary, body=article.body, cites=_cites(article.body), position=position,
                        event_date=article.event_date, event_source=article.event_source)
        reason = f"News: {main_title}"
        return self._review.submit(Changes(FilesOn.FEED, reason, item.id, self._change(item, reason, by)), by).proposal

    def desk(self, cursor: str | None = None) -> FeedDesk:
        items = self.items()
        page, after = page_of(items, cursor)
        return FeedDesk(drafts=tuple(_row(d.item, d.proposal) for d in self.drafts()),
                        published=tuple(_row(i) for i in page), total=len(items), next=after)

    def row(self, item_id: str) -> FeedDeskRow:
        found = self.find(item_id)
        return _row(found.item, found.proposal) if isinstance(found, Pending) else _row(found)

    def find(self, item_id: str) -> Pending | FeedItem:
        return next((d for d in self.drafts() if item_id in (d.item.id, d.item.slug)), None) or self.item(item_id)

    def item(self, item_id: str) -> FeedItem:
        found = next((i for i in self.items() if item_id in (i.id, i.slug)), None)
        if found is None:
            raise LookupError(f"no published item {item_id}")
        return found

    def revise(self, item_id: str, article: Article, note: str, by: Founder) -> Proposal:
        found = self.find(item_id)
        item = found.item if isinstance(found, Pending) else found
        revised = replace(item, title=article.title, summary=article.summary, body=article.body,
                          cites=_cites(article.body), event_date=article.event_date, event_source=article.event_source,
                          revised_at=self._clock() if item.published_at else None)
        if isinstance(found, Pending):
            return self._review.decide(Revision(found.proposal.id, self._change(revised, note, by), note), by).one()
        return self._review.decide(Enactment(Changes(FilesOn.FEED, note, item.id, self._change(revised, note, by))),
                                   by).one()

    def reorder(self, item_id: str, position: int, by: Founder) -> list[Proposal]:
        drafts = self.drafts()
        moved = next((d for d in drafts if item_id in (d.item.id, d.item.slug)), None)
        if moved is None:
            raise LookupError(f"no draft {item_id}")
        order = [d for d in drafts if d is not moved]
        order.insert(max(0, min(position - 1, len(order))), moved)
        places = sorted(d.item.position for d in drafts)
        note = f"Reordered: {moved.item.slug} at {position}"
        return [self._review.decide(Revision(d.proposal.id, self._change(replace(d.item, position=p), note, by), note),
                                    by).one()
                for d, p in zip(order, places) if d.item.position != p]

    def publish(self, note: str, by: Founder, item_id: str | None = None) -> Proposal:
        chosen = next((d for d in self.drafts() if item_id in (None, d.item.id, d.item.slug)), None)
        if chosen is None:
            raise LookupError("no draft to publish" if item_id is None else f"no draft {item_id}")
        return self._review.decide(Approval(Picked((chosen.proposal.id,)), note), by).one()

    def publish_templated(self, note: str, by: Founder) -> list[Proposal]:
        return [self.publish(note, by, d.item.id) for d in self.drafts() if d.item.authorship == "template"]

    def retract(self, item_id: str, note: str, by: Founder) -> Proposal:
        return self._review.decide(Enactment(Withdrawal(self.item(item_id).id, note)), by).one()
