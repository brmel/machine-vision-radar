from __future__ import annotations

from dataclasses import dataclass

import pytest

from radar import paths
from radar.tests.fixtures.corpus import MODEL
from radar.adapters.firestore.writer import StoreWriter
from radar.domain.validation.verdict import InvalidChangeset
from radar.adapters.firestore.ledgers.ai import CALLS, FirestoreBudget, FirestoreUsageLog, usage_collection
from radar.domain.ai.budget import Use, caps_of, model_of
from radar.domain.ai.meter import Capped, Meter
from radar.domain.model.entities import AiModel
from radar.domain.model.history.ids import keyed
from radar.domain.model.history.changeset import Change, Changeset, put_of
from radar.domain.ports.store.docs import Docs, Increment
from radar.domain.ports.ai.usage_log import Ended, Outcome
from radar.tests.store import stores

DAY = "2026-10-20"
USES = [u for u in Use if u is not Use.ALL]
AI = MODEL.registry.ai
DEFAULTS = caps_of(AI, [])

@dataclass(frozen=True)
class Called:
    model: str

    def ended(self) -> Ended:
        return Ended(Outcome.ANSWERED, 1000, 100)

def _meter(docs: Docs, use: Use) -> Meter[AiModel]:
    return Meter(FirestoreBudget(docs, MODEL), FirestoreUsageLog(docs), AI, use,
                 f"{use.value}/v1", lambda model: model)

def _called(model: AiModel) -> Called:
    return Called(model.id)

def _unasked(model: AiModel) -> Called:
    raise AssertionError("the model was asked past a cap")

def _outcomes(docs: Docs) -> list[str]:
    return sorted(f["outcome"] for _, f in docs.list(CALLS))

def _cap(docs: Docs, use: Use, month_cad: float, day_calls: int, cap_id: str = "", model: str | None = None) -> None:
    record = {"id": cap_id or keyed("cap", use.value), "use": use.value, "month_cad": month_cad, "day_calls": day_calls,
              **({"model": model} if model else {})}
    StoreWriter(docs, MODEL, lambda: f"{DAY}T00:00:00Z", stores.blobs()).apply(
        Changeset((Change(put_of(record, MODEL), "the founder approves this use's spend", "human", "founder", ()),)),
        "cap-test")

@pytest.mark.parametrize("use", USES)
def test_a_call_past_its_use_s_day_cap_is_refused_before_the_model_is_asked(use: Use) -> None:
    docs = stores.fresh()
    if not DEFAULTS[use].day_calls:
        _cap(docs, use, 1.0, 3)
    docs.commit([Increment(f"{usage_collection(use)}/{DAY}", {"calls": (DEFAULTS[use].day_calls or 3) - 1})])
    _meter(docs, use).call(DAY, _called)
    with pytest.raises(Capped, match=f"^{use.value}: [0-9]+ calls a day, made$"):
        _meter(docs, use).call(DAY, _unasked)
    assert _outcomes(docs) == ["answered", "capped"]

@pytest.mark.parametrize("use", USES)
def test_a_use_whose_spend_is_not_approved_is_refused_at_once(use: Use) -> None:
    docs = stores.fresh()
    _cap(docs, use, 0, DEFAULTS[use].day_calls)
    with pytest.raises(Capped, match=f"^{use.value}: CAD 0 a month, spent$"):
        _meter(docs, use).call(DAY, _unasked)
    assert _outcomes(docs) == ["capped"] and docs.get(f"{usage_collection(use)}/{DAY}") is None

def test_all_uses_together_are_held_to_their_own_cap() -> None:
    docs = stores.fresh()
    _cap(docs, Use.ASK, DEFAULTS[Use.ALL].month_cad * 2, DEFAULTS[Use.ASK].day_calls)
    docs.commit([Increment(f"{usage_collection(Use.ASK)}/{DAY[:7]}", {"cad": DEFAULTS[Use.ALL].month_cad})])
    with pytest.raises(Capped, match=f"^all AI: CAD {DEFAULTS[Use.ALL].month_cad:g} a month, spent$"):
        _meter(docs, Use.ASK).call(DAY, _unasked)

def test_a_second_cap_for_a_use_is_refused() -> None:
    docs = stores.fresh()
    _cap(docs, Use.DRAFT, 0.5, 10)
    with pytest.raises(InvalidChangeset, match=f"the cap of 'draft' is {keyed('cap', 'draft')}"):
        _cap(docs, Use.DRAFT, 1.0, 10, keyed("cap", "another draft cap"))

def test_a_model_the_registry_does_not_list_is_refused() -> None:
    with pytest.raises(InvalidChangeset,
                       match="'draft' runs 'no-such-model', which data/registry/ai.json does not list"):
        _cap(stores.fresh(), Use.DRAFT, 0.5, 10, model="no-such-model")
