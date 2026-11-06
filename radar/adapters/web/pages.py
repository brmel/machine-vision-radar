from __future__ import annotations

import http.client
import ipaddress
import socket
import time
from datetime import datetime
from html.parser import HTMLParser
from typing import Callable, Mapping, TypeVar
from urllib.parse import SplitResult, quote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from radar.domain.model.entities import Instant, Term
from radar.domain.ports.web.reader import File, Link, Page, Unread

T = TypeVar("T")
INTERVAL, TIMEOUT, MOST, FILE_MOST, CHUNK, HOPS, MAPS = 1.0, 5.0, 2_000_000, 20_000_000, 65_536, 5, 4
TEXT, XML = ("text/html", "text/plain"), ("application/xml", "text/xml")
PHOTOS = (".png", ".jpg", ".jpeg", ".webp")
SKIPPED = ("script", "style", "noscript", "template")
BLOCKS = frozenset(("address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "figure",
                    "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol",
                    "p", "pre", "section", "table", "tr", "ul"))
CELLS = ("td", "th")
PORTS = {"http": 80, "https": 443}
REDIRECTS = (301, 302, 303, 307, 308)
ROBOTS, SITEMAP = "/robots.txt", "/sitemap.xml"
UNESCAPED = "/%:@!$&'()*+,;=?~"

class _Unreadable(Exception):
    ...

def _parsed(url: str, against: str = "") -> SplitResult | str:
    try:
        parts = urlsplit(urljoin(against, url))
        web = parts.scheme in PORTS and parts.hostname and parts.username is None and parts.port != 0
    except ValueError as exc:
        return f"not a web address: {exc}"
    if not web:
        return "not a web address"
    return parts._replace(path=quote(parts.path, UNESCAPED) or "/", query=quote(parts.query, UNESCAPED), fragment="")

def _address(url: str, against: str = "") -> SplitResult:
    parts = _parsed(url, against)
    if isinstance(parts, str):
        raise _Unreadable(parts)
    return parts

def _link(parts: SplitResult) -> Link:
    return Link(urlunsplit(parts), (parts.hostname or "").removeprefix("www."))

def _links(addresses: list[str], against: str) -> tuple[Link, ...]:
    return tuple(dict.fromkeys(_link(p) for p in (_parsed(a, against) for a in addresses) if not isinstance(p, str)))

def _sitemap(body: bytes) -> tuple[bool, list[str]]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise _Unreadable(f"not a sitemap: {exc}") from exc
    return _named(root) == "sitemapindex", [e.text.strip() for e in root.iter() if _named(e) == "loc" and e.text]

def _named(element: ElementTree.Element) -> str:
    return element.tag.rpartition("}")[2]

