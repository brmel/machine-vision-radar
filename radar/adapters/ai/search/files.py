from __future__ import annotations

import hashlib
import json
from typing import Any

from radar.adapters.storage.blobs import StorageBlobStore

ROOT = "index"
CURRENT = f"{ROOT}/current.json"

def json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

class BlobStoreIndexFiles:
    def __init__(self, blobs: StorageBlobStore) -> None:
        self._blobs = blobs
        self._cache: dict[str, bytes] = {}

    def put(self, content: bytes, suffix: str, mime: str) -> str:
        path = f"{ROOT}/blobs/{sha256_hex(content)}{suffix}"
        if not self._blobs.exists(path):
            self._blobs.write(path, content, mime)
        self._cache[path] = content
        return path

    def read(self, path: str) -> bytes:
        if path == CURRENT:
            return b"".join(self._blobs.read(path))
        if path not in self._cache:
            self._cache[path] = b"".join(self._blobs.read(path))
        return self._cache[path]

    def current(self) -> str | None:
        if not self._blobs.exists(CURRENT):
            return None
        return json.loads(self.read(CURRENT)).get("manifest")

    def set_current(self, version: str, manifest: str) -> None:
        self._blobs.write(CURRENT, json_bytes({"version": version, "manifest": manifest}), "application/json")
