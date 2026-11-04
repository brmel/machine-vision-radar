from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import Identifier, Name, ProductOrgRole
from radar.domain.model.history.projection import plain
from radar.domain.model.registry import Registry

@dataclass(frozen=True, slots=True)
class ProductIdentity:
    ranks: Mapping[str, int]
    naming: frozenset[str]

    @staticmethod
    def of(registry: Registry) -> ProductIdentity:
        roles = registry.vocabularies["product_org_roles"].values()
        return ProductIdentity({t.id: t.vendor_for_view for t in roles if t.vendor_for_view},
                               registry.marked("identifier_schemes", lambda t: t.names_product))

    def makers(self, roles: Iterable[Mapping[str, Any]]) -> dict[str, str]:
        best: dict[str, tuple[int, str]] = {}
        for r in roles:
            rank = self.ranks.get(r.get("role", ""))
            if rank is not None and (r["product"] not in best or rank <= best[r["product"]][0]):
                best[r["product"]] = (rank, r["org"])
        return {product: org for product, (_, org) in best.items()}

    def called(self, kind: str, record: Mapping[str, Any]) -> tuple[str, str] | None:
        if kind == Name.__name__ or (kind == Identifier.__name__ and record.get("scheme") in self.naming):
            return kind, " ".join(str(record.get("value", "")).split()).casefold()
        return None

def identities(catalog: Catalog, registry: Registry) -> tuple[dict[str, str], dict[str, str]]:
    return ({n.subject: n.value for n in catalog.all(Name) if n.is_primary},
            ProductIdentity.of(registry).makers(plain(r) for r in catalog.all(ProductOrgRole)))
