from __future__ import annotations

import argparse

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.read_model.listings import comparison

def run(args: argparse.Namespace) -> int:
    if len(args.ids) < 2:
        return log.error("compare requires at least 2 product ids")

    repository = args.wiring.repository()
    index = repository.index()
    found = {i: repository.product(i) for i in args.ids}

    missing = [i for i, v in found.items() if v is None]
    if missing:
        return log.error(f"unknown product id(s): {', '.join(missing)}")

    return output.format_output(comparison(index, [v for v in found.values() if v is not None]), json_mode=True)

def register(commands: Commands) -> None:
    p = commands.verb("product", "compare", help="side-by-side spec comparison of 2+ products", func=run)
    p.add_argument("ids", nargs="+", help="product ids or slugs to compare")
