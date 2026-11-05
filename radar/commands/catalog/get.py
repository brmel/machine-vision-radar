from __future__ import annotations

import argparse
import datetime
from typing import Any

from radar.adapters.console import log, output
from radar.domain.model.history.projection import plain
from radar.domain.read_model.derived.ownership import OwnershipHistory
from radar.domain.read_model.products.views import product_sheet
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import OrgRelation, Organization
from radar.domain.model.registry import Registry
from radar.adapters.console.parser import Commands

def _organization(catalog: Catalog, registry: Registry, key: str, on: datetime.date) -> dict[str, Any] | None:
    orgs = {o.id: o for o in catalog.all(Organization)}
    org = next((o for o in orgs.values() if key in (o.id, o.slug)), None)
    if org is None:
        return None
    history = OwnershipHistory(catalog, registry)
    brief = lambda oid: {"id": oid, "slug": orgs[oid].slug, "name": orgs[oid].name}
    return {**brief(org.id), "on": on.isoformat(), "named": brief(history.name_on(org.id, on)),
            "owners": [brief(o) for o in history.owners_on(org.id, on)]}

def run_product(args: argparse.Namespace) -> int:
    try:
        sheet = product_sheet(args.wiring.repository(), args.id)
    except LookupError as exc:
        return log.error(str(exc), fix="radar product search <words> finds one")
    return output.format_output(plain(sheet), json_mode=True)

def run_org(args: argparse.Namespace) -> int:
    try:
        day = datetime.date.fromisoformat(args.on) if args.on else args.wiring.today()
    except ValueError:
        return log.error(f"--on wants a date as YYYY-MM-DD, got '{args.on}'", code=2)
    org = _organization(args.wiring.catalog((Organization.__name__, OrgRelation.__name__)),
                        args.wiring.model().registry, args.id, day)
    if org is None:
        return log.error(f"no organization '{args.id}'")
    return output.format_output(org, json_mode=True)

def register(commands: Commands) -> None:
    p = commands.verb("product", "get",
                      help="a product as its page shows it, with its rows' spec labels and units, as JSON",
                      func=run_product)
    p.add_argument("id", help="the product's id or slug")
    o = commands.verb("org", "get", help="an organization, its name and its chain of owners on a date, as JSON",
                      func=run_org)
    o.add_argument("id", help="the organization's id or slug")
    o.add_argument("--on", help="the date (YYYY-MM-DD) to name its owners on (default today)")
