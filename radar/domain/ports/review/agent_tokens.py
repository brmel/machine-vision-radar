from __future__ import annotations

from typing import Protocol

from radar.domain.review.agents.tokens import AgentToken, TokenUsage

class AgentTokens(Protocol):
    def issue(self, token: AgentToken) -> None:
        ...

    def page(self, cursor: str | None = None) -> tuple[tuple[AgentToken, ...], str | None, int]:
        ...

    def by_digest(self, digest: str) -> AgentToken | None:
        ...

    def revoke(self, token_id: str, at: str) -> AgentToken:
        ...

    def count(self, token_id: str, minute: str, proposal: bool) -> TokenUsage:
        ...
