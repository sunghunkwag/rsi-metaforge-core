"""The external tasks: verifier-defined puzzles, loaded from the frozen files of ``data/p3``.

A *family* is one puzzle; its *instances* differ only in the default parameters of the
verifier. The verifier's source is the whole statement of the task: there is no reference
solution anywhere in this package.

Three splits (``data/p3/MANIFEST.json``). ``development`` is open. ``validation`` is read by the
gate that decides whether a modification of the acquisition mechanism is adopted, and by
nothing a person develops against. ``evaluation`` is read only by a registered evaluation. The
loader refuses a sealed split unless the caller states one of these purposes, so that a
development script cannot open one by accident, and every load of a sealed split is recorded.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "p3")
SPLITS = ("development", "validation", "evaluation")
PURPOSES = {"development": (None, "development", "gate", "registered-evaluation"),
            "validation": ("gate", "registered-evaluation"),
            "evaluation": ("registered-evaluation",)}
LOADS = []                       # (split, purpose) of every load in this process, for audits


@dataclass(frozen=True)
class Instance:
    key: str                     # "<module>/<family>:<index>"
    family: str
    module: str
    index: int
    source: str                  # the verifier: "def sat(answer, a=..., b=...): ..."
    answer_type: str             # as the suite declares it: "int", "str", "List[int]", ...
    answer_name: str             # the name of the verifier's first argument
    parameters: tuple            # ((name, value), ...): the instance's parameters

    @property
    def kwargs(self) -> dict:
        return dict(self.parameters)


@dataclass(frozen=True)
class Family:
    name: str                    # "<module>/<family>"
    module: str
    answer_type: str
    instances: tuple             # of Instance, by index

    def public(self, hidden: int = 2) -> tuple:
        """The instances a solver may see: all but the last ``hidden`` (at least one)."""
        return self.instances[:max(1, len(self.instances) - hidden)]

    def held_back(self, hidden: int = 2) -> tuple:
        """The instances kept for the check that a solution is a capability and not one answer."""
        return self.instances[max(1, len(self.instances) - hidden):]


def _signature(source: str):
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef))
    arguments = function.args.args
    defaults = function.args.defaults
    named = arguments[len(arguments) - len(defaults):]
    return arguments[0].arg, tuple((a.arg, ast.literal_eval(d)) for a, d in zip(named, defaults))


def manifest() -> dict:
    return json.load(open(os.path.join(DATA, "MANIFEST.json")))


def load(split: str, purpose: str | None = None) -> list:
    """The families of a split, in the suite's order. ``purpose`` must be one the split allows."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    if purpose not in PURPOSES[split]:
        raise PermissionError(f"the {split} split is sealed: it opens for {PURPOSES[split]} only")
    raw = open(os.path.join(DATA, f"{split}.json"), "rb").read()
    if hashlib.sha256(raw).hexdigest() != manifest()["splits"][split]["sha256"]:
        raise RuntimeError(f"data/p3/{split}.json is not the frozen file")
    LOADS.append((split, purpose))
    families = {}
    for row in json.loads(raw.decode("utf-8")):
        base, index = row["name"].rsplit(":", 1)
        module = row["module"].removesuffix(".py")
        answer_name, parameters = _signature(row["sat"])
        families.setdefault((module, base), []).append(
            Instance(f"{module}/{row['name']}", f"{module}/{base}", module, int(index), row["sat"], row["ans_type"],
                     answer_name, parameters))
    return [Family(f"{module}/{base}", module, instances[0].answer_type, tuple(sorted(instances, key=lambda i: i.index)))
            for (module, base), instances in families.items()]


def modules(families) -> dict:
    """module -> its families, in order."""
    out = {}
    for family in families:
        out.setdefault(family.module, []).append(family)
    return out
