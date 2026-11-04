from __future__ import annotations

import argparse

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.model.entities import IndexStatus

def run(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate(f"index-{args.action}")
    built = args.wiring.indexer().run(args.action, args.actor, cid)
    text = (f"index {built.version}: {built.products} products, {len(built.embedded)} embedded, {len(built.removed)} "
            "removed")
    log.info(text)
    result = {"correlation_id": cid, "version": built.version, "products": built.products,
              "embedded": list(built.embedded), "removed": list(built.removed)}
    return output.format_output(result, json_mode=args.json, text_formatter=lambda _: text)

def _status_text(view: IndexStatus) -> str:
    runs = [f"  {r.at}  {r.action:<7}  {r.actor}: {r.version or 'failed: ' + (r.error or '')}" for r in view.runs]
    head = (f"index {view.version}: {view.products_indexed} of {view.products_in_catalog} products, "
            f"{view.embedder.model_id}"
            if view.embedder else f"no index; {view.products_in_catalog} products in the catalog")
    return "\n".join([head, *runs])

def run_status(args: argparse.Namespace) -> int:
    return output.format_output(args.wiring.indexer().status(), json_mode=args.json, text_formatter=_status_text)

def run_settings(args: argparse.Namespace) -> int:
    return output.format_output(args.wiring.indexer().settings(), json_mode=True)

def register(commands: Commands) -> None:
    for action, text in (("rebuild", "embed every product into a new search index on the registry's model (fastembed)"),
                         ("update", "embed only the changed products and drop the removed ones")):
        commands.verb("index", action, help=text, func=run, action=action).add_argument(
            "--actor", default="founder", help="who runs it (default: founder)")
    commands.verb("index", "status",
                  help="the current index against the catalog: its model and products, and its last runs",
                  func=run_status)
    commands.verb("index", "settings", help="the registry's search settings beside the model the index was built with",
                  func=run_settings)
