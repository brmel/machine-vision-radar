from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import islice
from typing import Callable, Mapping

from radar.adapters.console import log
from radar.adapters.firestore.layout import catalog_of, newest_first, record_of
from radar.domain.ai.budget import METERED, Cap, Usage, Use, caps_of
from radar.domain.model.entities import AiCap, AskAnswer, Citation
from radar.domain.model.history.projection import plain
from radar.domain.model.model import Model
from radar.domain.ports.ai.usage_log import ModelCall
from radar.domain.model.entities import IndexRunView
from radar.domain.ports.store.docs import Docs, Increment, Put

CACHE, METRICS, CALLS, RUNS = "ask_cache", "metrics", "ai_calls", "index_runs"

def usage_collection(use: Use) -> str:
    return f"{use.value}_usage"

COLLECTIONS = (CACHE, METRICS, CALLS, RUNS, *map(usage_collection, METERED))

class FirestoreBudget:
    def __init__(self, docs: Docs, model: Model) -> None:
        self._docs, self._model = docs, model
        self._caps = model.schema.collection(AiCap.__name__)

    def caps(self) -> Mapping[Use, Cap]:
        return caps_of(self._model.registry.ai,
                       catalog_of(self._model, [record_of(f) for _, f in self._docs.list(self._caps)]).all(AiCap))

    def usage(self, use: Use, day: str, client: str | None = None) -> Usage:
        today = self._docs.get(f"{usage_collection(use)}/{day}") or {}
        month = self._docs.get(f"{usage_collection(use)}/{day[:7]}") or {}
        return Usage(int(today.get("calls", 0)), int(today.get("clients", {}).get(client, 0)) if client else 0,
                     float(month.get("cad", 0.0)))

    def charge(self, use: Use, day: str, cad: float, client: str | None = None, calls: int = 1) -> None:
        self._docs.commit([Increment(f"{usage_collection(use)}/{day}",
                                     {"calls": calls, **({f"clients.{client}": calls} if client else {})}),
                           Increment(f"{usage_collection(use)}/{day[:7]}", {"cad": float(cad)})])

class FirestoreUsageLog:
    def __init__(self, docs: Docs, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._docs, self._now = docs, now

    def record(self, call: ModelCall) -> None:
        fields = {**asdict(call), "use": call.use.value, "outcome": call.outcome.value, "cad": round(call.cad, 8)}
        line = log.redact({k: v for k, v in fields.items() if v is not None})
        log.info("model call", **line)
        at, correlation = self._now(), str(log.bound().get("correlation_id", "none"))
        self._docs.commit([Put(f"{CALLS}/{at:%Y-%m-%d}-{uuid.uuid4().hex}",
                               {**line, "at": at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                                "correlation_id": correlation})])

class FirestoreIndexRuns:
    def __init__(self, docs: Docs) -> None:
        self._docs = docs

    def record(self, run: IndexRunView) -> None:
        self._docs.commit([Put(f"{RUNS}/{newest_first(run.at)}-{run.correlation_id}", plain(run))])

    def latest(self, limit: int) -> list[IndexRunView]:
        return [IndexRunView(action=f["action"], model_id=f["model_id"], actor=f["actor"], at=f["at"],
                             correlation_id=f["correlation_id"], version=f.get("version"), products=int(f["products"]),
                             embedded=int(f["embedded"]), removed=int(f["removed"]), error=f.get("error"))
                for _, f in islice(self._docs.list(RUNS), limit)]

class FirestoreAskLedger:
    def __init__(self, docs: Docs) -> None:
        self._docs = docs

    def cached(self, key: str) -> AskAnswer | None:
        doc = self._docs.get(f"{CACHE}/{key}")
        if doc is None:
            return None
        raw = json.loads(doc["json"])
        return AskAnswer(**{**raw, "citations": tuple(Citation(**c) for c in raw["citations"])})

    def remember(self, key: str, answer: AskAnswer) -> None:
        self._docs.commit([Put(f"{CACHE}/{key}", {"json": json.dumps(plain(answer), ensure_ascii=False)})])

    def count(self, day: str, events: Mapping[str, int]) -> None:
        self._docs.commit([Increment(f"{METRICS}/{day}", dict(events))])

    def counted(self, day: str) -> Mapping[str, int]:
        return {k: int(v) for k, v in (self._docs.get(f"{METRICS}/{day}") or {}).items()}
