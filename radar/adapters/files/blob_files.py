from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from radar.domain.validation.context import KeptFile

def kept_files(root: Path) -> dict[str, KeptFile]:
    files: dict[str, KeptFile] = {}
    for f in sorted(root.glob("*/*.*")):
        content = f.read_bytes()
        files[f.parent.name + f.stem] = KeptFile(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content),
                                                 mime=mimetypes.guess_type(f.name)[0] or "")
    return files

def kept_path(root: Path, sha256: str) -> Path:
    found = sorted(root.glob(f"{sha256[:2]}/{sha256[2:]}.*"))
    if not found:
        raise FileNotFoundError(f"no kept file for {sha256}")
    return found[0]
