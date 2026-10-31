"""Frozen, independently specified new-family program-transfer benchmark.

Four NEW composition families, six parameter variants each (24 tasks).
They are reference-Python specifications, not generated from RSI-2's
enumerator or selected after examining any solver's output.

There are 10 public input/output examples per task, used solely by
a previously frozen solver at evaluation time, and 14 distinct hidden
examples delivered only to the unchanged FrozenVerifier.

The benchmark uses its own input seed, independent of all training seeds.
Do not import this module during model fitting, self-play, or wake.
"""
from __future__ import annotations

import hashlib
import json
import random

from rsi2.corpus import parse_task
from rsi2.types import Arrow, INT, ListOf

BENCHMARK_ID = "FRESH-COMPOSE-20261031-V1"
INPUT_SEED = 2026103107
PUBLIC_COUNT = 10
HIDDEN_COUNT = 14
PARAMETERS = (1, 2, 3, 4, 5, 6)
FAMILIES = (
    "trim-and-increment",
    "append-reversed-prefix",
    "reverse-dropped-suffix",
    "filter-nondivisible-and-shift",
)


def reference_oracle(family: str, k: int, values: list[int]) -> list[int]:
    """Reference semantics independent of the RSI-2 executable language."""
    a = list(values)
    if family == "trim-and-increment":
        return [v + 1 for v in a[k:]]
    if family == "append-reversed-prefix":
        return a + list(reversed(a[:k]))
    if family == "reverse-dropped-suffix":
        return list(reversed(a[k:]))
    if family == "filter-nondivisible-and-shift":
        return [v + 1 for v in a if v % (k + 1) != 0]
    raise ValueError("unknown frozen family")


def _inputs(family_index: int, k: int) -> list[list[int]]:
    rng = random.Random(INPUT_SEED + 65537 * family_index + 101 * k)
    result, seen = [], set()
    while len(result) < PUBLIC_COUNT + HIDDEN_COUNT:
        n = rng.randint(4, 12)
        sample = tuple(rng.randint(-8, 9) for _ in range(n))
        if sample in seen:
            continue
        seen.add(sample)
        result.append(list(sample))
    return result


def frozen_records() -> list[dict]:
    signature = Arrow(ListOf(INT), ListOf(INT)).to_dict()
    records = []
    for family_index, family in enumerate(FAMILIES):
        for k in PARAMETERS:
            examples = []
            for values in _inputs(family_index, k):
                examples.append({"inputs": [values],
                                 "output": reference_oracle(family, k, values)})
            records.append({
                "name": f"fresh20261031::{family}::p{k}",
                "request_type": signature,
                "examples": examples[:PUBLIC_COUNT],
                "hidden": examples[PUBLIC_COUNT:],
            })
    return records


def suite_sha256() -> str:
    """Commit to all task inputs, outputs, and splits before any evaluation."""
    payload = json.dumps(frozen_records(), sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_frozen_tasks():
    return [parse_task(record) for record in frozen_records()]
