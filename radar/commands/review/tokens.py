from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from radar.adapters.console import output
from radar.adapters.console.parser import Commands
from radar.domain.model.entities import IssuedToken
from radar.domain.model.history.projection import ROWS, plain
from radar.domain.review.agents.tokens import Limits, Scope, issue, token_view, tokens_view

DEFAULT = Limits()

def _line(view: dict[str, Any]) -> str:
    return f"{view['id']}  {view['status']:<7}  {view['scope']:<7}  until {view['expires']}  {view['name']}"

def run_create(args: argparse.Namespace) -> int:
    token, secret = issue(args.name, Scope(args.scope), args.expires,
                          Limits(args.requests_per_minute, args.proposals_per_day), args.wiring.now())
    args.wiring.agent_tokens().issue(token)
    view = plain(IssuedToken(agent=token_view(token, args.wiring.today()), token=secret))
    return output.format_output(view, json_mode=args.json, text_formatter=lambda v: (
        f"{_line(v['agent'])}\n{v['token']}\nshown this once: give it to the agent now"))

def run_list(args: argparse.Namespace) -> int:
    tokens, after, total = args.wiring.agent_tokens().page(args.cursor)
    return output.format_output(plain(tokens_view(tokens, args.wiring.today(), after, total)), json_mode=args.json,
                                text_formatter=lambda v: output.paged(v, map(_line, v["tokens"])))

def run_revoke(args: argparse.Namespace) -> int:
    view = plain(token_view(args.wiring.agent_tokens().revoke(args.id, args.wiring.now()), args.wiring.today()))
    return output.format_output(view, json_mode=args.json, text_formatter=_line)

def register(commands: Commands) -> None:
    c = commands.verb("agent-token", "create",
                      help="issue a named token to an outside agent: printed this once, only its digest kept",
                      func=run_create)
    c.add_argument("name",
                   help="the agent's name, kept with what it proposes: every token issued under it sees those "
                        "proposals")
    c.add_argument("--scope", required=True, choices=[s.value for s in Scope],
                   help="read, or propose (which also reads)")
    c.add_argument("--expires", required=True, type=date.fromisoformat,
                   help="the day it stops working, YYYY-MM-DD, after today")
    c.add_argument("--requests-per-minute", type=int, default=DEFAULT.requests_per_minute,
                   help=f"the calls it may make a minute (default {DEFAULT.requests_per_minute})")
    c.add_argument("--proposals-per-day", type=int, default=DEFAULT.proposals_per_day,
                   help=f"the proposals it may file a day (default {DEFAULT.proposals_per_day})")
    li = commands.verb("agent-token", "list",
                       help=f"the agent tokens, newest first, {ROWS} a page, each with its scope, expiry, limits and "
                            "status; "
                       "never the token", func=run_list)
    li.add_argument("--cursor", help="the `next` of the previous page")
    r = commands.verb("agent-token", "revoke", help="revoke an agent token: every later call with it is refused",
                      func=run_revoke)
    r.add_argument("id", help="the token's id (agt_…), from `agent-token list`")
