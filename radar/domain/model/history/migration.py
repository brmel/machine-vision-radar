from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Sequence

from radar.domain.model.entities import CLASSES, Claim, Entity, Product, ProductOrgRole
from radar.domain.model.history.changeset import UNNUMBERED, Change, Changeset, PutEntity, as_record
from radar.domain.model.model import Model, ParseError
from radar.domain.ports.catalog.catalog import Catalog

MIGRATION = "migration"

@dataclass(frozen=True, slots=True)
class DropField:
    kind: str
    field: str

Rule = DropField

@dataclass(frozen=True, slots=True)
class MigrationPlan:
    reason: str
    rules: tuple[Rule, ...]

def parse_plan(raw: object, model: Model) -> MigrationPlan:
    if (not isinstance(raw, dict) or not isinstance(raw.get("reason"), str) or not raw["reason"].strip()
            or not isinstance(raw.get("rules"), list) or not raw["rules"]):
        raise ParseError('a migration plan is {"reason": "...", "rules": [...]} with at least one rule')
    return MigrationPlan(raw["reason"].strip(), tuple(_rule(n, r, model) for n, r in enumerate(raw["rules"])))

def _rule(n: int, raw: object, model: Model) -> Rule:
    if not isinstance(raw, dict) or raw.get("rule") != "drop_field":
        raise ParseError(f'rules[{n}]: a rule is {{"rule": "drop_field", "kind": "<entity>", "field": "<optional>"}}')
    kind, field = raw.get("kind"), raw.get("field")
    spec = model.schema.types.get(kind) if isinstance(kind, str) else None
    if spec is None or kind not in CLASSES:
        raise ParseError(f"rules[{n}]: no entity kind {kind!r}")
    found = next((f for f in spec.fields if f.name == field), None)
    if found is None or not found.optional:
        raise ParseError(f"rules[{n}]: {kind} has no optional field {field!r}")
    return DropField(kind, str(field))

def _cited(catalog: Catalog, entity: Entity) -> tuple[str, ...]:
    if refs := as_record(entity).get("source_refs"):
        return tuple(str(r) for r in refs)
    if isinstance(entity, Product):
        roles = [r for r in catalog.all(ProductOrgRole) if r.product == entity.id]
        claims = [c for c in catalog.all(Claim) if c.subject == entity.id]
        return next((tuple(r.source_refs) for r in (*roles, *claims) if r.source_refs), ())
    return ()

def _moved(rule: Rule, entity: Entity) -> Entity | None:
    if type(entity).__name__ != rule.kind or as_record(entity).get(rule.field) is None:
        return None
    return replace(entity, **{rule.field: None, "version": UNNUMBERED})

def migrated(catalog: Catalog, plan: MigrationPlan) -> tuple[Changeset, Counter[str]]:
    counts: Counter[str] = Counter()
    changes: list[Change] = []
    for rule in plan.rules:
        for entity in catalog.all(CLASSES[rule.kind]):
            moved = _moved(rule, entity)
            if moved is None:
                continue
            cited = _cited(catalog, entity)
            counts[f"{rule.kind}.{rule.field}" if cited else f"{rule.kind}.{rule.field}: uncited, left"] += 1
            if cited:
                changes.append(Change(PutEntity(moved), plan.reason, "agent", MIGRATION, cited))
    return Changeset(tuple(changes)), counts

def batches(changeset: Changeset, size: int) -> Sequence[Changeset]:
    return [Changeset(changeset.changes[n:n + size]) for n in range(0, len(changeset.changes), size)]
