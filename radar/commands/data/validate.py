from __future__ import annotations

import argparse

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    catalog, scope = args.wiring.catalog_at(args.path)
    verdict = args.wiring.model().check(catalog, scope, args.wiring.today())
    if args.json:
        output.format_output({"ok": verdict.ok, "errors": [f.report() for f in verdict.errors],
                              "warnings": [f.report() for f in verdict.warnings]}, json_mode=True)
        return 0 if verdict.ok else 1

    for w in verdict.warnings:
        log.warn(str(w))
    for e in verdict.errors:
        log.error(str(e))

    if not verdict.ok:
        return log.error(f"{len(verdict.errors)} validation error(s)")

    return output.format_output("catalog validation OK")

def register(commands: Commands) -> None:
    p = commands.verb("model", "validate",
                      help="validate the model and registry, or a catalog folder or file, against the invariants",
                      func=run)
    p.add_argument("path", nargs="?",
                   help="a catalog JSON file, or a folder of JSONL files (default: the model and registry alone)")
