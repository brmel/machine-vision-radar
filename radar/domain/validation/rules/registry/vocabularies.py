from __future__ import annotations

from typing import Any, Iterable

from radar.domain.validation.context import ValidationContext, ValidationResult
from radar.domain.validation.walk import Visit, visits

NAME = "vocabularies"

def _bound(v: Visit) -> Iterable[tuple[str, Any]]:
    if v.spec.vocabulary:
        yield from ((v.spec.vocabulary, x) for x in (v.value.values() if v.spec.type == "map" else v.items))
    if v.spec.key_vocabulary:
        yield from ((v.spec.key_vocabulary, k) for k in v.value)

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    for v in visits(ctx):
        for vocab, term_id in _bound(v):
            if term_id not in ctx.registry.items(vocab):
                res.error(NAME, v.entity.id, f"{v.path}: '{term_id}' is not in registry '{vocab}'")
