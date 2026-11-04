import ast
import re
import io
import subprocess
import tokenize
from pathlib import PurePosixPath

from radar.paths import DEV

GENERATED = {
    "radar/domain/model/entities.py", "app/src/domain/views.ts", "app/src/adapters/generated-views-zod.ts",
    "app/package-lock.json", "radar/adapters/web/mcp_tools.json",
}
CONTRACT_DATA = {
    "contracts/operations.json",
    "contracts/model/entities.json",
    "contracts/model/views.json",
}

CODE_ROOTS = ("app/src/", "app/scripts/", "app/studio/", "app/tests/", "radar/", "contracts/")
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".json", ".sh"}
PACKAGE_MARKERS = {"__init__.py", "__main__.py"}
BANNED_FOLDER_NAMES = {"utils", "misc", "helpers", "common", "lib", "config"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf"}

def _repo_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=DEV, capture_output=True, text=True,
                         check=True).stdout
    return [f for f in out.splitlines() if (DEV / f).is_file()]

def test_no_file_over_300_lines() -> None:
    offenders = [f for f in _repo_files() if PurePosixPath(f).suffix not in BINARY_SUFFIXES
                 and f not in GENERATED | CONTRACT_DATA and not f.startswith("data/")
                 and len((DEV / f).read_text(encoding="utf-8").splitlines()) > 300]
    assert not offenders, f"files over 300 lines: {offenders}"

WIDTH_SUFFIXES = {".py", ".ts", ".tsx", ".sh"}

def test_no_line_over_120_columns() -> None:
    files = [f for f in _repo_files() if (PurePosixPath(f).suffix in WIDTH_SUFFIXES or f.startswith(".githooks/"))
             and f not in GENERATED]
    offenders = [f"{f}:{n}" for f in files
                 for n, line in enumerate((DEV / f).read_text(encoding="utf-8").splitlines(), 1) if len(line) > 120]
    assert not offenders, f"lines over 120 characters: {len(offenders)}, first {offenders[:5]}"

def test_no_code_folder_over_7_entries() -> None:
    entries: dict[str, set[str]] = {}
    for path in map(PurePosixPath, _repo_files()):
        if str(path).startswith(CODE_ROOTS) and path.name not in PACKAGE_MARKERS and path.suffix in SOURCE_SUFFIXES:
            for parent, child in zip(path.parents, (path, *path.parents)):
                entries.setdefault(str(parent), set()).add(child.name)
    offenders = {folder: len(names) for folder, names in entries.items()
                 if folder.startswith(tuple(r.rstrip("/") for r in CODE_ROOTS)) and len(names) > 7}
    assert not offenders, f"code folders over 7 entries: {offenders}"

def test_no_banned_folder_names() -> None:
    offenders = sorted({str(p) for f in _repo_files() for p in PurePosixPath(f).parents
                        if p.name in BANNED_FOLDER_NAMES})
    assert not offenders, f"banned folder names: {offenders}"

TOP_LEVEL = {"app", "radar", "contracts", "data", "docs", ".claude", ".github", ".githooks", ".firebaserc",
             ".gitignore", ".nvmrc", "AGENTS.md", "CLAUDE.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "LICENSE",
             "README.md", "SECURITY.md", "firebase.json", "package.json"}

def test_the_root_holds_only_the_code_folders_and_the_files_tools_require() -> None:
    tracked = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=DEV,
                             capture_output=True, text=True, check=True).stdout.splitlines()
    extra = {f.split("/")[0] for f in tracked} - TOP_LEVEL
    assert not extra, f"top-level entries outside {sorted(TOP_LEVEL)}: {sorted(extra)}"

DATA_PATH_OWNERS = {"radar/paths.py", "app/scripts/head.ts", "app/studio/clips/script.ts"}
LOCATING = re.compile(r"\.\./(?:\.\./)*" + r"data/(?:registry|prompts|no_filler)|environ\.get\(\"MVR_" + r"DATA|"
                      r"process\.env\.MVR_" + "DATA")

def test_only_the_path_modules_locate_the_data_folder() -> None:
    offenders = [f for f in _repo_files() if f.startswith(CODE_ROOTS) and PurePosixPath(f).suffix in SOURCE_SUFFIXES
                 and f not in DATA_PATH_OWNERS and LOCATING.search((DEV / f).read_text(encoding="utf-8"))]
    assert not offenders, f"locate the data folder through paths.DATA or head.ts's DATA: {offenders}"

MARKS = re.compile(r"Justification \(typed boundary\)|Data-driven exception:|noqa|type: ignore|<reference|"
                   r"@vitest-environment|@ts-|eslint-")
TS_COMMENT = re.compile(r"^\s*(//|/\*|\*)")

def _py_comments(text: str) -> list[int]:
    found = [t.start[0] for t in tokenize.generate_tokens(io.StringIO(text).readline)
             if t.type == tokenize.COMMENT and not MARKS.search(t.string)]
    for node in ast.walk(ast.parse(text)):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str) and not MARKS.search(body[0].value.value)):
            found.append(body[0].lineno)
    return found

def test_no_comments_but_the_guards_marks() -> None:
    found = []
    for f in _repo_files():
        if not f.startswith(CODE_ROOTS) or f in GENERATED or not f.endswith((".py", ".ts", ".tsx")):
            continue
        text = (DEV / f).read_text(encoding="utf-8")
        if f.endswith(".py"):
            found += [f"{f}:{n}" for n in _py_comments(text)]
        else:
            found += [f"{f}:{n}" for n, line in enumerate(text.splitlines(), 1)
                      if TS_COMMENT.match(line) and not MARKS.search(line)]
    assert not found, f"comments: {len(found)}, first {found[:5]}"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED = ("app/public/",)

def test_images_only_in_allowed_folders() -> None:
    tracked = subprocess.run(["git", "ls-files"], cwd=DEV, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    offenders = [f for f in tracked if PurePosixPath(f).suffix.lower() in IMAGE_SUFFIXES and not f.startswith(ALLOWED)]
    assert not offenders, f"images outside {ALLOWED}: {offenders}"

def _branches(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    n, todo = 1, list(ast.iter_child_nodes(fn))
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            n += 1 + len(node.ifs)
        elif isinstance(node,
                        (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.Assert,
                         ast.match_case)):
            n += 1
        todo += ast.iter_child_nodes(node)
    return n

def test_no_python_function_over_ten_branches() -> None:
    files = [f for f in _repo_files() if f.startswith("radar/") and not f.startswith("radar/tests/")
             and f.endswith(".py") and f not in GENERATED]
    over = {f"{f}::{fn.name}" for f in files for fn in ast.walk(ast.parse((DEV / f).read_text(encoding="utf-8")))
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and _branches(fn) > 10}
    assert not over, f"functions over ten branches: {sorted(over)}"

def _second_blank_lines(source: str) -> list[int]:
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    blank = {t.start[0] for t in tokens if t.type == tokenize.NL and not t.line.strip()}
    return sorted(n for n in blank if n - 1 in blank)

def test_top_level_definitions_are_one_blank_line_apart() -> None:
    assert _second_blank_lines('def a():\n    pass\n\n\ndef b():\n    """x\n\n\ny"""\n    return '
                               'f"""\n\n\n"""\n') == [4]
    offenders = [f"{f}:{n}" for f in _repo_files() if f.startswith("radar/") and f.endswith(".py")
                 for n in _second_blank_lines((DEV / f).read_text(encoding="utf-8"))]
    assert not offenders, f"two blank lines in a row: {len(offenders)}, first {offenders[:5]}"
