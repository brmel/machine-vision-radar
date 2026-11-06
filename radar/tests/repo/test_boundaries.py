import ast
import re
from collections import Counter
from pathlib import Path
from typing import Iterator

from radar.paths import DEV
from radar.tests.repo.test_architecture import _base_name, _imported_modules, _reach

RADAR = DEV / "radar"
APP_SRC = DEV / "app" / "src"
STUDIO = DEV / "app" / "studio"
ANY, REFLECTION, JSON_TEXT, AS_CAST = "Any", "getattr or hasattr", "JSON text", "as cast"
UNTYPED: dict[str, dict[str, int]] = {
    ANY: {
        "radar/domain/model/history/changeset.py": 4,
        "radar/domain/model/history/projection.py": 12,
        "radar/domain/ports/ai/research_agent.py": 1,
        "radar/domain/ports/catalog/held_records.py": 1,
        "radar/domain/ports/catalog/views.py": 2,
        "radar/domain/ports/history/version_store.py": 3,
        "radar/domain/ports/review/feed_reads.py": 1,
        "radar/domain/ports/store/docs.py": 5,
        "radar/domain/ports/web/endpoint.py": 1,
        "radar/domain/read_model/derived/identity.py": 2,
        "radar/domain/read_model/derived/provenance.py": 1,
        "radar/domain/read_model/facets.py": 6,
        "radar/domain/read_model/history.py": 2,
        "radar/domain/read_model/listings.py": 6,
        "radar/domain/read_model/read_model.py": 1,
        "radar/domain/review/agents/drafts.py": 7,
        "radar/domain/review/agents/duplicates.py": 5,
        "radar/domain/review/feed/detector.py": 2,
        "radar/domain/review/feed/editor.py": 3,
        "radar/domain/review/feed/news.py": 1,
        "radar/domain/search/hits.py": 1,
        "radar/domain/search/sources.py": 2,
    },
    REFLECTION: {
        "radar/domain/model/history/projection.py": 1,
        "radar/domain/read_model/products/views.py": 1,
        "radar/domain/validation/rules/registry/registry_integrity.py": 2,
        "radar/domain/validation/walk.py": 2,
    },
    JSON_TEXT: {
        "radar/adapters/firestore/repository.py": 2,
        "radar/domain/read_model/history.py": 2,
        "radar/domain/review/views.py": 3,
    },
    AS_CAST: {
        "app/src/adapters/read-model/files.ts": 1,
        "app/src/adapters/read-model/firestore.ts": 1,
        "app/src/domain/views.ts": 1,
        "app/src/features/admin/news/article.ts": 1,
        "app/src/shell/i18n/index.tsx": 1,
        "app/src/ui/feedback/useRead.ts": 1,
    },
}
SEAM_CALLS = {"getattr": REFLECTION, "hasattr": REFLECTION, "json_text": JSON_TEXT}
PROVIDERS = re.compile(
    r"^(firebase|firebase_admin|firebase_functions|google\.cloud|google\.auth|google\.oauth2|googleapiclient|"
    r"google\.adk|google\.genai|fastembed|mcp|requests|httpx|urllib\.request|http\.client)(\.|$)")
SDK_HOMES = {re.compile(r"^(google\.adk|google\.genai)(\.|$)"): {"radar/adapters/ai/adk/runner.py"},
             re.compile(r"^(google\.oauth2|google\.auth)(\.|$)"): {
                 "radar/adapters/ai/adk/runner.py", "radar/adapters/web/admin/identity.py"},
             re.compile(r"^fastembed(\.|$)"): {"radar/adapters/ai/search/fastembed_embedder.py"},
             re.compile(r"^firebase_functions(\.|$)"): {"radar/adapters/web/function.py"},
             re.compile(r"^mcp(\.|$)"): set()}

def provider_imports(source: str) -> list[str]:
    names = [a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for a in n.names]
    names += [f"{n.module}.{a.name}" for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) and n.module
              for a in n.names]
    return [m for m in names if PROVIDERS.match(m)]

