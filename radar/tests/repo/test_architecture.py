import ast
import re
from pathlib import Path, PurePosixPath

from radar.paths import DEV
from radar.tests.repo.test_layout import GENERATED, PACKAGE_MARKERS, _repo_files

RADAR = DEV / "radar"
APP_SRC = DEV / "app" / "src"
COMMANDS_DIR = RADAR / "commands"
COMMANDS = {p.stem for p in COMMANDS_DIR.rglob("*.py") if not p.name.startswith("_")}

def test_subcommands_never_import_each_other() -> None:
    offenders = {}
    for path in sorted(p for p in COMMANDS_DIR.rglob("*.py") if not p.name.startswith("_")):
        bad = {node.module for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
               if isinstance(node, ast.ImportFrom) and node.module
               and ("commands" in node.module or node.module in COMMANDS)}
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, f"subcommand modules import each other: {offenders}"

IMPURE = re.compile(r"^(radar\.(adapters|commands|build|paths)|os|io|pathlib|glob|shutil|tempfile)(\.|$)")
FILE_CALLS = {"open", "read_text", "read_bytes", "write_text", "write_bytes", "rglob", "iterdir"}

def test_the_domain_is_pure() -> None:
    offenders = []
    for path in sorted((RADAR / "domain").rglob("*.py")):
        calls = {getattr(n.func, "id", getattr(n.func, "attr", ""))
                 for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.Call)}
        offenders += [f"{path.relative_to(DEV)} -> {m}"
                      for m in sorted({m for m in _imported_modules(path) if IMPURE.match(m)} | calls & FILE_CALLS)]
    assert not offenders, f"domain modules reach another layer, a file or the environment: {offenders}"

def test_the_read_model_and_validation_never_import_each_other() -> None:
    packages = ("radar.domain.read_model", "radar.domain.validation")
    offenders = [f"{p.relative_to(DEV)} -> {m}" for own, other in (packages, packages[::-1])
                 for p in sorted((DEV / own.replace(".", "/")).rglob("*.py")) for m in sorted(_imported_modules(p))
                 if m.startswith(other)]
    assert not offenders, f"the read model and validation import each other: {offenders}"

def test_no_deprecated_legacy_or_compat_code() -> None:
    pat = re.compile(r"deprecat|shim|legacy|compat", re.IGNORECASE)
    offenders = [f"{f.relative_to(DEV)}:{i}" for base, exts in ((RADAR, (".py",)), (APP_SRC, (".ts", ".tsx")))
                 for f in base.rglob("*") if f.suffix in exts and "__pycache__" not in f.parts
                 and "tests" not in f.parts and str(f.relative_to(DEV)) not in GENERATED
                 for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if pat.search(line)]
    assert not offenders, f"deprecated, legacy or compat code found: {offenders}"

def test_all_public_python_functions_annotated() -> None:
    offenders = []
    for path in sorted(RADAR.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and (node.name.endswith("__") or not node.name.startswith("_"))):
                args = node.args
                params = (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg)
                missing = [p.arg for p in params if p and p.annotation is None and p.arg not in ("self", "cls")]
                if missing or node.returns is None:
                    offenders.append(f"{path.relative_to(DEV)}:{node.lineno} {node.name} "
                                     f"{missing}{'' if node.returns else ' and its return'}")
    assert not offenders, f"unannotated public functions in radar/: {offenders}"

def test_no_python_module_named_types() -> None:
    offenders = [f for f in _repo_files() if PurePosixPath(f).name == "types.py"]
    assert not offenders, f"Python modules named types.py: {offenders}"

def _module_name(path: Path) -> str:
    rel = path.relative_to(DEV).with_suffix("")
    parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
    return ".".join(parts)

def _imported_modules(path: Path) -> set[str]:
    package = _module_name(path) if path.name == "__init__.py" else _module_name(path).rpartition(".")[0]
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package.split(".")[: len(package.split(".")) - (node.level - 1)] if node.level else []
            module = ".".join([*base, *([node.module] if node.module else [])])
            names.add(module)
            names.update(f"{module}.{a.name}" for a in node.names)
    return names

def _base_name(node: ast.expr) -> str:
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""

def _reach(*starts: Path) -> set[Path]:
    modules = {_module_name(p): p for p in RADAR.rglob("*.py") if "__pycache__" not in p.parts}
    seen: set[Path] = set()
    todo = list(starts)
    while todo:
        path = todo.pop()
        if path not in seen:
            seen.add(path)
            todo += [modules[name] for name in _imported_modules(path) if name in modules]
    return seen

def test_every_radar_module_is_imported_by_production_code() -> None:
    seen = _reach(RADAR / "cli.py", RADAR / "adapters" / "web" / "function.py")
    orphans = sorted(str(p.relative_to(DEV)) for p in RADAR.rglob("*.py") if "__pycache__" not in p.parts
                     and p not in seen and p.name not in PACKAGE_MARKERS and "tests" not in p.relative_to(RADAR).parts)
    assert not orphans, f"radar modules nothing imports: {orphans}"

def test_protocols_stand_alone() -> None:
    offenders = []
    for path in sorted(RADAR.rglob("*.py")):
        classes = [n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.ClassDef)]
        protocols = {c.name for c in classes if "Protocol" in map(_base_name, c.bases)}
        offenders += [f"{path.name}: {c.name}({b})" for c in classes for b in map(_base_name, c.bases)
                      if b in protocols]
        offenders += [f"{path.name}: {name} has an I prefix" for name in protocols if re.match(r"I[A-Z]", name)]
    assert not offenders, f"Protocols sharing a file with their implementation, or I-prefixed: {offenders}"
