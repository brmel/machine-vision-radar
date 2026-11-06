import base64
import dataclasses
import json
from contextlib import contextmanager
from typing import Callable, Collection, Iterator

import pytest

from radar import paths
from radar.adapters.ai.prompted.answer_model import PromptedAnswerModel
from radar.adapters.ai.scripted import ScriptedAnswerModel
from radar.adapters.ai.prompted.article_model import PromptedArticleModel
from radar.adapters.ai.prompted.datasheet_extractor import PromptedDatasheetExtractor
from radar.adapters.ai.prompted.image_judge import PromptedImageJudge
from radar.adapters.ai.prompted.research_agent import PromptedResearchAgent
from radar.adapters.files.prompts import FilesPromptRegistry
from radar.adapters.ai.adk.runner import AdkRunner
from radar.adapters.ai.meta.runner import MetaRunner
from radar.domain.ai.answerer import Answerer
from radar.domain.search.retriever import IndexRetriever, evidence_of
from radar.domain.model.entities import (AiProviderLocal, AiProviderMeta, ClaimValueQuantity, ClaimValueTerm, Quantity,
                                         Source)
from radar.domain.ports.ai.answer_model import AnswerModel, AnswerText, NeedText, Sentence
from radar.domain.ports.ai.datasheet_extractor import Datasheet, SpecValue
from radar.domain.ports.ai.image_judge import CandidateImage
from radar.domain.ports.ai.prompts import ModelRunner
from radar.domain.ports.ai.research_agent import FileDraft, Reading, RecordsDraft
from radar.domain.ports.ai.usage_log import Unparsed
from radar.domain.ports.web.reader import Link, Page
from radar.domain.ports.search.retriever import Evidence
from radar.domain.ports.search.search_engine import SearchRequest
from radar.tests.store import stores
from radar.tests.adapters.stub_server import EXCHANGE, META_EXCHANGE, Answer, meta_saying, serving, vertex_saying

FX = stores.fixture()
READ, REGISTRY = FX.read, FX.model.registry
GEMINI = REGISTRY.ai.models[0]
MUSE = next(m for m in REGISTRY.ai.models if isinstance(m.provider, AiProviderMeta))
GLIMMER = next(m for m in REGISTRY.ai.models if isinstance(m.provider, AiProviderLocal))
RECORDED = (["prd_0000000002", "prd_0000000005"], "Which widget has a glossy finish, and what replaces it?")
PAGE = Page(Link("https://example.com/products/widget-two", "example.com"), "Widget Two", "A glossy widget, 93 g.",
            (Link("https://example.com/media/widget-two.pdf", "example.com"),), (), stores.NOW)
SOURCE = Source(id="src_0000000009", version=1, type="datasheet", url="https://example.com/media/widget-two.pdf",
                retrieved_at=stores.NOW)
SHEET = Datasheet("prd_0000000002", b"%PDF-1.4\nfixture_mount: socket_b\n%%EOF\n", "application/pdf", SOURCE)
CANDIDATE = CandidateImage("https://example.com/widget-two.png", b"\x89PNG\r\n\x1a\nfakeimage", "image/png")
PROMPTS = FilesPromptRegistry(paths.PROMPTS)
USES: dict[str, Callable[[ModelRunner], object]] = {
    "ask": lambda runner: PromptedAnswerModel(PROMPTS.prompt("ask"), runner).answer(
        RECORDED[1], evidence_of(READ.products(RECORDED[0]), REGISTRY, "en"), "en"),
    "draft": lambda runner: PromptedArticleModel(PROMPTS.prompt("draft"), runner).draft(
        evidence_of(READ.products(RECORDED[0][:1]), REGISTRY, "en"), "Example Devices", "en"),
    "datasheet": lambda runner: PromptedDatasheetExtractor(
        PROMPTS.prompt("datasheet"), runner, REGISTRY).extract(SHEET),
    "image_judge": lambda runner: PromptedImageJudge(
        PROMPTS.prompt("image_judge"), runner).judge("Widget Two", (CANDIDATE,)),
    "research": lambda runner: PromptedResearchAgent(PROMPTS.prompt("research"), runner, REGISTRY).research(
        Reading(PAGE, "org_0000000001", (), {})),
}

