"""The sealing audit: nothing the system controls can reach J (OWNER_DIRECTIVE.md §5).

This extends ``rsi3/tests/test_sealing.py``'s pattern (AST checks over the
package's source) into an AST and path audit of every agent module, i.e.
every ``*.py`` under ``rsi4/`` outside ``rsi4/judge/`` and ``rsi4/tests/``
(the tests are the harness that plants faults in J and checks J catches
them; they are not part of the agent process). J runs it at every
``run_start`` and refuses the run on any finding; ``rsi4/tests`` runs it on
every build.

An agent module may not:

1. import ``rsi4.judge`` in any form (absolute, ``from rsi4 import judge``,
   or relative);
2. call a dynamic importer or code runner (``import_module``, ``__import__``,
   ``run_module``, ``run_path``, ``exec``, ``eval``, ``compile``);
3. hold a string literal that names the judge package or a path into it
   (``"rsi4.judge"``, ``"judge"`` as a path part, ``.../judge/...``), the
   pools, J's seed file, J's manifest, or the DreamCoder source file
   (``list_tasks2``). Docstrings are prose and are not checked;
4. read an attribute whose name contains ``hidden`` (rsi3's rule), or use
   frame and closure introspection (``__closure__``, ``__globals__``,
   ``__code__``, ``f_locals``, ``f_globals``, ``gi_frame``, ``tb_frame``).

Two harness modules are exempt from rules 2 and 3 and nothing else:
``client.py`` may hold exactly the literal ``"rsi4.judge"`` and call
``run_module`` (it starts J in a spawned process), and ``guard.py`` names
J's directory to block it. At run time ``guard.py`` closes the remaining gap
a static audit leaves (a path assembled at run time): it installs an audit
hook in the agent process that refuses to open, list or import anything
under ``rsi4/judge/`` or the source file.
"""
from __future__ import annotations

import ast
from pathlib import Path

from .registry import PACKAGE_DIR

JUDGE_MODULE = "rsi4.judge"
DYNAMIC = {"import_module", "__import__", "run_module", "run_path", "exec", "eval", "compile"}
INTROSPECTION = {"__closure__", "__globals__", "__code__", "f_locals", "f_globals",
                 "gi_frame", "tb_frame"}
FORBIDDEN_TEXT = ("rsi4.judge", "judge/", "/judge", "judge\\", "pools", "seed.json",
                  "MANIFEST", "list_tasks2")
HARNESS = {"client.py": {"literals": {JUDGE_MODULE}, "calls": {"run_module"}},
           "guard.py": {"literals": None, "calls": set()}}


def agent_modules(package_dir: Path = PACKAGE_DIR) -> list[Path]:
    package_dir = Path(package_dir)
    found = []
    for path in sorted(package_dir.rglob("*.py")):
        parts = path.relative_to(package_dir).parts
        if parts[0] in ("judge", "tests") or "__pycache__" in parts:
            continue
        found.append(path)
    return found


def _module_name(path: Path, package_dir: Path) -> list[str]:
    parts = list(path.relative_to(package_dir.parent).with_suffix("").parts)
    return parts[:-1] if parts[-1] == "__init__" else parts


def _docstrings(tree) -> set:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _resolve(node: ast.ImportFrom, module: list[str], is_package: bool) -> list[str]:
    """Fully qualified names an ImportFrom brings in."""
    if node.level:
        base = module if is_package else module[:-1]
        base = base[:len(base) - (node.level - 1)] if node.level > 1 else base
        prefix = ".".join(base + ([node.module] if node.module else []))
    else:
        prefix = node.module or ""
    return [prefix] + [f"{prefix}.{alias.name}" for alias in node.names]


def _is_judge(name: str) -> bool:
    return name == JUDGE_MODULE or name.startswith(JUDGE_MODULE + ".")


def check_module(path: Path, package_dir: Path = PACKAGE_DIR) -> list[str]:
    package_dir = Path(package_dir)
    rel = path.relative_to(package_dir).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = _module_name(path, package_dir)
    is_package = path.name == "__init__.py"
    exempt = HARNESS.get(rel, {"literals": set(), "calls": set()})
    docstrings = _docstrings(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_judge(alias.name):
                    found.append(f"{rel}:{node.lineno}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            for name in _resolve(node, module, is_package):
                if _is_judge(name):
                    found.append(f"{rel}:{node.lineno}: imports {name}")
                    break
        elif isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None)
            if called in DYNAMIC and called not in exempt["calls"]:
                found.append(f"{rel}:{node.lineno}: calls {called}")
        elif isinstance(node, ast.Attribute):
            if "hidden" in node.attr.lower():
                found.append(f"{rel}:{node.lineno}: reads attribute {node.attr}")
            if node.attr in INTROSPECTION:
                found.append(f"{rel}:{node.lineno}: introspects {node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings or exempt["literals"] is None:
                continue
            if node.value in exempt["literals"]:
                continue
            text = node.value
            if text.strip() == "judge" or any(f in text for f in FORBIDDEN_TEXT):
                found.append(f"{rel}:{getattr(node, 'lineno', 0)}: literal {text[:60]!r}")
    return found


def problems(package_dir: Path = PACKAGE_DIR) -> list[str]:
    """Every audit finding over the agent modules; [] when the package is sealed."""
    package_dir = Path(package_dir)
    found = []
    for path in agent_modules(package_dir):
        found.extend(check_module(path, package_dir))
    return found
