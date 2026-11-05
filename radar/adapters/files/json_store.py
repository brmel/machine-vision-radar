from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from radar.adapters.storage.memory_catalog import MemoryCatalog
from radar.domain.model.entities import CLASSES
from radar.domain.model.model import Model
from radar.domain.model.schema import ModelSchema
from radar.adapters.files.json_parser import refuse_constant

def write_catalog(data_dir: Path, schema: ModelSchema, records: Iterable[dict[str, Any]]) -> dict[str, int]:
    by_collection: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        kind = schema.kind_of(r["id"])
        if kind:
            by_collection.setdefault(schema.collection(kind), []).append(r)
    data_dir.mkdir(parents=True, exist_ok=True)
    for stale in data_dir.glob("*.jsonl"):
        if stale.stem not in by_collection:
            stale.unlink()
    for collection, rows in by_collection.items():
        lines = (json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in sorted(rows, key=lambda r: r["id"]))
        (data_dir / f"{collection}.jsonl").write_text("".join(lines), encoding="utf-8")
    return {c: len(rows) for c, rows in sorted(by_collection.items())}

def load_catalog(data_dir: Path, model: Model) -> MemoryCatalog:
    all_entities: list[Any] = []

    for ent_type, target_file in ((t, data_dir / f"{t.collection}.jsonl") for t in model.schema.entities):
        if not target_file.is_file():
            continue
        for line_no, line in enumerate(target_file.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if not s:
                continue
            try:
                raw = json.loads(s, parse_constant=refuse_constant)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{target_file.name}:{line_no}: invalid JSON: {exc}") from exc
            all_entities.append(model.parse(raw, CLASSES[ent_type.name], f"{target_file.name}:{line_no}"))

    return MemoryCatalog(sorted(all_entities, key=lambda e: e.id))
