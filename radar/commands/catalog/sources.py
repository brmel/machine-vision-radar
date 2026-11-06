from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
from typing import Any, Sequence

from radar.adapters.console import output
from radar.adapters.console.parser import Commands
from radar.domain.review.agents.duplicates import SourceGroup, SourceMerge
from radar.domain.review.proposal import Filed
from radar.domain.review.requests import Bundle, Job
from radar.domain.search.sources import KINDS, SourceQuery

ACTOR = "radar source dedupe"

def _lines(found: dict[str, Any]) -> str:
    rows = [f"{s['id']}  {s['retrieved_at'][:10]}  {s['type']['id']:<14} {s.get('url', '')}" for s in found["sources"]]
    rows += [f"{d['id']}  {d['fetched_at'][:10]}  {d['kind']['id']:<14} {d.get('source_url', d['sha256'])}"
             for d in found["documents"]]
    return "\n".join(rows) or "no source or document"

def run(args: argparse.Namespace) -> int:
    query = SourceQuery(limit=args.limit, url=args.url, vendor=args.vendor, type=args.type, since=args.since,
                        until=args.until)
    return output.format_output(query.found(args.wiring.catalog(KINDS), args.wiring.model().registry),
                                json_mode=args.json, text_formatter=_lines)

def _plan(groups: Sequence[SourceGroup], merged: dict[str, Any]) -> str:
    rows = [f"{g.url}\n  keep {g.kept}; merge {', '.join(g.extras)}; repoint {len(g.repoint)} record(s)"
            for g in groups]
    filed = f"; filed into bundle {merged['bundle']}: {', '.join(merged['filed'])}" if merged["bundle"] else ""
    return "\n".join([*rows, f"{len(groups)} URL(s) held by more than one Source, "
                             f"{merged['proposals']} proposal(s){filed}", *merged["refusals"]])

def run_dedupe(args: argparse.Namespace) -> int:
    model = args.wiring.model()
    merge = SourceMerge.of(args.wiring.catalog(SourceMerge.kinds(model.schema)), model)
    bundle = args.wiring.correlate("dedupe") if args.file and merge.drafts else None
    receipts = args.wiring.review().file(Bundle(bundle, merge.drafts), Job(ACTOR, bundle)) if bundle else ()
    merged = {"groups": [asdict(g) for g in merge.groups], "proposals": len(merge.drafts), "bundle": bundle,
              "filed": [r.proposal.id for r in receipts if isinstance(r, Filed)],
              "refusals": [refusal for r in receipts for refusal in r.refusals]}
    return output.format_output(merged, json_mode=args.json, text_formatter=lambda m: _plan(merge.groups, m))

def register(commands: Commands) -> None:
    p = commands.verb("source", "search",
                      help="the catalog's Sources and media Documents by address, vendor, type and date, newest first",
                      func=run)
    p.add_argument("--url", help="text the address contains, in any case")
    p.add_argument("--vendor", help="an organization's id or slug: the sources and files on its website")
    p.add_argument("--type", help="a source type or a document kind (the registry's source_types and document_kinds)")
    p.add_argument("--since", type=date.fromisoformat, help="retrieved on or after this day, YYYY-MM-DD")
    p.add_argument("--until", type=date.fromisoformat, help="retrieved on or before this day, YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=25,
                   help="the most sources, and the most documents, to list (default 25)")
    d = commands.verb("source", "dedupe",
                      help="each address more than one Source holds, merged into one: the earliest retrieved, then "
                           "the lowest id, is kept; each record naming another is repointed to it, and the others "
                           "are retracted. Prints the plan; only review changes the catalog",
                      func=run_dedupe)
    d.add_argument("--file", action="store_true",
                   help="file the plan as one bundle in the review queue, for the founder to approve (writes: --yes "
                        "on the project)")
