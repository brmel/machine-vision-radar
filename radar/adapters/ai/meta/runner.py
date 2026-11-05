from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from radar.adapters.console import log
from radar.domain.ai.prompts import Prompt
from radar.domain.ports.ai.prompts import Reply

TIMEOUT = 55

def _part(file: tuple[bytes, str]) -> dict[str, Any]:
    content, mime = file
    url = f"data:{mime};base64,{base64.b64encode(content).decode()}"
    if mime.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": url}}
    return {"type": "file", "file": {"filename": f"source.{mime.rsplit('/', 1)[-1]}", "file_data": url}}

class MetaRunner:
    def __init__(self, model: str, base_url: str, key: str) -> None:
        self.model, self._base_url, self._key = model, base_url, key

    def _body(self, prompt: Prompt, request: str, max_tokens: int,
              file: tuple[bytes, str] | None) -> bytes:
        parts = [{"type": "text", "text": request}, *([_part(file)] if file else [])]
        return json.dumps({
            "model": self.model, "max_completion_tokens": max_tokens, "reasoning_effort": "minimal",
            "messages": [{"role": "system", "content": prompt.instruction}, {"role": "user", "content": parts}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": prompt.id, "schema": json.loads(prompt.output_schema)}},
        }).encode()

    def reply(self, prompt: Prompt, request: str, max_tokens: int,
              file: tuple[bytes, str] | None = None) -> Reply:
        if not self._key:
            raise RuntimeError("a model call on the Meta Model API needs MODEL_API_KEY in the environment")
        log.debug("model request", prompt=prompt.id, model=self.model, request=request)
        req = urllib.request.Request(f"{self._base_url}/chat/completions", method="POST",
                                     data=self._body(prompt, request, max_tokens, file),
                                     headers={"Authorization": f"Bearer {self._key}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                said = json.load(res)
        except urllib.error.HTTPError as exc:
            raise OSError(f"Meta Model API: HTTP {exc.code} {exc.read()[:300]!r}") from exc
        usage, choices = said.get("usage") or {}, said.get("choices") or ()
        if not choices:
            raise ValueError(f"Meta Model API: a reply with no message: {str(said)[:300]}")
        return Reply(choices[0]["message"].get("content") or "", usage.get("prompt_tokens", 0),
                     usage.get("completion_tokens", 0), prompt.id)
