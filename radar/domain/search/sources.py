from __future__ import annotations

from typing import Any
import urllib.parse
from dataclasses import dataclass
from datetime import date

from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import Document, Organization, Source
from radar.domain.model.history.projection import plain
from radar.domain.model.registry import Registry
from radar.domain.read_model.products.values import Terms

KINDS = (Source.__name__, Document.__name__, Organization.__name__)

def _host(url: str | None) -> str:
    return (urllib.parse.urlsplit(url or "").hostname or "").removeprefix("www.")

@dataclass(frozen=True, slots=True, kw_only=True)
class SourceQuery:
    limit: int
    url: str | None = None
    vendor: str | None = None
    type: str | None = None
    since: date | None = None
    until: date | None = None

    def _site(self, catalog: Catalog) -> str | None:
        if self.vendor is None:
            return None
        org = next((o for o in catalog.all(Organization) if self.vendor in (o.id, o.slug)), None)
        if org is None:
            raise LookupError(f"no organization '{self.vendor}'")
        if not _host(org.website):
            raise ValueError(f"{org.name} has no website to find its sources on")
        return _host(org.website)

    def _keeps(self, url: str | None, kind: str, instant: str, site: str | None) -> bool:
        host, day = _host(url), date.fromisoformat(instant[:10])
        return ((self.url is None or self.url.lower() in (url or "").lower())
                and (site is None or host == site or host.endswith(f".{site}")) and self.type in (None, kind)
                and (self.since or day) <= day <= (self.until or day))

    def found(self, catalog: Catalog, registry: Registry) -> dict[str, Any]:
        if self.type is not None and self.type not in {*registry.vocabularies["source_types"],
                                                       *registry.vocabularies["document_kinds"]}:
            raise ValueError(f"type '{self.type}' is neither a source type nor a document kind")
        site, terms = self._site(catalog), Terms(registry)
        sources = [s for s in catalog.all(Source) if self._keeps(s.url, s.type, s.retrieved_at, site)]
        documents = [d for d in catalog.all(Document) if self._keeps(d.source_url, d.kind, d.fetched_at, site)]
        return {"sources": [plain(terms.source_view(s))
                            for s in sorted(sources, key=lambda s: (s.retrieved_at, s.id), reverse=True)[:self.limit]],
                "documents": [_document(d, terms)
                              for d in sorted(documents, key=lambda d: (d.fetched_at, d.id),
                                              reverse=True)[:self.limit]]}

def _document(d: Document, terms: Terms) -> dict[str, Any]:
    return {"id": d.id, "kind": plain(terms.term("document_kinds", d.kind)),
            **({"title": dict(d.title)} if d.title else {}),
            "mime": d.mime, "bytes": d.bytes, "sha256": d.sha256, "rights": plain(terms.term("media_rights", d.rights)),
            **({"source_url": d.source_url} if d.source_url else {}), "fetched_at": d.fetched_at,
            "subjects": list(d.subjects)}