@pytest.fixture(scope="module")
def retriever() -> IndexRetriever:
    return IndexRetriever(FX.search_engine, READ, REGISTRY)

@pytest.fixture(scope="module")
def vertex() -> Iterator[str]:
    def replay(path: str, sent: bytes) -> tuple[int, bytes]:
        known = path == EXCHANGE["path"] and all(i in sent.decode() for i in RECORDED[0])
        return ((200, json.dumps(EXCHANGE["response"]).encode()) if known
                else (400, b'{"error": {"code": 400, "message": "not the recorded request"}}'))

    with serving(replay, keep_alive=True) as url:
        yield f"{url}/"

@contextmanager
def _vertex_saying(text: str, heard: list[str]) -> Iterator[str]:
    with serving(vertex_saying(text, heard), keep_alive=True) as url:
        yield f"{url}/"

def _adk(url: str) -> AdkRunner:
    return AdkRunner(GEMINI.id, "mvradar", "us-central1", "recorded", url)

def _muse(url: str) -> MetaRunner:
    return MetaRunner(MUSE.id, f"{url}v1", "recorded")

RUNNERS: dict[str, tuple[Callable[[str, list[str]], Answer], Callable[[str], ModelRunner]]] = {
    "adk": (vertex_saying, _adk), "meta": (meta_saying, _muse),
    "local": (meta_saying, lambda url: MetaRunner(GLIMMER.id, f"{url}v1", None))}

class Scripted:
    def __init__(self, *sentences: Sentence, needs: tuple[NeedText, ...] = ()) -> None:
        self.sentences, self.needs = sentences, needs

    def answer(self, question: str, evidence: Evidence, locale: str) -> AnswerText:
        return AnswerText(self.sentences, 1, 1, self.needs)

class Unreachable:
    def answer(self, question: str, evidence: Evidence, locale: str) -> AnswerText:
        raise AssertionError("the model was asked")

def _contract(model: AnswerModel) -> None:
    evidence = evidence_of(READ.products(RECORDED[0]), REGISTRY, "en")
    text = model.answer(RECORDED[1], evidence, "en")
    assert text.sentences and text.tokens_in > 0 and text.tokens_out > 0
    assert all(s.text and s.cites and set(s.cites) <= evidence.ids() for s in text.sentences)

def test_the_adk_adapter_meets_the_contract_on_a_recorded_exchange_every_time_it_is_asked(vertex: str) -> None:
    model = PromptedAnswerModel(PROMPTS.prompt("ask"), _adk(vertex))
    _contract(model)
    _contract(model)

@pytest.mark.parametrize("question, locale",
                         [("widget à finition brillante", "fr"), ("glossy widget", "en"), ("glossy widget", "fr")])
def test_every_sentence_cites_a_keyword_hit_or_its_source_in_either_language(
        question: str, locale: str, retriever: IndexRetriever) -> None:
    asked = Answerer(retriever, ScriptedAnswerModel()).ask(question, locale)
    answer, text = asked.answer, asked.text
    assert not answer.refused and text is not None and answer.answer
    assert list(dict.fromkeys(c.product for c in answer.citations)) == [
        h.card.id for h in FX.search_engine.search(SearchRequest(question, 2))]
    views = {v.id: v for v in READ.products([c.product for c in answer.citations])}
    for c in answer.citations:
        assert c.source is None or c.source in {s.id for s in views[c.product].sources}
    first = next(v for v in views.values() if any(cell.value is not None for cell in v.core))
    shown = {c.source for c in answer.citations if c.product == first.id}
    assert next(cell.source for cell in first.core if cell.value is not None) in shown

def test_a_question_no_word_matches_rests_on_the_vector_hits(retriever: IndexRetriever) -> None:
    answer = Answerer(retriever, ScriptedAnswerModel()).ask("a shiny polished gadget", "en").answer
    assert not answer.refused
    assert list(dict.fromkeys(c.product for c in answer.citations)) == [
        h.card.id for h in FX.search_engine.search(SearchRequest("a shiny polished gadget", 2, semantic=True))]

