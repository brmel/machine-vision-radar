from __future__ import annotations

from radar.adapters.ai.adk.answer_model import LANGUAGES, evidence_json, sentences_of
from radar.adapters.ai.adk.runner import AdkRunner
from radar.domain.ai.prompts import Prompt
from radar.domain.ports.ai.article_model import ArticleText
from radar.domain.ports.search.retriever import Evidence

MAX_TOKENS = 800

class AdkArticleModel:
    def __init__(self, prompt: Prompt, runner: AdkRunner) -> None:
        self._prompt, self._runner = prompt, runner

    def draft(self, subject: Evidence, about: str, locale: str) -> ArticleText:
        request = self._prompt.render(language=LANGUAGES.get(locale, locale), about=about,
                                      evidence=evidence_json(subject))
        reply = self._runner.run("article_writer", self._prompt, request, MAX_TOKENS)
        return reply.read(lambda raw: ArticleText(raw["title"], raw["summary"], sentences_of(raw), reply.tokens_in,
                                                  reply.tokens_out))
