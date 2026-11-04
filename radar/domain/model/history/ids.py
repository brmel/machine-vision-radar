from __future__ import annotations

import hashlib
import re

CROCKFORD_BASE32 = "0123456789abcdefghjkmnpqrstvwxyz"
ENTITY_ID = re.compile(r"[a-z]{3}_[0-9a-z]{10}")

def keyed(prefix: str, key: str) -> str:
    digest = int.from_bytes(hashlib.sha256(f"{prefix}:{key}".encode()).digest(), "big")
    return f"{prefix}_" + "".join(CROCKFORD_BASE32[(digest >> (5 * i)) & 31] for i in range(10))
