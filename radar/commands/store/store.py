from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from radar.adapters.console import log, output
from radar.adapters.files import json_store
from radar.adapters.files.blob_files import kept_files, kept_path
from radar.adapters.firestore import layout, store
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import Change, Document
from radar.domain.model.history.changeset import Changeset, PutEntity, Retract
from radar.domain.model.history.migration import migrated, parse_plan
from radar.domain.model.history.projection import plain
from radar.domain.model.model import ParseError
from radar.domain.model.registry import Registry
from radar.domain.validation.context import Part, Whole
from radar.domain.validation.verdict import Verdict
from radar.adapters.console.parser import Commands

SOURCE = "src_"

def _errors(verdict: Verdict) -> int:
    for e in verdict.errors:
        log.error(str(e))
    return len(verdict.errors)

def _media(catalog: Catalog, registry: Registry, files: Path) -> dict[str, store.Media]:
    public = registry.marked("media_rights", lambda t: t.public)
    return {d.sha256: store.Media(kept_path(files, d.sha256), d.mime, d.rights in public)
            for d in catalog.all(Document)}

def run_load(args: argparse.Namespace) -> int:
    cid, now = args.wiring.correlate("load"), args.wiring.now()
    model = args.wiring.model()
    catalog_dir, files = Path(args.catalog), Path(args.blobs) if args.blobs else None
    catalog = json_store.load_catalog(catalog_dir, model)
    kept = kept_files(files) if files else {}
    if _errors(model.check(catalog, Part(), date.fromisoformat(now[:10]), kept)):
        return log.error("the catalog does not validate: nothing written")
    media = _media(catalog, model.registry, files) if files else {}
    docs, blobs = args.wiring.store(), args.wiring.blobs()
    written = store.load(docs, blobs, model, layout.records_of(catalog, model.schema), media, cid, now)
    log.info(f"load: {sum(written.values())} docs in {len(written)} collections, {len(media)} file(s)")
    return output.format_output({"correlation_id": cid, "docs": written, "blobs": len(media)}, json_mode=True)

