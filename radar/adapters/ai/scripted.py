from __future__ import annotations

import dataclasses
import json

from radar.domain.model.entities import ClaimValue, ClaimValueNone, ClaimValueQuantity, ClaimValueTerm, Quantity
from radar.adapters.files.model_json import DEFAULT_LANGUAGE, LANGUAGES
from radar.domain.ports.ai.answer_model import AnswerText, NeedText, Sentence
from radar.domain.ports.ai.article_model import ArticleText
from radar.domain.ports.ai.datasheet_extractor import Datasheet, Extraction, SpecValue
from radar.domain.ports.ai.image_judge import CandidateImage, ImageEvaluation, ImageKind, JudgedImage
from radar.domain.ports.ai.research_agent import FileDraft, Findings, Reading, RecordsDraft
from radar.domain.ports.search.retriever import Evidence, EvidenceProduct

PROPOSAL, FOLLOW = "proposal: ", "follow: "
NEEDS = ";"
SENTENCE = {l.code: l.sentence for l in LANGUAGES if l.sentence}
FACT = "{name}: {label}, {value}."

def _sentences(evidence: Evidence, locale: str, count: int) -> tuple[Sentence, ...]:
    tpl = SENTENCE.get(locale, SENTENCE[DEFAULT_LANGUAGE.code])
    return tuple(Sentence(tpl.format(name=p.name, category=p.category, vendor=p.vendor),
                          (p.id, *([p.facts[0].source] if p.facts and p.facts[0].source else [])))
                 for p in evidence.products[:count])

def _tokens(*texts: str) -> int:
    return sum(len(t.split()) for t in texts)

def _need(need: str, evidence: Evidence, locale: str) -> NeedText:
    words = {w for w in need.lower().split() if len(w) > 3}
    meeting = tuple(p for p in evidence.products if words & set(
        " ".join((p.name, p.summary, *(f"{f.label} {f.value}" for f in p.facts))).lower().split()))
    return NeedText(need.strip(), _sentences(Evidence(meeting), locale, 2))

class ScriptedAnswerModel:
    def answer(self, question: str, evidence: Evidence, locale: str) -> AnswerText:
        needs = (tuple(_need(n, evidence, locale) for n in question.split(NEEDS) if n.strip()) if NEEDS in question
                 else ())
        sentences = () if needs else _sentences(evidence, locale, 2)
        text = AnswerText(sentences, len(question.split()) + sum(len(p.facts) for p in evidence.products), 0, needs)
        return dataclasses.replace(text, tokens_out=_tokens(*(s.text for s in text.every_sentence())))

def _stated(product: EvidenceProduct, locale: str) -> tuple[Sentence, ...]:
    return (*_sentences(Evidence((product,)), locale, 1),
            *(Sentence(FACT.format(name=product.name, label=f.label, value=f.value),
                       (product.id, *([f.source] if f.source else []))) for f in product.facts))

class ScriptedArticleModel:
    def draft(self, subject: Evidence, about: str, locale: str) -> ArticleText:
        sentences = tuple(s for p in subject.products for s in _stated(p, locale))[:5]
        return ArticleText(about, sentences[0].text, sentences, sum(len(p.facts) for p in subject.products),
                           _tokens(*(s.text for s in sentences)))

class ScriptedResearchAgent:
    def research(self, reading: Reading) -> Findings:
        lines = reading.page.text.splitlines()
        stated = [json.loads(line.removeprefix(PROPOSAL)) for line in lines if line.startswith(PROPOSAL)]
        drafts = tuple(FileDraft(p["files_on"], p["reason"], p["subject"], p["media"]) if p.get("media")
                       else RecordsDraft(p["files_on"], p["reason"], p["subject"], tuple(p.get("puts", ())))
                       for p in stated)
        return Findings(drafts, tuple(line.removeprefix(FOLLOW) for line in lines if line.startswith(FOLLOW)),
                        _tokens(reading.page.text), len(drafts))

def _value(stated: str) -> ClaimValue:
    number, _, unit = stated.partition(" ")
    if number.replace(".", "", 1).isdigit():
        return ClaimValueQuantity(quantity=Quantity(value=float(number), unit=unit))
    return ClaimValueNone(none=unit) if number == "none" and unit else ClaimValueTerm(term=stated)

class ScriptedDatasheetExtractor:
    def extract(self, datasheet: Datasheet) -> Extraction:
        text = datasheet.content.decode("utf-8", "replace")
        stated = [(key.strip(), value.strip()) for key, _, value in (line.partition(":") for line in text.splitlines())]
        values = tuple(SpecValue(key, _value(value)) for key, value in stated if key and value)
        return Extraction(values, _tokens(text), len(values))

RULES: tuple[tuple[tuple[str, ...], ImageKind, float, str], ...] = (
    (("logo",), "logo", 0.9, "Logo image"),
    (("banner", "header"), "banner", 0.85, "Banner image"),
    (("diagram", "schematic", "drawing"), "diagram", 0.85, "Diagram image"),
    (("competitor", "alternate", "different"), "other_product", 0.8, "Other product photo"),
    ((".svg", ".png", ".jpg", ".jpeg", ".webp", "photo", "media"), "photo", 0.95, "Product photograph"),
)

def _judge_kind(url: str) -> tuple[ImageKind, float, str]:
    lower = url.lower()
    for tokens, kind, conf, reason in RULES:
        if any(t in lower for t in tokens):
            return kind, conf, reason
    return "unrelated", 0.5, "Unrelated image"

class ScriptedImageJudge:
    def judge(self, product_name: str, candidates: tuple[CandidateImage, ...]) -> ImageEvaluation:
        judged = tuple(JudgedImage(c.url, *_judge_kind(c.url)) for c in candidates)
        tokens = sum(len(c.content) // 100 for c in candidates) + len(product_name.split())
        return ImageEvaluation(judged, tokens, len(judged))
