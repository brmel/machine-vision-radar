from __future__ import annotations

import difflib
import json
import os
from pathlib import Path

from ... import paths
from ...adapters.console import log, output
from ...adapters.files.model_json import load_schema
from ...domain.model.schema import SchemaError
from .json_layout import layout
from .json_schema_emitter import emit_tools
from .py_emitter import emit_python
from .ts_emitter import emit_view_types
from .zod_emitter import emit_view_zod

FIX = "python -m radar model generate"

def render(model_dir: Path = paths.MODEL) -> dict[Path, str]:
    schema = load_schema(model_dir)
    return {
        paths.GENERATED_MODEL_PY: emit_python(schema),
        paths.GENERATED_MCP_TOOLS: emit_tools(schema),
        paths.GENERATED_VIEWS_TS: emit_view_types(schema),
        paths.GENERATED_VIEWS_ZOD: emit_view_zod(schema),
    }

def _outputs(model_dir: Path) -> dict[Path, str] | None:
    files = sorted({*model_dir.rglob("*.json"), *paths.CONTRACTS.rglob("*.json"), *paths.DATA.rglob("*.json")})
    try:
        laid = {p: layout(json.loads(p.read_text(encoding="utf-8"))) for p in files}
        return {**laid, **render(model_dir)}
    except SchemaError as exc:
        log.error(f"model schema: {exc}")
        return None

def generate(as_json: bool) -> int:
    if (outputs := _outputs(paths.MODEL)) is None:
        return 1
    written = []
    for dest, text in outputs.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        written.append(os.path.relpath(dest, paths.DEV))
    return output.format_output({"written": written}, as_json, lambda r: f"wrote {len(r['written'])} files")

def check(model_dir: Path = paths.MODEL, as_json: bool = False) -> int:
    if (outputs := _outputs(model_dir)) is None:
        return 1
    for dest, text in outputs.items():
        current = dest.read_text(encoding="utf-8") if dest.exists() else ""
        if current != text:
            diff = "\n".join(list(difflib.unified_diff(current.splitlines(), text.splitlines(), str(dest), "fresh",
                                                       lineterm=""))[:40])
            return log.error(f"{dest.name} is not what `model generate` writes\n{diff}", fix=FIX)
    names = [dest.name for dest in outputs]
    return output.format_output({"ok": True, "fresh": names}, as_json,
                                lambda r: f"{len(r['fresh'])} files are up to date")
