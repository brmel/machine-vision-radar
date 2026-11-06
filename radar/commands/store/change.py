from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from radar.adapters.console import log, output
from radar.domain.validation.verdict import Finding, InvalidChangeset
from radar.domain.model.history.changeset import parse_changeset
from radar.domain.model.history.plan import Refused, Stamp
from radar.domain.review.requests import Founder, Rollback
from radar.domain.model.history.projection import plain
from radar.domain.review.views import shown_view
from radar.adapters.console.parser import Commands

def run_apply(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("change")
    model, store = args.wiring.model(), args.wiring.catalog_store()
    try:
        changeset = parse_changeset(json.loads(Path(args.changeset).read_text(encoding="utf-8")), model)
    except InvalidChangeset as exc:
        return _refused(exc.findings)
    held = store.around(changeset)
    planned = model.change(held, changeset, Stamp(args.wiring.now(), cid))
    if isinstance(planned, Refused):
        return _refused(planned.findings)
    writes, events = store.write(held, planned), [plain(e) for e in planned.events]
    log.info(f"change: {len(events)} event(s), {writes} doc(s) written")
    lines = [f"{e.entity} v{e.version}: {op.op} {op.path}" + (f" = {op.value}" if op.value is not None else "")
             for e in planned.events for op in e.patch]
    output.format_output({"correlation_id": cid, "events": events, "writes": writes},
                         json_mode=args.json, text_formatter=lambda _: "\n".join(lines) or "no change: nothing written")
    return 0 if not events or args.wiring.reindex(changeset.changes[0].actor, cid) else 1

def _refused(findings: Sequence[Finding]) -> int:
    for f in findings:
        log.error(str(f))
    return log.error("the changeset is refused: nothing written")

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
