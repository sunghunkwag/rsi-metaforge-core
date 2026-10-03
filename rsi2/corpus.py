"""External task records and the two development-partition capabilities.

The source corpus is never executed. Request types are inferred from its plain
JSON examples without importing the benchmark's runtime or any learning code.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import count
import json
from pathlib import Path
import random

from .types import Arrow, BOOL, INT, ListOf, TVar, Type, arrows, substitute, unify


_DATA = Path(__file__).resolve().parent / "data"
SPLIT_SEED = 20261002


@dataclass(frozen=True)
class Task:
    name: str
    request_type: Type
    examples: tuple[tuple[tuple, object], ...]
    hidden: tuple[tuple[tuple, object], ...]


def infer_request_type(examples) -> Type:
    """Infer the common curried input/output type of external JSON examples."""
    serial = count()

    def value_type(value):
        if type(value) is bool:
            return BOOL
        if type(value) is int:
            return INT
        if type(value) is list:
            element = TVar(f"external_{next(serial)}")
            constraints = {}
            for item in value:
                constraints = unify(element, value_type(item), constraints)
                element = substitute(element, constraints)
            return ListOf(element)
        raise ValueError("external examples must contain ints, bools, or homogeneous lists")

    request = TVar(f"external_{next(serial)}")
    constraints = {}
    arity = None
    for inputs, expected in examples:
        if type(inputs) is not tuple:
            raise ValueError("external inputs must be an argument tuple")
        if arity is None:
            arity = len(inputs)
        if len(inputs) != arity:
            raise ValueError("external examples disagree on input arity")
        signature = arrows(*(value_type(v) for v in inputs), value_type(expected))
        constraints = unify(request, signature, constraints)
        request = substitute(request, constraints)
    if arity is None:
        raise ValueError("cannot infer a request type without examples")
    return request


def parse_task(record) -> Task:
    """Parse one already supplied record; this function opens no files."""
    def pairs(values):
        return tuple((tuple(item["inputs"]), item["output"]) for item in values)

    examples, hidden = pairs(record["examples"]), pairs(record["hidden"])
    if len(examples) < 10 or not hidden:
        raise ValueError("each external task requires ten search examples and separate hidden examples")
    public_inputs = {json.dumps(x, sort_keys=True) for x, _ in examples}
    if any(json.dumps(x, sort_keys=True) in public_inputs for x, _ in hidden):
        raise ValueError("search and hidden examples must have disjoint inputs")
    inferred = infer_request_type(examples + hidden)
    declared = Type.from_dict(record["request_type"])
    unify(inferred, declared)
    return Task(str(record["name"]), declared, examples, hidden)


def load_train() -> list[Task]:
    records = json.loads((_DATA / "train.json").read_text(encoding="utf-8"))
    return [parse_task(record) for record in records]


def load_validation() -> list[Task]:
    records = json.loads((_DATA / "validation.json").read_text(encoding="utf-8"))
    return [parse_task(record) for record in records]


def split_ids(names, seed=SPLIT_SEED, selected_count=60):
    """Seed-only selection and 60/20/20 assignment over named external tasks."""
    ids = sorted(names)
    if len(ids) != len(set(ids)):
        raise ValueError("external task identifiers must be unique")
    if selected_count > len(ids) or selected_count < 5 or selected_count % 5:
        raise ValueError("selected count must fit the population and divide into fifths")
    random.Random(seed).shuffle(ids)
    selected = ids[:selected_count]
    first, second = 3 * selected_count // 5, 4 * selected_count // 5
    return {"train": selected[:first], "validation": selected[first:second],
            "test": selected[second:]}
