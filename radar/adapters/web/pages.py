from __future__ import annotations

import http.client
import ipaddress
import socket
import time
from html.parser import HTMLParser
from typing import Callable, Mapping
from urllib.parse import SplitResult, quote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from radar.adapters.console import log
from radar.domain.model.entities import Term
from radar.domain.ports.web.page_fetcher import File, Page, Unfetchable

INTERVAL, TIMEOUT, MOST, FILE_MOST, CHUNK, HOPS = 1.0, 5.0, 2_000_000, 20_000_000, 65_536, 5
TEXT = ("text/html", "text/plain")
SKIPPED = ("script", "style", "noscript", "template")
BLOCKS = frozenset(("address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "figure",
                    "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol",
                    "p", "pre", "section", "table", "tr", "ul"))
CELLS = ("td", "th")
PORTS = {"http": 80, "https": 443}
REDIRECTS = (301, 302, 303, 307, 308)
ROBOTS = "/robots.txt"
UNESCAPED = "/%:@!$&'()*+,;=?~"

def _address(url: str, against: str = "") -> SplitResult:
    try:
        parts = urlsplit(urljoin(against, url))
        web = parts.scheme in PORTS and parts.hostname and parts.username is None and parts.port != 0
    except ValueError as exc:
        raise Unfetchable(f"not a web address: {exc}") from exc
    if not web:
        raise Unfetchable("not a web address")
    return parts._replace(path=quote(parts.path, UNESCAPED) or "/", query=quote(parts.query, UNESCAPED))

def _resolved(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    except OSError as exc:
        raise Unfetchable(f"no address: {exc}") from exc

class _Reader(HTMLParser):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url, self.title, self.lines, self.links, self.images, self._in, self._line = url, "", [], [], [], [""], []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and (link := self._resolved(attributes.get("href"))):
            self.links.append(link)
        elif tag == "img" and (image := self._resolved(attributes.get("src"))):
            self.images.append(image)
        elif (tag == "meta" and attributes.get("property") == "og:image"
                and (image := self._resolved(attributes.get("content")))):
            self.images.insert(0, image)
        self._opened(tag)

    def _opened(self, tag: str) -> None:
        if tag in BLOCKS:
            self._ended()
        elif tag in CELLS and "".join(self._line).strip():
            self._line.append(" | ")
        self._in.append(tag)

    def _resolved(self, address: str | None) -> str | None:
        try:
            return urljoin(self.url, address).split("#")[0] if address else None
        except ValueError as exc:
            log.info("fetch: a link or an image that is no address is skipped", page=self.url, address=address,
                     error=str(exc))
            return None

    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCKS:
            self._ended()
        while tag in self._in and self._in.pop() != tag:
            pass

    def handle_data(self, data: str) -> None:
        if self._in[-1] == "title":
            self.title += data.strip()
        elif not set(self._in) & set(SKIPPED):
            self._line.append(data)

    def close(self) -> None:
        super().close()
        self._ended()

    def _ended(self) -> None:
        if line := " ".join("".join(self._line).split()):
            self.lines.append(line)
        self._line = []

class _Pinned(http.client.HTTPConnection):
    address = ""

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), self.timeout, self.source_address)

class _PinnedTls(http.client.HTTPSConnection, _Pinned):
    ...

