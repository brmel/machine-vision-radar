from __future__ import annotations

import argparse
from typing import Any

from radar.adapters.console import log, output
from radar.domain.model.entities import ProductCard
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.adapters.console.parser import Commands

def _cards(repository: CatalogRepository, category: str) -> list[ProductCard]:
    cards: list[ProductCard] = []
    cursor = None
    while page := repository.category_page(category, cursor):
        cards += page.products
        cursor = page.next
        if cursor is None:
            break
    return cards

def run(args: argparse.Namespace) -> int:
    repository = args.wiring.repository()
    categories = {c.id: c for c in repository.index().categories if c.products > 0}
    if args.action == "list":
        result: Any = [{"id": c.id, "label": dict(c.label), "products": c.products, "path": f"/category/{c.id}"}
                       for c in categories.values()]
        lines = [f"{c['products']:>6}  {c['id']}" for c in result]
    elif args.id in categories:
        c = categories[args.id]
        cards = [{"id": p.id, "slug": p.slug, "name": p.name, "vendor_name": p.vendor_name}
                 for p in _cards(repository, c.id)]
        result = {"id": c.id, "label": dict(c.label), "description": dict(c.description), "products": c.products,
                  "path": f"/category/{c.id}", "cards": cards}
        lines = [f"{c.id}: {c.products} products", *(f"  {p['name']} ({p['vendor_name']})" for p in cards)]
    else:
        return log.error(f"no category with products named '{args.id}'", fix="radar category list", code=2)
    return output.format_output(result, json_mode=args.json, text_formatter=lambda _: "\n".join(lines))

def register(commands: Commands) -> None:
    commands.verb("category", "list", help="every category hub with products, and its count", func=run, action="list",
                  id=None)
    commands.verb("category", "show", help="one category's products in name order", func=run,
                  action="show").add_argument("id", help="the category id")
