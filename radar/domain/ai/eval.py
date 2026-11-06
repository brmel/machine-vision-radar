from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from radar.domain.ai.answerer import Answerer
from radar.domain.ports.ai.usage_log import Ended
from radar.domain.model.entities import Claim, EvalQuery
from radar.domain.ports.ai.article_model import ArticleModel
from radar.domain.ports.ai.datasheet_extractor import Datasheet, DatasheetExtractor, SpecValue
from radar.domain.ports.ai.image_judge import CandidateImage, ImageJudge
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.search.retriever import Retriever
from radar.domain.review.feed.drafter import drafted

@dataclass(frozen=True, slots=True)
class Graded:
    case: str
    failed: str | None
    call: Ended | None

    def ended(self) -> Ended | None:
        return self.call

@dataclass(frozen=True, slots=True)
class DatasheetCase:
    id: str
    datasheet: Datasheet
    expected: tuple[Claim, ...]

@dataclass(frozen=True, slots=True)
class ImageCase:
    id: str
    product: str
    candidates: tuple[CandidateImage, ...]
    photo: str | None

def graded_answer(read_model: CatalogRepository, query: EvalQuery, locale: str, answerer: Answerer) -> Graded:
    asked = answerer.ask(query.query, locale)
    cited = [c.product for c in asked.answer.citations]
    on_topic = set(cited) & set(query.targets) or any(v.category == query.category for v in read_model.products(cited))
    failed = (f"refused: {asked.answer.reason}" if asked.answer.refused else None if on_topic
              else "cites neither a target nor its category")
    return Graded(f"{query.id} {locale}", failed, asked.ended())

def graded_solution(problem: EvalQuery, answerer: Answerer) -> Graded:
    answer = (asked := answerer.ask(problem.query, problem.language)).answer
    missed = sorted(set(problem.targets) - {c.product for n in answer.needs or () for c in n.citations})
    failed = (f"refused: {answer.reason}" if answer.refused else "answered, not solved" if not answer.needs
              else f"no need cites {', '.join(missed)}" if missed else None)
    return Graded(problem.id, failed, asked.ended())

def graded_draft(retriever: Retriever, query: EvalQuery, model: ArticleModel) -> Graded:
    subject = retriever.about(query.targets, query.language)
    done = drafted(model, subject, subject.products[0].name, query.language)
    return Graded(query.id, done.rejected, done.ended())

def _unmatched(values: Sequence[SpecValue], others: Sequence[SpecValue]) -> list[str]:
    return [v.spec_key for v in values if v not in others]

def _extraction_failure(case: DatasheetCase, values: Sequence[SpecValue]) -> str | None:
    expected = [SpecValue(c.spec_key, c.value) for c in case.expected]
    missed, invented = _unmatched(expected, values), _unmatched(values, expected)
    if missed:
        return f"missed {', '.join(missed)}"
    return f"states {', '.join(invented)}, which the datasheet does not" if invented else None

def graded_judgement(case: ImageCase, judge: ImageJudge) -> Graded:
    evaluation = judge.judge(case.product, case.candidates)
    best = evaluation.best_photo()
    return Graded(case.id, None if best == case.photo else f"picked {best or 'no photo'}, not {case.photo or 'none'}",
                  evaluation.ended())

def graded_extraction(case: DatasheetCase, extractor: DatasheetExtractor) -> Graded:
    extraction = extractor.extract(case.datasheet)
    return Graded(case.id, _extraction_failure(case, extraction.values), extraction.ended())
