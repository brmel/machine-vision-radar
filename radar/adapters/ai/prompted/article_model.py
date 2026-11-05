from __future__ import annotations

from radar.adapters.ai.prompted.answer_model import LANGUAGES, evidence_json, sentences_of
from radar.domain.ai.prompts import Prompt
from radar.adapters.ai.prompted.reply import read
from radar.domain.ports.ai.prompts import ModelRunner
from radar.domain.ports.ai.article_model import ArticleText
from radar.domain.ports.search.retriever import Evidence

MAX_TOKENS = 800

class PromptedArticleModel:
    def __init__(self, prompt: Prompt, runner: ModelRunner) -> None:
        self._prompt, self._runner = prompt, runner

    def draft(self, subject: Evidence, about: str, locale: str) -> ArticleText:
        request = self._prompt.render(language=LANGUAGES.get(locale, locale), about=about,
                                      evidence=evidence_json(subject))
        reply = self._runner.reply(self._prompt, request, MAX_TOKENS)
        return read(reply, lambda raw: ArticleText(raw["title"], raw["summary"], sentences_of(raw), reply.tokens_in,
                                                  reply.tokens_out))
