from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from radar.domain.ai.prompts import Prompt
from radar.adapters.ai.prompted.reply import read
from radar.domain.ports.ai.prompts import ModelRunner
from radar.adapters.ai.prompted.specs import specs_json
from radar.domain.model.entities import (ClaimValue, ClaimValueNone, ClaimValueQuantity, ClaimValueString,
                                         ClaimValueTerm, ClaimValueTerms, Quantity, SpecDefinition)
from radar.domain.model.registry import Registry
from radar.domain.ports.ai.datasheet_extractor import Datasheet, Extraction, SpecValue

MAX_TOKENS = 4000

def _value(stated: Mapping[str, Any], spec: SpecDefinition | None) -> ClaimValue:
    if stated.get("none"):
        return ClaimValueNone(none=stated["none"])
    if stated.get("quantity") is not None and stated.get("unit"):
        return ClaimValueQuantity(quantity=Quantity(value=float(stated["quantity"]), unit=stated["unit"]))
    if not stated.get("term"):
        raise ValueError(f"{stated['spec_key']}: a value is a number with its unit, or a term")
    match spec.datatype if spec else "term":
        case "term_set":
            return ClaimValueTerms(terms=(stated["term"],))
        case "string":
            return ClaimValueString(string=stated["term"])
    return ClaimValueTerm(term=stated["term"])

def _single(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    given = Counter(v["spec_key"] for v in values)
    return [v for v in values if given[v["spec_key"]] == 1]

class PromptedDatasheetExtractor:
    def __init__(self, prompt: Prompt, runner: ModelRunner, registry: Registry) -> None:
        self._prompt, self._runner, self._defs, self._specs = (prompt, runner, registry.spec_definitions,
                                                               specs_json(registry, registry.spec_definitions))

    def extract(self, datasheet: Datasheet) -> Extraction:
        request = self._prompt.render(product=datasheet.product, source=datasheet.source.id, specs=self._specs)
        reply = self._runner.reply(self._prompt, request, MAX_TOKENS,
                                 (datasheet.content, datasheet.mime))
        return read(reply, 
            lambda raw: Extraction(tuple(SpecValue(v["spec_key"], _value(v, self._defs.get(v["spec_key"])))
                                         for v in _single(raw["values"])),
                                   reply.tokens_in, reply.tokens_out))
