from __future__ import annotations

import copy
import json
from dataclasses import fields, is_dataclass
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol, Sequence, TypeVar

from radar.domain.ports.history.change_log import ChangeLog, ChangePage
from radar.domain.ports.history.version_store import EntityVersion, FieldChange, VersionPage
from radar.domain.model.entities import Change, PatchOp

def plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = {f.name: getattr(value, f.name) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value

def json_text(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, sort_keys=True)

def _apply(state: dict[str, Any], op: PatchOp) -> None:
    *parents, leaf = op.path.split(".")
    node = state
    for key in parents:
        node = node.setdefault(key, {})
    present = leaf in node
    if op.op == "add" and present or op.op != "add" and not present:
        raise ValueError(f"cannot {op.op} '{op.path}': the field is {'already set' if present else 'absent'}")
    if op.op == "remove":
        del node[leaf]
    else:
        node[leaf] = json.loads(op.value or "null")

def states(changes: Iterable[Change]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{}]
    for change in sorted(changes, key=lambda c: c.version):
        state = copy.deepcopy(out[-1])
        for op in change.patch:
            _apply(state, op)
        out.append(state)
    return out

def replay(changes: Iterable[Change]) -> dict[str, Any]:
    return states(changes)[-1]

def _leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict) and value:
        return {k: v for key, sub in value.items() for k, v in _leaves(sub, f"{prefix}{key}.").items()}
    return {prefix.rstrip("."): value}

def field_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[FieldChange, ...]:
    a, b = _leaves(dict(before)), _leaves(dict(after))
    return tuple(FieldChange(p, a.get(p), b.get(p)) for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p) and p)

PAGE = 50
ROWS = 20
Row = TypeVar("Row")

def page_of(rows: Sequence[Row], cursor: str | None) -> tuple[tuple[Row, ...], str | None]:
    start = int(cursor or 0)
    return tuple(rows[start:start + ROWS]), str(start + ROWS) if start + ROWS < len(rows) else None

class _Paged(Protocol):
    @property
    def cursor(self) -> str | None: ...

Paged = TypeVar("Paged", bound=_Paged)

def every_page(read: Callable[[str | None], Paged]) -> Iterator[Paged]:
    page = read(None)
    yield page
    while page.cursor is not None:
        page = read(page.cursor)
        yield page

def paged(changes: Iterable[Change], cursor: str | None) -> ChangePage:
    after = int(cursor) if cursor else 0
    later = sorted((c for c in changes if c.version > after), key=lambda c: c.version)
    page = tuple(later[:PAGE])
    return ChangePage(page, str(page[-1].version) if len(later) > PAGE else None)

def later(changes: Iterable[Change], cursor: str | None) -> ChangePage:
    ordered = sorted((c for c in changes if cursor is None or f"{c.recorded_at}|{c.id}" > cursor),
                     key=lambda c: (c.recorded_at, c.id))
    return ChangePage(tuple(ordered), f"{ordered[-1].recorded_at}|{ordered[-1].id}" if ordered else cursor)

class Projection:
    def __init__(self, log: ChangeLog) -> None:
        self._log = log

    def _changes(self, entity: str) -> list[Change]:
        return [c for page in every_page(lambda cursor: self._log.for_entity(entity, cursor)) for c in page.changes]

    def get(self, entity: str, version: int) -> dict[str, Any] | None:
        changes = [c for c in self._changes(entity) if c.version <= version]
        return replay(changes) if any(c.version == version for c in changes) else None

    def history(self, entity: str, cursor: str | None = None) -> VersionPage:
        changes = sorted(self._changes(entity), key=lambda c: c.version)
        fields = states(changes)
        page, after = page_of(range(len(changes) - 1, -1, -1), cursor)
        versions = tuple(
            EntityVersion(c.entity, c.version, c.recorded_at, c.actor_kind, c.actor, c.reason, c.source_refs,
                          c.proposal, c.correlation_id, field_diff(fields[i], fields[i + 1]))
            for i, c in ((i, changes[i]) for i in page))
        return VersionPage(versions, after, len(changes))

    def diff(self, entity: str, v1: int, v2: int) -> tuple[FieldChange, ...]:
        before, after = self.get(entity, v1), self.get(entity, v2)
        if before is None or after is None:
            raise ValueError(f"{entity} has no recorded version {v1 if before is None else v2}")
        return field_diff(before, after)
