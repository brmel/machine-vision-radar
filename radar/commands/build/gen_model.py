from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from radar.build.codegen import check, generate
from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.model.entities import FilesOn
from radar.domain.model.history.migration import MIGRATION, batches, migrated, parse_plan
from radar.domain.model.history.projection import plain
from radar.domain.model.model import ParseError
from radar.domain.review.requests import Changes, Job
from radar.domain.review.views import admin_model

BATCH = 500

def run(args: argparse.Namespace) -> int:
    return check(as_json=args.json) if args.check else generate(as_json=args.json)

def run_show(args: argparse.Namespace) -> int:
    return output.format_output(plain(admin_model(args.wiring.model())), json_mode=True)

def _moved(result: dict[str, Any]) -> str:
    counted = "".join(f"\n  {rule}: {n}" for rule, n in result["counts"].items())
    filed = f"\nfiled as {', '.join(result['proposals'])}" if result["proposals"] else "\nnothing filed"
    return f"{result['changes']} record(s) move{counted}{filed}"

def run_migrate(args: argparse.Namespace) -> int:
    wiring, cid = args.wiring, args.wiring.correlate("migrate")
    try:
        plan = parse_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")), wiring.model())
    except (OSError, ValueError, ParseError) as exc:
        return log.error(f"{args.plan}: {exc}", code=2)
    changeset, counts = migrated(wiring.catalog(()), plan, wiring.model())
    proposals: list[str] = []
    if not args.dry_run:
        review, job = wiring.review(), Job(MIGRATION, cid)
        proposals = [review.submit(Changes(FilesOn.UPDATE, plan.reason, None, batch), job).proposal.id
                     for batch in batches(changeset, BATCH)]
    return output.format_output({"correlation_id": cid, "changes": len(changeset.changes), "counts": dict(counts),
                                 "proposals": proposals}, json_mode=args.json, text_formatter=_moved)

def register(commands: Commands) -> None:
    p = commands.verb("model", "generate", help="regenerate Python, TypeScript and Zod types from contracts/model/",
                      func=run)
    p.add_argument("--check", action="store_true",
                   help="verify the generated files and the contracts' layout are up to date; write nothing")
    commands.verb("model", "show", help="every kind's fields, references and labels, as the admin's forms read them",
                  func=run_show)
    m = commands.verb("model", "migrate",
                      help="derive one changeset from a migration plan over the whole store and file it through "
                           f"review, {BATCH} records a proposal; the founder approves the proposals under one note",
                      func=run_migrate)
    m.add_argument("plan", help='the plan JSON: {"reason": ..., "rules": [...]}, each rule one of drop_field, '
                                "rename_spec, move_terms, map_term, true_as_term and move_category")
    m.add_argument("--dry-run", action="store_true", help="print what would move and file nothing")
