from __future__ import annotations

import argparse
from typing import Any

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.read_model import read_model
from radar.domain.read_model.derived.coverage import Coverage, spec_shares
from radar.domain.model.entities import FilesOn
from radar.domain.review.requests import Job, Withdrawal

ACTOR = "radar quality report"

def _coverage(coverage: Coverage) -> dict[str, object]:
    listed = {"no_category": coverage.no_category, "untagged": coverage.untagged, "thin": coverage.thin}
    return {"products": coverage.products,
            **{name: {"count": len(ids), "ids": list(ids)} for name, ids in listed.items()}}

def _text(payload: dict[str, Any], coverage: Coverage, filing: bool) -> str:
    lines = [f"Provenance: {payload['products']} products, {payload['weak']} weak" + (
        f", {len(payload['filed'])} quarantines proposed" if filing else ""),
             f"Coverage: {len(coverage.no_category)} with no category | {len(coverage.untagged)} untagged | "
             f"{len(coverage.thin)} thin pages", "",
             *(f"{r['id']}  {r['claims']:>3} claims  {r['vendor_backed']:>3} vendor-backed  "
               f"{'; '.join(r['weak']) or 'ok'}" for r in payload["records"])]
    return "\n".join(lines)

def run(args: argparse.Namespace) -> int:
    model = args.wiring.model()
    found = read_model.quality(args.wiring.catalog(), model, args.wiring.media(), args.wiring.today())
    weak = [f for f in found.provenance if f.weak]
    filed: list[str] = []
    if args.file:
        review, job = args.wiring.review(), Job(ACTOR, args.wiring.correlate("quality"))
        filed = [review.submit(Withdrawal(f.product, f"Weak provenance: {'; '.join(f.weak)}", FilesOn.QUALITY),
                               job).proposal.id for f in weak]
    shown = (weak if args.weak_only else sorted(found.provenance, key=lambda f: (not f.weak, f.product)))[:args.limit]
    payload = {"products": len(found.provenance), "weak": len(weak),
               "records": [{**f.report(), "name": found.names.get(f.product, "")} for f in shown],
               "coverage": _coverage(found.coverage), "filed": filed}
    return output.format_output(payload, json_mode=args.json,
                                text_formatter=lambda p: _text(p, found.coverage, args.file))

def run_coverage(args: argparse.Namespace) -> int:
    registry = args.wiring.model().registry
    if args.category and args.category not in registry.categories:
        return log.error(f"no category '{args.category}'", fix="radar category list", code=2)
    shares = spec_shares(args.wiring.catalog(), registry, args.category)
    return output.format_output({"categories": shares}, json_mode=args.json, text_formatter=lambda p: "\n".join(
        f"{c.category} ({c.products} products, {c.missing_required} missing a required spec)\n" + "\n".join(
            f"  {s.share:>6.1%}  {s.key}" for s in c.specs) for c in p["categories"]))

def register(commands: Commands) -> None:
    c = commands.verb("quality", "coverage",
                      help="per category, how many products miss a required spec, and each profile spec's share of "
                           "products publishing a value of it, the most published first", func=run_coverage)
    c.add_argument("--category", help="one category's id (default: every category with products)")
    p = commands.verb("quality", "report",
                      help="each product's provenance from its sources and dates, the weak ones first, and the "
                           "catalog's coverage", func=run)
    p.add_argument("--weak-only", action="store_true", help="only the products whose provenance is weak")
    p.add_argument("--limit", type=int, default=20, help="how many products to list (default: 20)")
    p.add_argument("--file", action="store_true",
                   help="propose each weak product's quarantine in the review queue (writes: --yes on the project)")
