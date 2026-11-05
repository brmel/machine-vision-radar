from __future__ import annotations

import argparse
from dataclasses import asdict

from radar.adapters.console import log, output
from radar.domain.validation.context import ValidationContext
from radar.domain.validation.runner import validate
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    schema, registry = args.wiring.model()
    catalog, whole = args.wiring.catalog_at(args.path)
    res = validate(ValidationContext(catalog, registry, schema, args.wiring.today(), whole_catalog=whole))
    if args.json:
        output.format_output({"ok": res.ok, "errors": [asdict(f) for f in res.errors],
                              "warnings": [asdict(f) for f in res.warnings]}, json_mode=True)
        return 0 if res.ok else 1

    for w in res.warnings:
        log.warn(f"[{w.rule}] {w.entity_id}: {w.message}")
    for e in res.errors:
        log.error(f"[{e.rule}] {e.entity_id}: {e.message}")

    if not res.ok:
        return log.error(f"{len(res.errors)} validation error(s)")

    return output.format_output("catalog validation OK")

def register(commands: Commands) -> None:
    p = commands.verb("model", "validate",
                      help="validate the model and registry, or a catalog folder or file, against the invariants",
                      func=run)
    p.add_argument("path", nargs="?",
                   help="a catalog JSON file, or a folder of JSONL files (default: the model and registry alone)")
