from __future__ import annotations

import os
from typing import Callable, TypeVar

from radar import paths
from radar.adapters.console import log
from radar.adapters.ai.prompted.answer_model import PromptedAnswerModel
from radar.adapters.ai.prompted.article_model import PromptedArticleModel
from radar.adapters.ai.prompted.datasheet_extractor import PromptedDatasheetExtractor
from radar.adapters.ai.prompted.image_judge import PromptedImageJudge
from radar.adapters.ai.prompted.research_agent import PromptedResearchAgent
from radar.adapters.ai.adk.runner import AdkRunner
from radar.adapters.ai.meta.runner import MetaRunner
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
from radar.domain.model.entities import AiModel, AiProviderLocal, AiProviderMeta, AiProviderVertex
from radar.domain.ports.ai.article_model import ArticleModel
from radar.domain.ports.ai.datasheet_extractor import DatasheetExtractor
from radar.domain.ports.ai.image_judge import ImageJudge
from radar.domain.ports.ai.prompts import ModelRunner, PromptRegistry
from radar.domain.ports.ai.research_agent import ResearchAgent
from radar.domain.ports.ai.usage_log import Budget
from radar.domain.ports.search.ask_ledger import AskLedger
from radar.domain.ports.search.retriever import Retriever
from radar.domain.ports.search.search_engine import SearchEngine
from radar.domain.search.indexing import Indexer
from radar.domain.search.retriever import IndexRetriever

M = TypeVar("M")

class Models(Stores):
    def search_engine(self) -> ShardedSearch:
        registry = self.model().registry
        return ShardedSearch(BlobStoreIndexFiles(self.blobs()), FastembedEmbedder(registry.search.model), registry,
                             self.repository())

    def index_in_use(self) -> set[str]:
        return self.search_engine().files()

    def indexer(self) -> Indexer:
        return Indexer(self.search_engine(), self.repository(), FirestoreIndexRuns(self.store()),
                       self.model().registry.search, self.instant)

    def prompts(self) -> PromptRegistry:
        return FilesPromptRegistry(paths.PROMPTS)

    def _runner(self, model: AiModel, project: str) -> ModelRunner:
        match model.provider:
            case AiProviderVertex(vertex=location):
                return AdkRunner(model.id, project, location, os.environ.get("MVR_ACCESS_TOKEN"))
            case AiProviderMeta(meta=base_url):
                key = os.environ.get("MODEL_API_KEY")
                if not key:
                    raise RuntimeError(f"{model.id} runs on the Meta Model API: set MODEL_API_KEY in the environment")
                return MetaRunner(model.id, base_url, key)
            case AiProviderLocal(local=base_url):
                return MetaRunner(model.id, base_url, None)

    def _meter(self, use: Use, prompted: Callable[[Prompt, ModelRunner], M], scripted: M,
               prompt_id: str | None = None) -> Meter[M]:
        prompt, project = self.prompts().prompt(prompt_id or use.value), self._real

        def opened(model: AiModel) -> M:
            if project and not self._yes:
                raise NoStore("a model call is charged to the project's AI budget and recorded there: pass --yes")
            return prompted(prompt, self._runner(model, project)) if project else scripted
        return Meter(self.budget(), FirestoreUsageLog(self.store()), self.model().registry.ai, use, prompt.id, opened)

    def ask_meter(self, engine: SearchEngine) -> Meter[Answerer]:
        retriever = self.retriever(engine)
        return self._meter(Use.ASK, lambda prompt, runner: Answerer(retriever, PromptedAnswerModel(prompt, runner)),
                           Answerer(retriever, ScriptedAnswerModel()))

    def research_meter(self) -> Meter[ResearchAgent]:
        registry = self.model().registry
        return self._meter(Use.RESEARCH, lambda prompt, runner: PromptedResearchAgent(prompt, runner, registry),
                           ScriptedResearchAgent())

    def image_judge_meter(self) -> Meter[ImageJudge]:
        return self._meter(Use.RESEARCH, PromptedImageJudge, ScriptedImageJudge(), prompt_id="image_judge")

    def datasheet_meter(self) -> Meter[DatasheetExtractor]:
        registry = self.model().registry
        return self._meter(Use.DATASHEET, lambda prompt, runner: PromptedDatasheetExtractor(prompt, runner, registry),
                           ScriptedDatasheetExtractor())

    def draft_meter(self) -> Meter[ArticleModel]:
        return self._meter(Use.DRAFT, PromptedArticleModel, ScriptedArticleModel())

    def retriever(self, engine: SearchEngine) -> Retriever:
        return IndexRetriever(engine, self.repository(), self.model().registry)

    def ask_ledger(self) -> AskLedger:
        return FirestoreAskLedger(self.store())

    def budget(self) -> Budget:
        return FirestoreBudget(self.store(), self.model())

    def reindex(self, actor: str, correlation_id: str) -> bool:
        try:
            built = self.indexer().run("update", actor, correlation_id)
        except (OSError, ValueError, RuntimeError) as exc:
            log.error(f"the change is applied, but the search index is not updated: {exc}", fix="radar index update")
            return False
        log.info(f"search index {built.version}: {len(built.embedded)} embedded, {len(built.removed)} removed")
        return True
