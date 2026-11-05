from __future__ import annotations

import atexit
import functools
import hashlib
import json
import mimetypes
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeVar

from radar import paths
from radar.adapters.console import log
from radar.adapters.files import json_store
from radar.adapters.files.json_parser import Checker
from radar.adapters.files.model_json import load_model
from radar.adapters.storage.blobs import media_url
from radar.adapters.storage.memory_change_log import MemoryChangeLog
from radar.domain.model.entities import (CategoryPage, Change, HistoryView, IndexView, MarketView, ProductCard,
                                         ProductView)
from radar.domain.model.model import Model
from radar.domain.read_model import read_model
from radar.domain.model.history.projection import plain
from radar.domain.review.views import admin_model

FIXTURE = json.loads((Path(__file__).parent / "fixture_category.json").read_text(encoding="utf-8"))
WIDGETS = 16

def recorded_page(path: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
    found = FIXTURE["pages"].get(path, {"status": 404, "body": "no such page"})
    sent = {"Content-Type": found.get("type", "text/html; charset=utf-8"),
            **({"Location": found["location"]} if "location" in found else {})}
    return found.get("status", 200), sent, content(found) if "mime" in found else found["body"].encode()

def _write(path: Path, content: object) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def content(doc: dict) -> bytes:
    if doc["mime"] == "image/png":
        chunk = lambda kind, body: struct.pack(">I", len(body)) + kind + body + struct.pack(
            ">I", zlib.crc32(kind + body))
        rows = b"".join(b"\x00" + b"\x40\x80\xc0" * doc["width"] for _ in range(doc["height"]))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR",
                                             struct.pack(">IIBBBBB", doc["width"], doc["height"], 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))
    if doc["mime"] == "text/plain":
        return f"{doc['title']['en']}, a fictional file for tests\n".encode()
    return f"%PDF-1.4\n% {doc['title']['en']}, a fictional file for tests\n%%EOF\n".encode()

def with_blobs(documents: list[dict], root: Path) -> list[dict]:
    out = []
    for doc in documents:
        body = content(doc)
        sha = hashlib.sha256(body).hexdigest()
        target = root / sha[:2] / f"{sha[2:]}{mimetypes.guess_extension(doc['mime'])}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        out.append({**doc, "sha256": sha, "bytes": len(body)})
    return out

