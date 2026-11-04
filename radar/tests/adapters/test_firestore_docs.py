from __future__ import annotations

import http.client
import socket
from contextlib import AbstractContextManager, nullcontext
from typing import Iterator

import pytest

from radar.adapters.firestore.docs import BACKOFF, FirestoreDocs
from radar.domain.ports.store.docs import Put
from radar.tests.adapters.stub_server import serving

@pytest.fixture
def firestore() -> Iterator[tuple[str, list[int]]]:
    statuses: list[int] = []

    def answer(_path: str, _body: bytes) -> tuple[int, bytes]:
        status = statuses.pop(0) if statuses else 200
        return status, b"{}" if status == 200 else b'{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}'

    with serving(answer) as url:
        yield f"{url}/v1", statuses

@pytest.mark.parametrize(("turned_away", "outcome"), [([429, 503, 429], nullcontext()),
                                                      ([429] * (len(BACKOFF) + 1),
                                                       pytest.raises(OSError, match="HTTP 429"))])
def test_a_commit_turned_away_for_load_is_retried_with_growing_waits_then_fails_with_its_status(
        firestore: tuple[str, list[int]], turned_away: list[int], outcome: AbstractContextManager[object]) -> None:
    url, statuses = firestore
    statuses += turned_away
    waits: list[float] = []
    with outcome:
        FirestoreDocs(url, "demo-mvradar", pause=waits.append).commit([Put("a/b", {"json": "{}"})])
    assert waits == list(BACKOFF[:len(turned_away)]) and statuses == []

def test_one_connection_carries_the_requests_and_one_the_server_shut_while_idle_opens_afresh() -> None:
    peers: list[socket.socket] = []
    with serving(lambda _path, _body: (200, b"{}"), keep_alive=True, peers=peers) as url:
        docs = FirestoreDocs(f"{url}/v1", "demo-mvradar")
        for n in range(3):
            docs.commit([Put(f"a/{n}", {"json": "{}"})])
        assert len(peers) == 1
        peers[0].shutdown(socket.SHUT_RDWR)
        FirestoreDocs(f"{url}/v1", "demo-mvradar").commit([Put("b/0", {"json": "{}"})])
        docs.commit([Put("a/3", {"json": "{}"})])
    assert len(peers) == 3

def test_a_reply_that_breaks_the_exchange_leaves_the_connection_usable() -> None:
    replies = [(0, b"not HTTP\r\n"), (200, b"{}")]
    with serving(lambda _path, _body: replies.pop(0), keep_alive=True) as url:
        docs = FirestoreDocs(f"{url}/v1", "demo-mvradar")
        with pytest.raises(http.client.BadStatusLine):
            docs.commit([Put("a/b", {"json": "{}"})])
        docs.commit([Put("a/b", {"json": "{}"})])
    assert replies == []
