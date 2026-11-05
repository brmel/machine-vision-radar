from __future__ import annotations

from typing import Collection, Literal, Mapping, Sequence

from radar.domain.model.entities import (AdminModel, AiCap, BundleMember, BundleView, Category, Change,
                                         ClaimValueNone, DecisionOutcome, EntityShape, EvalQuery, FeedItem, FieldShape,
                                         HeldProposal, KindEntry, OwnedShape, ProposalEdit, ProposalPage, ProposalView,
                                         ProposedChange, RefusedProposal, SectionKeys, SpecGroup, SpecShape, Term,
                                         TermList, TermRef, UnitShape)
from radar.domain.model.registry import Registry
from radar.domain.model.schema import FieldSpec, ModelSchema, SchemaError, TypeSpec
from radar.domain.model.history.changeset import EntityChange, changeset_json
from radar.domain.model.history.projection import json_text
from radar.domain.ports.review.proposal_queue import QueuePage
from radar.domain.review.proposal import Member, Outcome, Proposal, Shown
from radar.domain.validation.rules.claims.claim_values import VARIANTS

def proposal_view(p: Proposal, changes: Sequence[EntityChange] | None = None,
                  problem: str | None = None) -> ProposalView:
    return ProposalView(id=p.id, files_on=p.files_on, status=p.status, subject=p.subject, reason=p.reason,
                        message=p.message, source_url=p.source_url, actor_kind=p.actor_kind, author=p.author,
                        created_at=p.created_at, reports=p.reports, reviewer=p.reviewer, note=p.note,
                        decided_at=p.decided_at, sources=p.sources,
                        edits=tuple(ProposalEdit(at=e.at, actor=e.actor, note=e.note) for e in p.edits),
                        token_id=p.token, bundle=p.bundle, problem=problem,
                        changes=None if changes is None
                        else tuple(ProposedChange(entity=c.entity, before=json_text(c.before), after=json_text(c.after))
                                   for c in changes),
                        changeset=json_text(changeset_json(p.changeset)) if changes is not None and p.changeset
                        else None)

def shown_view(shown: Shown) -> ProposalView:
    return proposal_view(shown.proposal, shown.changes, shown.problem)

def proposals_view(proposals: Sequence[Proposal]) -> ProposalPage:
    return ProposalPage(proposals=tuple(proposal_view(p) for p in proposals))

def bundle_view(bundle: str, members: Sequence[Member]) -> BundleView:
    return BundleView(id=bundle,
                      members=tuple(BundleMember(proposal=proposal_view(m.proposal), risk=m.risk, after=m.after)
                                    for m in members))

def outcome_view(outcome: Outcome) -> DecisionOutcome:
    return DecisionOutcome(done=tuple(proposal_view(p) for p in outcome.done),
                           refused=tuple(RefusedProposal(proposal=proposal_view(r.proposal), findings=r.findings)
                                         for r in outcome.refused),
                           held=tuple(HeldProposal(proposal=proposal_view(h.proposal), waits_on=h.waits_on)
                                      for h in outcome.held))

def page_view(page: QueuePage) -> ProposalPage:
    return ProposalPage(proposals=tuple(proposal_view(p) for p in page.proposals), next=page.cursor, total=page.total)

OWNED = {Change.__name__: "/queue/log", EvalQuery.__name__: "/search", AiCap.__name__: "/search/settings",
         FeedItem.__name__: "/news"}
SHAPED = ("units", "dimensions", "spec_definitions")
Input = Literal["text", "number", "flag", "date", "localized", "term", "terms", "choice", "json"]
INPUTS: dict[str, Input] = {
    "string": "text", "EntityId": "text", "TermId": "text", "Instant": "text", "integer": "number", "number": "number",
    "boolean": "flag", "PartialDate": "date", "LocalizedText": "localized", "enum": "choice"}

def _input(schema: ModelSchema, f: FieldSpec, listed: Collection[str]) -> Input:
    if f.vocabulary in listed:
        return "terms" if f.type == "array" else "term"
    if f.type in INPUTS:
        return INPUTS[f.type]
    if f.type in ("array", "map") or schema.types[f.type].kind in ("record", "union", "map"):
        return "json"
    raise SchemaError(f"the admin has no input for {f.name}, a {f.type}")

def _field(schema: ModelSchema, f: FieldSpec, listed: Collection[str]) -> FieldShape:
    return FieldShape(name=f.name, label=dict(f.label or {}), type=f.type, values=tuple(f.values),
                      optional=f.optional, vocabulary=f.vocabulary, refs=tuple(f.refs),
                      input=_input(schema, f, listed))

def _entity(schema: ModelSchema, t: TypeSpec, listed: Collection[str]) -> EntityShape:
    return EntityShape(id=t.name, label=dict(t.label or {}), prefix=t.prefix or "", provenance=t.provenance,
                       fields=tuple(_field(schema, f, listed) for f in t.fields))

def _vocabularies(types: Sequence[TypeSpec], registry: Registry, absence: str) -> dict[str, TermList]:
    bound = {f.vocabulary for t in types for f in t.fields if f.vocabulary} | {
        s.vocabulary for s in registry.spec_definitions.values() if s.vocabulary} | {absence}
    labelled: dict[str, Mapping[str, Term | Category | SpecGroup]] = {
        **registry.vocabularies, "categories": registry.categories, "spec_groups": registry.spec_groups}
    return {name: TermList(terms=tuple(TermRef(id=i, label=dict(t.label)) for i, t in labelled[name].items()))
            for name in sorted(bound - set(SHAPED))}

def _owned(schema: ModelSchema) -> tuple[OwnedShape, ...]:
    return tuple(OwnedShape(id=t.name, label=dict(t.label or {}), prefix=t.prefix or "", screen=OWNED[t.name])
                 for t in schema.entities if t.name in OWNED)

def _kinds(registry: Registry) -> tuple[KindEntry, ...]:
    return tuple(KindEntry(id=t.id, label=dict(t.label), files_on=t.files_on)
                 for t in registry.vocabularies["proposal_kinds"].values() if t.files_on)

def _specs(registry: Registry) -> dict[str, SpecShape]:
    return {k: SpecShape(label=dict(s.label), datatype=s.datatype, dimension=s.dimension, unit=s.unit,
                         vocabulary=s.vocabulary) for k, s in registry.spec_definitions.items()}

def admin_model(schema: ModelSchema, registry: Registry) -> AdminModel:
    types = [t for t in schema.entities if t.name not in OWNED]
    [absence] = [v.vocabulary for v in schema.types["ClaimValue"].variants if v.vocabulary]
    vocabularies = _vocabularies(types, registry, absence)
    return AdminModel(
        entities=tuple(_entity(schema, t, vocabularies) for t in types),
        owned=_owned(schema),
        vocabularies=vocabularies,
        specs=_specs(registry),
        units={k: UnitShape(symbol=u.symbol, dimension=u.dimension) for k, u in registry.units.items()},
        profiles={p.category_id: SectionKeys(core=tuple(p.sections.core), detail=tuple(p.sections.detail))
                  for p in registry.profiles},
        kinds=_kinds(registry),
        none_vocabulary=absence,
        none_datatypes=tuple(d for d, takes in VARIANTS.items() if ClaimValueNone in takes),
    )
