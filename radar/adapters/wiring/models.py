from __future__ import annotations

import os
from typing import Callable, TypeVar

from radar import paths
from radar.adapters.console import log
from radar.adapters.ai.adk.answer_model import AdkAnswerModel
from radar.adapters.ai.adk.article_model import AdkArticleModel
from radar.adapters.ai.adk.datasheet_extractor import AdkDatasheetExtractor
from radar.adapters.ai.adk.image_judge import AdkImageJudge
from radar.adapters.ai.adk.research_agent import AdkResearchAgent
from radar.adapters.ai.adk.runner import AdkRunner
from radar.adapters.ai.scripted import (ScriptedAnswerModel, ScriptedArticleModel, ScriptedDatasheetExtractor,
                                        ScriptedImageJudge, ScriptedResearchAgent)
from radar.adapters.ai.search.engine import ShardedSearch
from radar.adapters.ai.search.fastembed_embedder import FastembedEmbedder
from radar.adapters.ai.search.files import BlobStoreIndexFiles
from radar.adapters.files.prompts import FilesPromptRegistry
from radar.adapters.firestore.ledgers.ai import (FirestoreAskLedger, FirestoreBudget, FirestoreIndexRuns,
                                                 FirestoreUsageLog)
from radar.adapters.wiring.stores import NoStore, Stores
from radar.domain.ai.answerer import Answerer
from radar.domain.ai.budget import Use
from radar.domain.ai.meter import Meter
from radar.domain.ai.prompts import Prompt
from radar.domain.model.entities import AiModel
from radar.domain.ports.ai.article_model import ArticleModel
from radar.domain.ports.ai.datasheet_extractor import DatasheetExtractor
from radar.domain.ports.ai.image_judge import ImageJudge
from radar.domain.ports.ai.prompt_registry import PromptRegistry
from radar.domain.ports.ai.research_agent import ResearchAgent
from radar.domain.ports.ai.usage_log import Budget
from radar.domain.ports.search.ask_ledger import AskLedger
from radar.domain.ports.search.retriever import Retriever
from radar.domain.ports.search.search_engine import SearchEngine
from radar.domain.search.indexing import Indexer
from radar.domain.search.retriever import IndexRetriever

M = TypeVar("M")

class Models(Stores):
    def _sharded(self) -> ShardedSearch:
        registry = self.model()[1]
        return ShardedSearch(BlobStoreIndexFiles(self.blobs()), FastembedEmbedder(registry.search.model), registry,
                             self.repository())

    def search_engine(self) -> SearchEngine:
        return self._sharded()

    def index_in_use(self) -> set[str]:
        return self._sharded().files()

    def indexer(self) -> Indexer:
        return Indexer(self.search_engine(), self.repository(), FirestoreIndexRuns(self.store()),
                       self.model()[1].search, self.instant)

    def prompts(self) -> PromptRegistry:
        return FilesPromptRegistry(paths.PROMPTS)

    def _meter(self, use: Use, adk: Callable[[Prompt, AdkRunner], M], scripted: M,
               prompt_id: str | None = None) -> Meter[M]:
        prompt, project = self.prompts().prompt(prompt_id or use.value), self._real
        if project:
            self._token()
        else:
            self._demo()
        token = os.environ.get("MVR_ACCESS_TOKEN")

        def opened(model: AiModel) -> M:
            if project and not self._yes:
                raise NoStore("a model call is charged to the project's AI budget and recorded there: pass --yes")
            return adk(prompt, AdkRunner(model.id, project, model.location, token)) if project else scripted
        return Meter(self.budget(), FirestoreUsageLog(self.store()), self.model()[1].ai, use, prompt.id, opened)

    def ask_meter(self, engine: SearchEngine) -> Meter[Answerer]:
        retriever = self.retriever(engine)
        return self._meter(Use.ASK, lambda prompt, runner: Answerer(retriever, AdkAnswerModel(prompt, runner)),
                           Answerer(retriever, ScriptedAnswerModel()))

    def research_meter(self) -> Meter[ResearchAgent]:
        registry = self.model()[1]
        return self._meter(Use.RESEARCH, lambda prompt, runner: AdkResearchAgent(prompt, runner, registry),
                           ScriptedResearchAgent())

    def image_judge_meter(self) -> Meter[ImageJudge]:
        return self._meter(Use.RESEARCH, AdkImageJudge, ScriptedImageJudge(), prompt_id="image_judge")

    def datasheet_meter(self) -> Meter[DatasheetExtractor]:
        registry = self.model()[1]
        return self._meter(Use.DATASHEET, lambda prompt, runner: AdkDatasheetExtractor(prompt, runner, registry),
                           ScriptedDatasheetExtractor())

    def draft_meter(self) -> Meter[ArticleModel]:
        return self._meter(Use.DRAFT, AdkArticleModel, ScriptedArticleModel())

    def retriever(self, engine: SearchEngine) -> Retriever:
        return IndexRetriever(engine, self.repository(), self.model()[1])

    def ask_ledger(self) -> AskLedger:
        return FirestoreAskLedger(self.store())

    def budget(self) -> Budget:
        schema, registry = self.model()
        return FirestoreBudget(self.store(), schema, registry.ai)

    def reindex(self, actor: str, correlation_id: str) -> bool:
        try:
            built = self.indexer().run("update", actor, correlation_id)
        except (OSError, ValueError, RuntimeError) as exc:
            log.error(f"the change is applied, but the search index is not updated: {exc}", fix="radar index update")
            return False
        log.info(f"search index {built.version}: {len(built.embedded)} embedded, {len(built.removed)} removed")
        return True
