from __future__ import annotations

import argparse

from radar.adapters.console import log, output
from radar.domain.model.entities import Document
from radar.domain.ports.store.blob_store import BlobRef
from radar.adapters.console.parser import Commands

def _document(args: argparse.Namespace, sha256: str) -> Document | None:
    return next(iter(args.wiring.held().matching(Document, "sha256", sha256)), None)

def run_get(args: argparse.Namespace) -> int:
    args.wiring.correlate("media")
    doc = _document(args, args.sha256)
    if doc is None:
        return log.error(f"no Document has the file {args.sha256}")
    if args.json and not args.out:
        return log.error("media get --json writes the file to --out and prints where", fix="add --out <file>", code=2)
    chunks = args.wiring.blobs().get(BlobRef(args.sha256, doc.mime))
    if not args.out:
        output.write_bytes(chunks)
        return 0
    with open(args.out, "wb") as target:
        size = sum(target.write(chunk) for chunk in chunks)
    return output.format_output({"sha256": args.sha256, "bytes": size, "out": args.out}, args.json,
                                lambda r: f"wrote {r['bytes']} bytes to {r['out']}")

def run_url(args: argparse.Namespace) -> int:
    args.wiring.correlate("media")
    doc = _document(args, args.sha256)
    if doc is None:
        return log.error(f"no Document has the file {args.sha256}")
    public = bool(args.wiring.model().registry.vocabularies["media_rights"][doc.rights].public)
    url = args.wiring.blobs().url(BlobRef(args.sha256, doc.mime), public)
    return output.format_output({"sha256": args.sha256, "url": url}, args.json, lambda r: r["url"])

def register(commands: Commands) -> None:
    get = commands.verb("media", "get", help="stream a file, verifying its sha256", func=run_get)
    get.add_argument("sha256", help="the file's sha256")
    get.add_argument("--out", help="write to this file (default: stdout; required with --json)")
    commands.verb("media", "url", help="a public file's URL; a private file has none here", func=run_url).add_argument(
        "sha256", help="the file's sha256")
