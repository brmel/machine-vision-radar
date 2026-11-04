from __future__ import annotations

from typing import TYPE_CHECKING

from radar.domain.read_model.derived.ownership import OwnershipHistory
from radar.domain.model.entities import OrgBrief, Organization, OrganizationView, OwnershipRow, Source

if TYPE_CHECKING:
    from .products.views import ProductViews

def brief(o: Organization) -> OrgBrief:
    return OrgBrief(id=o.id, slug=o.slug, name=o.name, country=o.country)

def organization_view(o: Organization, views: ProductViews, history: OwnershipHistory) -> OrganizationView:
    cited: dict[str, Source] = {}
    rows = tuple(OwnershipRow(type=views.terms.term("org_relation_types", r.type),
                              from_org=brief(views.catalog.get(r.from_org)), to_org=brief(views.catalog.get(r.to_org)),
                              valid_from=r.valid_from, valid_to=r.valid_to,
                              source=views.sourced(r.source_refs, cited))
                 for r in history.relations_of(o.id))
    return OrganizationView(id=o.id, slug=o.slug, name=o.name, kind=views.terms.term("org_kinds", o.kind),
                            website=o.website, country=o.country, summary=dict(o.summary) if o.summary else None,
                            ownership=rows, sources=tuple(views.terms.source_view(cited[k]) for k in sorted(cited)))
