from __future__ import annotations

from radar.domain.model.entities import Change, Document, Product, ProductVersion
from radar.domain.validation.context import ValidationContext, ValidationResult
from radar.domain.validation.walk import visits

NAME = "references"

def _withdrawn(ctx: ValidationContext) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for c in ctx.catalog.all(Change):
        if ctx.catalog.get(c.entity) is None:
            first, last = out.get(c.entity, (c.recorded_at, c.recorded_at))
            out[c.entity] = (min(first, c.recorded_at), max(last, c.recorded_at))
    return out

def _check_thumbnails(ctx: ValidationContext, res: ValidationResult) -> None:
    kinds = ctx.registry.vocabularies.get("document_kinds", {})
    rights_vocab = ctx.registry.vocabularies.get("media_rights", {})
    for prod in ctx.catalog.all(Product):
        if not prod.thumbnail:
            continue
        doc = ctx.catalog.get(prod.thumbnail)
        if not isinstance(doc, Document):
            continue
        kind = kinds.get(doc.kind)
        if not any(m.startswith("image/") for m in (kind.mime_types if kind else ())):
            res.error(NAME, prod.id, f"thumbnail '{doc.id}' is not an image (kind '{doc.kind}')")
        rights = rights_vocab.get(doc.rights)
        if not (rights and rights.public):
            res.error(NAME, prod.id, f"thumbnail '{doc.id}' rights are not public ('{doc.rights}')")
        if prod.id not in doc.subjects:
            res.error(NAME, prod.id, f"thumbnail '{doc.id}' is not about product '{prod.id}'")

def _check_documents(ctx: ValidationContext, res: ValidationResult) -> None:
    kinds = ctx.registry.vocabularies.get("document_kinds", {})
    for doc in ctx.catalog.all(Document):
        kind = kinds.get(doc.kind)
        if kind and kind.version and not any(isinstance(ctx.catalog.get(s), ProductVersion) for s in doc.subjects):
            res.error(NAME, doc.id, f"document '{doc.id}' of kind '{doc.kind}' must name a ProductVersion")

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    withdrawn = _withdrawn(ctx)
    for v in visits(ctx):
        if not v.spec.refs:
            continue
        for target_id in v.items:
            target = ctx.catalog.get(target_id)
            first, last = withdrawn.get(target_id, ("", ""))
            if target is None and isinstance(v.entity, Change) and first <= v.entity.recorded_at <= last:
                continue
            if target is None:
                res.error(NAME, v.entity.id, f"{v.path}: '{target_id}' does not exist")
            elif type(target).__name__ not in v.spec.refs:
                res.error(NAME, v.entity.id,
                          f"{v.path}: '{target_id}' is of type {type(target).__name__}, expected "
                          f"{' or '.join(v.spec.refs)}")
    _check_thumbnails(ctx, res)
    _check_documents(ctx, res)
