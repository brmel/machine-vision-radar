from __future__ import annotations

import argparse

from radar.adapters.console import output
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    uid = args.wiring.identity().grant(args.email)
    return output.format_output({"email": args.email, "uid": uid}, json_mode=args.json,
                         text_formatter=lambda v: f"{v['email']} ({v['uid']}) is the admin: sign in again at /admin")

def register(commands: Commands) -> None:
    p = commands.verb("admin", "grant", help="set the admin claim on the account that signs in with this email",
                      func=run)
    p.add_argument("email", help="the founder's sign-in email")