def _resolved(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    except OSError as exc:
        raise _Unreadable(f"no address: {exc}") from exc

class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title, self.lines, self.links, self.images, self._in, self._line = "", [], [], [], [""], []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and (link := attributes.get("href")):
            self.links.append(link)
        elif tag == "img" and (image := attributes.get("src")):
            self.images.append(image)
        elif tag == "meta" and attributes.get("property") == "og:image" and (image := attributes.get("content")):
            self.images.insert(0, image)
        self._opened(tag)

    def _opened(self, tag: str) -> None:
        if tag in BLOCKS:
            self._ended()
        elif tag in CELLS and "".join(self._line).strip():
            self._line.append(" | ")
        self._in.append(tag)

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

class PoliteReader:
    def __init__(self, contact: str, now: Callable[[], str], kinds: Mapping[str, Term], base: str | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self._agent = f"mvradar-research/1 (+{contact})"
        self._media = tuple(dict.fromkeys(m for t in kinds.values() for m in t.mime_types or ()))
        self._now, self._base, self._clock, self._sleep = now, urlsplit(base) if base else None, clock, sleep
        self._robots: dict[str, RobotFileParser] = {}
        self._last: dict[str, float] = {}

    def link(self, address: str) -> Link | Unread:
        parts = _parsed(address)
        return Unread(address, parts) if isinstance(parts, str) else _link(parts)

    def page(self, link: Link, by: Instant) -> Page | Unread:
        return self._read(link, lambda: self._page(link, by))

    def file(self, link: Link, by: Instant) -> File | Unread:
        return self._read(link, lambda: self._file(link, by))

    def sitemap(self, site: Link, by: Instant) -> tuple[Link, ...] | Unread:
        return self._read(site, lambda: self._mapped(site, by))

    def _read(self, link: Link, read: Callable[[], T]) -> T | Unread:
        try:
            return read()
        except _Unreadable as exc:
            return Unread(link.address, str(exc))

    def _page(self, link: Link, by: Instant) -> Page:
        status, kind, body, at = self._public(link.address, "text/html, text/plain", MOST, by)
        if status != 200 or kind not in TEXT:
            raise _Unreadable(f"not a page: HTTP {status}, {kind or 'no type'}")
        html = _Html()
        html.feed(body.decode("utf-8", "replace"))
        html.close()
        address = urlunsplit(at)
        links = _links(html.links, address)
        images = tuple(i for i in dict.fromkeys((*_links(html.images, address), *links))
                       if urlsplit(i.address).path.lower().endswith(PHOTOS))
        return Page(_link(at), html.title, "\n".join(html.lines), links, images, self._now())

    def _file(self, link: Link, by: Instant) -> File:
        accept = ", ".join(f"{m}*" if m.endswith("/") else m for m in self._media)
        status, kind, body, at = self._public(link.address, accept, FILE_MOST + 1, by)
        if status != 200 or not kind.startswith(self._media):
            raise _Unreadable(f"not a document: HTTP {status}, {kind or 'no type'}")
        if len(body) > FILE_MOST:
            raise _Unreadable(f"over {FILE_MOST:,} bytes")
        return File(_link(at), kind, body, self._now())

    def _mapped(self, site: Link, by: Instant) -> tuple[Link, ...]:
        parts = _address(site.address)
        maps = list(self._robots_of(parts, by).site_maps() or [urlunsplit(parts._replace(path=SITEMAP, query=""))])
        pages: list[str] = []
        for _ in range(MAPS):
            if not maps:
                break
            status, kind, body, _ = self._public(maps.pop(0), ", ".join(XML), FILE_MOST, by)
            if status == 200 and kind in XML:
                index, locs = _sitemap(body)
                (maps if index else pages).extend(locs)
        return _links(pages, "")

    def _public(self, url: str, accept: str, most: int, by: Instant) -> tuple[int, str, bytes, SplitResult]:
        status, kind, body, at = self._followed(_address(url), accept, most, by)
        if status in (401, 403, 407):
            raise _Unreadable("not public: it asks for a sign-in")
        return status, kind.split(";")[0].strip(), body, at

    def _followed(self, parts: SplitResult, accept: str, most: int, by: Instant) -> tuple[
            int, str, bytes, SplitResult]:
        for _ in range(HOPS):
            if not self._allowed(parts, by):
                raise _Unreadable("robots.txt disallows it")
            status, kind, body, moved = self._get(parts, accept, most, by)
            if status not in REDIRECTS or not moved:
                return status, kind, body, parts
            target = _address(moved, urlunsplit(parts))
            if target.hostname != parts.hostname:
                raise _Unreadable(f"it redirects off its site, to {urlunsplit(target)}")
            parts = target
        raise _Unreadable(f"more than {HOPS} redirects")

    def _allowed(self, parts: SplitResult, by: Instant) -> bool:
        return parts.path == ROBOTS or self._robots_of(parts, by).can_fetch(self._agent, urlunsplit(parts))

    def _robots_of(self, parts: SplitResult, by: Instant) -> RobotFileParser:
        robots = self._robots.get(parts.netloc)
        if robots is None:
            status, _, body, _ = self._followed(parts._replace(path=ROBOTS, query=""), "text/plain", MOST, by)
            robots = self._robots[parts.netloc] = RobotFileParser()
            missing = 400 <= status < 500 and status not in (401, 403)
            robots.allow_all, robots.disallow_all = missing, status != 200 and not missing
            robots.parse(body.decode("utf-8", "replace").splitlines())
        return robots

    def _left(self, by: Instant) -> float:
        left = (datetime.fromisoformat(by) - datetime.fromisoformat(self._now())).total_seconds()
        if left <= 0:
            raise _Unreadable("the run's time is spent")
        return left

    def _wait(self, parts: SplitResult, by: Instant) -> None:
        robots = self._robots.get(parts.netloc)
        delay = max(INTERVAL, float((robots.crawl_delay(self._agent) if robots else None) or 0))
        wait = self._last.get(parts.netloc, float("-inf")) + delay - self._clock()
        if wait >= self._left(by):
            raise _Unreadable(f"its crawl delay of {delay:g} s would pass the run's time")
        if wait > 0:
            self._sleep(wait)
        self._last[parts.netloc] = self._clock()

    def _checked(self, host: str, port: int) -> str:
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [] if self._base else _resolved(host, port)
        if not all(a.is_global for a in addresses):
            raise _Unreadable(f"{host} is not a public address")
        return self._base.hostname or "" if self._base else str(addresses[0])

    def _connection(self, parts: SplitResult, by: Instant) -> _Pinned:
        web = self._base or parts
        host, port = parts.hostname or "", web.port or PORTS[web.scheme]
        address = self._checked(host, port)
        connection = (_PinnedTls if web.scheme == "https" else _Pinned)(
            host, port, timeout=min(TIMEOUT, self._left(by)))
        connection.address = address
        return connection

    def _get(self, parts: SplitResult, accept: str, most: int, by: Instant) -> tuple[int, str, bytes, str]:
        self._wait(parts, by)
        connection = self._connection(parts, by)
        try:
            connection.request("GET", urlunsplit(("", "", parts.path, parts.query, "")),
                               headers={"User-Agent": self._agent, "Accept": accept})
            res, body = connection.getresponse(), b""
            while len(body) < most and (chunk := res.read(min(CHUNK, most - len(body)))):
                body += chunk
                self._left(by)
            return res.status, res.getheader("Content-Type", ""), body, res.getheader("Location", "")
        except (OSError, http.client.HTTPException) as exc:
            raise _Unreadable(f"no answer: {exc}") from exc
        finally:
            connection.close()
