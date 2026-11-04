from __future__ import annotations

from typing import Any, Callable

Check = Callable[[dict[str, Any], str, str], dict[str, Any]]
MediaUrl = Callable[[str, str], str]
