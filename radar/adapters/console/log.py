from __future__ import annotations

import datetime
import json
import re
import sys
from contextvars import ContextVar
from functools import partial
from typing import Any, Mapping

from radar import paths

DEBUG, INFO, WARN, ERROR = 10, 20, 30, 40
_LEVEL_NAMES = {DEBUG: "debug", INFO: "info", WARN: "warn", ERROR: "error"}
_PREFIXES = {DEBUG: "DEBUG: ", WARN: "WARN: ", ERROR: "ERROR: "}

_RULES = json.loads((paths.CONTRACTS / "logging.json").read_text(encoding="utf-8"))
_SECRET_KEY = re.compile(_RULES["secret_key"], re.IGNORECASE)
_SECRET_VALUE = re.compile("|".join(_RULES["secret_values"]), re.IGNORECASE)

_current_level = INFO
_json_mode = False
_context: ContextVar[Mapping[str, Any]] = ContextVar("log_context", default={})

def configure(verbose: bool = False, quiet: bool = False, json_mode: bool = False) -> None:
    global _current_level, _json_mode
    _json_mode = json_mode
    _context.set({})
    _current_level = DEBUG if verbose else WARN if quiet else INFO

def bind(**fields: Any) -> None:
    _context.set({**_context.get(), **fields})

def bound() -> Mapping[str, Any]:
    return _context.get()

def redact(value: Any, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return _RULES["redacted"]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(_RULES["redacted"], value)
    if isinstance(value, Mapping):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value

def _log(level: int, msg: str, fix: str | None = None, **extra: Any) -> None:
    if level < _current_level:
        return
    time = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    payload: dict[str, Any] = redact({"time": time, "level": _LEVEL_NAMES[level], "event": msg, **_context.get(),
                                      **extra, **({"fix": fix} if fix else {})})
    if _json_mode:
        sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    else:
        tags = "".join(f" [{k}={v}]" for k, v in redact(_context.get()).items())
        sys.stderr.write(
            f"{_PREFIXES.get(level, '')}{payload['event']}{tags}\n" + (
                f"  fix: {payload['fix']}\n" if "fix" in payload else ""))
    sys.stderr.flush()

debug = partial(_log, DEBUG)
info = partial(_log, INFO)
warn = partial(_log, WARN)

def error(msg: str, fix: str | None = None, code: int = 1, **extra: Any) -> int:
    _log(ERROR, msg, fix=fix, code=code, **extra)
    return code
