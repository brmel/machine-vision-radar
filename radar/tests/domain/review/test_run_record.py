from __future__ import annotations

from datetime import date
from typing import Any

from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens, FirestoreResearchRuns
from radar.domain.model.entities import Standing
from radar.domain.ports.review.research_runs import STOPPED, ResearchRun, Status
from radar.domain.ports.store.docs import Docs
from radar.domain.review.agents.tokens import Limits, Scope, issue
from radar.tests.adapters.web.test_research import MAKER, NOW, _run, docs  # noqa: F401
from radar.tests.fixtures.fixture_category import MakerScope, ProductScope

EARLIER = "2026-10-17T12:00:00Z"
TODAY = date.fromisoformat(NOW[:10])

def test_a_dead_run_is_settled_by_the_next_and_runs_list_newest_first(docs: tuple[Docs, Any]) -> None:  # noqa: F811
    store = docs[0]
    runs, tokens = FirestoreResearchRuns(store), FirestoreAgentTokens(store)
    token, _ = issue("dead", Scope.PROPOSE, date(2026, 12, 1), Limits(), EARLIER)
    tokens.issue(token)
    runs.save(ResearchRun("research-dead", ProductScope("prd_1"), "founder", EARLIER, token.id))

    run = _run(docs, [], [])

    dead = runs.get("research-dead")
    assert dead.outcome and (dead.outcome.status, dead.outcome.reason) == (Status.FAILED, STOPPED)
    assert tokens.by_digest(token.digest).standing(TODAY) is Standing.REVOKED
    assert [(r.id, r.scope) for r in runs.page().runs] == [
        (run.id, MakerScope(MAKER["slug"])), ("research-dead", ProductScope("prd_1"))]
