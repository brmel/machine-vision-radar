from __future__ import annotations

import base64
import json
import time
import urllib.parse
from typing import Any

import pytest

from radar.adapters.firestore import layout
from radar.adapters.firestore.docs import encode
from radar.adapters.ai.search.files import CURRENT
from radar.adapters.storage.blobs import media_path
from radar.adapters.firestore.ledgers import COLLECTIONS
from radar.domain.model.history.ids import keyed
from radar.domain.review.proposal import content_hash
from radar.tests.store import stores

FX = stores.fixture()

def _signed_in(**claims: Any) -> str:
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    body = {"sub": "reader", "user_id": "reader", "aud": stores.PROJECT,
            "iss": f"https://securetoken.google.com/{stores.PROJECT}", **claims}
    return f"{part({'alg': 'none'})}.{part(body)}."

@pytest.fixture(scope="module")
def loaded() -> tuple[str, str]:
    return FX.loaded(("store", "backup"), ("index", "rebuild"))

def _doc(place: tuple[str, str], path: str) -> str:
    return f"http://{stores.FIRESTORE}/v1/projects/{stores.PROJECT}/databases/{place[0]}/documents/{path}"

def _path(place: tuple[str, str], collection: str) -> str:
    docs = stores.fresh_at(place[0])
    found = docs.group(collection) if collection in (layout.PAGES, layout.SNAPSHOTS) else docs.list(collection)
    return next((p for p, _ in found), f"{collection}/absent")

PUBLIC = (*layout.PUBLIC, layout.PAGES)
CLOSED = (*(e.collection for e in FX.model.schema.entities if e.collection), layout.SNAPSHOTS)

@pytest.mark.parametrize(("collection", "status"), [*((c, 200) for c in PUBLIC), *((c, 403) for c in CLOSED)])
@pytest.mark.parametrize("reader", ("anonymous", "signed-in"))
def test_the_public_read_docs_are_world_readable_and_canonical_changes_and_versions_closed(
        loaded: tuple[str, str], collection: str, status: int, reader: str) -> None:
    assert stores.status("GET", _doc(loaded, _path(loaded, collection)),
                         _signed_in() if reader == "signed-in" else None) == status

@pytest.mark.parametrize("collection", ("changesets", *COLLECTIONS, "anything_else"))
def test_everything_else_is_denied_by_default(loaded: tuple[str, str], collection: str) -> None:
    assert stores.status("GET", _doc(loaded, f"{collection}/x"), _signed_in()) == 403

@pytest.mark.parametrize("collection", (*PUBLIC, *CLOSED))
def test_no_client_writes_anywhere(loaded: tuple[str, str], collection: str) -> None:
    path = _path(loaded, collection)
    for token in (None, _signed_in()):
        assert stores.status("PATCH", _doc(loaded, path), token, {"fields": {"json": {"stringValue": "{}"}}}) == 403
        assert stores.status("DELETE", _doc(loaded, path), token) == 403

def _object(bucket: str, path: str) -> str:
    return f"http://{stores.STORAGE}/v0/b/{bucket}/o/{urllib.parse.quote(path, safe='')}?alt=media"

@pytest.mark.parametrize("public", (True, False))
def test_media_is_readable_only_when_its_rights_are_public(loaded: tuple[str, str], public: bool) -> None:
    sha, m = next((sha, m) for sha, m in FX.media.items() if m.public == public)
    assert stores.status("GET", _object(loaded[1], media_path(sha, m.mime)), None) == (200 if public else 403)

def test_backups_and_the_search_index_are_unreadable_and_storage_takes_no_client_write(loaded: tuple[str, str]) -> None:
    [manifest] = [o for o in stores.objects(loaded[1]) if o.endswith("manifest.json")]
    assert CURRENT in stores.objects(loaded[1])
    assert {stores.status("GET", _object(loaded[1], path), token)
            for path in (manifest, CURRENT) for token in (None, _signed_in())} == {403}
    upload = f"http://{stores.STORAGE}/v0/b/{loaded[1]}/o?name=media%2Faa%2Fbb.pdf&uploadType=media"
    assert stores.status("POST", upload, _signed_in(), {}) == 403

def test_no_reader_writes_a_report_or_its_log_line(loaded: tuple[str, str]) -> None:
    subject, message = FX.rows("products.jsonl")[0]["id"], "The maximum frame rate is 120 fps on the datasheet."
    digest = content_hash("public", subject, message, None, None)
    pid = keyed("prp", digest)
    report = (f"{layout.PROPOSALS}/{pid}",
              {"id": pid, "status": "suggested", "subject": subject, "message": message, "locale": "en",
              "actor_kind": "human", "author": "public", "content_hash": digest, "reports": 1}, "created_at")
    line = (f"{layout.LOG}/{10**13 - int(time.time() * 1000)}-{pid}-submit",
            {"action": "submit", "proposal": pid, "actor": "public",
             "actor_kind": "human", "changes": [], "correlation_id": f"report-{digest[:12]}"}, "at")
    root = f"projects/{stores.PROJECT}/databases/{loaded[0]}/documents"
    for token in (None, _signed_in()):
        for batch in ((report, line), (report,), (line,)):
            writes = [{"update": {"name": f"{root}/{path}", "fields": {k: encode(v) for k, v in fields.items()}},
                       "currentDocument": {"exists": False},
                       "updateTransforms": [{"fieldPath": at, "setToServerValue": "REQUEST_TIME"}]}
                      for path, fields, at in batch]
            assert stores.status("POST", f"http://{stores.FIRESTORE}/v1/{root}:commit", token,
                                 {"writes": writes}) == 403
