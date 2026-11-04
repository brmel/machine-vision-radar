from __future__ import annotations

from radar.domain.validation.context import ValidationContext, ValidationResult
from radar.domain.model.entities import Source

NAME = "source_integrity"

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    for src in ctx.catalog.all(Source):
        if not (src.url or "").strip() and not (src.document or "").strip():
            res.error(NAME, src.id, f"source '{src.id}' has neither a valid URL nor a Document reference")
