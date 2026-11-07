from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Sequence, assert_never

from radar.domain.model.entities import (CLASSES, Claim, ClaimValue, ClaimValueBoolean, ClaimValueTerm, ClaimValueTerms,
                                         Entity, Product, ProductOrgRole)
from radar.domain.model.history.changeset import UNNUMBERED, Change, Changeset, PutEntity, Retract, as_record
from radar.domain.model.history.ids import keyed
from radar.domain.model.model import Model, ParseError
from radar.domain.ports.catalog.catalog import Catalog

MIGRATION = "migration"

@dataclass(frozen=True, slots=True)
class DropField:
    kind: str
    field: str

@dataclass(frozen=True, slots=True)
class RenameSpec:
    spec: str
    to: str

@dataclass(frozen=True, slots=True)
class MoveTerms:
    spec: str
    to: str
    terms: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class MapTerm:
    spec: str
    term: str
    to: str | None
    slugs: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class TrueAsTerm:
    spec: str
    to: str
    term: str

@dataclass(frozen=True, slots=True)
class MoveCategory:
    slugs: tuple[str, ...]
    category: str

Rule = DropField | RenameSpec | MoveTerms | MapTerm | TrueAsTerm | MoveCategory

@dataclass(frozen=True, slots=True)
class MigrationPlan:
    reason: str
    rules: tuple[Rule, ...]

def parse_plan(raw: object, model: Model) -> MigrationPlan:
    if (not isinstance(raw, dict) or not isinstance(raw.get("reason"), str) or not raw["reason"].strip()
            or not isinstance(raw.get("rules"), list) or not raw["rules"]):
        raise ParseError('a migration plan is {"reason": "...", "rules": [...]} with at least one rule')
    return MigrationPlan(raw["reason"].strip(), tuple(_rule(n, r, model) for n, r in enumerate(raw["rules"])))