def _sourced(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = json.dumps([r for r in records if not str(r["id"]).startswith(SOURCE)])
    cited = set(re.findall(rf'"({SOURCE}[a-z0-9]+)"', text))
    return [r for r in records if not str(r["id"]).startswith(SOURCE) or r["id"] in cited]

def _applied(records: list[dict[str, Any]], changeset: Changeset) -> list[dict[str, Any]]:
    held = {r["id"]: {**r, "version": 1} for r in records}
    for change in changeset.changes:
        match change.action:
            case PutEntity(entity=entity):
                held[entity.id] = {**plain(entity), "version": 1}
            case Retract(id=gone):
                held.pop(gone, None)
    return _sourced(list(held.values()))

def run_rewrite(args: argparse.Namespace) -> int:
    model = args.wiring.model()
    try:
        plan = parse_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")), model)
        catalog = json_store.load_catalog(Path(args.catalog), model)
    except (OSError, ValueError, ParseError) as exc:
        return log.error(f"{exc}", code=2)
    changeset, counts = migrated(catalog, plan, model)
    records = [r for r in layout.records_of(catalog, model.schema)
               if model.schema.kind_of(r["id"]) != Change.__name__]
    written = json_store.write_catalog(Path(args.into), model.schema, _applied(records, changeset))
    return output.format_output({"changes": len(changeset.changes), "counts": dict(counts), "written": written},
                                json_mode=True)

def run_export(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("export")
    schema = args.wiring.model().schema
    counts = json_store.write_catalog(Path(args.catalog), schema, store.scan(args.wiring.store(), schema))
    log.info(f"export: {sum(counts.values())} entities in {len(counts)} file(s) to {args.catalog}")
    return output.format_output({"correlation_id": cid, "counts": counts}, json_mode=True)

def run_validate(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("validate")
    model = args.wiring.model()
    schema = model.schema
    records = list(store.scan(args.wiring.store(), schema))
    log.info(f"validate: {len(records)} entities read")
    verdict = model.check(layout.catalog_of(model, records), Whole(), args.wiring.today())
    counts = dict(sorted(Counter(schema.collection(schema.kind_of(r["id"]) or "") for r in records).items()))
    failed = _errors(verdict)
    if args.json:
        output.format_output({"correlation_id": cid, "ok": verdict.ok, "counts": counts,
                              "errors": [f.report() for f in verdict.errors],
                              "warnings": [f.report() for f in verdict.warnings]}, json_mode=True)
        return 1 if failed else 0
    if failed:
        return log.error(f"{failed} validation error(s) in the store")
    return output.format_output(f"store validation OK: {len(records)} entities "
                                f"({', '.join(f'{n} {kind}' for kind, n in counts.items())})")

def run_replay(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("replay")
    source, target = args.wiring.store(), args.wiring.store(args.into)
    written = store.replay(source, target, args.wiring.model())
    diffs = store.differences(source, target, source.collections())
    for d in diffs:
        log.error(f"replay: {d} differs from the live store")
    output.format_output({"correlation_id": cid, "into": args.into, "written": written, "differences": len(diffs)},
                         json_mode=True)
    return 1 if diffs else 0

def run_reproject(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("reproject")
    written = store.reproject(args.wiring.store(), args.wiring.model())
    log.info(f"reproject: {written} public doc(s) written")
    return output.format_output({"correlation_id": cid, "written": written}, json_mode=True)

def run_backup(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("backup")
    instant = args.wiring.now().replace("-", "").replace(":", "")
    manifest = store.backup(args.wiring.store(), args.wiring.blobs(), instant)
    return output.format_output({"correlation_id": cid, **manifest}, json_mode=True)

def run_restore(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("restore")
    manifest = store.restore(args.wiring.store(args.into), args.wiring.blobs(), args.instant)
    return output.format_output({"correlation_id": cid, "into": args.into, **manifest}, json_mode=True)

def run_purge(args: argparse.Namespace) -> int:
    cid = args.wiring.correlate("purge")
    docs, blobs = args.wiring.store(), args.wiring.blobs()
    found = store.purgeable(docs, blobs, args.wiring.model().schema, args.wiring.index_in_use())
    deleted = store.purge(docs, blobs, found) if args.apply else 0
    report = {"correlation_id": cid, "applied": args.apply, "collections": found.collections,
              "orphans": list(found.orphans), "objects": sorted(found.objects), "bytes": sum(found.objects.values()),
              "deleted": deleted}
    return output.format_output(report, args.json, lambda r: "\n".join(
        [f"{'deleted' if r['applied'] else 'would delete'}: {sum(r['collections'].values())} docs in "
         f"{len(r['collections'])} collection(s)"
         f" {sorted(r['collections'])}, {len(r['orphans'])} orphaned change(s) and version(s), {len(r['objects'])} "
         "object(s) of"
         f" {r['bytes']} bytes", *r["orphans"], *r["objects"]]))

def register(commands: Commands) -> None:
    m = commands.verb("store", "load",
                      help="validate a catalog folder and its files, then load them into an empty store", func=run_load,
                      publishes=True)
    m.add_argument("catalog", help="the catalog folder: one JSON Lines file per entity kind")
    m.add_argument("--blobs", help="the folder of its Documents' files, named by their sha256")
    r = commands.verb("store", "rewrite",
                      help="apply a migration plan to a catalog folder offline and write a clean one: every record at "
                           "version 1, no change history, no source nothing cites, ready for `store load`",
                      func=run_rewrite)
    r.add_argument("plan", help="the plan JSON, as `model migrate` takes it")
    r.add_argument("catalog", help="the catalog folder, from `store export`")
    r.add_argument("into", help="the folder to write")
    e = commands.verb("store", "export", help="write every entity and its Change events as the catalog folder "
                      "`store load` reads", func=run_export)
    e.add_argument("catalog", help="the folder to write: one JSON Lines file per entity kind, others removed")
    commands.verb("store", "validate",
                  help="validate every entity in the store (a paginated full scan), counted per kind",
                  func=run_validate)
    r = commands.verb("store", "replay",
                      help="rebuild the store from its Change events into an empty database and compare",
                      func=run_replay, publishes=True)
    r.add_argument("--into", default="replay", help="the empty database to rebuild into (default: replay)")
    commands.verb("store", "reproject",
                  help="write the public read model again from the store's entities, only the docs that differ",
                  func=run_reproject, publishes=True)
    commands.verb("store", "backup", help="write every collection as JSON Lines to Storage under backups/<instant>/",
                  func=run_backup)
    s = commands.verb("store", "restore", help="rebuild an empty database from a backup", func=run_restore,
                      publishes=True)
    s.add_argument("instant", help="the backup's instant, as `radar store backup` printed it")
    s.add_argument("--into", help="the empty database to restore into (default: the store's own)")
    p = commands.verb("store", "purge",
                      help="list what nothing live reads (collections the code doesn't name; the changes and versions "
                           "of a "
                      "kind the model no longer has; Storage objects but the newest backup, the daily export, the "
                      "current "
                      "index and the media files), and delete it with --apply", func=run_purge)
    p.add_argument("--apply", action="store_true",
                   help="delete what it lists (on the project, with --yes); without it, a dry run")
