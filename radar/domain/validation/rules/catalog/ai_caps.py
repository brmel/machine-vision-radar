from __future__ import annotations

from radar.domain.ai.budget import Use
from radar.domain.model.entities import AiCap
from radar.domain.model.history.ids import keyed
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "ai_caps"

def check(ctx: ValidationContext) -> Findings:
    models = {m.id for m in ctx.registry.ai.models}
    for cap in ctx.catalog.all(AiCap):
        if cap.id != keyed("cap", cap.use):
            yield Finding(NAME, cap.id, f"the cap of '{cap.use}' is {keyed('cap', cap.use)}: change that record")
        if cap.use == Use.ALL.value and cap.model:
            yield Finding(NAME, cap.id, "all uses together run no model")
        elif cap.model and cap.model not in models:
            yield Finding(NAME, cap.id,
                          f"'{cap.use}' runs '{cap.model}', which data/registry/ai.json does not list")
