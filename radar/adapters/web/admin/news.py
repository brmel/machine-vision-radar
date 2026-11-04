from __future__ import annotations

from typing import Callable, Mapping

from radar.adapters.web.admin.endpoint import Body, cursor, text, whole
from radar.domain.ports.web.endpoint import Response
from radar.domain.review.requests import Founder
from radar.domain.review.feed.drafter import Drafter
from radar.domain.review.feed.editor import Feed, article_of, share_view
from radar.domain.model.history.projection import plain
from radar.adapters.files.model_json import DEFAULT_LANGUAGE
from radar.domain.review.views import proposal_view, proposals_view

class NewsAdmin:
    def __init__(self, feed: Callable[[], Feed], drafter: Callable[[], Drafter], origin: str) -> None:
        self._feed, self._drafter, self._origin = feed, drafter, origin

    def route(self, method: str, parts: tuple[str, ...], query: Mapping[str, str], body: Body,
              by: Founder) -> Response | None:
        feed = self._feed()
        match (method, *parts):
            case ("GET",):
                return Response(200, plain(feed.desk(cursor(query))))
            case ("GET", item):
                return Response(200, plain(feed.row(item)))
            case ("GET", item, "share"):
                return Response(200,
                                share_view(feed.item(item), query.get("locale") or DEFAULT_LANGUAGE.code, self._origin))
            case ("POST",):
                return Response(201, plain(proposal_view(feed.write(article_of(body.get("article")), by))))
            case ("POST", "publish"):
                return Response(200, plain(proposal_view(feed.publish(text(body, "note"), by))))
            case ("POST", "approve"):
                return Response(200, plain(proposals_view(feed.publish_templated(text(body, "note"), by))))
            case ("POST", "draft"):
                return Response(201, plain(proposal_view(self._drafter().draft(text(body, "item"), by.correlation_id))))
        return self._item_route(feed, method, parts, body, by)

    def _item_route(self, feed: Feed, method: str, parts: tuple[str, ...], body: Body, by: Founder) -> Response | None:
        match (method, *parts):
            case ("POST", item, "edit"):
                return Response(200,
                                plain(proposal_view(feed.revise(item, article_of(body.get("article")),
                                                                text(body, "note"), by))))
            case ("POST", item, "move"):
                return Response(200,
                                plain(proposals_view(feed.reorder(item, whole(body.get("position"), "position"), by))))
            case ("POST", item, "retract"):
                return Response(200, plain(proposal_view(feed.retract(item, text(body, "note"), by))))
        return None