def test_only_adapters_import_a_provider_sdk() -> None:
    fixture = ("from google.cloud import firestore\nimport firebase_admin\nimport fastembed\nimport requests\n"
               "import httpx\nfrom urllib import request\nimport urllib.request\nfrom google import genai\n"
               "from mcp.server import FastMCP\n")
    assert sorted(provider_imports(fixture)) == ["fastembed", "firebase_admin", "google.cloud.firestore",
                                                 "google.genai", "httpx", "mcp.server.FastMCP", "requests",
                                                 "urllib.request", "urllib.request"]
    offenders = [str(p.relative_to(DEV)) for p in sorted(RADAR.rglob("*.py"))
                 if "adapters" not in p.parts and "tests" not in p.parts
                 and provider_imports(p.read_text(encoding="utf-8"))]
    assert not offenders, f"provider SDK imported outside radar/adapters/: {offenders}"

def test_each_search_sdk_stays_in_its_one_adapter() -> None:
    offenders = [f"{p.relative_to(DEV)}: {m}" for p in sorted(RADAR.rglob("*.py")) if "tests" not in p.parts
                 for m in provider_imports(p.read_text(encoding="utf-8"))
                 for sdk, homes in SDK_HOMES.items() if sdk.match(m) and str(p.relative_to(DEV)) not in homes]
    assert not offenders, f"an SDK imported outside its adapter: {offenders}"

ENGINE = ("radar", "adapters", "ai", "search")

def engine_imports(source: str) -> list[str]:
    names = [a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) and n.module]
    return [m for m in names if tuple(m.split("."))[:4] == ENGINE]

def test_past_the_wiring_the_search_engine_is_reached_by_its_port_only() -> None:
    assert engine_imports("from radar.adapters.ai.search.engine import ShardedSearch\nimport "
                          "radar.domain.search\n") == ["radar.adapters.ai.search.engine"]
    offenders = [f"{p.relative_to(DEV)}: {m}" for p in sorted(RADAR.rglob("*.py")) if "tests" not in p.parts
                 and p.relative_to(DEV).parts[:4] != ENGINE
                 and p.relative_to(DEV).parts[:3] != ("radar", "adapters", "wiring")
                 for m in engine_imports(p.read_text(encoding="utf-8"))]
    assert not offenders, f"the search engine's modules imported past the wiring: {offenders}"

DOMAIN_SERVICES = {"Drafter", "IndexRetriever", "MemoryCatalog", "Model", "Projection", "Review"}
COMMANDS_ON_ADAPTERS = {"radar/commands/store/store.py", "radar/build/codegen/__init__.py"}

def _classes(path: Path) -> Iterator[ast.ClassDef]:
    return (n for n in ast.parse(path.read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef))

def port_implementations(ports: dict[str, set[str]], path: Path) -> list[str]:
    return [c.name for c in _classes(path) for methods in ports.values()
            if methods <= {f.name for f in c.body if isinstance(f, ast.FunctionDef)}]

def test_no_storage_or_provider_implementation_sits_in_the_domain() -> None:
    ports = {c.name: {f.name for f in c.body if isinstance(f, ast.FunctionDef) and not f.name.startswith("_")}
             for p in (RADAR / "domain" / "ports").rglob("*.py") for c in _classes(p)
             if any(getattr(b, "id", None) == "Protocol" for b in c.bases)}
    found = {name for p in (RADAR / "domain").rglob("*.py") if "ports" not in p.parts
             for name in port_implementations({k: v for k, v in ports.items() if v}, p)}
    assert found - DOMAIN_SERVICES == set(), (
        f"a port implemented in radar/domain/: move it to radar/adapters/: {sorted(found - DOMAIN_SERVICES)}")
    assert DOMAIN_SERVICES - found == set(), f"DOMAIN_SERVICES only shrinks: drop {sorted(DOMAIN_SERVICES - found)}"

