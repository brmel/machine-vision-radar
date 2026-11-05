from __future__ import annotations

import re
from collections.abc import Mapping

from radar.domain.model.registry import Filler
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings
from radar.domain.validation.walk import visits

NAME = "no_filler_text"

def _findings(filler: Filler, text: str) -> list[str]:
    placeholder = any(re.fullmatch(b.pattern, text.strip(), re.IGNORECASE) for b in filler.placeholders)
    marketing = [f"marketing filler '{m.group()}' ({b.reason})" for b in filler.anywhere
                 for m in re.finditer(b.pattern, text, re.IGNORECASE)]
    return ([f"placeholder text '{text}'"] if placeholder else []) + marketing

def check(ctx: ValidationContext) -> Findings:
    for v in visits(ctx):
        if v.spec.leaf_type not in ("string", "LocalizedText"):
            continue
        if v.path.endswith((".url", ".website", ".website_url", ".catalog_url", ".source_url")) or ".patch[" in v.path:
            continue
        for item in v.items:
            for text in (item.values() if isinstance(item, Mapping) else (item,)):
                for found in _findings(ctx.registry.filler, text):
                    yield Finding(NAME, v.entity.id, f"{v.path}: {found}")
