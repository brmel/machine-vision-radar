from __future__ import annotations

import argparse

from radar.build.codegen import check, generate
from radar.adapters.console import output
from radar.adapters.console.parser import Commands
from radar.domain.model.history.projection import plain
from radar.domain.review.views import admin_model

def run(args: argparse.Namespace) -> int:
    return check(as_json=args.json) if args.check else generate(as_json=args.json)

def run_show(args: argparse.Namespace) -> int:
    return output.format_output(plain(admin_model(args.wiring.model())), json_mode=True)

def register(commands: Commands) -> None:
    p = commands.verb("model", "generate", help="regenerate Python, TypeScript and Zod types from contracts/model/",
                      func=run)
    p.add_argument("--check", action="store_true",
                   help="verify the generated files and the contracts' layout are up to date; write nothing")
    commands.verb("model", "show", help="every kind's fields, references and labels, as the admin's forms read them",
                  func=run_show)
