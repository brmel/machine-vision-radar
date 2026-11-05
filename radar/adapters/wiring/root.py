from __future__ import annotations

import os

from radar import paths
from radar.adapters.firestore.layout import catalog_of, record_of
from radar.adapters.firestore.repository import StoreChangeLog, StoreFeedReads
from radar.adapters.web.admin.agents import AgentsAdmin
from radar.adapters.web.admin.endpoint import AdminEndpoint
from radar.adapters.web.admin.news import NewsAdmin
from radar.adapters.web.admin.research import ResearchAdmin
from radar.adapters.web.admin.search import SearchAdmin
from radar.adapters.web.api import Api, AskEndpoint, FindEndpoint, ReportEndpoint
from radar.adapters.web.app_check import AppCheck, Unchecked
from radar.adapters.web.mcp import McpServer, proposal_tools, read_tools
from radar.adapters.web.pages import PoliteFetcher
from radar.adapters.wiring.models import Models
from radar.domain.ai.quota import Quota
from radar.domain.model.entities import FeedItem
from radar.domain.ports.web.attestation import Attestation
from radar.domain.read_model.history import Histories
from radar.domain.review.agents.files import Files
from radar.domain.review.agents.research.run import Researcher
from radar.domain.review.feed.detector import Detector
from radar.domain.review.feed.drafter import Drafter
from radar.domain.review.feed.editor import Feed
from radar.domain.review.requests import Job
from radar.domain.review.review import Review
from radar.domain.review.views import admin_model
from radar.domain.search.sources import KINDS

class Wiring(Models):
    def api(self) -> Api:
        engine, ledger = self.search_engine(), self.ask_ledger()
        quota = Quota(ledger, self.ask_meter(engine), engine, os.environ.get("K_REVISION", ""))
        return Api(AskEndpoint(quota, ledger, correlate=self.correlate), self.admin_endpoint(), self.mcp(),
                   ReportEndpoint(self.review(), self.attestation(), self.correlate),
                   FindEndpoint(engine, self.correlate))

    def attestation(self) -> Attestation:
        if self._real:
            return AppCheck(self._real, self._token())
        self._demo()
        return Unchecked()

    def mcp(self) -> McpServer:
        schema, registry = self.model()
        tools = {**read_tools(self.search_engine, self.repository(), lambda: self.catalog(schema, KINDS), registry),
                 **proposal_tools(self.review())}
        return McpServer(tools, self.agent_tokens(), self.now, self.correlate)

    def researcher(self) -> Researcher:
        schema, registry = self.model()
        fetcher = PoliteFetcher(f"{paths.site_origin()}/about", self.now, registry.vocabularies["document_kinds"],
                                os.environ.get("MVR_WEB_BASE"))
        files = Files(self.blobs(), self.datasheet_meter(), registry.vocabularies)
        return Researcher(self.research_meter(), self.image_judge_meter(), fetcher, files, self.review(),
                          self.research_runs(), self.agent_tokens(), self.repository(),
                          self.held(), schema, registry, self.now)

    def search_admin(self, review: Review, histories: Histories) -> SearchAdmin:
        return SearchAdmin(self.indexer, self.search_engine, lambda: self.ask_meter(self.search_engine()),
                           self.budget(), self.prompts(), self.ask_ledger(), review, histories, self.model()[1],
                           lambda: self.now()[:10])

    def news_admin(self, review: Review) -> NewsAdmin:
        return NewsAdmin(lambda: self.feed(review), self.drafter, paths.site_origin())

    def admin_endpoint(self) -> AdminEndpoint:
        review, histories = self.review(), self.histories()
        return AdminEndpoint(review, self.identity(), self.records(), histories, admin_model(*self.model()),
                             self.correlate, self.reindex,
                             {"search": self.search_admin(review, histories).route,
"news": self.news_admin(review).route, "agents": AgentsAdmin(self.agent_tokens(), self.now).route,
"research": ResearchAdmin(self.researcher, self.correlate).route})

    def detector(self) -> Detector:
        schema, registry = self.model()
        docs = self.store()
        return Detector(StoreChangeLog(docs, schema), self.feed(), registry.feed,
                        StoreFeedReads(docs, schema, self.repository()))

    def feed(self, review: Review | None = None) -> Feed:
        schema, registry = self.model()
        return Feed(review or self.review(), Job("news", self.correlate("feed")),
                    lambda: self.catalog(schema, (FeedItem.__name__,)).all(FeedItem),
                    lambda record: catalog_of(schema, [{"version": 1, **record_of(dict(record))}]).all(FeedItem)[0],
                    registry, self.instant)

    def drafter(self) -> Drafter:
        return Drafter(self.retriever(self.search_engine()), self.repository(), self.feed(), self.draft_meter(),
                       lambda: self.now()[:10])
