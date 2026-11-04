from __future__ import annotations

import re
import subprocess

from radar.paths import DEV

MD_PATH = re.compile(r"(?<![\w/.:-])((?:\.\./|\./)?[\w.-]+(?:/[\w.-]+)*\.md)\b")
EXCLUDES = [":!**/package-lock.json"]

def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=DEV, capture_output=True, text=True)
    assert out.returncode in (0, 1), out.stderr
    return out.stdout.splitlines()

def test_every_md_path_resolves() -> None:
    broken = []
    for doc in _git("ls-files", "*.md"):
        here = (DEV / doc).parent
        for n, line in enumerate((DEV / doc).read_text(encoding="utf-8").splitlines(), 1):
            broken += [f"{doc}:{n}: {ref}" for ref in MD_PATH.findall(line)
                       if not any((base / ref).exists() for base in (DEV, DEV.parent, here))]
    assert not broken, "unresolved .md paths:\n" + "\n".join(broken)

def _grep(*args: str) -> list[str]:
    return [line for line in _git("grep", "-nI", *args, "--", *EXCLUDES) if ' d="' not in line]

def test_no_internal_codes() -> None:
    assert _grep("-E", r"(^|[^[:alnum:]_])(S[0-9]{1,2}|DM[0-9]|dm[0-9]|M[1-5]|M[V]P)([^[:alnum:]_]|$)") == []

def test_no_roadmap_paths() -> None:
    assert _grep("roadmap" + "/") == []

def test_no_hosting_domain_address() -> None:
    assert _grep("-iE", "[a-z0-9._+-]+" + "@[a-z0-9-]+\\.(web\\.app|firebaseapp\\.com)") == []
