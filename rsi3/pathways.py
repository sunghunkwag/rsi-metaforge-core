"""Search pathways: designer pathways plus dormant pathways created from experience.

A pathway is a way of ordering candidate programs for a task, i.e. a grammar.

* ``prior``      (designer) RSI-2's current learned prior, library included.
* ``recognized`` (designer) the prior conditioned on the task's public examples
                 by RSI-2's recognition model (exists after the first sleep).
* ``analog:<S>`` (genesis) a grammar refit on the verified solution of an
                 already solved task S. One is created for every newly verified
                 task. It is born DORMANT: it holds no search state and receives
                 no budget until the controller allocates a window to it, which
                 AWAKENS it. Its applicability to an unsolved task T is limited
                 to the ``neighbors`` solved tasks most similar to T (cosine
                 similarity of RSI-2's public task features) whose request type
                 unifies with T's.

Genesis is the response to a structural criticism of pre-stocked pathway
designs: a router that only chooses among designer-written modules keeps the
design space closed. Here the pathway set grows from verified experience, and
every new pathway must earn budget through the same value model as the
designer pathways. This widens the ordering of an unchanged language; it does
not add primitives (the RSI-2 freeze rule stands).

Live search state is cached per (task, pathway, grammar fingerprint). When a
pathway's grammar changes, its fingerprint changes and the cached search is
discarded, because the enumeration order is no longer the one the cached
prefix was computed under.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import numpy as np

from rsi2.grammar import Grammar
from rsi2.terms import pretty
from rsi2.types import TypeInferenceError, instantiate, unify

from .resumable import ResumableSearch

DESIGNER_KINDS = ("prior", "recognized")
KINDS = DESIGNER_KINDS + ("analog",)


def grammar_fingerprint(grammar: Grammar) -> str:
    payload = {
        "weights": sorted((k, float(v)) for k, v in grammar.weights.items()),
        "context": sorted((list(ctx), sorted((k, float(v)) for k, v in table.items()))
                          for ctx, table in grammar.context_weights.items()),
        "library": sorted((name, pretty(term)) for name, term in grammar.library.items()),
        "primitives": sorted(grammar.primitives),
        "constants": [pretty(term) for term in grammar.constants],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def types_compatible(left, right) -> bool:
    try:
        unify(instantiate(left, "_rsi3_left_"), instantiate(right, "_rsi3_right_"))
    except TypeInferenceError:
        return False
    return True


@dataclass
class Pathway:
    pid: str
    kind: str
    origin: str
    born_generation: int
    source_task: str | None = None
    status: str = "dormant"
    awakened_generation: int | None = None
    windows: int = 0
    verified_solves: int = 0
    solved_tasks: list = field(default_factory=list)

    def to_record(self) -> dict:
        return dict(self.__dict__)


class PathwayRegistry:
    def __init__(self, tasks, features: dict, *, genesis: bool = True, neighbors: int = 2,
                 designer_kinds=DESIGNER_KINDS, search_config: dict):
        self.tasks = {task.name: task for task in tasks}
        self.features = features
        self.genesis_enabled = bool(genesis)
        self.neighbors = int(neighbors)
        self.designer_kinds = tuple(designer_kinds)
        self.search_config = dict(search_config)
        self.pathways: dict[str, Pathway] = {}
        for kind in self.designer_kinds:
            self.pathways[kind] = Pathway(kind, kind, "designer", 0, status="active")
        self._live: dict[tuple[str, str], tuple[str, ResumableSearch]] = {}
        self._analog_grammar: dict[str, tuple[str, Grammar]] = {}
        self._generation_cache: dict[tuple[str, str], tuple[str, Grammar]] = {}

    def begin_generation(self) -> None:
        """Grammars change only during sleep; recompute them once per generation."""
        self._generation_cache.clear()

    # ---- genesis -------------------------------------------------------
    def genesis(self, state, generation: int) -> list[str]:
        """Create one dormant analog pathway per newly solved task."""
        if not self.genesis_enabled:
            return []
        created = []
        for name in sorted(state.solutions):
            pid = f"analog:{name}"
            if pid not in self.pathways:
                self.pathways[pid] = Pathway(pid, "analog", "genesis", generation, source_task=name)
                created.append(pid)
        return created

    # ---- applicability -------------------------------------------------
    def similarity(self, task: str, other: str) -> float:
        a, b = self.features[task], self.features[other]
        denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(a @ b / denominator) if denominator > 0 else 0.0

    def applicable(self, task: str, state) -> list[tuple[str, float]]:
        """Return (pathway id, similarity) pairs usable for ``task`` now."""
        result = [("prior", 0.0)] if "prior" in self.pathways else []
        if "recognized" in self.pathways and state.recognition is not None:
            result.append(("recognized", 0.0))
        analogs = []
        for pid, pathway in self.pathways.items():
            if pathway.kind != "analog" or pathway.source_task not in state.solutions:
                continue
            source = self.tasks[pathway.source_task]
            if not types_compatible(self.tasks[task].request_type, source.request_type):
                continue
            analogs.append((self.similarity(task, pathway.source_task), pid))
        analogs.sort(key=lambda item: (-item[0], item[1]))
        result.extend((pid, sim) for sim, pid in analogs[:self.neighbors])
        return result

    # ---- grammars and live searches ------------------------------------
    def grammar(self, pid: str, task: str, state) -> Grammar:
        pathway = self.pathways[pid]
        if pathway.kind == "prior":
            return state.grammar
        if pathway.kind == "recognized":
            return state.condition(self.tasks[task])
        library_key = grammar_fingerprint(Grammar(library=state.grammar.library))
        cached = self._analog_grammar.get(pid)
        if cached is None or cached[0] != library_key:
            source = self.tasks[pathway.source_task]
            grammar = Grammar(library=state.grammar.library)
            grammar.fit([(state.solutions[pathway.source_task], source.request_type)])
            cached = (library_key, grammar)
            self._analog_grammar[pid] = cached
        return cached[1]

    def grammar_and_fingerprint(self, task: str, pid: str, state) -> tuple[str, Grammar]:
        key = (task, pid) if self.pathways[pid].kind == "recognized" else ("*", pid)
        cached = self._generation_cache.get(key)
        if cached is None:
            grammar = self.grammar(pid, task, state)
            cached = (grammar_fingerprint(grammar), grammar)
            self._generation_cache[key] = cached
        return cached

    def search(self, task: str, pid: str, state, generation: int) -> tuple[str, ResumableSearch]:
        """Return the live search for this slot, creating (awakening) it if needed."""
        fingerprint, grammar = self.grammar_and_fingerprint(task, pid, state)
        cached = self._live.get((task, pid))
        if cached is None or cached[0] != fingerprint:
            public = self.tasks[task]
            cached = (fingerprint, ResumableSearch(
                public.examples, public.request_type, grammar,
                step_budget=self.search_config["step_budget"],
                max_size=self.search_config["max_size"],
                max_expansions=self.search_config["max_expansions"]))
            self._live[(task, pid)] = cached
        pathway = self.pathways[pid]
        if pathway.status == "dormant":
            pathway.status = "active"
            pathway.awakened_generation = generation
        return cached

    def peek(self, task: str, pid: str, state) -> tuple[int, bool]:
        """Depth already searched and exhaustion under the *current* grammar."""
        cached = self._live.get((task, pid))
        if cached is None:
            return 0, False
        fingerprint, _ = self.grammar_and_fingerprint(task, pid, state)
        if cached[0] != fingerprint:
            return 0, False
        return cached[1].evaluated, cached[1].exhausted

    def drop_task(self, task: str) -> None:
        for key in [key for key in self._live if key[0] == task]:
            del self._live[key]

    def summary(self) -> dict:
        counts = {"designer": 0, "genesis": 0, "dormant": 0, "active": 0}
        for pathway in self.pathways.values():
            counts[pathway.origin] += 1
            counts[pathway.status] += 1
        return counts
