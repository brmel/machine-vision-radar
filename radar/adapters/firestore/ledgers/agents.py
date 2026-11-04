from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Mapping

from radar.adapters.console import log
from radar.adapters.firestore.docs import list_page
from radar.domain.ports.review.research_runs import Line, Outcome, ResearchRun, RunPage, Status, Step
from radar.domain.ports.store.docs import Docs, Increment, Put
from radar.domain.review.agents.tokens import AgentToken, Limits, Scope, TokenUsage

TOKENS, USAGE, RESEARCH, CANCELS = "agent_tokens", "agent_usage", "research_runs", "research_cancels"
COLLECTIONS = (TOKENS, USAGE, RESEARCH, CANCELS)

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
            log.info(f"research: {run.lines[-1].step.value}", scope=run.scope, detail=run.lines[-1].detail)
        else:
            log.info("research: started", scope=run.scope)
        ended = ({"outcome": run.outcome.status.value, "ended_at": run.outcome.at} if run.outcome
                 else {"outcome": Status.RUNNING.value})
        fields = {**asdict(run), **ended, "lines": [{**asdict(n), "step": n.step.value} for n in run.lines]}
        self._docs.commit([Put(f"{RESEARCH}/{run.id}", fields)])

    def cancel(self, run_id: str, at: str) -> None:
        self._docs.commit([Put(f"{CANCELS}/{run_id}", {"run": run_id, "at": at})])

    def get(self, run_id: str) -> ResearchRun:
        found = self._docs.get(f"{RESEARCH}/{run_id}")
        if found is None:
            raise LookupError(f"no research run {run_id}")
        return _run(found, (self._docs.get(f"{CANCELS}/{run_id}") or {}).get("at"))

    def page(self, cursor: str | None = None) -> RunPage:
        rows, after, total = list_page(self._docs, RESEARCH, cursor)
        cancel_paths = [f"{CANCELS}/{p.rsplit('/', 1)[1]}" for p, _ in rows]
        cancels = {f["run"]: f["at"] for f in self._docs.get_many(cancel_paths).values() if "run" in f and "at" in f}
        return RunPage(tuple(_run(f, cancels.get(f["id"])) for _, f in rows), after, total)

def _run(fields: Mapping[str, Any], cancelled_at: str | None) -> ResearchRun:
    lines = tuple(Line(n["at"], Step(n["step"]), n["detail"]) for n in fields["lines"])
    status = Status(fields["outcome"])
    if status is not Status.RUNNING:
        outcome = Outcome(status, next(n.detail for n in reversed(lines) if n.step is Step.ENDED), fields["ended_at"])
    else:
        outcome = Outcome(Status.CANCELLED, "cancelled by the founder", cancelled_at) if cancelled_at else None
    return ResearchRun(fields["id"], fields["scope"], fields["actor"], fields["started_at"], fields["token"],
                       float(fields["cad"]), lines, outcome)
