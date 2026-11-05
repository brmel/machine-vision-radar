from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radar import paths
from radar.domain.model.entities import AiSettings, CategoryProfile, CLASSES, FeedSettings, SearchSettings
from radar.domain.model.model import Model, ParseError, Parser
from radar.domain.model.registry import Banned, Filler, Language, Registry, composed
from radar.domain.model.schema import ModelSchema, parse_schema
from radar.adapters.files.json_parser import read_json

PROFILES_DIR = "category_profiles"

LANGUAGES: tuple[Language, ...] = tuple(Language(**item)
                                        for item in json.loads(paths.LANGUAGES.read_text(encoding="utf-8")))
DEFAULT_LANGUAGE: Language = next(l for l in LANGUAGES if l.default)

def load_filler() -> Filler:
    raw = json.loads(paths.NO_FILLER.read_text(encoding="utf-8"))
    return Filler(**{group: tuple(Banned(**item) for item in raw[group]) for group in ("placeholders", "anywhere")})

def load_schema(model_dir: Path | None = None) -> ModelSchema:
    def read(name: str) -> Any:
        return json.loads(((model_dir or paths.MODEL) / f"{name}.json").read_text(encoding="utf-8"))
    return parse_schema(read("value_types"), read("registry_types"), read("entities"), read("views"), read("tools"))

def _read(path: Path) -> Any:
    if not path.exists():
        raise ParseError(f"registry file not found: {path}")
    return read_json(path)

def _items(parser: Parser, type_name: str, path: Path) -> dict[str, Any]:
    raw = _read(path)
    if not isinstance(raw, list):
        raise ParseError(f"{path.name}: expected an array of {type_name}")
    out: dict[str, Any] = {}
    for i, item in enumerate(raw):
        obj = parser.parse(item, CLASSES[type_name], f"{path.name}[{i}]")
        if obj.id in out:
            raise ParseError(f"{path.name}: duplicate id '{obj.id}'")
        out[obj.id] = obj
    return out

def _registry(reg_dir: Path, schema: ModelSchema) -> Registry:
    parser = Parser(schema)
    files = {t.registry_file: t.name for t in schema.registry_types if t.registry_file}
    special = {f: _items(parser, t, reg_dir / f) for f, t in files.items() if not f.endswith("/")}
    profiles_dir = reg_dir / PROFILES_DIR
    if not profiles_dir.is_dir():
        raise ParseError(f"registry directory not found: {profiles_dir}")
    groups = special["spec_groups.json"]
    try:
        profiles = tuple(composed(parser.parse(_read(p), CategoryProfile, f"{PROFILES_DIR}/{p.name}"), groups)
                         for p in sorted(profiles_dir.glob("*.json")))
    except (KeyError, ValueError) as exc:
        raise ParseError(f"{PROFILES_DIR}: {exc}") from exc
    return Registry(
        units=special["units.json"], dimensions=special["dimensions.json"],
        spec_definitions=special["spec_definitions.json"], categories=special["categories.json"], spec_groups=groups,
        profiles=profiles,
        vocabularies={p.stem: _items(parser, "Term", p)
                      for p in sorted((reg_dir / "vocabularies").glob("*.json"))},
        search=parser.parse(_read(reg_dir / "search.json"), SearchSettings, "search.json"),
        feed=parser.parse(_read(reg_dir / "feed.json"), FeedSettings, "feed.json"),
        ai=parser.parse(_read(reg_dir / "ai.json"), AiSettings, "ai.json"),
        filler=load_filler(),
        languages=LANGUAGES,
    )

def load_model(reg_dir: Path | None = None) -> Model:
    schema = load_schema()
    return Model(schema, _registry(reg_dir or paths.REGISTRY, schema))
