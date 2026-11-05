from __future__ import annotations

import argparse
from typing import Any

from radar.adapters.console import output
from radar.domain.ai.budget import Use, cap_draft
from radar.domain.ai.meter import caps_today
from radar.domain.model.history.ids import keyed
from radar.domain.review.requests import Enactment, Founder
from radar.domain.model.history.projection import plain
from radar.domain.review.views import proposal_view
from radar.adapters.console.parser import Commands

USES = [u.value for u in Use]

def _text(view: dict[str, Any]) -> str:
    return "\n".join(f"{r['use']:<9}  {r.get('model', '-'):<22}  CAD {r['cad_month']:g} of {r['month_cad']:g} this "
                     "month  "
                     f"{r['calls_today']} of {r['day_calls']} calls today" + (
                         f"  {r['client_calls']} a client" if "client_calls" in r else "")
                     for r in view["uses"])

def run_get(args: argparse.Namespace) -> int:
    view = caps_today(args.wiring.budget(), args.wiring.model()[1].ai, args.wiring.prompts(), args.wiring.now()[:10])
    return output.format_output(plain(view), json_mode=args.json, text_formatter=_text)

def run_set(args: argparse.Namespace) -> int:
    use = Use(args.use)
    cap = args.wiring.budget().caps()[use].changed(args.month_cad, args.day_calls, args.client_calls, args.model)
    founder = Founder(args.actor, args.wiring.correlate("ai-caps"))
    approved = args.wiring.review().decide(Enactment(cap_draft(use, cap, args.reason, founder.name)), founder).one()
    return output.format_output(plain(proposal_view(approved)), json_mode=args.json,
                                text_formatter=lambda v: f"{v['id']}: {args.use} set, {v['reason']}")

def run_history(args: argparse.Namespace) -> int:
    view = plain(args.wiring.histories().page(keyed("cap", args.use), args.cursor))
    return output.format_output(view, json_mode=args.json, text_formatter=lambda v: "\n".join(
        f"v{e['version']}  {e['recorded_at']}  {e['actor']}: {e['reason']}" + (
            f"  proposal={e['proposal']}" if "proposal" in e else "")
        for e in v["versions"]) or f"{args.use}: the registry's model and caps, never changed")

def register(commands: Commands) -> None:
    commands.verb("ai-caps", "get",
                  help="each AI use's model, prompt and caps against its spend of the month and calls of the day",
                  func=run_get)
    s = commands.verb("ai-caps", "set",
                      help="change a use's model or caps, with a reason: filed and approved at once, undone by "
                           "retracting it", func=run_set)
    s.add_argument("use", choices=USES, help="the use, or all of them together")
    s.add_argument("--model", help="the model the use runs, one of data/registry/ai.json's")
    s.add_argument("--month-cad", type=float, help="the most model spend a month, in CAD")
    s.add_argument("--day-calls", type=int, help="the most model calls a day")
    s.add_argument("--client-calls", type=int, help="the most calls one client makes a day (Ask)")
    s.add_argument("--reason", required=True, help="why the cap changes, kept with its version")
    s.add_argument("--actor", default="founder", help="who changes it (default: founder)")
    h = commands.verb("ai-caps", "history",
                      help="a use's versions: who changed its model or caps, when, why, and the proposal that did",
                      func=run_history)
    h.add_argument("use", choices=USES, help="the use")
    h.add_argument("--cursor", help="the next page's cursor, from the last page")
