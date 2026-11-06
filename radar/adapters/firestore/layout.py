from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable

from radar.adapters.files.json_parser import parse_catalog
from radar.adapters.storage.blobs import media_path
from radar.domain.model import entities
from radar.domain.model.catalog import MemoryCatalog
from radar.domain.model.model import Model
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.history.projection import plain
from radar.domain.read_model.listings import Tally, index_card
from radar.domain.read_model.read_model import ReadModel
from radar.domain.model.schema import ModelSchema
from radar.domain.ports.store.docs import Docs, Fields

INDEX, PRODUCTS, FACETS = "public_index", "public_products", "public_facets"
ORGANIZATIONS, HISTORY, NEWS = "public_organizations", "public_history", "public_news"
PUBLIC = (INDEX, PRODUCTS, FACETS, ORGANIZATIONS, HISTORY, NEWS)
PAGES, CHANGES, VERSIONS, SNAPSHOTS = "pages", "changes", "versions", "v"
PROPOSALS, LOG, FEED_STATE = "proposals", "proposal_log", "feed_state"
SUBCOLLECTIONS = {VERSIONS: SNAPSHOTS, FACETS: PAGES}
BACKUPS, EXPORTS = "backups", "managed-exports/"
CHUNK = 500
STORAGE_PATH = "storage_path"
Record = dict[str, Any]

def collections(schema: ModelSchema) -> dict[str, str]:
    return {e.prefix: e.collection for e in schema.entities if e.prefix and e.collection}

def rebuilt(schema: ModelSchema) -> list[str]:
    return sorted(set(collections(schema).values()) | {VERSIONS, *PUBLIC})

def changes_prefix(schema: ModelSchema) -> str | None:
    return next(e.prefix for e in schema.entities if e.collection == CHANGES)

def canonical(schema: ModelSchema, entity_id: str) -> str:
    kind = schema.kind_of(entity_id)
    if not kind:
        raise ValueError(f"'{entity_id}' names no entity kind")
    return f"{schema.collection(kind)}/{entity_id}"

def held(docs: Docs, schema: ModelSchema, entity_id: str) -> Record | None:
    return record_of(found) if schema.kind_of(entity_id) and (found := docs.get(canonical(schema, entity_id))) else None

def ranked_first(docs: Docs, schema: ModelSchema, record: Record) -> str | None:
    if schema.kind_of(record["id"]) != entities.Claim.__name__:
        return None
    return next((f["id"]
                 for _, f in docs.where(schema.collection(entities.Claim.__name__), "subject", [record.get("subject")])
                 if f.get("spec_key") == record.get("spec_key") and f.get("rank") == 1), None)

def canonical_doc(record: dict[str, Any]) -> Fields:
    return {**record,
            **({STORAGE_PATH: media_path(record["sha256"], record["mime"])} if "sha256" in record and "mime" in record
               else {})}

def record_of(fields: Fields) -> Record:
    return {k: v for k, v in fields.items() if k != STORAGE_PATH}

def read_records(docs: Docs, schema: ModelSchema, ids: Iterable[str]) -> dict[str, Record]:
    return {f["id"]: record_of(f) for f in docs.get_many([canonical(schema, i) for i in ids]).values()}

def catalog_of(model: Model, records: Iterable[Record]) -> MemoryCatalog:
    grouped: dict[str, list[Record]] = {}
    for r in sorted(records, key=lambda r: r["id"]):
        kind = model.schema.kind_of(r["id"])
        if kind:
            grouped.setdefault(model.schema.collection(kind), []).append(r)
    return parse_catalog(grouped, model)

def records_of(catalog: Catalog, schema: ModelSchema) -> list[Record]:
    return [plain(e) for t in schema.entities if t.collection for e in catalog.all(entities.CLASSES[t.name])]

def value_at(fields: Fields, path: str) -> Any:
    value: Any = fields
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value

def newest_first(at: str) -> str:
    return f"{10**13 - int(datetime.fromisoformat(at.replace('Z', '+00:00')).timestamp() * 1000):013d}"

def version(entity_id: str, n: int) -> str:
    return f"{VERSIONS}/{entity_id}/{SNAPSHOTS}/{n}"

def backup(instant: str, name: str) -> str:
    return f"{BACKUPS}/{instant}/{name}"

def as_json(value: Any) -> str:
    return json.dumps(plain(value), ensure_ascii=False, separators=(",", ":"))

def doc(value: Any, **extra: Any) -> Fields:
    return {"json": as_json(value), **extra}

def doc_value(found: Fields | None) -> Any:
    return json.loads(found["json"]) if found else None

def product_doc(view: entities.ProductView) -> Fields:
    return doc(view, slug=view.slug, card=as_json(index_card(view)), category=view.category,
               vendor=view.vendor.slug, name_key=view.name.lower(), vendor_key=view.vendor.name.lower(),
               uses=[c.id for c in view.components])

def chunks(items: list[Any]) -> list[list[Any]]:
    return [items[n:n + CHUNK] for n in range(0, len(items), CHUNK)] or [[]]

def listing_docs(category: str, pages: list[dict[str, Any]]) -> dict[str, Fields]:
    return {f"{FACETS}/{category}": doc(pages[0]["facets"], pages=len(pages)),
            **{f"{FACETS}/{category}/{PAGES}/{page['page']}": doc({k: v for k, v in page.items() if k != "facets"})
               for page in pages}}

def index_docs(index: dict[str, Any], tally: Tally) -> dict[str, Fields]:
    cards = chunks(index["products"])
    registry = {k: v for k, v in index.items() if k not in ("products", "organizations")}
    return {f"{INDEX}/registry": doc(registry, cards=len(cards), tally=as_json(tally.plain())),
            f"{INDEX}/organizations": doc(index["organizations"]),
            **{f"{INDEX}/cards-{n}": doc(chunk) for n, chunk in enumerate(cards, 1)}}

def public_docs(rm: ReadModel) -> dict[str, Fields]:
    out = index_docs(rm.index, rm.tally)
    out.update({f"{PRODUCTS}/{pid}": product_doc(v) for pid, v in rm.products.items()})
    for category, pages in rm.pages.items():
        out.update(listing_docs(category, pages))
    out.update({f"{ORGANIZATIONS}/{slug}": doc(v) for slug, v in rm.organizations.items()})
    out.update({f"{HISTORY}/{pid}": doc(v) for pid, v in rm.histories.items()})
    out.update(news_docs(rm.news, rm.feed))
    out[f"{INDEX}/market"] = doc(rm.market)
    return out

def news_docs(articles: dict[str, Any], feed: entities.FeedPageView) -> dict[str, Fields]:
    return {f"{INDEX}/news": doc(feed), **{f"{NEWS}/{slug}": doc(v) for slug, v in articles.items()}}
