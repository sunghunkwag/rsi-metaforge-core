"""The exposed partitions RSI-5 reports on, loaded through the read-only rsi2/rsi3 loaders.

Every partition here is *exposed*: its results were read by earlier studies
(``rsi3/*RESULTS.md``), so nothing may be tuned on it and nothing here gates, selects
or decides. TEST is never loaded. J's pools are J's (``rsi5/judge``), never loaded here.
Hidden examples travel inside ``rsi2.corpus.Task`` objects and are read only by the
frozen verifier (``rsi5/verifier.py``); the engine receives ``public_view`` tasks.
"""
from __future__ import annotations

from rsi2.corpus import Task, load_train, load_validation
from rsi3.compose24 import load_frozen_tasks
from rsi3.fresh import load_fresh
from rsi3.reserve import load_reserve

from .dsl.types import Type


def request_type(task: Task) -> Type:
    """The task's request type in RSI-5's type language (rsi2 and rsi5 share the dict form)."""
    return Type.from_dict(task.request_type.to_dict())


PARTITIONS = {
    "fresh1": ("FRESH-1", "33 single routines from DreamCoder's second list file, outside the corpus"),
    "fresh2": ("FRESH-2", "100 two-stage pipelines from the same file"),
    "near": ("RESERVE-NEAR", "100 unselected corpus tasks whose family has a member in the 60"),
    "far": ("RESERVE-FAR", "12 unselected corpus tasks in families no split contains"),
    "far2": ("RESERVE-FAR2", "21 unselected corpus tasks in the 5 research families"),
    "compose24": ("COMPOSE-24", "24 reference-oracle composition tasks (PR #45's suite)"),
    "validation": ("VALIDATION", "RSI-2's 12 validation tasks"),
    "train": ("TRAIN", "RSI-2's 36 training tasks (report only)"),
}
PHASE1_ORDER = ("fresh1", "fresh2", "near", "far2", "compose24", "validation", "far", "train")


def load(partition: str) -> list[Task]:
    if partition in ("fresh1", "fresh2"):
        loaded = load_fresh(partition)
    elif partition in ("near", "far", "far2"):
        loaded = load_reserve(partition)
    elif partition == "compose24":
        loaded = load_frozen_tasks()
    elif partition == "validation":
        loaded = load_validation()
    elif partition == "train":
        loaded = load_train()
    else:
        raise KeyError(f"unknown partition {partition!r}")
    return loaded


def public_view(task: Task) -> Task:
    """A copy with no hidden examples: what the engine receives."""
    return Task(task.name, task.request_type, task.examples, ())


def family(name: str) -> str:
    """The routine family of a task name, for closure-escape accounting (§8.1).

    Corpus names: ``"add-k with k=3"`` -> ``"add-k"``. DreamCoder second-file names:
    ``"((add-k (dyn . 0) (static . 3)))"`` -> ``"add-k"``; a pipeline gives its routines
    joined by ``" then "``. COMPOSE-24: ``"fresh20261031::trim-and-increment::p1"`` -> the
    middle field.
    """
    if name.startswith("fresh20261031::"):
        return name.split("::")[1]
    if name.startswith("(("):
        from rsi3.fresh import components
        return " then ".join(routine for routine, _ in components(name))
    return name.split(" with ", 1)[0]
