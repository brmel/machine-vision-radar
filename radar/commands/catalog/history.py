from __future__ import annotations

import argparse

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.ports.store.records import LISTED
from radar.domain.model.history.projection import ROWS, plain

def run_list(args: argparse.Namespace) -> int:
    return output.format_output(plain(args.wiring.records().rows(args.kind, args.query, args.cursor, args.category)),
                                json_mode=args.json, text_formatter=lambda v: output.paged(
v, (f"{r['id']}  {r['label']}" + (f"  {r['detail']}" if r.get("detail") else "") for r in v["records"])))

def run_get(args: argparse.Namespace) -> int:
    found = args.wiring.records().record(args.id)
    if found is None:
        return log.error(f"no record with id {args.id}")
    return output.format_output(plain(found), json_mode=True)

def run_history(args: argparse.Namespace) -> int:
    view = plain(args.wiring.histories().shown(args.id, args.cursor))
    if not view["versions"]:
        return log.error(f"no record with id {args.id}")
    lines = [("" if v["entity"] == args.id else f"{v['entity']} ")
             + f"v{v['version']}  {v['recorded_at']}  {v['actor_kind']}:{v['actor']}  {v['reason']}  "
             f"sources={','.join(s['id'] for s in v['sources']) or '-'}  correlation={v['correlation_id']}"
             + (f"  proposal={v['proposal']}" if "proposal" in v else "")
             for v in view["versions"]] + ([f"next: --cursor {view['next']}"] if "next" in view else [])
    return output.format_output(view, json_mode=args.json, text_formatter=lambda _: "\n".join(lines))

def run_diff(args: argparse.Namespace) -> int:
    try:
        diff = args.wiring.histories().diff(args.id, args.v1, args.v2)
    except ValueError as exc:
        return log.error(str(exc))
    text = "\n".join(f"{c.path}: {c.before or '-'} -> {c.after or '-'}" for c in diff.changes)
    return output.format_output(plain(diff), json_mode=args.json, text_formatter=lambda _: text or "no difference")

def register(commands: Commands) -> None:
    r = commands.verb("record", "list",
                      help=f"a kind's records whose name or id holds a query, in name order, {ROWS} a page, as the "
                           "admin's Catalog lists them", func=run_list)
    r.add_argument("kind", choices=LISTED, help="the kind of record")
    r.add_argument("--query", default="", help="only the records whose name or id holds this")
    r.add_argument("--cursor", help="the `next` of the previous page")
    r.add_argument("--category", help="only the products of this category (the admin's grid)")
    commands.verb("record", "get", help="one record of any kind, as the admin's record page edits it",
                  func=run_get).add_argument("id", help="the record's id")
    h = commands.verb("record", "history",
                      help=f"a record's versions, {ROWS} a page: actor, time, reason, sources, proposal, correlation "
                           "id; "
                      "a product's are its History page's when it has one, its own and those of the public records "
                      "about it", func=run_history)
    h.add_argument("id", help="the record's id")
    h.add_argument("--cursor", help="the `next` of the previous page")
    d = commands.verb("record", "diff", help="the fields that differ between two versions of a record", func=run_diff)
    d.add_argument("id", help="the record's id")
    d.add_argument("v1", type=int, help="the first version")
    d.add_argument("v2", type=int, help="the second version")
