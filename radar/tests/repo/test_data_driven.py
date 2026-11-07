"""No registry id or organization name is a quoted literal in app/src, app/scripts or radar/, but a HOMONYMS entry, or
in an ALLOWLIST file a line under a `Data-driven exception: <why>` comment (or any, with one in its first 3 lines)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from radar import paths
from radar.tests.repo.test_layout import GENERATED, _repo_files

REGISTRY = paths.REGISTRY
ROOTS = ("app/src/", "app/scripts/", "app/studio/", "radar/")
SKIPPED = ("radar/tests/", *GENERATED)
SUFFIXES = (".py", ".ts", ".tsx", ".sh")
MARK = "Data-driven exception:"
QUOTED = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'|`([^`\n]*)`")
ARIA = re.compile(r"\b(?:role|aria-[a-z]+)=\"[^\"]*\"")

HOMONYMS: dict[str, tuple[str, ...]] = {
    "article": ("app/scripts/prerender/news.ts", "app/src/features/home/news/ArticleView.tsx",
                "app/src/shell/root/App.tsx", "app/src/shell/routing/RouteView.tsx", "app/src/shell/routing/router.ts",
                "app/src/shell/routing/routes.ts", "app/src/shell/seo/news.ts", "app/src/shell/seo/seo.ts",
                "app/src/ui/page/Card.tsx", "app/src/ui/data/ProductCard.tsx", "radar/adapters/web/admin/news.py",
                "radar/adapters/web/pages.py", "radar/commands/review/feed.py", "radar/domain/review/feed/editor.py"),
    "capabilities": ("radar/adapters/web/mcp.py",),
    "catalog": ("app/src/features/browse/hooks/useBrowse.ts", "app/src/shell/admin/AdminView.tsx",
                "app/studio/clips/templates.ts", "app/studio/render.ts", "radar/adapters/console/parser.py",
                "radar/commands/catalog/ask.py", "radar/commands/store/store.py"),
    "code": ("radar/adapters/web/mcp.py",),
    "datasheet": ("radar/commands/catalog/evaluation.py",),
    "end_of_support": ("app/src/features/product-detail/components/ProductLifecycle.tsx",),
    "family": ("app/src/features/product-detail/header/ProductLinks.tsx",),
    "form": ("radar/adapters/web/pages.py",),
    "image": ("radar/adapters/web/pages.py",),
    "model": ("app/src/adapters/review/HttpAdminApi.ts", "app/src/features/admin/search/settings/KnobsTable.tsx",
              "app/src/features/admin/search/settings/UseForm.tsx", "app/src/shell/admin/AdminView.tsx",
              "radar/adapters/ai/runners/chat_completions.py", "radar/adapters/ai/search/fastembed_embedder.py",
              "radar/adapters/console/parser.py", "radar/adapters/web/admin/endpoint.py",
              "radar/adapters/web/admin/search.py", "radar/commands/build/gen_model.py",
              "radar/commands/data/validate.py", "radar/paths.py"),
    "press": ("app/src/ui/theme/brand.ts",),
    "released": ("app/src/features/product-detail/components/ProductLifecycle.tsx",),
    "ul": ("radar/adapters/web/pages.py",),
    "vendor": ("app/src/adapters/read-model/firestore.ts",
               "app/src/domain/filtering/browseView.ts", "app/src/domain/filtering/filterUrl.ts",
               "app/src/domain/ports/CatalogRepository.ts", "radar/adapters/ai/prompted/answer_model.py",
               "radar/domain/read_model/listings.py",
               "radar/adapters/ai/search/records.py",
               "radar/domain/search/hits.py",
               "radar/domain/validation/rules/registry/registry_integrity.py"),
    "website": ("app/src/shell/seo/hubs.ts", "app/src/shell/seo/seo.ts"),
}

ALLOWLIST: dict[str, str] = {
    "radar/domain/model/catalog.py": "each version scheme is an ordering of its own, which the in-memory catalog "
                                      "applies with no registry; "
                                      "registry_integrity holds the vocabulary to the schemes it orders",
    "radar/domain/read_model/products/views.py": "a model's page links its parent as its family",
    "radar/domain/validation/rules/catalog/variant_axes.py": "family, model and variant are the levels of the product "
                                                             "tree, not a list the registry grows",
    "radar/domain/validation/rules/sources/source_preference.py": "the rule weighs the two kinds of evidence it names: "
                                                                  "a datasheet's and an inherited record's",
}

def registry_ids() -> set[str]:
    def read(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def ids(items: list[dict[str, str]]) -> set[str]:
        return {item["id"] for item in items}
    terms = {i for p in (REGISTRY / "vocabularies").glob("*.json") for i in ids(read(p))}
    models = ids(read(REGISTRY / "ai.json")["models"]) | {read(REGISTRY / "search.json")["model"]}
    return ids(read(REGISTRY / "categories.json")) | ids(read(REGISTRY / "spec_definitions.json")) | terms | models

def _files() -> list[str]:
    return [f for f in _repo_files() if f.startswith(ROOTS) and f.endswith(SUFFIXES) and not f.startswith(SKIPPED)]

def hits(terms: set[str]) -> list[tuple[str, int, str, bool]]:
    found = []
    for path in _files():
        lines = (paths.DEV / path).read_text(encoding="utf-8").splitlines()
        file_marked = any(MARK in line for line in lines[:3])
        for i, line in enumerate(lines):
            for match in QUOTED.finditer(ARIA.sub("", line)):
                literal = next(g for g in match.groups() if g is not None)
                if literal in terms:
                    found.append((path, i + 1, literal, file_marked or (i > 0 and MARK in lines[i - 1])))
    return found

def test_no_registry_id_is_hard_coded() -> None:
    bad = [f"{p}:{n}: '{t}'" for p, n, t, marked in hits(registry_ids()) if p not in HOMONYMS.get(t, ())
           and not (p in ALLOWLIST and marked)]
    assert not bad, (
        f"registry ids written in code (derive them from the registry, or allowlist and mark the line): {bad}")

def test_every_allowlist_entry_and_homonym_is_still_needed() -> None:
    found = {(p, t) for p, _, t, _ in hits(registry_ids())}
    stale = sorted(set(ALLOWLIST) - {p for p, t in found if p not in HOMONYMS.get(t, ())})
    stale += sorted(f"{t} in {p}" for t, files in HOMONYMS.items() for p in files if (p, t) not in found)
    assert not stale, f"allowlist entries or homonyms with no hit left: {stale}"

def test_no_organization_is_named_in_code_or_the_registry() -> None:
    fixtures = paths.DEV / "radar" / "tests" / "fixtures"
    category = json.loads((fixtures / "fixture_category.json").read_text(encoding="utf-8"))
    orgs = [*json.loads((fixtures / "canonical_corpus.json").read_text(encoding="utf-8"))["organizations"],
            *category["data"]["organizations.jsonl"]]
    named = {o[k] for o in orgs for k in ("name", "slug")}
    in_registry = [f"{f.relative_to(paths.DEV)}: {n}" for f in sorted(REGISTRY.rglob("*.json")) for n in named
                   if json.dumps(n) in f.read_text(encoding="utf-8")]
    assert not hits(named) and not in_registry, (
        f"an organization named in code or the registry: {hits(named) + in_registry}")

def test_no_language_code_is_hard_coded() -> None:
    from radar.adapters.files.model_json import LANGUAGES
    codes = [l.code for l in LANGUAGES]
    pattern = re.compile(rf"""["'`]\b(?:{"|".join(codes)})\b["'`]""")
    bad = []
    for p in sorted((paths.DEV / "radar").rglob("*.py")):
        if "tests" in p.parts or str(p.relative_to(paths.DEV)) in GENERATED:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                bad.append(f"{p.relative_to(paths.DEV)}:{i}: {line.strip()}")
    assert not bad, f"language codes written in code: {bad}"

def test_third_language_added_to_contract_needs_no_code_change() -> None:
    from radar.domain.model.registry import Language
    from radar.domain.read_model.facets import value_options
    de = Language("de", "DE", "Deutsch", "ltr", "de-DE", False, ",", "{name} ist in {category}, von {vendor}.")
    [(_, labels, _)] = value_options({"quantity": {"value": 3.5}}, (de,))
    assert labels["de"] == "3,5"
