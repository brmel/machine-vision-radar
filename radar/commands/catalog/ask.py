from __future__ import annotations

import argparse
from typing import Sequence

from radar.adapters.console import log, output
from radar.domain.model.history.projection import plain
from radar.domain.ai.meter import Capped
from radar.domain.model.entities import AskAnswer, Citation
from radar.domain.ports.search.search_engine import IndexMismatch, NoIndex
from radar.adapters.console.parser import Commands

def _cited(text: str, citations: Sequence[Citation]) -> str:
    return text + "".join(f"\n  {c.product}" + (f" ({c.source})" if c.source else "") for c in citations)

def _text(answer: AskAnswer) -> str:
    if answer.refused:
        return f"refused: {answer.reason}"
    if not answer.needs:
        return _cited(answer.answer, answer.citations)
    return "\n".join(_cited(f"{n.need}: {n.answer or 'no product of the catalog meets it'}", n.citations)
                     for n in answer.needs)

def run(args: argparse.Namespace) -> int:
    args.wiring.correlate("ask")
    meter, locale = (args.wiring.ask_meter(args.wiring.search_engine()), args.locale
                     or args.wiring.model()[1].default_language.code)
    try:
        asked, cad = meter.call(args.wiring.now()[:10], lambda answerer: answerer.ask(args.question, locale))
    except (NoIndex, IndexMismatch) as exc:
        return log.error(str(exc), code=2)
    except Capped as exc:
        return log.error(f"no answer: the AI budget's cap, {exc}")
    except (OSError, ValueError, RuntimeError) as exc:
        return log.error(f"no answer: {exc}")
    answer = asked.answer
    if asked.text:
        log.info(f"answer model: {asked.text.tokens_in} tokens in, {asked.text.tokens_out} out, CAD {cad:.6f}")
    if asked.rejected:
        log.warn(f"the model's answer was refused: {asked.rejected}")
    return output.format_output(plain(answer), json_mode=args.json, text_formatter=lambda _: _text(answer))

def register(commands: Commands) -> None:
    p = commands.verb("catalog", "ask",
                      help="answer a question, or solve an application problem need by need, from the catalog with "
                           "citations, or refuse (Ask's model, under the AI caps; needs --project --yes)", func=run)
    p.add_argument("question", help="the question or the problem, in any language the site speaks")
    p.add_argument("--locale",
                   help="the language code to answer in (default: contracts/languages.json's default language)")
