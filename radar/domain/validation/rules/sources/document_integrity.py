from __future__ import annotations

import re

from radar.domain.model.entities import Document
from radar.domain.validation.context import ValidationContext, ValidationResult
from radar.domain.validation.walk import repeated

NAME = "document_integrity"
SHA256 = re.compile(r"^[0-9a-f]{64}$")

def _shape(ctx: ValidationContext, doc: Document) -> list[str]:
    kind = ctx.registry.vocabularies["document_kinds"].get(doc.kind)
    allowed = kind.mime_types if kind else None
    problems = ([] if not allowed or doc.mime.startswith(tuple(allowed))
                else [f"mime '{doc.mime}' does not fit kind '{doc.kind}'"])
    visual = doc.mime.startswith(("image/", "video/"))
    if not visual and (doc.width is not None or doc.height is not None):
        problems.append("width/height belong to images and videos only")
    if not doc.mime.startswith("video/") and doc.duration is not None:
        problems.append("duration belongs to videos only")
    return problems

def _file_problems(ctx: ValidationContext, doc: Document) -> list[str]:
    if ctx.kept_files is None:
        return []
    kept = ctx.kept_files.get(doc.sha256)
    if kept is None:
        return [f"no kept file for sha256 {doc.sha256[:12]}…"]
    if kept.sha256 != doc.sha256:
        return [f"the kept file hashes to {kept.sha256[:12]}…, not {doc.sha256[:12]}…"]
    if (kept.bytes, kept.mime) != (doc.bytes, doc.mime):
        return [f"the kept file is {kept.bytes} bytes of {kept.mime}, not {doc.bytes} bytes of {doc.mime}"]
    return []

def check(ctx: ValidationContext, res: ValidationResult) -> None:
    docs = list(ctx.catalog.all(Document))
    for sha, n in repeated(d.sha256 for d in docs):
        res.error(NAME, sha[:12], f"{n} documents for one file (sha256 {sha[:12]}…); keep one")
    for doc in docs:
        if not SHA256.match(doc.sha256):
            res.error(NAME, doc.id, f"invalid sha256 '{doc.sha256}'")
            continue
        for problem in (*_shape(ctx, doc), *_file_problems(ctx, doc)):
            res.error(NAME, doc.id, problem)
    for sha in sorted(set(ctx.kept_files or ()) - {d.sha256 for d in docs}):
        res.error(NAME, sha[:12], f"kept file {sha[:12]}… has no Document")
