from __future__ import annotations

import argparse
import os
import sys
import traceback
from typing import Sequence

from .adapters.console import log
from .adapters.wiring.root import Wiring
from .adapters.wiring.stores import NoStore, RegistryDrift
from .domain.ports.search.search_engine import IndexMismatch, NoIndex
from .commands.catalog import ask, compare, evaluation, get, history, search, sources
from .commands.data import category, hub, metrics, quality, validate
from .commands.build import export, gen_model, index
from .commands.store import change, media, store
from .commands.review import admin, caps, feed, mcp, proposals, research, tokens
from .adapters.console.parser import JSON_HELP, Commands, Parser

def build_parser() -> argparse.ArgumentParser:
    ap = Parser(prog="radar",
                description="Machine Vision Radar — All machine vision knowledge, in one place. `radar <noun> <verb>`: "
                            "the catalog and pipeline CLI.")
    ap.add_argument("--verbose", "-v", action="store_true", help="enable verbose diagnostic logging to stderr")
    ap.add_argument("--quiet", "-q", action="store_true", help="suppress info logs; errors only")
    ap.add_argument("--json", action="store_true", help=JSON_HELP)
    ap.add_argument("--project", default=os.environ.get("MVR_PROJECT"),
                    help="the Firebase project's store (.firebaserc's; default MVR_PROJECT), with the token in "
                         "MVR_ACCESS_TOKEN")
    ap.add_argument("--yes", action="store_true",
                    help="let a command write to --project's store, refused while the registry here differs from the "
                         "one the store's site serves")

    commands = Commands(ap.add_subparsers(dest="cmd", required=True, metavar="<noun>", parser_class=Parser,
                                          help="what the command acts on; `radar <noun> --help` lists its verbs"))
    for mod in (admin, ask, caps, category, change, compare, evaluation, feed, export, gen_model, get, history, hub,
                index, mcp, media, metrics, proposals, quality, research, search, sources, store, tokens, validate):
        mod.register(commands)
    return ap

def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    log.configure(json_mode="--json" in argv)
    args = build_parser().parse_args(argv)
    log.configure(verbose=args.verbose, quiet=args.quiet, json_mode=args.json)

    args.wiring = Wiring(args.project, args.yes)
    try:
        if args.yes and not args.publishes:
            args.wiring.match_registry()
        return int(args.func(args) or 0)
    except (NoStore, NoIndex, IndexMismatch) as exc:
        return log.error(str(exc), code=2)
    except RegistryDrift as exc:
        return log.error(str(exc), fix="run from the deployed commit, or deploy first")
    except Exception as exc:
        log.debug(traceback.format_exc())
        return log.error(f"radar {args.cmd} {args.verb} failed: {exc}")
