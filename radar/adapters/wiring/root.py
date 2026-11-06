from __future__ import annotations

import os

from radar import paths
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
        tools = {**read_tools(self.search_engine, self.repository(), lambda: self.catalog(KINDS),
                              self.model().registry),
                 **proposal_tools(self.review(), self.model())}
        return McpServer(tools, self.agent_tokens(), self.now, self.correlate)

    def researcher(self) -> Researcher:
        model = self.model()
        fetcher = PoliteFetcher(f"{paths.site_origin()}/about", self.now, model.registry.vocabularies["document_kinds"],
                                os.environ.get("MVR_WEB_BASE"))
        files = Files(self.blobs(), self.datasheet_meter(), model.registry.vocabularies)
        return Researcher(self.research_meter(), self.image_judge_meter(), fetcher, files, self.review(),
                          self.research_runs(), self.agent_tokens(), self.repository(), self.held(), model, self.now)

    def search_admin(self, review: Review, histories: Histories) -> SearchAdmin:
        return SearchAdmin(self.indexer, self.search_engine, lambda: self.ask_meter(self.search_engine()),
                           self.budget(), self.prompts(), self.ask_ledger(), review, histories, self.model().registry,
                           lambda: self.now()[:10])

    def news_admin(self, review: Review) -> NewsAdmin:
        return NewsAdmin(lambda: self.feed(review), self.drafter, paths.site_origin())

    def admin_endpoint(self) -> AdminEndpoint:
        review, histories = self.review(), self.histories()
        return AdminEndpoint(review, self.identity(), self.records(), histories, self.model(),
                             self.correlate, self.reindex,
                             {"search": self.search_admin(review, histories).route,
"news": self.news_admin(review).route, "agents": AgentsAdmin(self.agent_tokens(), self.now).route,
"research": ResearchAdmin(self.researcher, self.correlate).route})

    def detector(self) -> Detector:
        model, docs = self.model(), self.store()
        return Detector(StoreChangeLog(docs, model), self.feed(), model.registry.feed,
                        StoreFeedReads(docs, model.schema, self.repository()), model.schema)

    def feed(self, review: Review | None = None) -> Feed:
        return Feed(review or self.review(), Job("news", self.correlate("feed")),
                    lambda: self.catalog((FeedItem.__name__,)).all(FeedItem), self.model().registry, self.instant)

    def drafter(self) -> Drafter:
        return Drafter(self.retriever(self.search_engine()), self.repository(), self.feed(), self.draft_meter(),
                       lambda: self.now()[:10])
