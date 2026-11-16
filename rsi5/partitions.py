"""The exposed partitions RSI-5 reports on, loaded through the read-only rsi2/rsi3 loaders.

Every partition here is *exposed*: its results were read by earlier studies
(``rsi3/*RESULTS.md``), so nothing may be tuned on it and nothing here gates, selects
or decides. J's pools are J's (``rsi5/judge``), never loaded here.

TEST is never loaded and RSI-2's TEST file is never opened; ``rsi5/guard.py`` seals it.
Precisely: the three RESERVE partitions are built by ``rsi3/reserve.py``, which parses
DreamCoder's source file (it holds every source record, the 12 TEST tasks' among them) and
the split manifest (it lists TEST's names) and keeps only names outside the 60 selected
tasks. No TEST record is normalised, turned into a task or counted.

Hidden examples travel inside ``rsi2.corpus.Task`` objects and are read only by the frozen
verifier (``rsi5/verifier.py``). A search worker receives ``PublicTask`` values: a name, a
request type in dict form and the public examples, with no object of a loader package inside.

The loaders are imported inside ``load()`` and ``family()``, never at module import. A
process that loads no partition, such as a search worker forked before the first
``load()``, therefore holds no loader module, and ``guard.seal_task_data()`` can refuse
their import there.
"""
from __future__ import annotations

from dataclasses import dataclass

from .dsl.types import Type


@dataclass(frozen=True)
class PublicTask:
    """What a search worker receives: plain data, no hidden example."""
    name: str
    request: dict        # the request type as ``Type.to_dict()`` gives it
    examples: tuple      # the public examples: ((inputs, output), ...)


def request_type(task) -> Type:
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


def load(partition: str) -> list:
    """The partition's ``rsi2.corpus.Task`` objects, hidden examples included: driver side only."""
    if partition in ("fresh1", "fresh2"):
        from rsi3.fresh import load_fresh
        loaded = load_fresh(partition)
    elif partition in ("near", "far", "far2"):
        from rsi3.reserve import load_reserve
        loaded = load_reserve(partition)
    elif partition == "compose24":
        from rsi3.compose24 import load_frozen_tasks
        loaded = load_frozen_tasks()
    elif partition == "validation":
        from rsi2.corpus import load_validation
        loaded = load_validation()
    elif partition == "train":
        from rsi2.corpus import load_train
        loaded = load_train()
    else:
        raise KeyError(f"unknown partition {partition!r}")
    return loaded


def public_view(task) -> PublicTask:
    """The task without its hidden examples, as plain data: what a search worker receives."""
    return PublicTask(task.name, request_type(task).to_dict(), task.examples)


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
