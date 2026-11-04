from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .. import paths
from ..domain.model.entities import IndexView, ProductView
from ..domain.search.retriever import value_text
from ..domain.ports.catalog.catalog_repository import CatalogRepository

def render_llms_txt(index: IndexView, base: str, language: str) -> str:
    counts = index.counts
    domains = {d.id: d.label.get(language, "") for d in index.domains}
    used = list(dict.fromkeys(domains[c.domain] for c in index.categories))
    lines = [
        "# Machine Vision Radar — llms.txt",
        "",
        "> All machine vision knowledge, in one place.",
        "",
        "## What this is",
        "",
        "Machine Vision Radar (`machineVisionRadar`) is an open, structured catalog of the machine",
        f"vision industry, in {len(used)} domains: {', '.join(used)}.",
        "Data is curated from vendor sources, validated by an executable contract, and published",
        "as one prerendered page per product.",
        "",
        "## The data",
        "",
        f"- {counts.products} products from {counts.organizations} organizations, in {counts.categories} categories",
        f"- Full catalog as markdown (one section per product): {base}/llms-full.txt",
        f"- One product: {base}/product/<slug>, a prerendered page that embeds its view as JSON",
        "  (`script#mvr-product`): specs with their current source, versions, offerings, lifecycle,",
        "  identifiers, relations and media",
        f"- The registry (categories, specs, units, vocabularies): {base}/read-model/registry.json",
        f"- News: {base}/news, each article's sentences citing the products, organizations and sources they rest on;",
        f"  the latest in an Atom feed, {base}/news/feed.atom, and a JSON Feed, {base}/news/feed.json",
        "",
        "## Taxonomy",
        "",
        "### Categories",
        "",
        *(f"- `{c.id}` — {c.label.get(language, '')}" for c in sorted(index.categories, key=lambda c: c.id)),
        "",
        "### Tags",
        "",
        *(f"- `{t.id}` — {t.label.get(language, '')}" for t in sorted(index.tags, key=lambda t: t.id)),
        "",
        "## How agents should consume it",
        "",
        f"- MCP server: POST /api/mcp, streamable HTTP under a bearer token; setup at {base}/agents.",
        "- Read llms-full.txt, or fetch the product pages you need over HTTPS.",
        "- Each spec row is `{key, value?, source?}`: `source` is the id of the one current source in the",
        "  product's `sources` list. A row without a value is not published.",
        "",
        "## Provenance and license",
        "",
        "- Every product lists its public `sources` with type, retrieval date and URL.",
        "- House rule: a missing product always beats a wrong one.",
        f"- Licence: {base}/terms states the data's licence and how to ask for commercial use.",
        "",
        "## Repository",
        "",
        "- The CLI reads the store: `python -m radar product get|search|compare`; `python -m radar store validate`.",
        "- Model contracts: `contracts/model/`.",
        "",
    ]
    return "\n".join(lines)

def render_llms_full_txt(index: IndexView, views: Sequence[ProductView], base: str, language: str) -> str:
    counts = index.counts
    tags = {t.id: t.label.get(language, "") for t in index.tags}
    labels = {k: d.label.get(language, "") for k, d in index.spec_definitions.items()}
    lines = [
        "# Machine Vision Radar — Full Catalog",
        "",
        f"> {counts.products} machine-vision products from {counts.organizations} organizations.",
        f"> Single-file markdown export for AI agents and LLM context. Source: the read model behind {base}",
        "",
    ]
    for v in sorted(views, key=lambda v: v.id):
        lines += _section(v, tags, labels, language)
    return "\n".join(lines)

def _section(v: ProductView, tags: Mapping[str, str], labels: Mapping[str, str], language: str) -> list[str]:
    lines = [f"## {v.name}", "", f"- ID: `{v.id}`", f"- Vendor: {v.vendor.name}", f"- Category: `{v.category}`",
             f"- URL: {v.website_url or ''}"]
    if v.tags:
        lines.append(f"- Tags: {', '.join(tags[t.id] for t in v.tags)}")
    if v.summary:
        lines.append(f"- Summary: {v.summary.get(language, '')}")
    cells = [(c.key, c.value) for c in (*v.core, *v.detail) if c.value is not None]
    if cells:
        lines.append("- Key specs:")
        lines += [f"  - {labels[key]}: {value_text(value, language)}" for key, value in cells]
    return [*lines, ""]

def write_llms(repo: CatalogRepository, out: Path, language: str, site_origin: str | None = None) -> int:
    index, base = repo.index(), (site_origin or paths.site_origin()).rstrip("/")
    views = repo.products([card.id for card in index.products])
    out.mkdir(parents=True, exist_ok=True)
    (out / "llms.txt").write_text(render_llms_txt(index, base, language) + "\n", encoding="utf-8")
    (out / "llms-full.txt").write_text(render_llms_full_txt(index, views, base, language) + "\n", encoding="utf-8")
    return len(views)
