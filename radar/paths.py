import os
from pathlib import Path

DEV = Path(__file__).resolve().parent.parent

CONTRACTS = DEV / "contracts"
MODEL = CONTRACTS / "model"
DATA = (DEV / (os.environ.get("MVR_DATA") or "data")).resolve()
REGISTRY = DATA / "registry"
PROMPTS = DATA / "prompts"
NO_FILLER = DATA / "no_filler.json"
LANGUAGES = CONTRACTS / "languages.json"
GENERATED_MODEL_PY = DEV / "radar" / "domain" / "model" / "entities.py"
GENERATED_VIEWS_TS = DEV / "app" / "src" / "domain" / "views.ts"
GENERATED_VIEWS_ZOD = DEV / "app" / "src" / "adapters" / "generated-views-zod.ts"
GENERATED_MCP_TOOLS = DEV / "radar" / "adapters" / "web" / "mcp_tools.json"

DIST = DEV / "dist"

def firebase_project() -> str:
    import json
    projects = json.loads((DEV / ".firebaserc").read_text(encoding="utf-8")).get("projects", {})
    project = projects.get("default", "").strip()
    if not project:
        raise ValueError("Missing projects.default in .firebaserc")
    return project

def deployed_build() -> str | None:
    marker = DEV / "build"
    return marker.read_text(encoding="utf-8").strip() if marker.exists() else None

def site_origin() -> str:
    env_url = os.environ.get("MVR_SITE_URL", "").strip().rstrip("/")
    return env_url or f"https://{firebase_project()}.web.app"
