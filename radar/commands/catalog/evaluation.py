from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path
from typing import Callable, Sequence, TypeVar

from radar.adapters.console import log, output
from radar.domain.ai.eval import Graded, graded_answer, graded_draft, graded_extraction, graded_solution
from radar.domain.ai.meter import Meter
from radar.domain.model.entities import EvalQuery
from radar.domain.ports.search.search_engine import SearchRequest
from radar.domain.search.eval import evaluate
from radar.adapters.console.parser import Commands

M = TypeVar("M")

def _search(args: argparse.Namespace, queries: Sequence[EvalQuery]) -> float:
    engine = args.wiring.search_engine()
    score = evaluate(queries, lambda q, k: engine.search(SearchRequest(q, k, args.semantic)), k=args.k)
    result = {"use": "search", "mode": "hybrid" if args.semantic else "keyword", "k": args.k,
              "queries": len(score.outcomes), "hits": score.hits, "hit_rate": round(score.hit_rate, 4),
              "mrr": round(score.mrr, 4),
              "misses": [{"id": o.query.id, "query": o.query.query, "returned": list(o.returned)}
                         for o in score.outcomes if o.rank is None]}
    output.format_output(result, json_mode=args.json,
                         text_formatter=lambda r: f"Hit@{r['k']} {r['hits']}/{r['queries']} ({r['hit_rate']:.0%}), MRR "
                                                  f"{r['mrr']:.3f}, {r['mode']}")
    return score.hit_rate

def _graded(args: argparse.Namespace, meter: Meter[M], grades: Sequence[Callable[[M], Graded]]) -> float:
    day = args.wiring.now()[:10]
    graded = [meter.call(day, grade)[0] for grade in grades]
    failures = [{"case": g.case, "why": g.failed} for g in graded if g.failed]
    rate = (len(graded) - len(failures)) / len(graded)
    output.format_output({"use": args.use, "cases": len(graded), "passed": len(graded) - len(failures),
                          "rate": round(rate, 4), "failures": failures},
                         json_mode=args.json, text_formatter=lambda r: f"{r['use']}: {r['passed']}/{r['cases']} passed"
                         + "".join(f"\n  {f['case']}: {f['why']}" for f in r["failures"]))
    return rate

def _queries(args: argparse.Namespace, queries: Sequence[EvalQuery]) -> float:
    if args.use == "search":
        return _search(args, queries)
    if args.use == "ask":
        read_model, languages = args.wiring.repository(), tuple(l.code for l in args.wiring.model().registry.languages)
        return _graded(args, args.wiring.ask_meter(args.wiring.search_engine()),
                       [partial(graded_answer, read_model, q, locale) for q in queries for locale in languages])
    retriever = args.wiring.retriever(args.wiring.search_engine())
    return _graded(args, args.wiring.draft_meter(), [partial(graded_draft, retriever, q) for q in queries])

def _scored(args: argparse.Namespace, score: Callable[[], float]) -> int:
    rate = score()
    if args.floor is not None and rate < args.floor:
        return log.error(f"{args.use}: {rate:.2f} is under the floor {args.floor}")
    return 0

def _cased(args: argparse.Namespace, path: Path) -> Callable[[], float]:
    if args.use == "datasheet":
        cases = args.wiring.datasheet_cases(path)
        return lambda: _graded(args, args.wiring.datasheet_meter(), [partial(graded_extraction, c) for c in cases])
    problems = args.wiring.problems(path)
    return lambda: _graded(args, args.wiring.ask_meter(args.wiring.search_engine()),
                           [partial(graded_solution, p) for p in problems])

def run(args: argparse.Namespace) -> int:
    if args.use in ("datasheet", "solve"):
        if not args.cases:
            return log.error(f"eval run {args.use} reads its cases from --cases FILE", code=2)
        try:
            score = _cased(args, Path(args.cases))
        except (OSError, ValueError) as exc:
            return log.error(f"--cases {args.cases}: {exc}", code=2)
        return _scored(args, score)
    queries = args.wiring.catalog(("EvalQuery",)).all(EvalQuery)
    if not queries:
        return log.error("no EvalQuery records in the store: add them with `radar change apply`", code=2)
    return _scored(args, lambda: _queries(args, sorted(queries, key=lambda q: q.id)))

def register(commands: Commands) -> None:
    p = commands.verb("eval", "run",
                      help="score one use, read-only on the catalog: search's Hit@k and MRR, or the share of an AI "
                           "use's cases passed", func=run)
    p.add_argument("use", choices=("search", "ask", "solve", "draft", "datasheet"),
                   help="search and ask on the store's curated queries; draft on their targets; solve (application "
                        "problems) and datasheet on --cases")
    p.add_argument("--k", type=int, default=5, help="search: how many results count (default 5)")
    p.add_argument("--semantic", action="store_true", help="search: blend keyword with vector similarity")
    p.add_argument("--cases", help="datasheet: the eval set's file, fictional datasheets and the claims each states; "
                                   "solve: a catalog file of EvalQuery records, each a problem and the products its "
                                   "needs cite")
    p.add_argument("--floor", type=float, help="exit 1 when the score (Hit@k, or the share passed) is under this rate")
