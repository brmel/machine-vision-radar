from __future__ import annotations

import argparse
import datetime

from radar.adapters.console import log, output
from radar.domain.model.entities import MarketView
from radar.domain.search.eval import Traffic
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    if args.days < 1:
        return log.error(f"--days wants a number of days from 1, got {args.days}", code=2)
    try:
        last = datetime.date.fromisoformat(args.to) if args.to else args.wiring.today()
    except ValueError:
        return log.error(f"--to wants a date as YYYY-MM-DD, got '{args.to}'", code=2)
    period = Traffic(args.wiring.ask_ledger()).days(last, args.days)
    result = {"from": period.first.isoformat(), "to": period.last.isoformat(), "counts": period.counts,
              "kpis": period.kpis}
    return output.format_output(result, json_mode=args.json, text_formatter=lambda r: "\n".join(
        [f"{r['from']} to {r['to']}", *(f"  {k}: {v}" for k, v in r["counts"].items()),
         *(f"  {k}: {v}" for k, v in r["kpis"].items())]))

def run_weekly(args: argparse.Namespace) -> int:
    if args.weeks < 1:
        return log.error(f"--weeks wants a number of weeks from 1, got {args.weeks}", code=2)
    view = Traffic(args.wiring.ask_ledger()).weeks(args.wiring.today(), args.weeks)
    return output.format_output(view, json_mode=args.json, text_formatter=lambda v: "\n".join(
        f"{w.week} to {w.to}: " + ", ".join(f"{k} {c}" for k, c in w.counts.items()) for w in v.weeks))

def _market_lines(v: MarketView) -> str:
    return "\n".join(
        ["categories: " + ", ".join(f"{c.category} {c.products} products from {c.vendors} vendors"
                                    for c in v.categories),
         "vendors: " + ", ".join(f"{m.organization.slug} {m.products} products in {m.categories} categories"
                                 for m in v.vendors),
         f"countries of {v.organizations} organizations: " + ", ".join(
             f"{c.country} {c.organizations} organizations, {c.products} products" for c in v.countries),
         "consolidation: " + ", ".join(f"{'undated' if e.year is None else e.year} {e.organization.slug} {e.type.id} "
                                       f"{e.owner.slug}" for e in v.consolidation)])

def run_market(args: argparse.Namespace) -> int:
    return output.format_output(args.wiring.repository().market(), json_mode=args.json, text_formatter=_market_lines)

def register(commands: Commands) -> None:
    commands.verb("metrics", "market", func=run_market,
                  help="the market as the catalog counts it: the categories, the vendors and the countries by "
                  "products, and the owning relations newest first")
    w = commands.verb("metrics", "weekly",
                      help="the site's anonymous counters week by week, newest first, with the search KPIs",
                      func=run_weekly)
    w.add_argument("--weeks", type=int, default=8, help="how many weeks, ending with this one (default 8)")
    p = commands.verb("metrics", "show",
                      help="the site's anonymous counters and the search KPIs over the last days, read-only", func=run)
    p.add_argument("--days", type=int, default=7, help="how many days, ending with --to (default 7)")
    p.add_argument("--to", help="the last day, YYYY-MM-DD in UTC (default today)")
