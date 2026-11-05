from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import replace
from pathlib import Path
from typing import Any

from radar.adapters.console import log, output
from radar.adapters.console.parser import Commands
from radar.domain.model.entities import ActorKind, FilesOn, ProposalStatus, Source
from radar.domain.ports.catalog.held_records import HeldRecords
from radar.domain.model.history.projection import ROWS, plain
from radar.domain.model.changeset import Change, Changeset, PutEntity, parse_changeset
from radar.domain.ports.review.proposal_queue import Query
from radar.domain.review.proposal import Outcome, Shown
from radar.domain.review.requests import (Approval, Bundled, Changes, Founder, Picked, Rejection, Retraction, Revision,
                                          Withdrawal, draft_of)
from radar.domain.review.views import bundle_view, outcome_view, page_view, shown_view

def _founder(args: argparse.Namespace) -> Founder:
    return Founder(args.actor, args.wiring.correlate("proposal"))

def _reading(args: argparse.Namespace) -> Founder:
    return Founder("founder", args.wiring.correlate("proposal"))

def _read(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _line(view: dict[str, Any]) -> str:
    return (f"{view['id']}  {view['status']:<9}  {view['files_on']:<8}  {view['author']}: "
            f"{view.get('reason') or view.get('message', '')}")

def show(args: argparse.Namespace, shown: Shown) -> int:
    view = plain(shown_view(shown))
    lines = [_line(view),
             *(f"  {c['entity']}: {c.get('before', '(new)')} -> {c.get('after', '(withdrawn)')}"
               for c in view.get("changes", []))]
    return output.format_output(view, json_mode=args.json,
                                text_formatter=lambda _: "\n".join(
                                    lines + ([f"  problem: {view['problem']}"] if "problem" in view else [])))

def run_submit(args: argparse.Namespace) -> int:
    return show(args, args.wiring.review().submit(draft_of(_read(args.draft)), _founder(args)))

def run_list(args: argparse.Namespace) -> int:
    query = Query(args.status, args.files_on, args.actor_kind, args.author, args.bundle)
    view = plain(page_view(args.wiring.review().queue(query, _reading(args), args.cursor)))
    return output.format_output(view, json_mode=args.json,
                                text_formatter=lambda v: output.paged(v, map(_line, v["proposals"])))

def run_show(args: argparse.Namespace) -> int:
    return show(args, args.wiring.review().proposal(args.id, _reading(args)))

def run_bundle(args: argparse.Namespace) -> int:
    view = plain(bundle_view(args.id, args.wiring.review().bundle(args.id, _reading(args))))
    return output.format_output(view, json_mode=args.json, text_formatter=lambda v: "\n".join(
        f"{_line(m['proposal'])}{'  ' + m['risk'] if 'risk' in m else ''}"
        f"{'  after ' + ', '.join(m['after']) if m['after'] else ''}" for m in v["members"]))

def _decided(args: argparse.Namespace, outcome: Outcome, founder: Founder) -> int:
    output.format_output(plain(outcome_view(outcome)), json_mode=args.json, text_formatter=lambda v: "\n".join(
        [*map(_line, v["done"]), *(f"refused {r['proposal']['id']}: {'; '.join(r['findings'])}" for r in v["refused"]),
         *(f"held {h['proposal']['id']}: waits on {', '.join(h['waits_on'])}" for h in v["held"])]))
    reindexed = not outcome.changed or args.wiring.reindex(founder.name, founder.correlation_id)
    return 0 if reindexed and not outcome.refused else 1

def run_edit(args: argparse.Namespace) -> int:
    founder = _founder(args)
    return _decided(args,
                    args.wiring.review().decide(Revision(args.id, parse_changeset(_read(args.changeset)), args.note),
                                                founder), founder)

def run_decide(args: argparse.Namespace) -> int:
    if bool(args.ids) == bool(args.bundle):
        return log.error("name the proposals or --bundle, not both", fix=f"radar proposal {args.verb} <id>… --note …",
                         code=2)
    founder, target = _founder(args), Bundled(args.bundle) if args.bundle else Picked(tuple(args.ids))
    decision = {"approve": Approval, "reject": Rejection, "retract": Retraction}[args.verb](target, args.note)
    return _decided(args, args.wiring.review().decide(decision, founder), founder)

def run_log(args: argparse.Namespace) -> int:
    view = plain(args.wiring.review().log(_reading(args), args.actor_filter, args.cursor))
    return output.format_output(view, json_mode=args.json, text_formatter=lambda v: output.paged(
        v,
        (f"{e['at']}  {e['action']:<7}  {e['proposal']}  {e['actor']}{': ' + e['note'] if 'note' in e else ''}"
         for e in v["entries"])))

NOUNS = {"product": "Product", "org": "Organization", "media": "Document"}

def _file(args: argparse.Namespace, files_on: FilesOn, changeset: Changeset, subject: str) -> int:
    return show(args, args.wiring.review().submit(Changes(files_on, args.reason, subject, changeset), _founder(args)))

def _thumbnail_sources(args: argparse.Namespace, held: HeldRecords) -> tuple[str, ...]:
    if args.source or not args.thumbnail:
        return tuple(args.source or ())
    return tuple(s.id for s in held.matching(Source, "document", args.thumbnail))

def _product_thumbnail_edit(args: argparse.Namespace) -> int:
    held = args.wiring.held()
    found = held.held(args.changeset)
    if found is None:
        return log.error(f"no product '{args.changeset}'")
    updated = dict(found)
    if args.thumbnail:
        updated["thumbnail"] = args.thumbnail
    else:
        updated.pop("thumbnail", None)
    sources = _thumbnail_sources(args, held)
    if not sources:
        return log.error(f"no Source cites '{args.thumbnail}': the change needs one", fix="pass --source <src_id>",
                         code=2)
    change = Change(PutEntity(updated), args.reason, "human", args.actor, sources)
    return _file(args, FilesOn.UPDATE, Changeset((change,)), args.changeset)

def run_put(args: argparse.Namespace) -> int:
    if args.cmd == "product" and getattr(args, "thumbnail", None) is not None:
        return _product_thumbnail_edit(args)
    read = parse_changeset(_read(args.changeset))
    changeset = Changeset(tuple(c if c.source_refs else replace(c, source_refs=tuple(args.source or ()))
                                for c in read.changes))
    return _file(args, FilesOn.CREATE if args.verb == "add" else FilesOn.UPDATE, changeset,
                 changeset.subject(args.wiring.model()[0].types[NOUNS[args.cmd]]))

def run_retract(args: argparse.Namespace) -> int:
    return show(args, args.wiring.review().submit(Withdrawal(args.id, args.reason), _founder(args)))

def run_media_add(args: argparse.Namespace) -> int:
    mime = args.mime or mimetypes.guess_type(args.file)[0] or "application/octet-stream"
    stored = args.wiring.records().upload(Path(args.file).read_bytes(), mime)
    document = {**_read(args.document), "sha256": stored.sha256, "mime": stored.mime, "bytes": stored.bytes}
    change = Change(PutEntity(document), args.reason, "human", args.actor, tuple(args.source or ()))
    return _file(args, FilesOn.CREATE, Changeset((change,)), str(document.get("id", "")))

def _editing(commands: Commands) -> None:
    def verb(noun: str, name: str, text: str, func: Any) -> argparse.ArgumentParser:
        p = commands.verb(noun, name, help=text, func=func)
        p.add_argument("--reason", required=True, help="why (required)")
        p.add_argument("--actor", default="founder", help="who proposes (default: founder)")
        if name != "retract":
            p.add_argument("--source", action="append", help="a source id the change cites (repeat for several)")
        return p

    for noun, kind in NOUNS.items():
        for name in ("add", "edit") if noun != "media" else ("edit",):
            text = (f"file a proposal that {'adds' if name == 'add' else 'changes'} a {kind} and its records from a "
                    "changeset JSON file")
            p = verb(noun, name, text, run_put)
            thumbnail = " or product id when using --thumbnail" if noun == "product" and name == "edit" else ""
            p.add_argument("changeset", help=f"path to the changeset JSON{thumbnail}")
            if noun == "product" and name == "edit":
                p.add_argument("--thumbnail",
                               help="set the product's thumbnail document id (or empty string to remove)")
        verb(noun, "retract",
             f"file a proposal that withdraws a {kind} and lets go of it where other records name it; its history "
             "stays", run_retract).add_argument("id", help="the record id")
    p = verb("media", "add", "put a file into the BlobStore and file a proposal that adds its Document", run_media_add)
    p.add_argument("file", help="the file")
    p.add_argument("document",
                   help="path to the Document JSON (id, kind, subjects, rights, fetched_at…); the file fills sha256, "
                        "mime, bytes")
    p.add_argument("--mime", help="the file's media type (default: from its name)")

def register(commands: Commands) -> None:
    def acting(p: argparse.ArgumentParser) -> None:
        p.add_argument("--actor", default="founder", help="who acts (default: founder)")

    p = commands.verb("proposal", "submit",
                      help="file a proposal from a draft JSON file (files_on, reason, subject, changeset); it waits "
                           "for approval", func=run_submit)
    p.add_argument("draft", help="path to the draft JSON")
    acting(p)
    p = commands.verb("proposal", "list", help=f"the review queue, newest first, filtered, {ROWS} a page",
                      func=run_list)
    p.add_argument("--status", type=ProposalStatus, choices=[e.value for e in ProposalStatus],
                   help="only proposals in this status")
    p.add_argument("--files-on", type=FilesOn, choices=[e.value for e in FilesOn],
                   help="only proposals filed on this event (each is a proposal_kinds term)")
    p.add_argument("--actor-kind", type=ActorKind, choices=[e.value for e in ActorKind],
                   help="only proposals from this kind of actor")
    p.add_argument("--author", help="only proposals by this author (a named agent, say)")
    p.add_argument("--bundle", help="only the proposals of this research run's bundle")
    p.add_argument("--cursor", help="the `next` of the previous page")
    commands.verb("proposal", "show", help="one proposal with what it changes", func=run_show).add_argument(
        "id", help="the proposal id")
    p = commands.verb("proposal", "bundle",
                      help="a research run's proposals in dependency order, the riskiest first where it leaves a "
                           "choice", func=run_bundle)
    p.add_argument("id", help="the run's id")
    p = commands.verb("proposal", "edit",
                      help="replace a suggested proposal's change with a changeset JSON file, validated again",
                      func=run_edit)
    p.add_argument("id", help="the proposal id")
    p.add_argument("changeset", help="path to the changeset JSON")
    p.add_argument("--note", required=True, help="why (required)")
    acting(p)
    for name, text in (("approve",
                                   "approve proposals, or a bundle, under one note: each applied on its own in "
                                   "dependency order; one refused or "
                                   "waiting on one not approved waits"),
                       ("reject", "reject suggested proposals, or a bundle's: nothing changes"),
                       ("retract",
                        "retract approved proposals, or a bundle's: what each changed goes back, as new versions")):
        p = commands.verb("proposal", name, help=text, func=run_decide)
        p.add_argument("ids", nargs="*", help="the proposal ids")
        p.add_argument("--bundle", help="a research run's id: its whole bundle")
        p.add_argument("--note", required=True, help="why (required)")
        acting(p)
    p = commands.verb("proposal", "log", help=f"the audit log, newest first, {ROWS} a page", func=run_log)
    p.add_argument("--actor", dest="actor_filter", help="only this actor's entries")
    p.add_argument("--cursor", help="the `next` of the previous page")
    _editing(commands)
