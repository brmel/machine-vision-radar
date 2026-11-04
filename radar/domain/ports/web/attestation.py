from __future__ import annotations

from enum import Enum
from typing import Protocol

class Verdict(Enum):
    ATTESTS = "attests"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"

class Attestation(Protocol):
    def check(self, token: str) -> Verdict:
        ...