def _text(n: int, raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ParseError(f"rules[{n}]: {raw.get('rule')} takes a {key}")
    return value

def _spec(n: int, raw: dict[str, object], key: str, model: Model) -> str:
    spec = _text(n, raw, key)
    if spec not in model.registry.spec_definitions:
        raise ParseError(f"rules[{n}]: no spec {spec!r}")
    return spec

def _texts(n: int, raw: dict[str, object], key: str) -> tuple[str, ...]:
    values = raw.get(key)
    if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
        raise ParseError(f"rules[{n}]: {raw.get('rule')} takes a list of {key}")
    return tuple(values)

def _drop_field(n: int, raw: dict[str, object], model: Model) -> Rule:
    kind, field = raw.get("kind"), raw.get("field")
    spec = model.schema.types.get(kind) if isinstance(kind, str) else None
    if spec is None or kind not in CLASSES:
        raise ParseError(f"rules[{n}]: no entity kind {kind!r}")
    found = next((f for f in spec.fields if f.name == field), None)
    if found is None or not found.optional:
        raise ParseError(f"rules[{n}]: {kind} has no optional field {field!r}")
    return DropField(kind, str(field))

def _move_category(n: int, raw: dict[str, object], model: Model) -> Rule:
    category = _text(n, raw, "category")
    if category not in model.registry.categories:
        raise ParseError(f"rules[{n}]: no category {category!r}")
    return MoveCategory(_texts(n, raw, "slugs"), category)

def _rule(n: int, raw: object, model: Model) -> Rule:
    if not isinstance(raw, dict):
        raise ParseError(f"rules[{n}]: a rule is an object")
    match raw.get("rule"):
        case "drop_field":
            return _drop_field(n, raw, model)
        case "rename_spec":
            return RenameSpec(_spec(n, raw, "spec", model), _spec(n, raw, "to", model))
        case "move_terms":
            return MoveTerms(_spec(n, raw, "spec", model), _spec(n, raw, "to", model), _texts(n, raw, "terms"))
        case "map_term":
            to, slugs = raw.get("to"), _texts(n, raw, "slugs") if "slugs" in raw else ()
            return MapTerm(_spec(n, raw, "spec", model), _text(n, raw, "term"), to if isinstance(to, str) else None,
                           slugs)
        case "true_as_term":
            return TrueAsTerm(_spec(n, raw, "spec", model), _spec(n, raw, "to", model), _text(n, raw, "term"))
        case "move_category":
            return _move_category(n, raw, model)
    raise ParseError(f"rules[{n}]: a rule is one of drop_field, rename_spec, move_terms, map_term, true_as_term, "
                     "move_category")

def _cited(catalog: Catalog, entity: Entity) -> tuple[str, ...]:
    if refs := as_record(entity).get("source_refs"):
        return tuple(str(r) for r in refs)
    if isinstance(entity, Product):
        roles = [r for r in catalog.all(ProductOrgRole) if r.product == entity.id]
        claims = [c for c in catalog.all(Claim) if c.subject == entity.id]
        return next((tuple(r.source_refs) for r in (*roles, *claims) if r.source_refs), ())
    return ()

def _terms_of(claim: Claim) -> tuple[str, ...]:
    match claim.value:
        case ClaimValueTerm(term=term):
            return (term,)
        case ClaimValueTerms(terms=terms):
            return terms
    return ()

def _valued(terms: tuple[str, ...], datatype: str) -> ClaimValue:
    match datatype:
        case "boolean":
            return ClaimValueBoolean(boolean=True)
        case "term_set":
            return ClaimValueTerms(terms=terms)
    return ClaimValueTerm(term=terms[0])

class _Claims:
    def __init__(self, catalog: Catalog, model: Model) -> None:
        self._specs = model.registry.spec_definitions
        self.held = {c.id: c for c in catalog.all(Claim)}
        self.now: dict[str, Claim] = dict(self.held)
        self._at = {(c.subject, c.spec_key): c.id for c in self.held.values()}

    def _of(self, spec: str) -> list[Claim]:
        return [c for c in self.now.values() if c.spec_key == spec]

    def _gone(self, claim: Claim) -> None:
        del self.now[claim.id]
        self._at.pop((claim.subject, claim.spec_key), None)

    def _set(self, like: Claim, spec: str, terms: tuple[str, ...]) -> None:
        datatype = self._specs[spec].datatype
        held = self.now.get(self._at.get((like.subject, spec), ""))
        if held is not None and terms:
            merged = tuple(dict.fromkeys((*_terms_of(held), *terms)))
            self.now[held.id] = replace(held, value=_valued(merged, datatype), version=UNNUMBERED)
        elif terms:
            made = replace(like, id=keyed("clm", f"{like.subject}:{spec}"), spec_key=spec,
                           value=_valued(terms, datatype), version=UNNUMBERED)
            self.now[made.id] = made
            self._at[(like.subject, spec)] = made.id

    def rename(self, rule: RenameSpec) -> None:
        for claim in self._of(rule.spec):
            self._gone(claim)
            if (claim.subject, rule.to) not in self._at:
                made = replace(claim, id=keyed("clm", f"{claim.subject}:{rule.to}"), spec_key=rule.to,
                               version=UNNUMBERED)
                self.now[made.id] = made
                self._at[(claim.subject, rule.to)] = made.id

    def move(self, rule: MoveTerms) -> None:
        for claim in self._of(rule.spec):
            moved = tuple(t for t in _terms_of(claim) if t in rule.terms)
            if moved:
                self._kept(claim, tuple(t for t in _terms_of(claim) if t not in rule.terms))
                self._set(claim, rule.to, moved)

    def true_as(self, rule: TrueAsTerm) -> None:
        for claim in self._of(rule.spec):
            self._gone(claim)
            if claim.value == ClaimValueBoolean(boolean=True) and (claim.subject, rule.to) not in self._at:
                self._set(claim, rule.to, (rule.term,))

    def map(self, rule: MapTerm, ids: frozenset[str]) -> None:
        for claim in self._of(rule.spec):
            terms = _terms_of(claim)
            if rule.term in terms and (not rule.slugs or claim.subject in ids):
                mapped = (rule.to,) if rule.to else ()
                rest = tuple(t for t in terms if t != rule.term)
                self._kept(claim, tuple(dict.fromkeys((*rest, *mapped))))

    def _kept(self, claim: Claim, terms: tuple[str, ...]) -> None:
        if terms:
            self.now[claim.id] = replace(claim, value=_valued(terms, self._specs[claim.spec_key].datatype),
                                         version=UNNUMBERED)
        else:
            self._gone(claim)

    def outside(self, subject: str, allowed: frozenset[str]) -> None:
        for claim in [c for c in self.now.values() if c.subject == subject and c.spec_key not in allowed]:
            self._gone(claim)

    def changes(self, reason: str) -> tuple[list[Change], Counter[str]]:
        counts: Counter[str] = Counter()
        changes = []
        for claim_id, claim in self.now.items():
            if claim != self.held.get(claim_id):
                counts[f"claim put: {claim.spec_key}"] += 1
                changes.append(Change(PutEntity(claim), reason, "agent", MIGRATION, tuple(claim.source_refs)))
        for claim_id, claim in self.held.items():
            if claim_id not in self.now:
                counts[f"claim retracted: {claim.spec_key}"] += 1
                changes.append(Change(Retract(claim_id), reason, "agent", MIGRATION, tuple(claim.source_refs)))
        return changes, counts

def _dropped(catalog: Catalog, plan: MigrationPlan, rule: DropField) -> tuple[list[Change], Counter[str]]:
    counts: Counter[str] = Counter()
    changes = []
    for entity in catalog.all(CLASSES[rule.kind]):
        if as_record(entity).get(rule.field) is None:
            continue
        cited = _cited(catalog, entity)
        counts[f"{rule.kind}.{rule.field}" if cited else f"{rule.kind}.{rule.field}: uncited, left"] += 1
        if cited:
            moved = replace(entity, **{rule.field: None, "version": UNNUMBERED})
            changes.append(Change(PutEntity(moved), plan.reason, "agent", MIGRATION, cited))
    return changes, counts

def _recategorized(catalog: Catalog, plan: MigrationPlan, rule: MoveCategory, claims: _Claims,
                   model: Model) -> tuple[list[Change], Counter[str]]:
    profile = next(p for p in model.registry.profiles if p.category_id == rule.category)
    allowed = frozenset((*profile.sections.core, *profile.sections.detail))
    wanted = set(rule.slugs)
    counts: Counter[str] = Counter()
    changes = []
    for product in catalog.all(Product):
        if product.slug not in wanted or product.category == rule.category:
            continue
        claims.outside(product.id, allowed)
        cited = _cited(catalog, product)
        counts[f"category: {rule.category}" if cited else "category: uncited, left"] += 1
        if cited:
            moved = replace(product, category=rule.category, version=UNNUMBERED)
            changes.append(Change(PutEntity(moved), plan.reason, "agent", MIGRATION, cited))
    return changes, counts

def _applied(rule: Rule, catalog: Catalog, plan: MigrationPlan, claims: _Claims,
             model: Model) -> tuple[list[Change], Counter[str]]:
    match rule:
        case DropField():
            return _dropped(catalog, plan, rule)
        case MoveCategory():
            return _recategorized(catalog, plan, rule, claims, model)
        case RenameSpec():
            claims.rename(rule)
        case MoveTerms():
            claims.move(rule)
        case MapTerm():
            claims.map(rule, frozenset(p.id for p in catalog.all(Product) if p.slug in rule.slugs))
        case TrueAsTerm():
            claims.true_as(rule)
        case _:
            assert_never(rule)
    return [], Counter()

def migrated(catalog: Catalog, plan: MigrationPlan, model: Model) -> tuple[Changeset, Counter[str]]:
    claims = _Claims(catalog, model)
    changes: list[Change] = []
    counts: Counter[str] = Counter()
    for rule in plan.rules:
        made, counted = _applied(rule, catalog, plan, claims, model)
        changes += made
        counts += counted
    moved, counted = claims.changes(plan.reason)
    return Changeset((*changes, *moved)), counts + counted

def batches(changeset: Changeset, size: int) -> Sequence[Changeset]:
    return [Changeset(changeset.changes[n:n + size]) for n in range(0, len(changeset.changes), size)]