def widgets(n: int) -> dict[str, list[dict]]:
    [category] = FIXTURE["registry"]["categories.json"]
    reach, finish, mount = (s["id"] for s in FIXTURE["registry"]["spec_definitions.json"][:3])
    finishes = [t["id"] for t in FIXTURE["registry"]["vocabularies/fixture_finishes.json"]]
    mounts = [t["id"] for t in FIXTURE["registry"]["vocabularies/fixture_mounts.json"]]
    org, src = FIXTURE["data"]["organizations.jsonl"][0]["id"], FIXTURE["data"]["sources.jsonl"][0]["id"]
    rows: dict[str, list[dict]] = {"products.jsonl": [], "names.jsonl": [], "product_org_roles.jsonl": [],
                                   "claims.jsonl": []}
    for i in range(1, n + 1):
        pid, cited = f"prd_w{i:09d}", {"method": "datasheet", "recorded_at": "2026-10-11T00:00:00Z", "rank": 1,
                                       "source_refs": [src]}
        rows["products.jsonl"].append({"id": pid, "version": 1, "kind": "model", "category": category["id"],
                                       "slug": f"example-devices__widget-{i:03d}"})
        rows["names.jsonl"].append({"id": f"nam_w{i:09d}", "version": 1, "subject": pid, "value": f"Widget {i:03d}",
                                    "is_primary": True})
        rows["product_org_roles.jsonl"].append({"id": f"por_w{i:09d}", "version": 1, "product": pid, "org": org,
                                                "role": "manufacturer", "source_refs": [src]})
        rows["claims.jsonl"] += [
            {"id": f"clm_w{i:09d}", "version": 1, "subject": pid, "spec_key": reach,
             "value": {"quantity": {"value": 100.0 + i, "unit": "mm"}}, **cited},
            {"id": f"clm_x{i:09d}", "version": 1, "subject": pid, "spec_key": finish,
             "value": {"term": finishes[i % len(finishes)]}, **cited},
            {"id": f"clm_y{i:09d}", "version": 1, "subject": pid, "spec_key": mount,
             "value": {"term": mounts[i // 2 % len(mounts)]}, **cited},
        ]
    return rows

def build(out: Path, extra: int = 0) -> Path:
    registry, catalog_dir = out / "registry", out / "data"
    for entry in (e for e in paths.DATA.iterdir() if e.name != "store"):
        (shutil.copytree if entry.is_dir() else shutil.copy)(entry, out / entry.name)
    for name, addition in FIXTURE["registry"].items():
        target = registry / name
        _write(target, json.loads(target.read_text(encoding="utf-8")) + addition if target.exists() else addition)
    catalog_dir.mkdir(parents=True, exist_ok=True)
    rows_by_file = {**FIXTURE["data"], "documents.jsonl": with_blobs(FIXTURE["data"]["documents.jsonl"], out / "blobs")}
    for name, rows in widgets(extra).items():
        rows_by_file[name] = [*rows_by_file[name], *rows]
    for name, rows in rows_by_file.items():
        (catalog_dir / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                        encoding="utf-8")
    export_bundle(catalog_dir, out / "dist", registry)
    _write(out / "admin-model.json", plain(admin_model(load_model(registry))))
    return out / "dist"

def _write_view(path: Path, view: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(view), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

def export_bundle(catalog_dir: Path, dist: Path, registry_dir: Path) -> None:
    public = dist / "public"
    shutil.rmtree(public, ignore_errors=True)
    model = load_model(registry_dir)
    catalog = json_store.load_catalog(catalog_dir, model)
    rm = read_model.build(catalog, model, MemoryChangeLog(catalog.all(Change)), Checker(model), media_url)
    for folder, views in (("products", rm.products), ("organizations", rm.organizations), ("history", rm.histories),
                          ("news", rm.news)):
        for key, view in views.items():
            _write_view(public / folder / f"{key}.json", view)
    for category, pages in rm.pages.items():
        for page in pages:
            _write_view(public / "categories" / category / f"{page['page']}.json", page)
    _write_view(public / "news.json", rm.feed)
    _write_view(public / "market.json", rm.market)
    _write_view(public / "index.json", rm.index)
    _write_view(public / "registry.json", rm.registry)
    _write_view(public / "organizations.json", rm.index["organizations"])
    log.info(f"exported the read model: {len(rm.products)} products, {len(rm.organizations)} organizations to {public}")

T = TypeVar("T")

class FilesCatalogRepository:
    def __init__(self, public: Path, model: Model) -> None:
        self._public, self._views = public, Checker(model)

    def _read(self, view_type: type[T], *parts: str) -> T | None:
        path = self._public.joinpath(*parts)
        raw: Any = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        return None if raw is None else self._views.parse(raw, view_type, "/".join(parts))

    def index(self) -> IndexView:
        found = self._read(IndexView, "index.json")
        if found is None:
            raise LookupError(f"no read model in {self._public}")
        return found

    def product(self, key: str) -> ProductView | None:
        card = next((c for c in self.index().products if key in (c.id, c.slug)), None)
        return self._read(ProductView, "products", f"{card.id}.json") if card else None

    def products(self, ids: Sequence[str]) -> list[ProductView]:
        views = [self._read(ProductView, "products", f"{i}.json") for i in ids]
        missing = [i for i, v in zip(ids, views) if v is None]
        if missing:
            raise LookupError(f"no product view for {missing[0]}")
        return [v for v in views if v is not None]

    def category_page(self, category: str, cursor: str | None = None) -> CategoryPage | None:
        return self._read(CategoryPage, "categories", category, f"{cursor or 1}.json")

    def users(self, product: str) -> list[ProductCard]:
        cards = {c.id: c for c in self.index().products}
        using = [v.id for v in self.products(sorted(cards)) if any(c.id == product for c in v.components)]
        return sorted((cards[i] for i in using), key=lambda c: (c.name.lower(), c.id))

    def history(self, entity: str) -> HistoryView | None:
        return self._read(HistoryView, "history", f"{entity}.json")

    def market(self) -> MarketView:
        found = self._read(MarketView, "market.json")
        if found is None:
            raise LookupError(f"no read model in {self._public}")
        return found

@functools.cache
def built() -> Path:
    out = Path(tempfile.mkdtemp(prefix="mvr-fixture-"))
    atexit.register(shutil.rmtree, out, True)
    build(out, WIDGETS)
    return out

if __name__ == "__main__":
    print(build(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 0))
