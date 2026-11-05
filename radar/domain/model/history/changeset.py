from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from radar.domain.model.entities import ActorKind
from radar.domain.model.schema import TypeSpec

@dataclass(frozen=True, slots=True)
class PutEntity:
    record: Mapping[str, Any]

@dataclass(frozen=True, slots=True)
class Retract:
    id: str

@dataclass(frozen=True, slots=True)
class Change:
    action: PutEntity | Retract
    reason: str
    actor_kind: ActorKind = "human"
    actor: str = ""
    source_refs: tuple[str, ...] = ()
    proposal: str | None = None

    @property
    def entity(self) -> str:
        return self.action.record["id"] if isinstance(self.action, PutEntity) else self.action.id

@dataclass(frozen=True, slots=True)
class Changeset:
    changes: tuple[Change, ...]

    def subject(self, kind: TypeSpec) -> str:
        about = [c.entity for c in self.changes] + [str(c.action.record.get(f)) for c in self.changes
                                                    if isinstance(c.action, PutEntity) for f in ("subject", "product")]
        found = next((i for i in about if i.startswith(f"{kind.prefix}_")), None)
        if found is None:
            raise ValueError(f"the changeset is about no {kind.name} ({kind.prefix}_…)")
        return found

@dataclass(frozen=True, slots=True)
class Applied:
    events: tuple[Any, ...]
    writes: int

@dataclass(frozen=True, slots=True)
class EntityChange:
    entity: str
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None

def parse_changeset(raw: Any) -> Changeset:
    if not isinstance(raw, dict) or not isinstance(raw.get("changes"), list) or not raw["changes"]:
        raise ValueError("a changeset is {\"changes\": [...]} with at least one change")
    return Changeset(tuple(_change(c, f"changes[{n}]") for n, c in enumerate(raw["changes"])))

def _author(c: dict[str, Any], where: str) -> tuple[str, str]:
    actor_kind = c.get("actor_kind")
    if actor_kind is not None and actor_kind not in ActorKind:
        raise ValueError(f"{where}: actor_kind is one of {', '.join(a.value for a in ActorKind)}")
    actor = c.get("actor")
    if actor is not None and (not isinstance(actor, str) or not actor.strip()):
        raise ValueError(f"{where}: actor is required")
    return actor_kind or "human", (actor or "").strip()

def _change(c: Any, where: str) -> Change:
    if not isinstance(c, dict):
        raise ValueError(f"{where}: expected an object")
    if not isinstance(c.get("reason"), str) or not c["reason"].strip():
        raise ValueError(f"{where}: reason is required")
    actor_kind, actor = _author(c, where)
    refs = c.get("source_refs", [])
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        raise ValueError(f"{where}: source_refs is a list of source ids")
    return Change(_action(c, where), c["reason"], actor_kind, actor, tuple(refs))

def without_version(record: Mapping[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (record or {}).items() if k != "version"}

def _action(c: dict[str, Any], where: str) -> PutEntity | Retract:
    if c.get("op") == "put" and isinstance(c.get("entity"), dict) and isinstance(c["entity"].get("id"), str):
        return PutEntity(without_version(c["entity"]))
    if c.get("op") == "retract" and isinstance(c.get("id"), str):
        return Retract(c["id"])
    raise ValueError(f"{where}: op is put (with an entity carrying its id) or retract (with an id)")

def changeset_json(changeset: Changeset) -> dict[str, Any]:
    def one(c: Change) -> dict[str, Any]:
        op = ({"op": "put", "entity": dict(c.action.record)} if isinstance(c.action, PutEntity)
              else {"op": "retract", "id": c.action.id})
        return {**op, "reason": c.reason, "actor_kind": c.actor_kind, "actor": c.actor,
                "source_refs": list(c.source_refs)}
    return {"changes": [one(c) for c in changeset.changes]}
