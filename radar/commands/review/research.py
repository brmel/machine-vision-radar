from __future__ import annotations

import argparse
from typing import Any

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.model.history.projection import ROWS, plain
from radar.domain.ports.review.research_runs import ResearchRun, Status
from radar.domain.review.agents.research.run import FOLLOW, PAGES, SECONDS
from radar.domain.review.agents.research.sites import CategoryScope, MakerScope, ProductScope, RunScope
from radar.domain.review.agents.runs import run_row, run_view, runs_view
from radar.domain.review.requests import Founder

def _line(row: dict[str, Any]) -> str:
    return (f"{row['id']}  {row['status']:<9}  {row['scope']}  {row['pages']} pages, {row['filed']} filed, "
            f"{row['rejected']} rejected, CAD {row['cad']:g}")

def _shown(run: ResearchRun, args: argparse.Namespace) -> int:
    view = plain(run_view(run))
    lines = [_line(plain(run_row(run))), *(f"{n['at']}  {n['step']:<8}  {n['detail']}" for n in view["lines"])]
    return output.format_output(view, json_mode=args.json, text_formatter=lambda _: "\n".join(lines))

def _scope(args: argparse.Namespace) -> RunScope:
    if args.product:
        return ProductScope(args.product)
    return MakerScope(args.maker) if args.maker else CategoryScope(args.category)

def run_run(args: argparse.Namespace) -> int:
    research = args.wiring.researcher()
    run = research.status(research.start(_scope(args), Founder(args.actor, args.wiring.correlate("research"))))
    if run.outcome and run.outcome.status is Status.CAPPED:
        log.warn(f"the research cap stopped the run: {run.outcome.reason}",
                 fix="radar ai-caps set research --day-calls N --month-cad X --reason …")
    return _shown(run, args)

def run_cancel(args: argparse.Namespace) -> int:
    return _shown(args.wiring.researcher().cancel(args.id), args)

def run_list(args: argparse.Namespace) -> int:
    return output.format_output(plain(runs_view(args.wiring.researcher().runs(args.cursor))), json_mode=args.json,
                                text_formatter=lambda v: output.paged(v, map(_line, v["runs"])))

def run_log(args: argparse.Namespace) -> int:
    return _shown(args.wiring.researcher().status(args.id), args)

def _measured(m: dict[str, Any]) -> str:
    statuses = ", ".join(f"{n} {status}" for status, n in m["statuses"].items())
    lines = [f"since {m['since']}: {m['runs']} runs, {m['pages']} pages, {m['filed']} filed, "
             f"{m['values']} values ({m['filter_values']} filter values), CAD {m['cad']:g}",
             f"values now: {statuses or 'none'}; {m['published']} published"]
    for step in ("skipped", "refused"):
        if m[step]:
            lines += [f"{step}:", *(f"  {n:>3}  {why}" for why, n in m[step].items())]
    return "\n".join([*lines, "profile cells filled, at the start and now:",
                      *(f"  {c['before']:>5} {c['now']:>5} of {c['cells']:>5}  {cid}"
                        for cid, c in m["cells"].items())])

def run_measure(args: argparse.Namespace) -> int:
    measures = args.wiring.researcher().measure(args.since, Founder("founder", args.wiring.correlate("research")))
    return output.format_output(plain(measures), json_mode=args.json, text_formatter=_measured)

def register(commands: Commands) -> None:
    r = commands.verb("research", "run",
                      help=f"run the research agent on a scope until it stops (at most {PAGES} pages, no step "
                           f"started after {SECONDS:g} s, {FOLLOW} links followed a page), filing each proposal into "
                           "the run's bundle as it is found", func=run_run)
    scope = r.add_mutually_exclusive_group(required=True)
    scope.add_argument("--product", help="a product, by id or slug: its own page, else its maker's website, is read")
    scope.add_argument("--maker", help="an organization, by id or slug: its website is read")
    scope.add_argument("--category", help="a category id: the website of each maker of its products is read")
    r.add_argument("--actor", default="founder", help="who starts it (default: founder)")
    c = commands.verb("research", "cancel", help="cancel a running research run: it stops at its next step",
                      func=run_cancel)
    c.add_argument("id", help="the run's id (research-…), from `research list`")
    li = commands.verb("research", "list",
                       help=f"the research runs, newest first, {ROWS} a page, each with how many pages it read, "
                            "proposals it filed "
                       "(media and datasheets among them) and had rejected, and its cost", func=run_list)
    li.add_argument("--cursor", help="the `next` of the previous page")
    g = commands.verb("research", "log",
                      help="a research run's log: each page or file read or skipped, proposal filed or rejected, and "
                           "why it ended", func=run_log)
    g.add_argument("id", help="the run's id (research-…), from `research list`")
    m = commands.verb("research", "measure",
                      help="the research runs started since an instant, summed: pages read, what was skipped and "
                           "refused "
                      "by why, proposals filed, the values they put, how many are filter values, are approved, "
                      "rejected or waiting "
                      "and are published, each category's profile cells filled then and now, and the cost; reads only",
                      func=run_measure)
    m.add_argument("--since", required=True,
                   help="an Instant (2026-10-29T18:59:00Z): the runs started at or after it are measured")
