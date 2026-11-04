from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from radar.domain.ai.grounding import ungrounded
from radar.domain.ai.meter import Meter
from radar.domain.model.entities import FeedSentence
from radar.domain.ports.ai.answer_model import Sentence
from radar.domain.ports.ai.article_model import ArticleModel, ArticleText
from radar.domain.ports.ai.usage_log import Ended, Outcome
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.search.retriever import Evidence, Retriever
from radar.domain.review.feed.editor import Article, Feed
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Job

DRAFTER = "article model"

@dataclass(frozen=True, slots=True)
class Drafted:
    text: ArticleText
    rejected: str | None

    def ended(self) -> Ended:
        return Ended(Outcome.REFUSED if self.rejected else Outcome.ANSWERED, self.text.tokens_in, self.text.tokens_out,
                     self.rejected)

def drafted(model: ArticleModel, subject: Evidence, about: str, locale: str) -> Drafted:
    text = model.draft(subject, about, locale)
    headline = Sentence(f"{text.title} {text.summary}", tuple(c for s in text.sentences for c in s.cites))
    return Drafted(text, ungrounded((*text.sentences, headline), subject))

class Drafter:
    def __init__(self, retriever: Retriever, read: CatalogRepository, feed: Feed, meter: Meter[ArticleModel],
                 day: Callable[[], str]) -> None:
        self._retriever, self._read, self._feed, self._meter, self._day = retriever, read, feed, meter, day

    def _subject(self, key: str) -> tuple[str, str, tuple[str, ...]]:
        index = self._read.index()
        product = next((p for p in index.products if key in (p.id, p.slug)), None)
        org = next((o for o in index.organizations if key in (o.id, o.slug)), None)
        if product:
            return product.id, product.name, (product.id,)
        if org is None:
            raise LookupError(f"no product or organization {key}")
        return org.id, org.name, tuple(p.id for p in index.products if p.vendor == org.slug)

    def draft(self, key: str, correlation_id: str) -> Proposal:
        locale = self._feed._registry.default_language.code
        item, name, products = self._subject(key)
        subject = self._retriever.about(products, locale)
        if not subject.products:
            raise LookupError(f"{key}: no published product to draft from")
        done, _ = self._meter.call(self._day(), lambda model: drafted(model, subject, name, locale))
        if done.rejected:
            raise ValueError(f"the model's article does not stand on the record: {done.rejected}")
        body = tuple(FeedSentence(text={locale: s.text}, cites=tuple(dict.fromkeys((item, *s.cites))))
                     for s in done.text.sentences)
        article = Article({locale: done.text.title}, {locale: done.text.summary}, body)
        return self._feed.write(article, Job(DRAFTER, correlation_id), authorship="ai_draft")
