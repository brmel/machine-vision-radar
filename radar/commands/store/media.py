from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from radar.adapters.console import log, output
from radar.domain.model.entities import Document
from radar.domain.ports.store.blob_store import BlobRef
from radar.adapters.console.parser import Commands

def _document(args: argparse.Namespace, sha256: str) -> Document | None:
    return next(iter(args.wiring.held().matching(Document, "sha256", sha256)), None)

def run_put(args: argparse.Namespace) -> int:
    args.wiring.correlate("media")
    path = Path(args.file)
    mime = args.mime or mimetypes.guess_type(path.name)[0] or ""
    if not mime:
        return log.error(f"no mime for {path.name}; pass --mime")
    blobs = args.wiring.blobs()
    ref = blobs.put(path.read_bytes(), mime, args.public)
    return output.format_output({"sha256": ref.sha256, "bytes": path.stat().st_size, "mime": mime,
                                 "storage_path": blobs.path_of(ref)}, json_mode=True)

def run_get(args: argparse.Namespace) -> int:
    args.wiring.correlate("media")
    doc = _document(args, args.sha256)
    if doc is None:
        return log.error(f"no Document has the file {args.sha256}")
    if args.json and not args.out:
        return log.error("media get --json writes the file to --out and prints where", fix="add --out <file>", code=2)
    chunks = args.wiring.blobs().get(BlobRef(args.sha256, doc.mime))
    try:
        if not args.out:
            output.write_bytes(chunks)
            return 0
        with open(args.out, "wb") as target:
            size = sum(target.write(chunk) for chunk in chunks)
    except (OSError, ValueError) as exc:
        return log.error(f"media get {args.sha256}: {exc}")
    return output.format_output({"sha256": args.sha256, "bytes": size, "out": args.out}, args.json,
                                lambda r: f"wrote {r['bytes']} bytes to {r['out']}")

def run_url(args: argparse.Namespace) -> int:
    args.wiring.correlate("media")
    doc = _document(args, args.sha256)
    if doc is None:
        return log.error(f"no Document has the file {args.sha256}")
    public = bool(args.wiring.model()[1].vocabularies["media_rights"][doc.rights].public)
    try:
        url = args.wiring.blobs().url(BlobRef(args.sha256, doc.mime), public)
        output.format_output({"sha256": args.sha256, "url": url}, args.json, lambda r: r["url"])
    except PermissionError as exc:
        return log.error(f"{args.sha256} has {doc.rights} rights: {exc}")
    return 0

def register(commands: Commands) -> None:
    put = commands.verb("media", "put", help="store a file once; prints the fields its Document record needs",
                        func=run_put)
    put.add_argument("file", help="the file to store")
    put.add_argument("--mime", help="the file's mime (default: from its name)")
    put.add_argument("--public", action="store_true", help="the file's rights are public (own, open licence)")
    get = commands.verb("media", "get", help="stream a file, verifying its sha256", func=run_get)
    get.add_argument("sha256", help="the file's sha256")
    get.add_argument("--out", help="write to this file (default: stdout; required with --json)")
    commands.verb("media", "url", help="a public file's URL; a private file has none here", func=run_url).add_argument(
        "sha256", help="the file's sha256")
