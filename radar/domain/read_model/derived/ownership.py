from __future__ import annotations

from datetime import date

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import OrgRelation
from radar.domain.model.dates import start_of
from radar.domain.model.registry import Registry

class OwnershipHistory:
    def __init__(self, catalog: Catalog, registry: Registry) -> None:
        self._relations = sorted(catalog.all(OrgRelation),
                                 key=lambda r: (start_of(r.valid_from) if r.valid_from else date.min, r.id))
        self._owning = registry.marked("org_relation_types", lambda t: t.owns)
        self._renaming = registry.marked("org_relation_types", lambda t: t.renames)

    def _valid(self, r: OrgRelation, day: date) -> bool:
        return ((r.valid_from is None or start_of(r.valid_from) <= day)
                and (r.valid_to is None or day < start_of(r.valid_to)))

    def _names(self, org: str) -> set[str]:
        names, todo = {org}, [org]
        while todo:
            current = todo.pop()
            for r in self._relations:
                if r.type in self._renaming and current in (r.from_org, r.to_org):
                    for other in (r.from_org, r.to_org):
                        if other not in names:
                            names.add(other)
                            todo.append(other)
        return names

    def name_on(self, org: str, day: date) -> str:
        renamed = [r for r in self._relations if r.type in self._renaming and r.to_org == org and self._valid(r, day)]
        return self.name_on(renamed[-1].from_org, day) if renamed else org

    def owner_on(self, org: str, day: date) -> str | None:
        names = self._names(org)
        owning = [r for r in self._relations if r.type in self._owning and r.from_org in names and self._valid(r, day)]
        return self.name_on(owning[-1].to_org, day) if owning else None

    def owners_on(self, org: str, day: date) -> list[str]:
        chain: list[str] = []
        owner = self.owner_on(org, day)
        while owner is not None and owner not in chain:
            chain.append(owner)
            owner = self.owner_on(owner, day)
        return chain

    def relations_of(self, org: str) -> list[OrgRelation]:
        names = self._names(org)
        return [r for r in self._relations if r.from_org in names or r.to_org in names]