def test_a_port_names_no_storage_path_and_encodes_no_json() -> None:
    ports = RADAR / "domain" / "ports"
    blob_args = {a.arg for c in _classes(ports / "store" / "blob_store.py") for f in c.body
                 if isinstance(f, ast.FunctionDef) for a in f.args.args}
    assert "path" not in blob_args, "the BlobStore port takes a path"
    assert [str(p.relative_to(DEV)) for p in ports.rglob("*.py") if "json" in _imported_modules(p)] == []

def test_commands_reach_adapters_through_the_wiring() -> None:
    allowed = ("radar.adapters.console", "radar.adapters.wiring")
    offenders = [f"{p.relative_to(DEV)}: {m}"
                 for p in sorted([*(RADAR / "commands").rglob("*.py"), *(RADAR / "build").rglob("*.py")])
                 if str(p.relative_to(DEV)) not in COMMANDS_ON_ADAPTERS for m in sorted(_imported_modules(p))
                 if m.startswith("radar.adapters") and not m.startswith(allowed)]
    assert not offenders, f"a command imports an adapter: take it from args.wiring: {offenders}"

def _app_lines(*roots: Path) -> Iterator[tuple[str, str, str]]:
    for f in (f for root in roots or (APP_SRC,) for f in root.rglob("*")):
        if f.suffix in (".ts", ".tsx"):
            lines = f.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                yield f"{f.relative_to(DEV)}:{i + 1}", line, lines[i - 1] if i else ""

def test_app_never_imports_contracts() -> None:
    import_re = re.compile(r"^\s*(import|export)[^'\"]*['\"]([^'\"]*contracts/[^'\"]*)['\"]")
    offenders = [at for at, line, _ in _app_lines() if import_re.search(line)
                 and "contracts/languages.json" not in line]
    assert not offenders, f"app/ imports contracts/ directly: {offenders}"

def test_no_hash_routes() -> None:
    offenders = [at for at, line, _ in _app_lines() if "#/" in line]
    assert not offenders, f"hash routes found (use real URLs + prerendering): {offenders}"

CAST = re.compile(r"\bas\s+[A-Z{\[]")

def _code_lines() -> list[tuple[str, str, str]]:
    return [(at, line, above) for at, line, above in _app_lines(APP_SRC, STUDIO) if "generated" not in at
            and not line.strip().startswith(("//", "*", "import "))]

def test_ts_domain_casts_and_records_guarded() -> None:
    code = _code_lines()
    record_offenders = [at for at, line, _ in code if "Record<string, unknown>" in line]
    cast_offenders = [f"{at}: {line.strip()}" for at, line, above in code if CAST.search(line)
                      and "Justification (typed boundary):" not in above]
    assert not record_offenders, f"Record<string, unknown> in domain paths: {record_offenders}"
    assert not cast_offenders, f"Unjustified `as` cast in production TS: {cast_offenders}"

def _seam(node: ast.AST) -> str | None:
    if isinstance(node, (ast.Name, ast.Attribute)) and _base_name(node) == "Any":
        return ANY
    return SEAM_CALLS.get(_base_name(node.func)) if isinstance(node, ast.Call) else None

def _untyped() -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {kind: Counter() for kind in UNTYPED}
    for path in sorted(p for p in RADAR.rglob("*.py") if "tests" not in p.relative_to(RADAR).parts):
        at, domain = str(path.relative_to(DEV)), path.is_relative_to(RADAR / "domain")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (kind := _seam(node)) and (domain or kind == JSON_TEXT):
                counts[kind][at] += 1
    counts[AS_CAST].update(at.rsplit(":", 1)[0] for at, line, _ in _code_lines() if CAST.search(line))
    return counts

