"""Scoped self-edit (OWNER_DIRECTIVE.md §5; original core §20's discipline, widened).

The original core patched one line of a copy of its source, proved with a
guard that only that line changed, and evaluated the copy in isolation.
Here the Builder patches a copy of its whole mutable tree through
structured operators, the guard proves the diff is within scope, and the
kernel evaluates the copy on the archive (``kernel/edits.py``).

Operators (what the Builder can change about itself):

- ``forge``: add a primitive (name, DSL type, checker-language body,
  source tasks) to ``forged.json``;
- ``unforge``: remove a forged primitive;
- ``param``: set one of the parameters ``params.json`` exposes from a
  menu: search limits, the learning rule (learn from crossed solutions or
  from mined ones), the adoption cap, the allocation strategy and window;
- ``prune``: remove a library entry.

Scope, stated: the operators rewrite the tree's data files (forged
primitives, library, parameters that select among the search and
allocation strategies ``solve.py`` implements); the Python files of the
tree, the evaluator above all, are not rewritten by this implementation,
and the guard rejects any candidate whose code files differ from the live
tree's. That is a bounded form of "the Builder rewrites its search".
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil

DATA_FILES = ("forged.json", "params.json", "library.json")
PARAM_MENU = {
    ("search", "max_size"): [8, 10, 12, 14],
    ("search", "max_expansions"): [10000, 20000, 40000],
    ("learn", "from"): ["crossed", "mined"],
    ("learn", "max_adoptions"): [2, 4, 8],
    ("allocation", "strategy"): ["even", "commit"],
    ("allocation", "window"): [8, 16, 32],
}


def copy_tree(source: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pkl"))
    return destination


def apply_patch(tree: Path, patch: dict) -> None:
    """Apply one structured patch to the data files of ``tree`` (a copy, never the live tree)."""
    kind = patch["kind"]
    if kind == "forge":
        path = tree / "forged.json"
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged[patch["name"]] = {"type": patch["type"], "body": patch["body"],
                                 "sources": list(patch.get("sources", []))}
        path.write_text(json.dumps(forged, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    elif kind == "unforge":
        path = tree / "forged.json"
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged.pop(patch["name"], None)
        path.write_text(json.dumps(forged, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    elif kind == "param":
        path = tree / "params.json"
        params = json.loads(path.read_text(encoding="utf-8"))
        section, key = patch["path"]
        if (section, key) not in PARAM_MENU or patch["value"] not in PARAM_MENU[(section, key)]:
            raise ValueError("parameter outside the menu")
        params.setdefault(section, {})[key] = patch["value"]
        path.write_text(json.dumps(params, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    elif kind == "prune":
        path = tree / "library.json"
        library = json.loads(path.read_text(encoding="utf-8"))
        library["entries"].pop(patch["name"], None)
        path.write_text(json.dumps(library, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"unknown patch kind {kind!r}")


def make_candidate(live: Path, root: Path, index: int, patch: dict) -> Path:
    """A patched copy of the live tree at ``root/<index>/mutable``."""
    candidate = copy_tree(live / "mutable", Path(root) / str(index) / "mutable")
    apply_patch(candidate, patch)
    return candidate.parent


def guard(candidate_dir: Path, live: Path) -> list:
    """Violations of scope: any file outside DATA_FILES that differs from the live tree."""
    violations = []
    live_tree, candidate_tree = Path(live) / "mutable", Path(candidate_dir) / "mutable"
    live_files = {p.relative_to(live_tree): p for p in live_tree.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pkl"}
    candidate_files = {p.relative_to(candidate_tree): p for p in candidate_tree.rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pkl"}
    for relative in sorted(set(live_files) | set(candidate_files)):
        if relative.name in DATA_FILES and relative.parent == Path("."):
            continue
        if relative not in live_files or relative not in candidate_files:
            violations.append(f"{relative}: added or removed")
        elif live_files[relative].read_bytes() != candidate_files[relative].read_bytes():
            violations.append(f"{relative}: code changed")
    return violations


def adopt(candidate_dir: Path, live: Path) -> None:
    """Copy the candidate's data files over the live tree's (the kernel said yes)."""
    for name in DATA_FILES:
        shutil.copyfile(Path(candidate_dir) / "mutable" / name, Path(live) / "mutable" / name)
