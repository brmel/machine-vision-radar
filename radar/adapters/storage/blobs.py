from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

from radar import paths
from radar.domain.ports.store.blob_store import BlobRef

CHUNK = 1 << 16

MEDIA = "media/"

def media_path(sha256: str, mime: str) -> str:
    return f"{MEDIA}{sha256[:2]}/{sha256[2:]}{mimetypes.guess_extension(mime) or ''}"

def bucket() -> str:
    return os.environ.get("MVR_STORAGE_BUCKET") or f"{paths.firebase_project()}.firebasestorage.app"

def media_url(sha256: str, mime: str) -> str:
    return StorageBlobStore(os.environ.get("MVR_MEDIA_BASE") or "https://firebasestorage.googleapis.com",
                            bucket()).url(BlobRef(sha256, mime), True)

def verified(chunks: Iterator[bytes], sha256: str) -> Iterator[bytes]:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
        yield chunk
    if digest.hexdigest() != sha256:
        raise ValueError(f"the file named {sha256} hashes to {digest.hexdigest()}")

class StorageBlobStore:
    def __init__(self, url: str, bucket_name: str, token: str = "owner", writable: bool = True) -> None:
        self._url, self._bucket, self._token, self._writable = url.rstrip("/"), bucket_name, token, writable

    def put(self, content: bytes, mime: str, public: bool) -> BlobRef:
        ref = BlobRef(hashlib.sha256(content).hexdigest(), mime)
        if not self.has(ref):
            self.write(media_path(ref.sha256, mime), content, mime, public)
        return ref

    def get(self, ref: BlobRef) -> Iterator[bytes]:
        return verified(self.read(media_path(ref.sha256, ref.mime)), ref.sha256)

    def has(self, ref: BlobRef) -> bool:
        return self.exists(media_path(ref.sha256, ref.mime))

    def remove(self, ref: BlobRef) -> None:
        self.delete(media_path(ref.sha256, ref.mime))

    def _object(self, path: str) -> str:
        return f"{self._url}/v0/b/{self._bucket}/o/{urllib.parse.quote(path, safe='')}"

    def _call(self, method: str, url: str, body: bytes | None = None,
              mime: str = "application/json") -> urllib.request.addinfourl | None:
        if method != "GET" and not self._writable:
            raise PermissionError(f"bucket {self._bucket} is read-only here: a write to a project needs --yes")
        req = urllib.request.Request(url, method=method, data=body,
                                     headers={"Authorization": f"Bearer {self._token}", "Content-Type": mime})
        try:
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method in ("GET", "DELETE"):
                return None
            raise OSError(f"Storage {method} {url}: HTTP {exc.code} {exc.read()[:300]!r}") from exc

    def write(self, path: str, content: bytes, mime: str, public: bool = False) -> None:
        self._call("POST",
                   f"{self._url}/v0/b/{self._bucket}/o?name={urllib.parse.quote(path, safe='')}&uploadType=media",
                   content, mime)
        self._mark(path, public)

    def _mark(self, path: str, public: bool) -> None:
        meta = {"metadata": {"public": "true" if public else "false"}}
        self._call("PATCH", self._object(path), json.dumps(meta).encode())

    def publish(self, ref: BlobRef, public: bool) -> None:
        self._mark(media_path(ref.sha256, ref.mime), public)

    def read(self, path: str) -> Iterator[bytes]:
        res = self._call("GET", f"{self._object(path)}?alt=media")
        if res is None:
            raise FileNotFoundError(f"no file at {path}")
        with res:
            while chunk := res.read(CHUNK):
                yield chunk

    def exists(self, path: str) -> bool:
        return self._call("GET", self._object(path)) is not None

    def delete(self, path: str) -> None:
        self._call("DELETE", self._object(path))

    def sizes(self) -> Iterator[tuple[str, int]]:
        token = ""
        while True:
            query = urllib.parse.urlencode({"pageToken": token} if token else {})
            res = self._call("GET", f"{self._url}/v0/b/{self._bucket}/o?{query}")
            page = json.load(res) if res else {}
            for item in page.get("items", []):
                meta = self._call("GET", self._object(item["name"]))
                yield item["name"], int(json.load(meta)["size"]) if meta else 0
            token = page.get("nextPageToken", "")
            if not token:
                return

    def path_of(self, ref: BlobRef) -> str:
        return media_path(ref.sha256, ref.mime)

    def url(self, ref: BlobRef, public: bool) -> str:
        if public:
            return f"{self._object(media_path(ref.sha256, ref.mime))}?alt=media"
        raise PermissionError("a private file has no URL: only its Document's source_url is linked")
