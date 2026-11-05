from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from radar.domain.model.entities import Change, FeedRule, FeedSentence, FeedSettings, PartialDate
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.history.change_log import ChangeLog
from radar.domain.ports.review.feed_reads import FeedReads
from radar.domain.review.feed.editor import Article, Feed
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Job

Record = Mapping[str, Any]

@dataclass(frozen=True, slots=True)
class Found:
    rule: FeedRule
    record: Record
    subject: str
    batch: str

def _fill(template: Mapping[str, str], values: Mapping[str, Any]) -> dict[str, str]:
    return {lang: text.format(**values) for lang, text in template.items()}

def _dated(batch: list[Found]) -> tuple[PartialDate | None, str | None]:
    found = batch[0]
    date = found.record.get(found.rule.event_date or "") if len(batch) == 1 else None
    sources = found.record.get("source_refs") or ()
    return (PartialDate(**date), sources[0]) if date and sources else (None, None)

class Detector:
    def __init__(self, log: ChangeLog, feed: Feed, settings: FeedSettings, store: FeedReads,
                 schema: ModelSchema) -> None:
        self._log, self._feed, self._settings, self._store, self._schema = log, feed, settings, store, schema

    def _rule(self, change: Change, record: Record) -> FeedRule | None:
        kind = self._schema.kind_of(change.entity)
        return next((r for r in self._settings.rules if r.entity == kind
                     and all(record.get(k) == v for k, v in (r.match or {}).items())), None)

    def found(self, changes: Sequence[Change]) -> list[Found]:
        created = [c for c in changes if c.version == 1 and c.actor_kind != "import"]
        records = self._store.records([c.entity for c in created])
        out = []
        for c in (c for c in created if c.entity in records):
            rule = self._rule(c, records[c.entity])
            if rule:
                out.append(Found(rule, records[c.entity], records[c.entity][rule.subject] if rule.subject else c.entity,
                                 c.correlation_id))
        return out

    def _sentence(self, found: Found) -> FeedSentence:
        values = {**{k: v for k, v in found.record.items() if isinstance(v, str)},
                  "name": self._store.name_of(found.subject)}
        return FeedSentence(text=_fill(found.rule.sentence, values),
                            cites=(found.subject, *found.record.get("source_refs", ())))

    def _article(self, batch: list[Found]) -> Article:
        rule, first = batch[0].rule, batch[0]
        values = {**{k: v for k, v in first.record.items() if isinstance(v, str)},
                  "name": self._store.name_of(first.subject), "count": len(batch)}
        date, source = _dated(batch)
        return Article(_fill(rule.title if len(batch) == 1 else rule.batch_title, values), _fill(rule.summary, values),
                       tuple(self._sentence(f) for f in batch), date, source)

    def _digest(self, by: Job) -> Proposal:
        digest, counts = self._settings.digest, self._store.counts()
        sentence = FeedSentence(text=_fill(digest.sentence, counts), cites=tuple(self._store.examples()))
        return self._feed.write(Article(_fill(digest.title, counts), _fill(digest.summary, counts), (sentence,)), by,
                                digest.kind, "template")

    def detect(self, by: Job) -> list[Proposal]:
        start = self._store.cursor()
        page = self._log.after(start)
        if start is None:
            drafts = [self._digest(by)]
        else:
            batches: dict[tuple[str, str], list[Found]] = {}
            for f in self.found(page.changes):
                batches.setdefault((f.batch, f.rule.kind), []).append(f)
            drafts = [self._feed.write(self._article(b), by, b[0].rule.kind, "template") for b in batches.values()]
        if page.cursor:
            self._store.advance(page.cursor)
        return drafts
