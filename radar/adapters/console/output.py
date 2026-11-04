from __future__ import annotations

import json
import sys
from typing import Any, Callable, Iterable, Mapping

from radar.domain.model.history.projection import plain

def format_output(content: Any, json_mode: bool = False, text_formatter: Callable[[Any], str] | None = None) -> int:
    if json_mode or (text_formatter is None and not isinstance(content, str)):
        text = json.dumps(content, indent=2, ensure_ascii=False, default=plain)
    else:
        text = text_formatter(content) if text_formatter else content
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    return 0

def paged(view: Mapping[str, Any], rows: Iterable[str]) -> str:
    return "\n".join(
        [*rows, f"{view['total']} in all" + (f"; next: --cursor {view['next']}" if "next" in view else "")])

def line(message: Mapping[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def write_bytes(chunks: Iterable[bytes]) -> None:
    for chunk in chunks:
        sys.stdout.buffer.write(chunk)
    sys.stdout.flush()
