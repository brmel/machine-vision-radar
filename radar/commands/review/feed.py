from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar import paths
from radar.adapters.console import output
from radar.domain.model.history.projection import ROWS, plain
from radar.domain.review.feed.editor import article_of, share_view
from radar.domain.review.proposal import Proposal
from radar.domain.review.requests import Founder, Job
from radar.domain.review.views import proposals_view
from radar.adapters.console.parser import Commands

def _founder(args: argparse.Namespace) -> Founder:
    return Founder(args.actor, args.wiring.correlate("feed"))

def _done(args: argparse.Namespace, proposals: list[Proposal]) -> int:
    return output.format_output(plain(proposals_view(proposals)), json_mode=args.json,
                                text_formatter=lambda v: "\n".join(
                                    f"{p['id']}  {p['status']}  {p['reason']}" for p in v["proposals"]))

def _new(args: argparse.Namespace) -> int:
    return _done(args,
                 [args.wiring.feed().write(article_of(json.loads(Path(args.article).read_text(encoding="utf-8"))),
                                           _founder(args))])

def _edit(args: argparse.Namespace) -> int:
    article = article_of(json.loads(Path(args.article).read_text(encoding="utf-8")))
    return _done(args, [args.wiring.feed().revise(args.id, article, args.note, _founder(args))])

def _reorder(args: argparse.Namespace) -> int:
    return _done(args, args.wiring.feed().reorder(args.id, args.position, _founder(args)))

def _publish(args: argparse.Namespace) -> int:
    return _done(args, [args.wiring.feed().publish(args.note, _founder(args), args.id)])

def _approve(args: argparse.Namespace) -> int:
    return _done(args, args.wiring.feed().publish_templated(args.note, _founder(args)))

def _retract(args: argparse.Namespace) -> int:
    return _done(args, [args.wiring.feed().retract(args.id, args.note, _founder(args))])

def _detect(args: argparse.Namespace) -> int:
    return _done(args, args.wiring.detector().detect(Job(args.actor, args.wiring.correlate("feed-detect"))))

def _draft(args: argparse.Namespace) -> int:
    return _done(args, [args.wiring.drafter().draft(args.id, args.wiring.correlate("feed-draft"))])

def _list(args: argparse.Namespace) -> int:
    code = args.wiring.model().registry.default_language.code
    return output.format_output(args.wiring.feed().desk(args.cursor), json_mode=args.json,
                                text_formatter=lambda v: output.paged(plain(v), [
*(f"draft {r.position:>3}  {r.slug}  {r.title[code]}" for r in v.drafts),
*(f"{r.published_at}  {r.slug}  {r.title[code]}" for r in v.published)]))

def _show(args: argparse.Namespace) -> int:
    return output.format_output(args.wiring.feed().row(args.id), json_mode=True)

def _share(args: argparse.Namespace) -> int:
    view = share_view(args.wiring.feed().item(args.id),
                      args.locale or args.wiring.model().registry.default_language.code, paths.site_origin())
    return output.format_output(view, json_mode=args.json, text_formatter=lambda v: v["text"])

def _acted(p: argparse.ArgumentParser, note: bool = True) -> argparse.ArgumentParser:
    if note:
        p.add_argument("--note", required=True, help="why: kept with the decision or the version")
    p.add_argument("--actor", default="founder", help="who acts (default: founder)")
    return p

def register(commands: Commands) -> None:
    new = _acted(commands.verb("feed", "new", func=_new,
                               help="file a new article as a draft at the end of the publishing order, from its JSON "
                                    "{title, summary, body: [{text, cites}]}"), note=False)
    new.add_argument("article", help="the article's JSON file")
    edit = _acted(commands.verb("feed", "edit", func=_edit,
                                help="a draft's new text, or a published article's next version, approved at once, "
                                     "from its JSON"))
    edit.add_argument("id", help="the article's id or slug")
    edit.add_argument("article", help="the article's JSON file")
    reorder = _acted(commands.verb("feed", "reorder", func=_reorder,
                                   help="move a draft to a place in the publishing order (1 is next)"), note=False)
    reorder.add_argument("id", help="the draft's id or slug")
    reorder.add_argument("position", type=int, help="the place it moves to")
    detect = commands.verb("feed", "detect", func=_detect,
                           help="the significant changes since the last run as templated drafts (feed.json); the first "
                                "run drafts the launch digest")
    detect.add_argument("--actor", default="feed detector", help="who drafts (default: feed detector)")
    draft = commands.verb("feed", "draft", func=_draft,
                          help="an article about a product or an organization, written by the article model from its "
                               "record only, "
                          "under the draft cap: a draft at the end of the publishing order")
    draft.add_argument("id", help="the product's or organization's id or slug")
    draft.add_argument("--ai", action="store_true", required=True,
                       help="the article model writes it (the draft use's model, with --yes)")
    commands.verb("feed", "list", func=_list,
                  help=f"the drafts in publishing order, and the published articles, newest first, {ROWS} a "
                       "page").add_argument(
"--cursor", help="the `next` of the previous page of published articles")
    commands.verb("feed", "show", func=_show,
                  help="one draft or published article, as the desk lists it").add_argument(
                      "id", help="the article's id or slug")
    publish = _acted(commands.verb("feed", "publish", func=_publish,
                                   help="publish the next draft (or the one named): the founder's approval, which "
                                        "dates it"))
    publish.add_argument("id", nargs="?", help="the draft to publish (default: the next one)")
    approve = _acted(commands.verb("feed", "approve", func=_approve,
                                   help="publish every templated draft under one note: the batch's one approval"))
    approve.add_argument("--all-proposed", action="store_true", required=True,
                         help="every templated draft waiting in the queue")
    retract = _acted(commands.verb("feed", "retract", func=_retract,
                                   help="withdraw a published article: its approval is retracted, its history kept"))
    retract.add_argument("id", help="the article's id or slug")
    share = commands.verb("feed", "share-text", func=_share,
                          help="the post to copy to share a published article by hand: title, summary and address")
    share.add_argument("id", help="the article's id or slug")
    share.add_argument("--locale",
                       help="the language of the post (default: contracts/languages.json's default language)")