def test_an_answer_rests_on_at_most_the_products_search_json_names(retriever: IndexRetriever) -> None:
    found = len(retriever.evidence("widget", "en").products)
    fewer = dataclasses.replace(REGISTRY, search=dataclasses.replace(REGISTRY.search, evidence=found - 1))
    evidence = IndexRetriever(FX.search_engine, READ, fewer).evidence("widget", "en")
    assert len(evidence.products) == found - 1 == REGISTRY.search.evidence - 1

@pytest.mark.parametrize("sentence, why", [
    (Sentence("A widget is glossy.", ()), "sentence 1 cites nothing"),
    (Sentence("Widget Two is glossy.", ("prd_zzzzzzzzzz",)),
     "sentence 1 cites prd_zzzzzzzzzz, which is not in the evidence"),
    (Sentence("Widget Two reaches 9,999 mm.", ("prd_0000000002",)),
     "sentence 1 states 9999, which what it cites does not hold"),
])
def test_an_ungrounded_sentence_refuses_the_answer_with_its_reason(
        sentence: Sentence, why: str, retriever: IndexRetriever) -> None:
    asked = Answerer(retriever, Scripted(sentence)).ask("glossy widget", "en")
    assert (asked.answer.refused, asked.answer.reason, asked.answer.citations, asked.rejected) == (
        True, "not_enough_evidence", (), why)

def test_a_number_of_the_evidence_or_of_the_question_stands_however_it_is_grouped(retriever: IndexRetriever) -> None:
    reach = next(f for p in retriever.evidence("glossy widget", "en").products for f in p.facts
                 if any(ch.isdigit() for ch in f.value))
    product = next(p.id for p in retriever.evidence("glossy widget", "en").products if reach in p.facts)
    stated = reach.value.replace(".", ",")
    asked = Answerer(retriever,
                     Scripted(Sentence(f"It reaches {stated}, more than the 42 asked for.", (product,)))).ask(
                         "glossy widget over 42", "en")
    assert asked.rejected is None and not asked.answer.refused

def test_a_question_the_catalog_does_not_match_is_refused_before_any_model_call(retriever: IndexRetriever) -> None:
    asked = Answerer(retriever, Unreachable()).ask("What is the capital of Australia?", "en")
    assert (asked.answer.refused, asked.answer.reason, asked.text) == (True, "off_topic", None)

def test_a_problem_is_solved_need_by_need_and_a_need_nothing_meets_says_so(retriever: IndexRetriever) -> None:
    answer = Answerer(retriever, ScriptedAnswerModel()).ask("a glossy finish; zzqxv", "en").answer
    needs = answer.needs or ()
    assert [(n.need, bool(n.answer and n.citations)) for n in needs] == [("a glossy finish", True), ("zzqxv", False)]
    assert (answer.refused, answer.answer, answer.citations) == (False, "", needs[0].citations)
    stray = NeedText("a long reach", (Sentence("Widget Two reaches far.", ("prd_zzzzzzzzzz",)),))
    asked = Answerer(retriever, Scripted(needs=(stray,))).ask("glossy widget", "en")
    assert (asked.answer.refused, asked.rejected) == (True, "sentence 1 cites prd_zzzzzzzzzz, which is not in the "
                                                            "evidence")
    unmet = Answerer(retriever, Scripted(needs=(NeedText("zzqxv", ()),))).ask("glossy widget", "en")
    assert (unmet.answer.refused, unmet.answer.reason, unmet.rejected) == (True, "not_enough_evidence", "no sentence")

def _specs_in(request: str, keys: Collection[str]) -> bool:
    asked = json.loads(request)["contents"][0]["parts"][0]["text"]
    specs = [s for s in REGISTRY.spec_definitions.values() if s.id in keys]
    spec = next(s for s in specs if s.aliases and s.bounds)
    terms = next(REGISTRY.vocabularies[s.vocabulary] for s in specs if s.vocabulary)
    return (all(json.dumps(a, ensure_ascii=False) in asked for a in spec.aliases)
            and f'"bounds": {{"min": {spec.bounds.min}' in asked
            and json.dumps({"terms": {i: t.label["en"] for i, t in terms.items()}}, ensure_ascii=False)[1:-1] in asked)

