from __future__ import annotations

import hashlib
import math
import secrets
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from typing import Sequence

from radar.domain.model.entities import AgentLimits, AgentTokenList, AgentTokenView, Scope, Standing
from radar.domain.model.history.ids import keyed

class Refused(PermissionError):
    ...

class Throttled(Refused):
    def __init__(self, reason: str, retry_after: int) -> None:
        super().__init__(reason)
        self.retry_after = retry_after

@dataclass(frozen=True, slots=True)
class TokenUsage:
    requests: int
    proposals: int

@dataclass(frozen=True, slots=True)
class Limits:
    requests_per_minute: int = 60
    proposals_per_day: int = 50

    def __post_init__(self) -> None:
        if min(self.requests_per_minute, self.proposals_per_day) < 1:
            raise ValueError("a limit is a whole number from 1")

@dataclass(frozen=True, slots=True)
class AgentToken:
    id: str
    name: str
    scope: Scope
    expires: date
    created_at: str
    limits: Limits
    digest: str
    revoked_at: str | None = None

    def standing(self, today: date) -> Standing:
        if self.revoked_at is not None:
            return Standing.REVOKED
        return Standing.EXPIRED if today >= self.expires else Standing.ACTIVE

    def revoked(self, at: str) -> AgentToken:
        return self if self.revoked_at else replace(self, revoked_at=at)

def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def issue(name: str, scope: Scope, expires: date, limits: Limits, now: str) -> tuple[AgentToken, str]:
    if not name.strip():
        raise ValueError("a token needs the name of its agent")
    if expires <= date.fromisoformat(now[:10]):
        raise ValueError(f"a token expires after today, not on {expires.isoformat()}")
    token = f"mvr_{secrets.token_hex(16)}"
    found = digest(token)
    return AgentToken(keyed("agt", found), name.strip(), scope, expires, now, limits, found), token

def admit(found: AgentToken | None, needed: Scope, today: date) -> AgentToken:
    if found is None:
        raise Refused("no such token")
    if found.revoked_at is not None:
        raise Refused(f"revoked on {found.revoked_at[:10]}")
    if found.standing(today) is Standing.EXPIRED:
        raise Refused(f"expired on {found.expires.isoformat()}")
    if not found.scope.covers(needed):
        raise Refused(f"its scope is {found.scope.value}; this needs {needed.value}")
    return found

def throttle(token: AgentToken, used: TokenUsage, now: str) -> None:
    at = datetime.fromisoformat(now)
    if used.requests > token.limits.requests_per_minute:
        raise Throttled(f"over its {token.limits.requests_per_minute} requests a minute", 60 - at.second)
    if used.proposals > token.limits.proposals_per_day:
        midnight = datetime.combine(at.date() + timedelta(days=1), datetime.min.time(), at.tzinfo)
        raise Throttled(f"over its {token.limits.proposals_per_day} proposals a day",
                        math.ceil((midnight - at).total_seconds()))

def token_view(token: AgentToken, today: date) -> AgentTokenView:
    return AgentTokenView(id=token.id, name=token.name, scope=token.scope.value, expires=token.expires.isoformat(),
                          created_at=token.created_at, limits=AgentLimits(**asdict(token.limits)),
                          status=token.standing(today).value, revoked_at=token.revoked_at)

def tokens_view(tokens: Sequence[AgentToken], today: date, cursor: str | None, total: int) -> AgentTokenList:
    return AgentTokenList(tokens=tuple(token_view(t, today) for t in tokens), limits=AgentLimits(**asdict(Limits())),
                          next=cursor, total=total)
