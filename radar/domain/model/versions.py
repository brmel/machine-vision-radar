"""ProductVersion ordering per version scheme. Data-driven exception: each scheme is an ordering of its own, which the
in-memory catalog applies with no registry; registry_integrity holds the version_schemes vocabulary to these."""
from __future__ import annotations

import re
from typing import Callable, Sequence

from .entities import ProductVersion

def _numeric(v: ProductVersion) -> tuple[int, ...]:
    parts = re.findall(r"\d+", v.label)
    if not parts:
        raise ValueError(f"version '{v.label}' of {v.product} has no numeric part for scheme '{v.scheme}'")
    return tuple(int(p) for p in parts)

def _released(v: ProductVersion) -> str:
    if v.released is None:
        raise ValueError(f"version '{v.label}' of {v.product} uses scheme 'continuous' but has no released date")
    return v.released.value

def _supersedes_chain(versions: Sequence[ProductVersion]) -> list[ProductVersion]:
    by_id = {v.id: v for v in versions}
    successors = {v.supersedes: v for v in versions if v.supersedes in by_id}
    roots = [v for v in versions if v.supersedes not in by_id]
    if len(roots) != 1:
        raise ValueError(f"vendor scheme needs one supersedes chain, found {len(roots)} roots")
    chain = [roots[0]]
    while chain[-1].id in successors:
        chain.append(successors[chain[-1].id])
    if len(chain) != len(versions):
        raise ValueError("vendor scheme: supersedes chain does not cover every version")
    return chain

_ORDERS: dict[str, Callable[[Sequence[ProductVersion]], list[ProductVersion]]] = {
    "semver": lambda vs: sorted(vs, key=_numeric),
    "calver": lambda vs: sorted(vs, key=_numeric),
    "continuous": lambda vs: sorted(vs, key=_released),
    "vendor": _supersedes_chain,
}

def order(versions: Sequence[ProductVersion]) -> list[ProductVersion]:
    if not versions:
        return []
    schemes = {v.scheme for v in versions}
    if len(schemes) != 1:
        raise ValueError(f"versions of {versions[0].product} mix schemes {sorted(schemes)}")
    scheme = schemes.pop()
    if scheme not in _ORDERS:
        raise ValueError(f"no ordering for version scheme '{scheme}'")
    return _ORDERS[scheme](versions)

SCHEMES = frozenset(_ORDERS)
