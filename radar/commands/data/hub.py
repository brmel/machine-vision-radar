from __future__ import annotations

import argparse

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands

def run(args: argparse.Namespace) -> int:
    repository = args.wiring.repository()
    product = repository.product(args.slug)
    category = next((c for c in repository.index().categories if product and c.id == product.category), None)
    if product is None or category is None or category.component_hub != args.path or product.hub is None:
        return log.error(f"no hub at /{args.path}/{args.slug}",
                         fix="a hub's path is its category's component_hub in the registry", code=2)
    users = [{"id": u.id, "slug": u.slug, "name": u.name, "vendor_name": u.vendor_name}
             for u in repository.users(product.id)]
    result = {"path": f"/{args.path}/{product.slug}",
              "product": {"id": product.id, "slug": product.slug, "name": product.name}, "users": len(users),
              "cards": users}
    return output.format_output(result, json_mode=args.json, text_formatter=lambda r: "\n".join(
        [f"{product.name}: used by {r['users']}", *(f"  {u['name']} ({u['vendor_name']})" for u in users)]))

def register(commands: Commands) -> None:
    p = commands.verb("hub", "show", help="a component's hub: the products that use it, in name order", func=run)
    p.add_argument("path", help="the hub's path, its category's component_hub in the registry")
    p.add_argument("slug", help="the product's slug")
