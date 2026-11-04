from __future__ import annotations

import argparse
import sys
from typing import Any, Callable, NoReturn

from radar.adapters.console import log

NOUNS = {
    "product": "products: find them, compare them, read one; propose one added, changed or withdrawn",
    "org": "organizations: one, with its owners on a date; propose one added, changed or withdrawn",
    "record": "the records the admin lists by kind, any record's versions, and a rollback to one",
    "catalog": "the catalog as a whole: a cited answer to a question",
    "category": "the category hubs and their products",
    "hub": "component hubs: the products that use a component",
    "proposal": "the review queue: proposed changes the founder approves, edits, rejects or retracts",
    "change": "changesets, applied through the CatalogWriter",
    "media": "media files through the BlobStore, by sha256; propose one added, changed or withdrawn",
    "source": "the catalog's Sources and media Documents, found to cite one rather than propose it again",
    "index": "the search index in the store's bucket",
    "eval": "evaluations on the store's curated queries",
    "ai-caps": "the model and caps of every AI use, their usage and their changes",
    "feed": "the news feed: articles drafted, ordered and published through the review queue",
    "metrics": "the site's anonymous counters and the search KPIs",
    "quality": "catalog quality and coverage",
    "store": "whole-store jobs on Firestore and Storage",
    "model": "the model and the registry in contracts/model/",
    "admin": "the admin's account",
    "agent-token": "the outside agents' tokens: issued with a scope and an expiry, listed, revoked",
    "mcp": "the MCP server for outside agents, over stdio as /api/mcp serves it over HTTP",
    "research": "research runs the founder starts on a scope: the research agent reads the makers' public pages and "
                "files proposals",
    "site": "the site's agent files",
}

JSON_HELP = "emit machine-readable JSON: the result on stdout, log lines and errors on stderr"

class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        log.error(f"{self.prog}: {message}", fix=f"{self.prog} --help", code=2)
        sys.exit(2)

_JSON = Parser(add_help=False)
_JSON.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=JSON_HELP)

class Commands:
    def __init__(self, subparsers: argparse._SubParsersAction) -> None:
        self._verbs = {
            noun: subparsers.add_parser(noun, help=text, description=text).add_subparsers(
                dest="verb", required=True, metavar="<verb>", parser_class=Parser,
                help="what to do; `radar <noun> <verb> --help` lists its arguments")
            for noun, text in NOUNS.items()
        }

    def verb(self, noun: str, name: str, help: str, func: Callable[[argparse.Namespace], int],
             **defaults: Any) -> argparse.ArgumentParser:
        p = self._verbs[noun].add_parser(name, help=help, description=help, parents=[_JSON])
        p.set_defaults(func=func, **defaults)
        return p
