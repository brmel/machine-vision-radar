from __future__ import annotations

import argparse
from pathlib import Path

from radar import paths
from radar.adapters.console import output
from radar.build.llms import write_llms
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else paths.DIST
    products = write_llms(args.wiring.repository(), out, args.wiring.model().registry.default_language.code)
    return output.format_output({"products": products}, args.json,
                                lambda r: f"wrote llms.txt and llms-full.txt for {r['products']} products to {out}")

def register(commands: Commands) -> None:
    p = commands.verb("site", "export", help="write llms.txt and llms-full.txt from the store's read model", func=run)
    p.add_argument("--out", help="the folder to write them to (default: dist/)")