def test_untyped_seams_only_fall() -> None:
    counts = _untyped()
    moved = [(counts[kind][at] - pins.get(at, 0), f"{at}: {counts[kind][at]} {kind}, pinned at {pins.get(at, 0)}")
             for kind, pins in UNTYPED.items() for at in sorted(pins.keys() | counts[kind].keys())
             if counts[kind][at] != pins.get(at, 0)]
    rose = [line for by, line in moved if by > 0]
    assert not rose, f"untyped seams rose; type what crosses there instead: {rose}"
    assert not moved, (
        f"untyped seams fell; lower each pin in UNTYPED to its count in this commit: {[line for _, line in moved]}")

DOC_WRITER = "radar/adapters/firestore/"

def _calling(pattern: str) -> set[str]:
    return {str(p.relative_to(DEV)) for p in RADAR.rglob("*.py") if "tests" not in p.parts
            and re.search(pattern, p.read_text(encoding="utf-8"))}

def test_the_review_queue_is_the_only_way_in() -> None:
    writers = _calling(r"(?<!def )\bcommit\(")
    assert writers and all(w.startswith(DOC_WRITER) for w in writers), (
        f"documents written outside {DOC_WRITER}: {sorted(writers)}")
    assert _calling(r"store\.write\(") == {"radar/domain/review/review.py", "radar/commands/store/change.py"}
    assert _calling(r"\.decide\(") == {"radar/commands/review/proposals.py", "radar/commands/review/caps.py",
                                       "radar/adapters/web/admin/endpoint.py", "radar/adapters/web/admin/search.py",
                                       "radar/domain/review/feed/editor.py"}
    assert not _calling(r"auto[_-]?approv"), "no auto-approve path or setting"
    assert _calling(r"blobs\.publish\(") == {"radar/adapters/firestore/writer.py"}, (
        "a file turns public by its rights only")

FOUNDER_ONLY = {"CatalogStore", "decide", "commit"}

def _founder_only(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    return FOUNDER_ONLY & (names | attributes | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})

def _agent_facing() -> list[Path]:
    research = [p for p in RADAR.rglob("*.py") if "tests" not in p.parts
                and "research" in p.relative_to(RADAR).with_suffix("").parts]
    return [RADAR / "adapters" / "web" / "mcp.py", RADAR / "commands" / "review" / "mcp.py", *research]

def test_agent_facing_code_cannot_reach_the_catalog_writer_a_decision_or_a_document_write() -> None:
    assert set().union(*map(_founder_only, _reach(RADAR / "adapters" / "web" / "admin" / "endpoint.py"))) == {
        "CatalogStore", "decide"}
    assert set().union(*map(_founder_only, _reach(RADAR / "adapters" / "wiring" / "stores.py"))) == FOUNDER_ONLY
    offenders = sorted(f"{start.relative_to(DEV)} reaches {path.relative_to(DEV)}: {sorted(names)}"
                       for start in _agent_facing() for path in _reach(start) if (names := _founder_only(path)))
    assert not offenders, "agent-facing code reaches what only the founder does:\n" + "\n".join(offenders)

def test_only_the_founder_starts_a_research_run_or_an_ai_draft() -> None:
    assert _calling(r"\bResearcher\(") == _calling(r"\bDrafter\(") == {"radar/adapters/wiring/root.py"}
    assert _calling(r"drafter\(\)\.draft\(") == {"radar/commands/review/feed.py", "radar/adapters/web/admin/news.py"}
    assert _calling(r"\.draft_meter\(\)") == {"radar/adapters/wiring/root.py", "radar/commands/catalog/evaluation.py"}
    assert _calling(r"\.researcher\b") == {"radar/adapters/wiring/root.py", "radar/commands/review/research.py"}
    assert _calling(r"\bresearch\.start\(") == {"radar/commands/review/research.py",
                                                "radar/adapters/web/admin/research.py"}
    assert (not _calling(r"scheduler_fn|on_schedule|\bcron\b")
            and "schedule" not in (DEV / "firebase.json").read_text(encoding="utf-8"))
