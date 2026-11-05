from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar.adapters.console import log, output
from radar.domain.validation.context import InvalidChangeset
from radar.domain.model.changeset import Changeset, parse_changeset
from radar.domain.review.requests import Founder, Rollback
from radar.domain.model.history.projection import plain
from radar.domain.review.views import shown_view
from radar.adapters.console.parser import Commands

def _apply(args: argparse.Namespace, changeset: Changeset, cid: str) -> int:
    try:
        applied = args.wiring.writer().apply(changeset, cid)
    except InvalidChangeset as exc:
        for f in exc.findings:
            log.error(f if isinstance(f, str) else f"[{f.rule}] {f.entity_id}: {f.message}")
        return log.error("the changeset is refused: nothing written")
    log.info(f"change: {len(applied.events)} event(s), {applied.writes} doc(s) written")
    lines = [f"{e['entity']} v{e['version']}: {op['op']} {op['path']}" + (f" = {op['value']}" if "value" in op else "")
             for e in applied.events for op in e["patch"]]
    output.format_output({"correlation_id": cid, "events": list(applied.events), "writes": applied.writes},
                         json_mode=args.json, text_formatter=lambda _: "\n".join(lines) or "no change: nothing written")
    return 0 if not applied.events or args.wiring.reindex(changeset.changes[0].actor, cid) else 1

def run_apply(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("change")
    return _apply(args, parse_changeset(json.loads(Path(args.changeset).read_text(encoding="utf-8"))), cid)

def run_rollback(args: argparse.Namespace) -> int:
    shown = args.wiring.review().submit(Rollback(args.id, args.to, args.reason),
                                        Founder(args.actor, args.wiring.correlate("rollback")))
    view = plain(shown_view(shown))
    return output.format_output(view, json_mode=args.json,
                                text_formatter=lambda v: f"{v['id']} filed: approve it with `radar proposal approve "
                                                         f"{v['id']} --note …`")

def register(commands: Commands) -> None:
    a = commands.verb("change", "apply", help="validate a changeset JSON file, print its diff and apply it",
                      func=run_apply)
    a.add_argument("changeset", help="path to the changeset JSON")
    r = commands.verb("record", "rollback",
                      help="file a proposal for a new version of a record equal to an earlier one; history keeps every "
                           "version", func=run_rollback)
    r.add_argument("id", help="the record id")
    r.add_argument("--to", type=int, required=True, help="the version to return to")
    r.add_argument("--reason", required=True, help="why (required)")
    r.add_argument("--actor", default="founder", help="who proposes the rollback (default: founder)")
