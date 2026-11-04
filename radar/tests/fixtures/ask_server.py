from __future__ import annotations

import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from radar.adapters.console import log
from radar.adapters.web.api import Served, wire
from radar.domain.ports.web.endpoint import Request
from radar.adapters.wiring.root import Wiring
from radar.tests.adapters.stub_server import serving
from radar.tests.fixtures.fixture_category import recorded_page

SERVED = Served(lambda: Wiring().api())

class Handler(BaseHTTPRequestHandler):
    def _serve(self, method: str) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        url = urllib.parse.urlsplit(self.path)
        query = dict(urllib.parse.parse_qsl(url.query))
        response = SERVED(Request(method, url.path, body, {k.lower(): v for k, v in self.headers.items()},
                                  self.client_address[0], query))
        payload = wire(response).encode()
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        for name, value in response.headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._serve("GET")

    def do_POST(self) -> None:
        self._serve("POST")

    def log_message(self, format: str, *args: object) -> None:
        log.debug(format % args)

if __name__ == "__main__":
    log.configure(json_mode=True)
    with serving(pages=recorded_page) as site:
        os.environ["MVR_WEB_BASE"] = site
        ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
