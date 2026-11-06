from __future__ import annotations

from typing import Protocol

from radar.domain.model.history.changeset import Changeset
from radar.domain.model.history.plan import Held, Plan

class CatalogStore(Protocol):
    def around(self, changeset: Changeset) -> Held:
        ...

    def write(self, held: Held, plan: Plan) -> int:
        ...