def test_the_adk_research_agent_returns_the_records_a_page_states_for_the_run_to_cite() -> None:
    card = next(p for p in READ.index().products if p.id == "prd_0000000002")
    claim = {"id": "clm_0000000009", "subject": "prd_0000000002", "spec_key": "fixture_mass", "method": "website",
             "recorded_at": stores.NOW, "rank": 1, "value": {"quantity": {"value": 93.0, "unit": "g"}}}
    said = {"proposals": [{"files_on": "update", "reason": "The page gives its mass", "subject": "prd_0000000002",
                           "records": json.dumps([claim])},
                          {"files_on": "update", "reason": "The page links its datasheet", "subject": "prd_0000000002",
                           "records": "[]", "media": PAGE.links[0].address}],
            "follow": ["https://example.com/products/widget-nine"]}
    heard: list[str] = []
    with _vertex_saying(json.dumps(said), heard) as url:
        agent = PromptedResearchAgent(PROMPTS.prompt("research"), _adk(url), REGISTRY)
        findings = agent.research(Reading(PAGE, "org_0000000001", (card,), {}))
        agent.research(Reading(PAGE, "org_0000000001", (), {}))
    with _vertex_saying(json.dumps({**said, "proposals": [{**said["proposals"][0], "records": '[{"value": 93}]'}]}),
                        []) as url:
        with pytest.raises(Unparsed, match="each with its id"):
            USES["research"](_adk(url))
    assert findings.proposals == (
        RecordsDraft("update", "The page gives its mass", "prd_0000000002", (claim,)),
        FileDraft("update", "The page links its datasheet", "prd_0000000002", PAGE.links[0].address))
    assert (findings.follow == ("https://example.com/products/widget-nine",) and findings.tokens_in > 0
            and findings.tokens_out > 0)
    sections = REGISTRY.profile(card.category).sections
    assert (PAGE.text in heard[0] and PAGE.links[0].address in heard[0]
            and _specs_in(heard[0], {*sections.core, *sections.detail}))
    carded, uncarded = (json.loads(h)["contents"][0]["parts"][0]["text"] for h in heard)
    assert ('"id": "line_rate"' not in carded and '"id": "line_rate"' in uncarded
            and _specs_in(heard[1], REGISTRY.spec_definitions))

def test_the_adk_article_model_returns_the_text_it_wrote_about_the_record_it_was_given() -> None:
    said = {"sentences": [{"text": "Widget Two is glossy.", "cites": [RECORDED[0][0]]}], "title": "Widget Two",
            "summary": "A glossy widget."}
    heard: list[str] = []
    with _vertex_saying(json.dumps(said), heard) as url:
        text = PromptedArticleModel(PROMPTS.prompt("draft"), _adk(url)).draft(
            evidence_of(READ.products(RECORDED[0][:1]), REGISTRY, "en"), "Example Devices", "en")
    assert (text.title, text.summary, text.sentences) == ("Widget Two", "A glossy widget.",
                                                          (Sentence("Widget Two is glossy.", (RECORDED[0][0],)),))
    assert text.tokens_in > 0 and RECORDED[0][0] in heard[0] and "About: Example Devices" in heard[0]

def test_the_adk_datasheet_extractor_reads_each_value_the_datasheet_states() -> None:
    said = {"values": [{"spec_key": "fixture_mount", "term": "socket_b"},
                       {"spec_key": "fixture_mass", "quantity": 93, "unit": "g"},
                       {"spec_key": "fixture_reach", "quantity": 125, "unit": "mm"},
                       {"spec_key": "fixture_reach", "quantity": 150, "unit": "mm"}]}
    heard: list[str] = []
    with _vertex_saying(json.dumps(said), heard) as url:
        extraction = PromptedDatasheetExtractor(PROMPTS.prompt("datasheet"), _adk(url), REGISTRY).extract(SHEET)
    assert extraction.values == (SpecValue("fixture_mount", ClaimValueTerm(term="socket_b")),
                                 SpecValue("fixture_mass", ClaimValueQuantity(quantity=Quantity(value=93.0, unit="g"))))
    assert (extraction.tokens_in > 0 and base64.b64encode(SHEET.content).decode() in heard[0]
            and _specs_in(heard[0], REGISTRY.spec_definitions))

