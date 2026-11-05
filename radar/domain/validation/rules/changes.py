from __future__ import annotations

import re
from collections import defaultdict

from radar.domain.model.history.projection import field_diff, plain, replay
from radar.domain.model.entities import Change
from radar.domain.model.history.changeset import without_version
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.verdict import Finding, Findings

NAME = "changes"
PROPOSAL = re.compile(r"prp_[0-9a-hjkmnp-tv-z]{10}")

def _check_entity(ctx: ValidationContext, entity_id: str, changes: list[Change]) -> Findings:
    versions = sorted(c.version for c in changes)
    if versions != list(range(1, len(versions) + 1)):
        yield Finding(NAME, entity_id, f"change versions are {versions}; they must run 1..{len(versions)} without gaps")
        return
    try:
        replayed = replay(changes)
    except ValueError as exc:
        yield Finding(NAME, entity_id, f"patches do not apply: {exc}")
        return
    entity = ctx.catalog.get(entity_id)
    if entity is None:
        if replayed != {}:
            yield Finding(NAME, entity_id,
                          "changes for an entity that is not stored (only a retraction's last change empties it)")
        return
    if entity.version != versions[-1]:
        yield Finding(NAME, entity_id,
                      f"stored version {entity.version} is not the latest change version {versions[-1]}")
    for diff in field_diff(replayed, without_version(plain(entity)))[:1]:
        yield Finding(NAME, entity_id,
                      f"patches replay to {diff.before!r} at '{diff.path}', the stored entity has {diff.after!r}")
    yield from _check_changes(changes, sourced=hasattr(entity, "source_refs"))

def _check_changes(changes: list[Change], sourced: bool) -> Findings:
    for c in changes:
        if sourced and not c.source_refs and any(op.op != "remove" for op in c.patch):
            yield Finding(NAME, c.id, f"version {c.version} sets a sourced fact without citing a source")
        if c.proposal is not None and not PROPOSAL.fullmatch(c.proposal):
            yield Finding(NAME, c.id, f"proposal '{c.proposal}' is not a proposal id")

def check(ctx: ValidationContext) -> Findings:
    by_entity: dict[str, list[Change]] = defaultdict(list)
    for c in ctx.catalog.all(Change):
        by_entity[c.entity].append(c)
    for entity_id, changes in sorted(by_entity.items()):
        yield from _check_entity(ctx, entity_id, changes)
