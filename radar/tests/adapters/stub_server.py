from __future__ import annotations

import copy
import json
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator, Mapping

Answer = Callable[[str, bytes], tuple[int, bytes]]
Pages = Callable[[str, Mapping[str, str]], tuple[int, Mapping[str, str], bytes]]
EXCHANGE = json.loads((Path(__file__).parents[1] / "fixtures" / "adk_exchange.json").read_text(encoding="utf-8"))

def vertex_saying(text: str, heard: list[str]) -> Answer:
    reply = copy.deepcopy(EXCHANGE["response"])
    reply["candidates"][0]["content"]["parts"][0]["text"] = text

    def answer(path: str, sent: bytes) -> tuple[int, bytes]:
        heard.append(sent.decode())
        return ((200, json.dumps(reply).encode()) if path == EXCHANGE["path"]
                else (404, b'{"error": {"code": 404, "message": "no such model"}}'))

    return answer

@contextmanager
def serving(answer: Answer | None = None, keep_alive: bool = False, pages: Pages | None = None,
            peers: list[socket.socket] | None = None) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1" if keep_alive else "HTTP/1.0"

        def setup(self) -> None:
            super().setup()
            if peers is not None:
                peers.append(self.connection)

        def do_POST(self) -> None:
            assert answer is not None, f"POST {self.path}: this server answers no POST"
            status, body = answer(self.path, self.rfile.read(int(self.headers["Content-Length"])))
            if status == 0:
                self.wfile.write(body)
                return
            self._send(status, {"Content-Type": "application/json"}, body)

        def do_GET(self) -> None:
            assert pages is not None, f"GET {self.path}: this server serves no page"
            self._send(*pages(self.path, dict(self.headers)))

        def _send(self, status: int, headers: Mapping[str, str], body: bytes) -> None:
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
