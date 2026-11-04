from __future__ import annotations

import json

from radar.adapters.files.model_json import load_registry, load_schema
from radar.paths import DEV

FIXTURE = DEV / "radar" / "tests" / "fixtures" / "canonical_corpus.json"
CORPUS = json.loads(FIXTURE.read_text(encoding="utf-8"))
SCHEMA = load_schema()
REGISTRY = load_registry(schema=SCHEMA)
