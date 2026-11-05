from __future__ import annotations

import argparse

from radar.adapters.console import output
from radar.domain.ports.search.search_engine import SearchRequest
from radar.domain.search.hits import hits_json
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    hits = args.wiring.search_engine().search(SearchRequest(args.query, args.limit, args.semantic, args.category,
                                                            args.tag))
    found = hits_json(hits, args.wiring.model()[1])
    lines = [f"{h['score']:>8}  {h['id']}  {h['name']} ({h['vendor_name']})" for h in found]
    return output.format_output(found, json_mode=args.json, text_formatter=lambda _: "\n".join(lines) or "no matches")

def register(commands: Commands) -> None:
    p = commands.verb("product", "search",
                      help="rank products for a query from the search index (keyword, or hybrid with --semantic)",
                      func=run)
    p.add_argument("query", help="search query")
    p.add_argument("--limit", type=int, default=10, help="max results to return (default 10)")
    p.add_argument("--category", help="search one category's shard only")
    p.add_argument("--tag", help="keep products with this tag")
    p.add_argument("--semantic", action="store_true",
                   help="blend keyword with vector similarity (embeds the query with fastembed)")
