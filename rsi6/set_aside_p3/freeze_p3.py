"""Freeze the external task suite into the repository (run once; the result is committed).

Source: Python Programming Puzzles (P3), github.com/microsoft/PythonProgrammingPuzzles,
``puzzles/puzzles.json``, MIT licence (``data/p3/LICENSE``). A puzzle is a Python function
``sat(answer, **parameters) -> bool`` written by the suite's authors: the verifier is the task.

What is kept of every instance: its name, module, the source of ``sat``, the declared answer
type and the header of the solution function (the parameter names and values). What is NOT
kept: the reference solutions (``sol_bodies``), the English docstrings and the notes. Nothing
in this package can read a reference solution, because none is stored.

The 18 modules are split into development, validation and evaluation by a rule fixed before
any puzzle was read: four modules named in ``DEVELOPMENT`` (chosen by their names), the other 14
shuffled by ``SEED`` and dealt so that validation holds about a third of the remaining puzzles
and evaluation about two thirds. The third split is called evaluation because TEST is the name
of a sealed set of another package of this repository.

    python freeze_p3.py <path to the downloaded puzzles.json>

Prints counts only. It never prints a puzzle of the validation or evaluation split.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "p3")
SEED = "rsi6:p3:split:20261111"
DEVELOPMENT = ("tutorial.py", "study.py", "trivial_inverse.py", "basic.py")
KEPT = ("name", "module", "sat", "ans_type", "sol_header")
SOURCE = "https://raw.githubusercontent.com/microsoft/PythonProgrammingPuzzles/main/puzzles/puzzles.json"


def split_modules(puzzles_by_module: dict) -> dict:
    rest = sorted(m for m in puzzles_by_module if m not in DEVELOPMENT)
    random.Random(SEED).shuffle(rest)
    target = {"validation": 1 / 3, "evaluation": 2 / 3}
    total = sum(puzzles_by_module[m] for m in rest)
    groups, size = {"validation": [], "evaluation": []}, {"validation": 0, "evaluation": 0}
    for module in rest:
        group = min(groups, key=lambda k: size[k] / (target[k] * total))
        groups[group].append(module)
        size[group] += puzzles_by_module[module]
    return {"development": list(DEVELOPMENT), "validation": sorted(groups["validation"]), "evaluation": sorted(groups["evaluation"])}


def main(path: str) -> None:
    raw = open(path, "rb").read()
    instances = json.loads(raw.decode("utf-8"))
    families = collections.defaultdict(set)
    for p in instances:
        families[p["module"]].add(p["name"].rsplit(":", 1)[0])
    split = split_modules({m: len(v) for m, v in families.items()})
    os.makedirs(OUT, exist_ok=True)
    manifest = {"source": SOURCE, "source_sha256": hashlib.sha256(raw).hexdigest(), "licence": "MIT (data/p3/LICENSE)",
                "retrieved": "2026-11-11", "seed": SEED, "kept_fields": list(KEPT),
                "dropped_fields": ["sol_bodies", "sol_docstring", "notes", "weight"], "splits": {}}
    for name, modules in split.items():
        rows = [{k: p[k] for k in KEPT} for p in instances if p["module"] in modules]
        text = json.dumps(rows, indent=1, sort_keys=True)
        with open(os.path.join(OUT, f"{name}.json"), "w") as handle:
            handle.write(text)
        manifest["splits"][name] = {"modules": modules, "puzzles": sum(len(families[m]) for m in modules),
                                    "instances": len(rows), "sha256": hashlib.sha256(text.encode()).hexdigest()}
        print(name, manifest["splits"][name]["puzzles"], "puzzles,", len(rows), "instances,", modules)
    json.dump(manifest, open(os.path.join(OUT, "MANIFEST.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
