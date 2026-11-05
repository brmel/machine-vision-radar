from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

from radar.domain.ports.ai.prompts import Reply
from radar.domain.ports.ai.usage_log import Unparsed

T = TypeVar("T")

def read(reply: Reply, shape: Callable[[Any], T]) -> T:
    try:
        return shape(json.loads(reply.text))
    except (ValueError, LookupError, TypeError) as exc:
        raise Unparsed(f"{reply.prompt}: the reply does not fit its shape: {type(exc).__name__}: {exc}",
                       reply.tokens_in, reply.tokens_out) from exc
