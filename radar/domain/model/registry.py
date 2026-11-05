from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Collection, Mapping, Sequence

from .entities import (AiSettings, Category, CategoryProfile, Dimension, FeedSettings, Product, SearchSettings,
                       SpecDefinition, SpecGroup, Term, Unit)

RegistryItem = Term | Unit | Dimension | SpecDefinition | Category | SpecGroup

def composed(profile: CategoryProfile, groups: Mapping[str, SpecGroup]) -> CategoryProfile:
    own = (*profile.sections.core, *profile.sections.detail)
    taken = [k for g in profile.groups for k in groups[g].specs]
    twice = sorted({k for k in (*own, *taken) if [*own, *taken].count(k) > 1} - set(profile.sections.core))
    if twice:
        raise ValueError(f"profile {profile.category_id}: specs both its own and a group's, or in two groups: {twice}")
    detail = (*profile.sections.detail, *(k for k in taken if k not in profile.sections.core))
    return replace(profile, sections=replace(profile.sections, detail=detail))

@dataclass(frozen=True, slots=True)
class Language:
    code: str
    label: str
    name: str
    dir: str
    intl: str
    default: bool
    decimal: str
    sentence: str = ""
    yes: str = ""
    no: str = ""

@dataclass(frozen=True, slots=True)
class Banned:
    pattern: str
    reason: str

@dataclass(frozen=True, slots=True)
class Filler:
    placeholders: tuple[Banned, ...]
    anywhere: tuple[Banned, ...]

@dataclass(frozen=True, slots=True)
class Registry:
    units: Mapping[str, Unit]
    dimensions: Mapping[str, Dimension]
    spec_definitions: Mapping[str, SpecDefinition]
    categories: Mapping[str, Category]
    spec_groups: Mapping[str, SpecGroup]
    profiles: tuple[CategoryProfile, ...]
    vocabularies: Mapping[str, Mapping[str, Term]]
    search: SearchSettings
    feed: FeedSettings
    ai: AiSettings
    filler: Filler
    languages: tuple[Language, ...] = ()

    @property
    def default_language(self) -> Language:
        return next((l for l in self.languages if l.default), self.languages[0])

    def items(self, name: str) -> Mapping[str, RegistryItem]:
        special = {"units": self.units, "dimensions": self.dimensions, "spec_definitions": self.spec_definitions,
                   "categories": self.categories, "spec_groups": self.spec_groups}
        found = special.get(name) or self.vocabularies.get(name)
        if found is None:
            raise KeyError(f"unknown registry '{name}'")
        return found

    def converted(self, value: float, unit: str, to: str) -> float:
        if unit == to:
            return value
        return float(f"{value * self.units[unit].factor / self.units[to].factor:.12g}")

    def marked(self, vocabulary: str, mark: Callable[[Term], bool | None]) -> frozenset[str]:
        return frozenset(i for i, t in self.vocabularies[vocabulary].items() if mark(t))

    def has(self, name: str) -> bool:
        return (name in ("units", "dimensions", "spec_definitions", "categories", "spec_groups")
                or name in self.vocabularies)

    def profile(self, category: str) -> CategoryProfile:
        return next(p for p in self.profiles if p.category_id == category)

    def keys(self, product: Product) -> frozenset[str]:
        sections = self.profile(product.category).sections
        return frozenset((*sections.core, *sections.detail, *self.group_specs(product.spec_groups or ())))

    def unstated(self, product: Product, stated: Collection[str]) -> tuple[str, ...]:
        return tuple(k for k in self.profile(product.category).required if k not in stated)

    def group_specs(self, groups: Sequence[str]) -> tuple[str, ...]:
        return tuple(k for g in groups for k in self.spec_groups[g].specs)

    def group_of(self, groups: Sequence[str], key: str) -> str | None:
        return next((g for g in groups if key in self.spec_groups[g].specs), None)

    def proposal_kinds(self) -> dict[str, str]:
        return {t.files_on: t.id for t in self.vocabularies["proposal_kinds"].values() if t.files_on}
