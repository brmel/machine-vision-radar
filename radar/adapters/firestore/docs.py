from __future__ import annotations

import contextlib
import http.client
import json
import select
import threading
import time
import urllib.parse
from typing import Any, Callable, Collection, Iterator, Mapping, Sequence

from radar.adapters.console import log
from radar.domain.model.history.projection import ROWS
from radar.domain.ports.catalog.catalog_store import Contended
from radar.domain.ports.store.docs import BATCH, Docs, Fields, Increment, Put, Write

def list_page(docs: Docs, collection: str, cursor: str | None, where: Mapping[str, Any] | None = None) -> tuple[
        list[tuple[str, Fields]], str | None, int]:
    rows = docs.page(collection, cursor, ROWS, where=where)
    return rows, rows[-1][0].rsplit("/", 1)[1] if len(rows) == ROWS else None, docs.count(collection, where=where)

PAGE = 300
ANY = 30

def encode(value: Any) -> dict[str, Any]:
    if isinstance(value, (list, tuple)):
        if any(isinstance(v, (list, tuple)) for v in value):
            raise ValueError("Firestore holds no array directly inside an array")
        return {"arrayValue": {"values": [encode(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: encode(v) for k, v in value.items()}}}
    return _scalar(value)

def _scalar(value: Any) -> dict[str, Any]:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    raise TypeError(f"no Firestore value for {type(value).__name__}")

def decode(value: dict[str, Any]) -> Any:
    kind, inner = next(iter(value.items()))
    if kind == "integerValue":
        return int(inner)
    if kind == "arrayValue":
        return [decode(v) for v in inner.get("values", [])]
    if kind == "mapValue":
        return {k: decode(v) for k, v in inner.get("fields", {}).items()}
    if kind in ("nullValue", "booleanValue", "doubleValue", "stringValue"):
        return inner
    if kind == "timestampValue":
        return f"{inner[:19]}Z"
    raise TypeError(f"Firestore value {kind} is not one the adapters write")

def _write(name: str, w: Write) -> dict[str, Any]:
    if isinstance(w, Put):
        return {"update": {"name": name, "fields": {k: encode(v) for k, v in w.fields.items()}},
                **({"currentDocument": {"exists": False}} if w.create else {})}
    if isinstance(w, Increment):
        return {"transform": {"document": name,
                              "fieldTransforms": [{"fieldPath": f, "increment": encode(by)} for f, by in w.by.items()]}}
    return {"delete": name}

BACKOFF = (1, 2, 4, 8, 16, 32, 64)

def _filter(where: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if where is None:
        return None
    filters = [{"fieldFilter": {"field": {"fieldPath": k}, "op": "EQUAL", "value": encode(v)}}
               for k, v in where.items()]
    return filters[0] if len(filters) == 1 else {"compositeFilter": {"op": "AND", "filters": filters}}

def _exchange(connection: http.client.HTTPConnection, method: str, target: str, body: bytes | None,
              token: str) -> tuple[int, bytes]:
    try:
        connection.request(method, target, body,
                           {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        res = connection.getresponse()
        return res.status, res.read()
    except Exception:
        connection.close()
        raise

class FirestoreDocs:
    def __init__(self, url: str, project: str, database: str = "(default)", token: str = "owner", writable: bool = True,
                 pause: Callable[[float], None] = time.sleep) -> None:
        self._root = f"projects/{project}/databases/{database}/documents"
        self._api, self._token, self._writable, self._pause = (urllib.parse.urlsplit(url.rstrip("/")), token, writable,
                                                               pause)
        self._held = threading.local()

    def _connection(self) -> http.client.HTTPConnection:
        if not hasattr(self._held, "connection"):
            opened = http.client.HTTPSConnection if self._api.scheme == "https" else http.client.HTTPConnection
            self._held.connection = opened(self._api.netloc, timeout=60)
        elif self._held.connection.sock is not None and select.select([self._held.connection.sock], [], [], 0)[0]:
            self._held.connection.close()
        return self._held.connection

    def _call(self, method: str, path: str, body: Any = None) -> Any:
        target = f"{self._api.path}/{urllib.parse.quote(path, safe='/():,=?&')}"
        for wait in (*BACKOFF, None):
            status, payload = _exchange(self._connection(), method, target,
                                        json.dumps(body).encode() if body is not None else None, self._token)
            if status < 300:
                return json.loads(payload or b"null")
            if status == 404 and method == "GET":
                return None
            if status == 409:
                raise Contended(f"Firestore {method} {path}: another write landed first: {payload[:300]!r}")
            if status in (429, 503) and wait is not None:
                log.warn(f"Firestore {method} {path}: HTTP {status}, retried in {wait} s")
                self._pause(wait)
                continue
            raise OSError(f"Firestore {method} {path}: HTTP {status} {payload[:300]!r}")

    def _name(self, path: str) -> str:
        return f"{self._root}/{path}"

    def _row(self, doc: dict[str, Any]) -> tuple[str, Fields]:
        return doc["name"].split("/documents/", 1)[1], {k: decode(v) for k, v in doc.get("fields", {}).items()}

    def _run(self, query: dict[str, Any], parent: str = "") -> list[dict[str, Any]]:
        under = self._name(parent) if parent else self._root
        return [r["document"] for r in self._call("POST", f"{under}:runQuery", self._within({"structuredQuery": query}))
                if "document" in r]

    def _open(self) -> str | None:
        return getattr(self._held, "transaction", None)

    def _within(self, body: dict[str, Any]) -> dict[str, Any]:
        return {**body, "transaction": self._open()} if self._open() else body

    @contextlib.contextmanager
    def transaction(self) -> Iterator[None]:
        if self._open():
            raise RuntimeError("a transaction is already open on this thread")
        self._held.transaction = self._call("POST", f"{self._root}:beginTransaction", {})["transaction"]
        try:
            yield
        finally:
            if left := self._open():
                self._held.transaction = None
                self._call("POST", f"{self._root}:rollback", {"transaction": left})

    def get(self, path: str) -> Fields | None:
        return self.get_many([path]).get(path)

    def get_many(self, paths: Sequence[str]) -> dict[str, Fields]:
        out: dict[str, Fields] = {}
        for start in range(0, len(paths), PAGE):
            found = self._call("POST", f"{self._root}:batchGet",
                               self._within({"documents": [self._name(p) for p in paths[start:start + PAGE]]}))
            out.update(self._row(item["found"]) for item in found if "found" in item)
        return out

    def list(self, collection: str) -> Iterator[tuple[str, Fields]]:
        parent, _, name = collection.rpartition("/")
        return self._ordered({"collectionId": name}, ["__name__"], None, parent)

    def where(self, collection: str, field: str, values: Collection[Any],
              contains: bool = False) -> list[tuple[str, Fields]]:
        wanted, found = list(values), {}
        for start in range(0, len(wanted), ANY):
            found.update(map(self._row, self._run({"from": [{"collectionId": collection}], "where": {"fieldFilter": {
                "field": {"fieldPath": field}, "op": "ARRAY_CONTAINS_ANY" if contains else "IN",
                "value": encode(wanted[start:start + ANY])}}})))
        return list(found.items())

    def _ordered(self, source: dict[str, Any], fields: list[str], start: list[Any] | None,
                 parent: str = "") -> Iterator[tuple[str, Fields]]:
        while True:
            query: dict[str, Any] = {"from": [source], "orderBy": [{"field": {"fieldPath": f}} for f in fields],
                                     "limit": PAGE}
            if start:
                query["startAt"] = {"values": start, "before": False}
            rows = self._run(query, parent)
            yield from map(self._row, rows)
            if len(rows) < PAGE:
                return
            start = [*(rows[-1]["fields"][f] for f in fields[:-1]), {"referenceValue": rows[-1]["name"]}]

    def group(self, collection_id: str) -> Iterator[tuple[str, Fields]]:
        return self._ordered({"collectionId": collection_id, "allDescendants": True}, ["__name__"], None)

    def after(self, collection: str, field: str, start: tuple[Any, str] | None) -> Iterator[tuple[str, Fields]]:
        named = [{"referenceValue": self._name(f"{collection}/{start[1]}")}] if start and start[1] else []
        return self._ordered({"collectionId": collection}, [field, "__name__"],
                             [encode(start[0]), *named] if start else None)

    def count(self, collection: str, where: Mapping[str, Any] | None = None) -> int:
        clause = _filter(where)
        query: dict[str, Any] = {"from": [{"collectionId": collection}], **({"where": clause} if clause else {})}
        rows = self._call("POST", f"{self._root}:runAggregationQuery",
                          self._within({"structuredAggregationQuery": {
                              "structuredQuery": query, "aggregations": [{"alias": "n", "count": {}}]}}))
        return int(rows[0]["result"]["aggregateFields"]["n"]["integerValue"])

    def page(self, collection: str, cursor: str | None = None, limit: int = 20,
             where: Mapping[str, Any] | None = None) -> list[tuple[str, Fields]]:
        clause = _filter(where)
        query: dict[str, Any] = {"from": [{"collectionId": collection}],
                                 "orderBy": [{"field": {"fieldPath": "__name__"}}], "limit": limit,
                                 **({"where": clause} if clause else {})}
        if cursor is not None:
            if cursor.isdigit():
                query["offset"] = int(cursor)
            else:
                query["startAt"] = {"values": [{"referenceValue": self._name(f"{collection}/{cursor}")}],
                                    "before": False}
        return [self._row(doc) for doc in self._run(query)]

    def commit(self, writes: Sequence[Write]) -> None:
        if not self._writable:
            raise PermissionError(f"{self._root} is read-only here: a write to a project needs --yes")
        if len(writes) > BATCH:
            raise ValueError(f"a batch holds at most {BATCH} writes, not {len(writes)}")
        body = self._within({"writes": [_write(self._name(w.path), w) for w in writes]})
        self._held.transaction = None
        self._call("POST", f"{self._root}:commit", body)

    def collections(self) -> list[str]:
        ids, token = [], ""
        while True:
            page = self._call("POST", f"{self._root}:listCollectionIds",
                              {"pageSize": PAGE, **({"pageToken": token} if token else {})}) or {}
            ids += page.get("collectionIds", [])
            token = page.get("nextPageToken", "")
            if not token:
                return sorted(ids)
