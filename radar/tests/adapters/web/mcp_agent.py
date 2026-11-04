from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import jsonschema

from radar.adapters.web.mcp import SCHEMAS
from radar.domain.ports.web.endpoint import Endpoint, Request, Response

@dataclass(frozen=True)
class McpAgent:
    server: Endpoint
    secret: str

    def send(self, method: str, params: Any = None, rid: int | None = 1) -> Response:
        message = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {}),
                   **({"id": rid} if rid is not None else {})}
        headers = {"authorization": f"Bearer {self.secret}"} if self.secret else {}
        return self.server.respond(Request("POST", "/api/mcp", json.dumps(message).encode(), headers, "127.0.0.1"))

    def answer(self, tool: str, arguments: Any) -> Any:
        result = self._result(tool, arguments)
        assert result.get("isError") is not True, result["content"]
        jsonschema.validate(result["structuredContent"], SCHEMAS[tool]["outputSchema"])
        assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
        return result["structuredContent"]

    def refused(self, tool: str, arguments: Any) -> str:
        result = self._result(tool, arguments)
        assert result["isError"] is True and "structuredContent" not in result
        return result["content"][0]["text"]

    def _result(self, tool: str, arguments: Any) -> dict[str, Any]:
        res = self.send("tools/call", {"name": tool, "arguments": arguments})
        assert res.status == 200, res.body
        return res.body["result"]
