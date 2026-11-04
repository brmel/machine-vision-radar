from __future__ import annotations

import json
from typing import Any

WIDTH = 120

def layout(value: Any) -> str:
    return _laid(value, 0, "") + "\n"

def _laid(value: Any, indent: int, head: str) -> str:
    flat = json.dumps(value, ensure_ascii=False)
    entries = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    if not any(isinstance(v, (dict, list)) for _, v in entries) or len(head) + len(flat) + 1 <= WIDTH:
        return head + flat
    pad = " " * (indent + 2)
    if isinstance(value, dict):
        lines = [_laid(v, indent + 2, f"{pad}{json.dumps(k, ensure_ascii=False)}: ") for k, v in value.items()]
        return head + "{\n" + ",\n".join(lines) + "\n" + " " * indent + "}"
    return head + "[\n" + ",\n".join(_laid(v, indent + 2, pad) for v in value) + "\n" + " " * indent + "]"
