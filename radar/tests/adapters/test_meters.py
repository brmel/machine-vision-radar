from __future__ import annotations

from radar.adapters.ai.scripted import ScriptedImageJudge
from radar.adapters.firestore.ledgers.ai import FirestoreBudget, FirestoreUsageLog
from radar.domain.ai.budget import Use
from radar.domain.ai.meter import Meter
from radar.domain.ports.ai.image_judge import CandidateImage
from radar.tests.store import stores

FX = stores.fixture()
DAY = "2026-10-19"

def test_a_judgement_of_three_candidates_charges_three_calls() -> None:
    ledger = stores.fresh_at(stores.place()[0])
    budget = FirestoreBudget(ledger, FX.model)
    meter = Meter(budget, FirestoreUsageLog(ledger), FX.model.registry.ai, Use.RESEARCH, "image_judge",
                  lambda model: ScriptedImageJudge())
    candidates = tuple(CandidateImage(f"https://example.com/{n}.png", b"x" * 100, "image/png") for n in range(3))
    judged, _ = meter.call(DAY, lambda judge: judge.judge("Widget", candidates))
    assert len(judged.judged) == 3 and budget.usage(Use.RESEARCH, DAY).calls_today == 3
