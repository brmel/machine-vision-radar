from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from radar.domain.model.entities import AiCap, AiCapRow, AiCaps, AiModel, AiSettings, FilesOn, Use
from radar.domain.model.history.ids import keyed
from radar.domain.model.history.changeset import UNNUMBERED, Change, Changeset, PutEntity
from radar.domain.review.requests import Changes

METERED = tuple(u for u in Use if u is not Use.ALL)

@dataclass(frozen=True, slots=True)
class Cap:
    month_cad: float
    day_calls: int
    client_calls: int | None = None
    model: str | None = None

    def changed(self, month_cad: float | None = None, day_calls: int | None = None, client_calls: int | None = None,
                model: str | None = None) -> Cap:
        return Cap(self.month_cad if month_cad is None else month_cad,
                   self.day_calls if day_calls is None else day_calls,
                   self.client_calls if client_calls is None else client_calls, model or self.model)

@dataclass(frozen=True, slots=True)
class Usage:
    calls_today: int
    client_today: int
    cad_month: float

def total_usage(usages: Iterable[Usage]) -> Usage:
    items = tuple(usages)
    return Usage(sum(u.calls_today for u in items), 0, sum(u.cad_month for u in items))

def caps_of(ai: AiSettings, records: Iterable[AiCap]) -> dict[Use, Cap]:
    return {**{Use(u.use): Cap(u.month_cad, u.day_calls, u.client_calls) for u in ai.uses},
            **{Use(r.use): Cap(r.month_cad, r.day_calls, r.client_calls, r.model) for r in records}}

def model_id(ai: AiSettings, use: Use, chosen: str | None) -> str | None:
    return chosen or next(u.model for u in ai.uses if u.use == use.value)

def model_of(ai: AiSettings, use: Use, chosen: str | None) -> AiModel:
    wanted = model_id(ai, use, chosen)
    found = next((m for m in ai.models if m.id == wanted), None)
    if found is None:
        raise LookupError(f"{use.value} runs {wanted}, which data/registry/ai.json no longer lists: set its "
                          "model again")
    return found

def over_cap(use: Use, caps: Mapping[Use, Cap], usage: Usage, total: Usage) -> str | None:
    for name, cap, spent in ((use.value, caps[use], usage), ("all AI", caps[Use.ALL], total)):
        if spent.cad_month >= cap.month_cad:
            return f"{name}: CAD {cap.month_cad:g} a month, spent"
        if spent.calls_today >= cap.day_calls:
            return f"{name}: {cap.day_calls} calls a day, made"
        if cap.client_calls is not None and spent.client_today >= cap.client_calls:
            return f"{name}: {cap.client_calls} calls a client a day, made"
    return None

def cap_draft(use: Use, cap: Cap, reason: str, author: str) -> Changes:
    held = AiCap(id=keyed("cap", use.value), version=UNNUMBERED, use=use.value, model=cap.model,
                 month_cad=cap.month_cad, day_calls=cap.day_calls, client_calls=cap.client_calls)
    return Changes(FilesOn.UPDATE, reason, held.id, Changeset((Change(PutEntity(held), reason, "human", author, ()),)))

def caps_view(ai: AiSettings, caps: Mapping[Use, Cap], usages: Mapping[Use, Usage], prompts: Mapping[Use, str],
              day: str) -> AiCaps:
    total = total_usage(usages.values())

    def row(use: Use) -> AiCapRow:
        cap, spent = caps[use], usages.get(use, total)
        return AiCapRow(use=use.value, cap=keyed("cap", use.value), model=model_id(ai, use, cap.model),
                        prompt=prompts.get(use), month_cad=cap.month_cad, day_calls=cap.day_calls,
                        client_calls=cap.client_calls, cad_month=round(spent.cad_month, 6),
                        calls_today=spent.calls_today)
    return AiCaps(day=day, cad_per_usd=ai.cad_per_usd, models=ai.models, uses=tuple(row(u) for u in Use))
