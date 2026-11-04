from __future__ import annotations

import time
from typing import Callable, Generic, Mapping, Protocol, TypeVar

from radar.domain.ai.budget import METERED, Cap, Use, caps_view, model_of, over_cap, total_usage
from radar.domain.model.entities import AiCaps, AiModel, AiSettings
from radar.domain.ports.ai.prompt_registry import PromptRegistry
from radar.domain.ports.ai.usage_log import Budget, Ended, ModelCall, Outcome, Unparsed, UsageLog

def cost(ai: AiSettings, model: AiModel, tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * model.usd_in + tokens_out * model.usd_out) * ai.cad_per_usd / 1e6

def caps_today(budget: Budget, ai: AiSettings, prompts: PromptRegistry, day: str) -> AiCaps:
    return caps_view(ai, budget.caps(), {u: budget.usage(u, day) for u in METERED},
                     {u: prompts.prompt(u.value).id for u in METERED}, day)

class Called(Protocol):
    def ended(self) -> Ended | None:
        ...

class Capped(Exception):
    ...

C = TypeVar("C", bound=Called)
M = TypeVar("M")

class Meter(Generic[M]):
    def __init__(self, budget: Budget, usage: UsageLog, ai: AiSettings, use: Use, prompt: str,
                 opened: Callable[[AiModel], M], clock: Callable[[], float] = time.monotonic) -> None:
        self._budget, self._usage, self._ai, self._use, self._prompt, self._opened, self._clock = (
            budget, usage, ai, use, prompt, opened, clock)

    def _record(self, started: float, model: AiModel, ended: Ended) -> float:
        cad = cost(self._ai, model, ended.tokens_in, ended.tokens_out)
        self._usage.record(ModelCall(self._use, self._prompt, model.id, ended.tokens_in, ended.tokens_out, cad,
                                     round((self._clock() - started) * 1000), ended.outcome, ended.reason))
        return cad

    def _capped(self, caps: Mapping[Use, Cap], day: str, client: str | None) -> str | None:
        usages = [self._budget.usage(u, day) for u in METERED]
        return over_cap(self._use, caps, self._budget.usage(self._use, day, client), total_usage(usages))

    def call(self, day: str, run: Callable[[M], C], client: str | None = None) -> tuple[C, float]:
        started, caps = self._clock(), self._budget.caps()
        model = model_of(self._ai, self._use, caps[self._use].model)
        capped = self._capped(caps, day, client)
        if capped:
            self._record(started, model, Ended(Outcome.CAPPED, 0, 0, capped))
            raise Capped(capped)
        opened = self._opened(model)
        try:
            called = run(opened)
        except Unparsed as exc:
            cad = self._record(started, model, Ended(Outcome.ERROR, exc.tokens_in, exc.tokens_out, type(exc).__name__))
            self._budget.charge(self._use, day, cad, client)
            raise Unparsed(exc.reason, exc.tokens_in, exc.tokens_out, cad) from exc
        except Exception as exc:
            self._record(started, model, Ended(Outcome.ERROR, 0, 0, type(exc).__name__))
            raise
        ended = called.ended()
        cad = self._record(started, model, ended) if ended else 0.0
        self._budget.charge(self._use, day, cad, client)
        return called, cad