class PoliteFetcher:
    def __init__(self, contact: str, now: Callable[[], str], kinds: Mapping[str, Term], base: str | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self._agent = f"mvradar-research/1 (+{contact})"
        self._media = tuple(dict.fromkeys(m for t in kinds.values() for m in t.mime_types or ()))
        self._now, self._base, self._clock, self._sleep = now, urlsplit(base) if base else None, clock, sleep
        self._robots: dict[str, RobotFileParser] = {}
        self._last: dict[str, float] = {}

    def fetch(self, url: str, within: float) -> Page:
        status, kind, body, at = self._public(url, "text/html, text/plain", MOST, self._clock() + within)
        if status != 200 or kind not in TEXT:
            raise Unfetchable(f"not a page: HTTP {status}, {kind or 'no type'}")
        reader = _Reader(at)
        reader.feed(body.decode("utf-8", "replace"))
        reader.close()
        return Page(at, reader.title, "\n".join(reader.lines), tuple(dict.fromkeys(reader.links)), self._now(),
                    tuple(dict.fromkeys(reader.images)))

    def file(self, url: str, within: float) -> File:
        accept = ", ".join(f"{m}*" if m.endswith("/") else m for m in self._media)
        status, kind, body, at = self._public(url, accept, FILE_MOST + 1, self._clock() + within)
        if status != 200 or not kind.startswith(self._media):
            raise Unfetchable(f"not a document: HTTP {status}, {kind or 'no type'}")
        if len(body) > FILE_MOST:
            raise Unfetchable(f"over {FILE_MOST:,} bytes")
        return File(at, kind, body, self._now())

    def _public(self, url: str, accept: str, most: int, deadline: float) -> tuple[int, str, bytes, str]:
        status, kind, body, at = self._followed(_address(url), accept, most, deadline)
        if status in (401, 403, 407):
            raise Unfetchable("not public: it asks for a sign-in")
        return status, kind.split(";")[0].strip(), body, urlunsplit(at)

    def _followed(self, parts: SplitResult, accept: str, most: int, deadline: float) -> tuple[
            int, str, bytes, SplitResult]:
        for _ in range(HOPS):
            if not self._allowed(parts, deadline):
                raise Unfetchable("robots.txt disallows it")
            status, kind, body, moved = self._get(parts, accept, most, deadline)
            if status not in REDIRECTS or not moved:
                return status, kind, body, parts
            target = _address(moved, urlunsplit(parts))
            if target.hostname != parts.hostname:
                raise Unfetchable(f"it redirects off its site, to {urlunsplit(target)}")
            parts = target
        raise Unfetchable(f"more than {HOPS} redirects")

    def _allowed(self, parts: SplitResult, deadline: float) -> bool:
        if parts.path == ROBOTS:
            return True
        robots = self._robots.get(parts.netloc)
        if robots is None:
            status, _, body, _ = self._followed(parts._replace(path=ROBOTS, query=""), "text/plain", MOST, deadline)
            robots = self._robots[parts.netloc] = RobotFileParser()
            missing = 400 <= status < 500 and status not in (401, 403)
            robots.allow_all, robots.disallow_all = missing, status != 200 and not missing
            robots.parse(body.decode("utf-8", "replace").splitlines())
        return robots.can_fetch(self._agent, urlunsplit(parts))

    def _left(self, deadline: float) -> float:
        left = deadline - self._clock()
        if left <= 0:
            raise Unfetchable("the run's time is spent")
        return left

    def _wait(self, parts: SplitResult, deadline: float) -> None:
        robots = self._robots.get(parts.netloc)
        delay = max(INTERVAL, float((robots.crawl_delay(self._agent) if robots else None) or 0))
        wait = self._last.get(parts.netloc, float("-inf")) + delay - self._clock()
        if wait >= self._left(deadline):
            raise Unfetchable(f"its crawl delay of {delay:g} s would pass the run's time")
        if wait > 0:
            self._sleep(wait)
        self._last[parts.netloc] = self._clock()

    def _checked(self, host: str, port: int) -> str:
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [] if self._base else _resolved(host, port)
        if not all(a.is_global for a in addresses):
            raise Unfetchable(f"{host} is not a public address")
        return self._base.hostname or "" if self._base else str(addresses[0])

    def _connection(self, parts: SplitResult, deadline: float) -> _Pinned:
        web = self._base or parts
        host, port = parts.hostname or "", web.port or PORTS[web.scheme]
        address = self._checked(host, port)
        connection = (_PinnedTls if web.scheme == "https" else _Pinned)(
            host, port, timeout=min(TIMEOUT, self._left(deadline)))
        connection.address = address
        return connection

    def _get(self, parts: SplitResult, accept: str, most: int, deadline: float) -> tuple[int, str, bytes, str]:
        self._wait(parts, deadline)
        connection = self._connection(parts, deadline)
        try:
            connection.request("GET", urlunsplit(("", "", parts.path, parts.query, "")),
                               headers={"User-Agent": self._agent, "Accept": accept})
            res, body = connection.getresponse(), b""
            while len(body) < most and (chunk := res.read(min(CHUNK, most - len(body)))):
                body += chunk
                self._left(deadline)
            return res.status, res.getheader("Content-Type", ""), body, res.getheader("Location", "")
        except (OSError, http.client.HTTPException) as exc:
            raise Unfetchable(f"no answer: {exc}") from exc
        finally:
            connection.close()
