from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

from radar.adapters.console import log
from radar.domain.ai.prompts import Prompt
from radar.domain.ports.ai.prompts import ModelRunner, Reply
from radar.domain.ports.ai.usage_log import Unparsed

T = TypeVar("T")

def ask(runner: ModelRunner, prompt: Prompt, request: str, max_tokens: int,
        file: tuple[bytes, str] | None = None) -> Reply:
    log.debug("model request", prompt=prompt.id, request=request)
    return runner.reply(prompt, request, max_tokens, file)

def read(reply: Reply, shape: Callable[[Any], T]) -> T:
    try:
        return shape(json.loads(reply.text))
    except (ValueError, LookupError, TypeError) as exc:
        raise Unparsed(f"{reply.prompt}: the reply does not fit its shape: {type(exc).__name__}: {exc}",
                       reply.tokens_in, reply.tokens_out) from exc
