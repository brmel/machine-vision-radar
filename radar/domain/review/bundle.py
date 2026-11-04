from __future__ import annotations

from typing import Callable, Sequence

from radar.domain.model.changeset import EntityChange, PutEntity
from radar.domain.model.entities import Risk
from radar.domain.review.agents.drafts import References, naming
from radar.domain.review.proposal import Proposal

RANK = {risk: n for n, risk in enumerate(Risk)}

def puts(proposal: Proposal) -> tuple[PutEntity, ...]:
    return tuple(c.action for c in (proposal.changeset.changes if proposal.changeset else ())
                 if isinstance(c.action, PutEntity))

def _names(proposal: Proposal, refs: References) -> set[str]:
    return {ref for put in puts(proposal) for _, ref in naming(put.record, refs)}

def after(proposals: Sequence[Proposal], refs: References) -> dict[str, tuple[str, ...]]:
    putting = {p.id: {put.record["id"] for put in puts(p)} for p in proposals}
    return {p.id: tuple(q.id for q in proposals if q.id != p.id and putting[q.id] & (_names(p, refs) - putting[p.id]))
            for p in proposals}

def ordered(proposals: Sequence[Proposal], waits: dict[str, tuple[str, ...]],
            key: Callable[[Proposal], tuple[object, ...]]) -> list[Proposal]:
    left, placed, order = sorted(proposals, key=key), set(), []
    while left:
        ready = next((p for p in left if placed.issuperset(waits[p.id])), left[0])
        order.append(ready)
        placed.add(ready.id)
        left.remove(ready)
    return order

def risk(changes: Sequence[EntityChange]) -> Risk:
    if any(c.after is None for c in changes):
        return Risk.WITHDRAWS
    return Risk.CHANGES if any(c.before is not None for c in changes) else Risk.ADDS
