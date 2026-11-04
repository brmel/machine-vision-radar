from __future__ import annotations

from typing import Protocol

from radar.domain.ports.review.proposal_queue import Query, QueuePage
from radar.domain.review.proposal import Receipt, Shown
from radar.domain.review.requests import Agent, Bundle, Draft, Founder, Job, Submitter

class Proposing(Protocol):
    def submit(self, draft: Draft, by: Submitter) -> Shown:
        ...

    def file(self, bundle: Bundle, by: Agent | Job) -> tuple[Receipt, ...]:
        ...

    def queue(self, query: Query, by: Founder | Agent | Job, cursor: str | None = None) -> QueuePage:
        ...

    def proposal(self, proposal: str, by: Founder | Agent) -> Shown:
        ...
