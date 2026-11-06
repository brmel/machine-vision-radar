from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date
from typing import Any, Mapping, Sequence

from radar.adapters.console import log
from radar.adapters.firestore.docs import list_page
from radar.adapters.firestore.layout import newest_first
from radar.domain.model.entities import RunScope, RunScopeKind
from radar.domain.ports.review.research_runs import Line, Outcome, ResearchRun, RunPage, Status, Step
from radar.domain.ports.store.docs import BATCH, Docs, Increment, Put
from radar.domain.ports.web.crawl_records import CrawlRecord, CrawlStatus, PageKind
from radar.domain.review.agents.tokens import AgentToken, Limits, Scope, TokenUsage

TOKENS, USAGE, RESEARCH, CANCELS, CRAWL = ("agent_tokens", "agent_usage", "research_log", "research_cancels",
                                           "crawl_records")
COLLECTIONS = (TOKENS, USAGE, RESEARCH, CANCELS, CRAWL)

class FirestoreAgentTokens:
    def __init__(self, docs: Docs) -> None:
        self._docs = docs

    def _put(self, token: AgentToken, create: bool = False) -> None:
        fields = {**asdict(token), "scope": token.scope.value, "expires": token.expires.isoformat()}
        self._docs.commit([Put(f"{TOKENS}/{token.id}", fields, create)])

    def issue(self, token: AgentToken) -> None:
        self._put(token, create=True)

    def page(self, cursor: str | None = None) -> tuple[tuple[AgentToken, ...], str | None, int]:
        rows, after, total = list_page(self._docs, TOKENS, cursor)
        return tuple(_token(f) for _, f in rows), after, total

    def by_digest(self, digest: str) -> AgentToken | None:
        found = self._docs.where(TOKENS, "digest", [digest])
        return _token(found[0][1]) if found else None

    def revoke(self, token_id: str, at: str) -> AgentToken:
        doc = self._docs.get(f"{TOKENS}/{token_id}")
        if doc is None:
            raise LookupError(f"no agent token {token_id}")
        token = _token(doc).revoked(at)
        self._put(token)
        return token

    def count(self, token_id: str, minute: str, proposal: bool) -> TokenUsage:
        path, slot = f"{USAGE}/{token_id}-{minute[:10]}", "m" + minute[11:16].replace(":", "")
        self._docs.commit([Increment(path, {f"requests.{slot}": 1, **({"proposals": 1} if proposal else {})})])
        used = self._docs.get(path) or {}
        return TokenUsage(int(used.get("requests", {}).get(slot, 0)), int(used.get("proposals", 0)) if proposal else 0)

def _token(fields: Mapping[str, Any]) -> AgentToken:
    return AgentToken(fields["id"], fields["name"], Scope(fields["scope"]), date.fromisoformat(fields["expires"]),
                      fields["created_at"], Limits(**fields["limits"]), fields["digest"], fields.get("revoked_at"))

class FirestoreResearchRuns:
    def __init__(self, docs: Docs) -> None:
        self._docs = docs

    def save(self, run: ResearchRun) -> None:
        if run.lines:
            log.info(f"research: {run.lines[-1].step.value}", scope=run.scope.key, detail=run.lines[-1].detail)
        else:
            log.info("research: started", scope=run.scope.key)
        ended = ({"outcome": run.outcome.status.value, "ended_at": run.outcome.at} if run.outcome
                 else {"outcome": Status.RUNNING.value})
        fields = {**asdict(run), **ended, "scope": {"kind": run.scope.kind.value, "key": run.scope.key},
                  "lines": [{**asdict(n), "step": n.step.value} for n in run.lines]}
        self._docs.commit([Put(f"{RESEARCH}/{newest_first(run.started_at)}-{run.id}", fields)])

    def cancel(self, run_id: str, at: str) -> None:
        self._docs.commit([Put(f"{CANCELS}/{run_id}", {"run": run_id, "at": at})])

    def get(self, run_id: str) -> ResearchRun:
        found = self._docs.where(RESEARCH, "id", [run_id])
        if not found:
            raise LookupError(f"no research run {run_id}")
        return _run(found[0][1], (self._docs.get(f"{CANCELS}/{run_id}") or {}).get("at"))

    def page(self, cursor: str | None = None) -> RunPage:
        rows, after, total = list_page(self._docs, RESEARCH, cursor)
        cancel_paths = [f"{CANCELS}/{f['id']}" for _, f in rows]
        cancels = {f["run"]: f["at"] for f in self._docs.get_many(cancel_paths).values() if "run" in f and "at" in f}
        return RunPage(tuple(_run(f, cancels.get(f["id"])) for _, f in rows), after, total)

class FirestoreCrawlRecords:
    def __init__(self, docs: Docs) -> None:
        self._docs = docs

    def listed(self, org: str) -> tuple[CrawlRecord, ...]:
        return tuple(CrawlRecord(**{**f, "status": CrawlStatus(f["status"]), "kind": PageKind(f["kind"])})
                     for _, f in self._docs.where(CRAWL, "org", [org]))

    def save(self, records: Sequence[CrawlRecord]) -> None:
        writes = [Put(f"{CRAWL}/{hashlib.sha256(r.address.encode()).hexdigest()}",
                      {**asdict(r), "status": r.status.value, "kind": r.kind.value}) for r in records]
        for start in range(0, len(writes), BATCH):
            self._docs.commit(writes[start:start + BATCH])

def _run(fields: Mapping[str, Any], cancelled_at: str | None) -> ResearchRun:
    lines = tuple(Line(n["at"], Step(n["step"]), n["detail"]) for n in fields["lines"])
    status = Status(fields["outcome"])
    if status is not Status.RUNNING:
        outcome = Outcome(status, next(n.detail for n in reversed(lines) if n.step is Step.ENDED), fields["ended_at"])
    else:
        outcome = Outcome(Status.CANCELLED, "cancelled by the founder", cancelled_at) if cancelled_at else None
    scope = RunScope(kind=RunScopeKind(fields["scope"]["kind"]), key=fields["scope"]["key"])
    return ResearchRun(fields["id"], scope, fields["actor"], fields["started_at"], fields["token"],
                       float(fields["cad"]), lines, outcome)