def test_the_adk_image_judge_ranks_candidates_and_picks_a_photo() -> None:
    said = {"kind": "photo", "confidence": 0.95, "reason": "A clear photo of Widget Two"}
    heard: list[str] = []
    with _vertex_saying(json.dumps(said), heard) as url:
        eval_res = PromptedImageJudge(PROMPTS.prompt("image_judge"), _adk(url)).judge("Widget Two", (CANDIDATE,))
    replies = iter((vertex_saying(json.dumps(said), []), vertex_saying("{}", [])))
    with serving(lambda path, sent: next(replies)(path, sent),
                 keep_alive=True) as url, pytest.raises(Unparsed) as refused:
        PromptedImageJudge(PROMPTS.prompt("image_judge"), _adk(f"{url}/")).judge("Widget Two", (CANDIDATE, CANDIDATE))
    assert len(eval_res.judged) == 1 and eval_res.judged[0].kind == "photo"
    assert eval_res.tokens_in > 0 and base64.b64encode(CANDIDATE.content).decode() in heard[0]
    assert (refused.value.tokens_in, refused.value.tokens_out) == (2 * eval_res.tokens_in, 2 * eval_res.tokens_out)

@pytest.mark.parametrize("said", ["{}", ""])
@pytest.mark.parametrize("use", USES)
@pytest.mark.parametrize("runner", RUNNERS)
def test_a_reply_out_of_its_port_s_shape_is_unparsed_naming_its_prompt_with_its_tokens(
        runner: str, use: str, said: str) -> None:
    saying, opened = RUNNERS[runner]
    with serving(saying(said, []), keep_alive=True) as url, pytest.raises(Unparsed, match=rf"^{use}: ") as refused:
        USES[use](opened(f"{url}/"))
    assert refused.value.tokens_in > 0 and refused.value.tokens_out > 0

def test_the_meta_runner_asks_for_the_prompt_s_shape_and_meets_the_contract_on_meta_s_documented_reply() -> None:
    heard: list[str] = []
    prompt = PROMPTS.prompt("ask")
    with serving(meta_saying(META_EXCHANGE["response"]["choices"][0]["message"]["content"], heard),
                 keep_alive=True) as url:
        _contract(PromptedAnswerModel(prompt, _muse(f"{url}/")))
    sent = json.loads(heard[0])
    assert (sent["model"], sent["messages"][0], sent["response_format"]["json_schema"]["schema"]) == (
        MUSE.id, {"role": "system", "content": prompt.instruction}, json.loads(prompt.output_schema))

def test_the_meta_runner_sends_a_datasheet_as_a_file_and_an_image_inline() -> None:
    heard: list[str] = []
    for use, said in (("datasheet", '{"values": []}'), ("image_judge", '{"kind": "photo", "confidence": 0.9, '
                                                                        '"reason": "A photo"}')):
        with serving(meta_saying(said, heard), keep_alive=True) as url:
            USES[use](_muse(f"{url}/"))
    sheet, image = (json.loads(h)["messages"][1]["content"][1] for h in heard)
    pdf, png = (base64.b64encode(f.content).decode() for f in (SHEET, CANDIDATE))
    assert sheet == {"type": "file",
                     "file": {"filename": "source.pdf", "file_data": f"data:application/pdf;base64,{pdf}"}}
    assert image == {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png}"}}

def test_a_refused_meta_call_names_its_status_never_the_key() -> None:
    refusing: Answer = lambda path, sent: (401, b'{"error": {"message": "invalid key"}}')
    with serving(refusing, keep_alive=True) as url, pytest.raises(OSError, match="HTTP 401") as refused:
        MetaRunner(MUSE.id, f"{url}/v1", "mk-secret").reply(PROMPTS.prompt("ask"), "w", 10)
    assert "mk-secret" not in str(refused.value)

def test_a_refused_adk_call_is_an_os_error_naming_its_status() -> None:
    refusing: Answer = lambda path, sent: (400, b'{"error": {"code": 400, "message": "invalid argument"}}')
    with serving(refusing, keep_alive=True) as url, pytest.raises(OSError, match="HTTP 400"):
        _adk(f"{url}/").reply(PROMPTS.prompt("ask"), "w", 10)
