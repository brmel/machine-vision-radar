from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Any

from radar.domain.ai.prompts import Prompt
from radar.adapters.ai.prompted.reply import read
from radar.domain.ports.ai.prompts import ModelRunner
from radar.domain.ports.ai.image_judge import CandidateImage, ImageEvaluation, JudgedImage

MAX_TOKENS = 1000

def _judged(url: str, raw: Any) -> JudgedImage:
    return JudgedImage(url, raw["kind"], float(raw["confidence"]), raw["reason"])

class PromptedImageJudge:
    def __init__(self, prompt: Prompt, runner: ModelRunner) -> None:
        self._prompt, self._runner = prompt, runner

    def judge(self, product_name: str, candidates: tuple[CandidateImage, ...]) -> ImageEvaluation:
        judged: list[JudgedImage] = []
        tokens_in, tokens_out = 0, 0
        for candidate in candidates:
            request = self._prompt.render(product=product_name, url=candidate.url)
            reply = self._runner.reply("image_judge", self._prompt, request, MAX_TOKENS,
                                     (candidate.content, candidate.mime))
            tokens_in, tokens_out = tokens_in + reply.tokens_in, tokens_out + reply.tokens_out
            judged.append(
                read(replace(reply, tokens_in=tokens_in, tokens_out=tokens_out), partial(_judged, candidate.url)))
        return ImageEvaluation(tuple(judged), tokens_in, tokens_out)
