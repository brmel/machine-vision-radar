from __future__ import annotations

from dataclasses import replace
from typing import Collection, Mapping, Sequence

from radar.domain.read_model.derived.lineage import DisplayedStatus
from radar.domain.read_model.derived.current_source import current_source
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import (AltName, CategoryProfile, Claim, ComponentLink, Document, EventRow, HubRef,
                                         Identifier, IdentifierRow, LifecycleEvent, MediaItem, ModelRow, ModelSpec,
                                         Name, Offering, OfferingRow, OrgBrief, PartialDate, Price, Product,
                                         ProductLink, ProductSheet, ProductVersion, ProductView, Relation, RelationRow,
                                         RelationSide, Source, SpecCell, StatusView, TermRef, VersionRow)
from radar.domain.model.registry import Registry
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.catalog.views import MediaUrl
from radar.domain.model.dates import start_of
from radar.domain.read_model.products.values import Terms, view_value

RowField = str | TermRef | PartialDate | Price

class ProductViews:
    def __init__(self, catalog: Catalog, registry: Registry, schema: ModelSchema, exported: dict[str, Product],
                 media_url: MediaUrl, built: Collection[str], kept: Mapping[str, Sequence[ModelRow]] | None) -> None:
        self.catalog, self.registry, self.schema, self.terms, self.exported = (
            catalog, registry, schema, Terms(registry), exported)
        self.media_url, self.built, self.kept = media_url, set(built), kept or {}
        self.hubs = {c.id: c.component_hub for c in registry.categories.values() if c.component_hub}
        used = [r for r in catalog.all(Relation) if r.from_entity in exported and r.to_entity in exported
                and (hub := self.hubs.get(exported[r.to_entity].category)) is not None and r.type == hub.relation]
        self.uses: dict[str, set[str]] = {}
        self.users: dict[str, set[str]] = {}
        for r in used:
            self.uses.setdefault(r.from_entity, set()).add(r.to_entity)
            self.users.setdefault(r.to_entity, set()).add(r.from_entity)

    def link(self, pid: str, names: dict[str, str]) -> ProductLink:
        p = self.exported[pid]
        return ProductLink(id=p.id, slug=p.slug, name=names[p.id])

    def cells(self, p: Product, keys: tuple[str, ...], cited: dict[str, Source]) -> tuple[SpecCell, ...]:
        by_key: dict[str, list[Claim]] = {}
        for c in self.catalog.claims_for(p.id):
            by_key.setdefault(c.spec_key, []).append(c)
        return tuple(self._cell(key, by_key.get(key, []), cited) for key in keys)

    def _cell(self, key: str, claims: list[Claim], cited: dict[str, Source]) -> SpecCell:
        claims = [c for c in claims if c.rank == min(x.rank for x in claims)]
        value = view_value([c.value for c in claims], self.registry.spec_definitions[key], self.terms)
        source = None if value is None else self.sourced(tuple(sorted({r for c in claims for r in c.source_refs})),
                                                         cited)
        return SpecCell(key=key, value=value, source=source) if source else SpecCell(key=key)

    def sourced(self, refs: tuple[str, ...], cited: dict[str, Source]) -> str | None:
        sources = [s for s in map(self.catalog.get, refs) if isinstance(s, Source)]
        if not sources:
            return None
        src = current_source(sources, self.registry)
        cited[src.id] = src
        return src.id

    def _fields(self, entity: object, names: tuple[str, ...], vocabs: dict[str, str]) -> dict[str, RowField]:
        out: dict[str, RowField] = {}
        for name in names:
            value = getattr(entity, name, None)
            if value is None:
                continue
            out[name] = self.terms.term(vocabs[name], value) if name in vocabs else value
        return out

    def view(self, p: Product, names: dict[str, str], vendor: OrgBrief, history: bool) -> ProductView:
        profile = self.registry.profile(p.category)
        cited: dict[str, Source] = {}
        models = self._models(p, names, profile)
        core, detail = self._specs(p, profile, cited)
        return ProductView(
            id=p.id, slug=p.slug, name=names[p.id], kind=p.kind, version=p.version, history=history,
            category=p.category, summary=dict(p.summary) if p.summary else None, website_url=p.website_url or None,
            vendor=vendor, status=self._status(p, cited), tags=tuple(self.terms.term("tags", t) for t in p.tags or ()),
            identifiers=self._identifiers(p), aliases=self._aliases((p.id, vendor.id)),
            thumbnail_url=self._thumbnail_url(p), family=self._family(p, names), models=models, core=core,
            detail=detail, versions=self._versions(p, profile, cited), offerings=self._offerings(p, profile, cited),
            lifecycle=self._lifecycle(p, cited), relations=self._relations(p, names),
            components=self._components(p, names), hub=self._hub(p), media=self.media(p),
            indexable=set(profile.required_at_publish) <= {c.key for c in (*core, *detail) if c.value is not None},
            sources=tuple(self.terms.source_view(cited[k]) for k in sorted(cited)))

    def _family(self, p: Product, names: dict[str, str]) -> ProductLink | None:
        # Data-driven exception: a model's parent is its family, a level of the product tree.
        return self.link(p.parent, names) if p.parent in self.exported and p.kind == "model" else None

    def _thumbnail_url(self, p: Product) -> str | None:
        if not p.thumbnail:
            return None
        doc = self.catalog.get(p.thumbnail)
        if not isinstance(doc, Document):
            return None
        rights = self.registry.vocabularies["media_rights"].get(doc.rights)
        return self.media_url(doc.sha256, doc.mime) if rights and rights.public else None

    def _status(self, p: Product, cited: dict[str, Source]) -> StatusView | None:
        status = DisplayedStatus.of(self.catalog, self.registry, p.id)
        return StatusView(term=self.terms.term("lifecycle_event_types", status.term),
                          source=self.sourced(status.source_refs, cited)) if status else None

    def _identifiers(self, p: Product) -> tuple[IdentifierRow, ...]:
        schemes = self.registry.vocabularies["identifier_schemes"]
        order = list(schemes)
        found = sorted((i for i in self.catalog.all(Identifier) if i.subject == p.id),
                       key=lambda i: (order.index(i.scheme), i.value))
        return tuple(IdentifierRow(scheme=self.terms.term("identifier_schemes", i.scheme), value=i.value,
                                   schema_org=schemes[i.scheme].schema_org or None) for i in found)

    def _aliases(self, subjects: tuple[str, ...]) -> tuple[str, ...] | None:
        return tuple(sorted({a.value for a in self.catalog.all(AltName) if a.subject in subjects}
                            | {n.value for n in self.catalog.all(Name) if n.subject in subjects and not n.is_primary})
                     ) or None

    def _versions(self, p: Product, profile: CategoryProfile, cited: dict[str, Source]) -> tuple[VersionRow, ...]:
        vocabs = {f.name: f.vocabulary for f in self.schema.types[ProductVersion.__name__].fields if f.vocabulary}
        return tuple(VersionRow(id=v.id, **self._fields(v, profile.sections.versions, vocabs),
                                source=self.sourced(v.source_refs, cited))
                     for v in self.catalog.versions_of(p.id))

    def _offerings(self, p: Product, profile: CategoryProfile, cited: dict[str, Source]) -> tuple[OfferingRow, ...]:
        vocabs = {f.name: f.vocabulary for f in self.schema.types[Offering.__name__].fields if f.vocabulary}
        found = sorted((o for o in self.catalog.all(Offering) if o.product == p.id), key=lambda o: o.id)
        return tuple(OfferingRow(id=o.id, **self._fields(o, profile.sections.offerings, vocabs),
                                 source=self.sourced(o.source_refs, cited))
                     for o in found)

    def _lifecycle(self, p: Product, cited: dict[str, Source]) -> tuple[EventRow, ...]:
        states = self.registry.vocabularies["lifecycle_event_states"]
        return tuple(EventRow(id=e.id, type=self.terms.term("lifecycle_event_types", e.type),
                              state=self.terms.term("lifecycle_event_states", e.state),
                              occurred=bool(states[e.state].occurred), date=e.date,
                              source=self.sourced(e.source_refs, cited))
                     for e in self._events(p))

    def _specs(self, p: Product, profile: CategoryProfile,
               cited: dict[str, Source]) -> tuple[tuple[SpecCell, ...], tuple[SpecCell, ...]]:
        groups = (*profile.groups, *(p.spec_groups or ()))
        detail = tuple(dict.fromkeys((*profile.sections.detail, *self.registry.group_specs(p.spec_groups or ()))))
        core = self.cells(p, profile.sections.core, cited)
        return core, tuple(replace(cell, group=self.registry.group_of(groups, cell.key))
                           for cell in self.cells(p, detail, cited))

    def _models(self, p: Product, names: dict[str, str], profile: CategoryProfile) -> tuple[ModelRow, ...]:
        built = (ModelRow(id=m.id, slug=m.slug, name=names[m.id], specs=tuple(
            ModelSpec(key=c.key, value=c.value) for c in self.cells(m, profile.sections.core, {})))
                 for m in self.exported.values() if m.parent == p.id and m.id in self.built)
        return tuple(sorted((*self.kept.get(p.id, ()), *built), key=lambda r: (r.name.lower(), r.id)))

    def _events(self, p: Product) -> list[LifecycleEvent]:
        return sorted((e for e in self.catalog.all(LifecycleEvent) if e.product == p.id),
                      key=lambda e: (start_of(e.date), e.id))

    def _side(self, r: Relation, product: str) -> tuple[str, RelationSide | None]:
        sides = self.registry.vocabularies["relation_types"][r.type]
        return (r.to_entity, sides.from_side) if r.from_entity == product else (r.from_entity, sides.to_side)

    def _hubbed(self, product: str) -> set[tuple[str, str]]:
        return {(product, c) for c in self.uses.get(product, ())} | {(u, product) for u in self.users.get(product, ())}

    def _relations(self, p: Product, names: dict[str, str]) -> tuple[RelationRow, ...]:
        hubbed = self._hubbed(p.id)
        order = list(self.registry.vocabularies["relation_types"])
        found = [(r, *self._side(r, p.id)) for r in self.catalog.all(Relation) if p.id in (r.from_entity, r.to_entity)
                 and (r.from_entity, r.to_entity) not in hubbed]
        shown = sorted(((r, o, s) for r, o, s in found if o in self.exported and s),
                       key=lambda f: (order.index(f[0].type), f[0].to_entity == p.id, names[f[1]].lower(), f[1]))
        return tuple(RelationRow(type=r.type, label=dict(side.label), product=self.link(other, names), basis=r.basis,
                                 schema_org=side.schema_org or None) for r, other, side in shown)

    def _components(self, p: Product, names: dict[str, str]) -> tuple[ComponentLink, ...]:
        return tuple(ComponentLink(id=c, slug=self.exported[c].slug, name=names[c],
                                   hub=self.hubs[self.exported[c].category].path)
                     for c in sorted(self.uses.get(p.id, ()), key=lambda c: (names[c].lower(), c)))

    def _hub(self, p: Product) -> HubRef | None:
        return HubRef(path=self.hubs[p.category].path, users=len(self.users[p.id])) if p.id in self.users else None

    def _media_item(self, d: Document, versions: dict[str, ProductVersion], public: bool) -> MediaItem:
        href = self.media_url(d.sha256, d.mime) if public else d.source_url
        v = next((versions[s] for s in d.subjects if s in versions and versions[s].label), None)
        return MediaItem(id=d.id, kind=self.terms.term("document_kinds", d.kind), mime=d.mime, bytes=d.bytes,
                         rights=self.terms.term("media_rights", d.rights), title=dict(d.title) if d.title else None,
                         language=d.language or None, href=href or None, source_url=d.source_url or None,
                         version=v.label if v else None)

    def media(self, p: Product) -> tuple[MediaItem, ...]:
        kinds = list(self.registry.vocabularies["document_kinds"])
        versions = {v.id: v for v in self.catalog.all(ProductVersion) if v.product == p.id}
        docs = sorted((d for d in self.catalog.all(Document) if p.id in d.subjects
                       or any(s in versions for s in d.subjects)),
                      key=lambda d: (kinds.index(d.kind) if d.kind in kinds else len(kinds), d.id))
        rights = self.registry.vocabularies["media_rights"]
        return tuple(self._media_item(d, versions, rights[d.rights].public) for d in docs)

def product_sheet(repository: CatalogRepository, key: str) -> ProductSheet:
    if (product := repository.product(key)) is None:
        raise LookupError(f"no product '{key}'")
    labels = repository.index().spec_definitions
    return ProductSheet(product=product,
                        spec_definitions={c.key: labels[c.key] for c in (*product.core, *product.detail)})
