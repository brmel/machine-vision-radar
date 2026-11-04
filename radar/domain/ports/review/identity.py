from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Admin:
    uid: str
    email: str

class Identity(Protocol):
    def admin(self, id_token: str) -> Admin | None:
        ...

    def grant(self, email: str) -> str:
        ...
