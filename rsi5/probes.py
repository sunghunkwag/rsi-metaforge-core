"""The frozen probe set: extra inputs every search evaluates on, fixed before any run.

Observational equivalence compares programs on the task's public inputs *and* on these
probes (OWNER_DIRECTIVE.md §3.2), so two programs that agree on the public inputs by
accident stay distinct. Phase 2 reads residual fingerprints on the same probes. The set
is generated once from a fixed seed and committed as ``data/probe_set.json``;
``check()`` fails if the committed file and the generator disagree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random

from .dsl.types import BOOL, INT, ListOf, Type

SEED = 20261109
DATA = Path(__file__).resolve().parent / "data" / "probe_set.json"
COUNTS = {"int": 12, "bool": 2, "list[int]": 16, "list[bool]": 8}


def generate(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    ints = [0, 1, -1, 2, 3, 5, 7, 10]
    while len(ints) < COUNTS["int"]:
        v = rng.randint(-9, 20)
        if v not in ints:
            ints.append(v)
    lists = [[], [0], [1, 1], [3, 1, 2]]
    seen = {json.dumps(x) for x in lists}
    while len(lists) < COUNTS["list[int]"]:
        n = rng.randint(2, 9)
        xs = [rng.randint(-6, 16) for _ in range(n)]
        if rng.random() < 0.3 and n >= 3:
            xs[rng.randrange(n)] = xs[rng.randrange(n)]      # a repeated element
        key = json.dumps(xs)
        if key not in seen:
            seen.add(key)
            lists.append(xs)
    bools = [[], [True], [False, True, True], [True, False]]
    seenb = {json.dumps(x) for x in bools}
    while len(bools) < COUNTS["list[bool]"]:
        n = rng.randint(2, 7)
        xs = [rng.random() < 0.5 for _ in range(n)]
        key = json.dumps(xs)
        if key not in seenb:
            seenb.add(key)
            bools.append(xs)
    return {"seed": seed, "int": ints, "bool": [False, True], "list[int]": lists,
            "list[bool]": bools}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def sha256() -> str:
    return hashlib.sha256(DATA.read_bytes()).hexdigest()


def check() -> bool:
    return load() == generate()


def for_type(type_: Type, probes: dict | None = None) -> list:
    probes = load() if probes is None else probes
    return [v for v in probes[str(type_)]]


def inputs_for(input_types, probes: dict | None = None) -> list:
    """Probe input tuples for a request type: the per-type lists zipped (arity 1 in practice)."""
    probes = load() if probes is None else probes
    columns = [for_type(t, probes) for t in input_types]
    n = min(len(c) for c in columns)
    return [tuple(c[i] for c in columns) for i in range(n)]


if __name__ == "__main__":
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(generate(), indent=1) + "\n", encoding="utf-8")
    print(sha256())
