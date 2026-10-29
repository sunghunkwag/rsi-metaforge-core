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
KINDS = DESIGNER_KINDS + ("analog", "invented", "decompose")


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
                 designer_kinds=DESIGNER_KINDS, search_config: dict, failure_memory=None):
        self.tasks = {task.name: task for task in tasks}
        # Optional per-task sets of programs that failed the public examples,
        # shared by every pathway and kept across grammar changes.
        self.failure_memory = failure_memory
        self.features = features
        self.genesis_enabled = bool(genesis)
        self.neighbors = int(neighbors)
        self.designer_kinds = tuple(designer_kinds)
        self.search_config = dict(search_config)
        self.pathways: dict[str, Pathway] = {}
        for kind in self.designer_kinds:
            self.pathways[kind] = Pathway(kind, kind, "designer", 0, status="active")
        # Concepts the self-model invented for this generation (selfmodel.py):
        # library entries every pathway may use until the generation ends.
        self.extra_library: dict = {}
        self.concept_weight = 0.1
        self.concepts_in_prior = True
        self.near_miss_memory = None      # memory.NearMissMemory, set by the runtime
        self._live: dict[tuple[str, str], tuple[str, ResumableSearch]] = {}
        # Execution option, not part of any arm: release each live search after
        # its window and rebuild it on next use by fast-forwarding (bounded
        # memory, identical logical behaviour; tests/test_resumable.py).
        self.compact = False
        self._parked: dict[tuple[str, str], tuple] = {}
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
    def add_decompose_pathways(self, fold: bool = False) -> None:
        """One pathway per skeleton that some task's public examples fit (decompose.py)."""
        from .decompose import skeletons_for
        self.skeletons = {name: {sk.name: sk for sk in skeletons_for(task.examples, fold)}
                          for name, task in self.tasks.items()}
        for names in self.skeletons.values():
            for sk in names:
                self.pathways.setdefault(f"decompose:{sk}", Pathway(
                    f"decompose:{sk}", "decompose", "designer", 0, status="dormant"))

    def refresh_conjugates(self, state, step_budget: int, fold: bool) -> int:
        """Per generation: conjugate skeletons from the system's current programs."""
        from .decompose import conjugate_skeletons
        from rsi2.types import ListOf, INT, Arrow
        from .selfmodel import normalize
        list_type = str(Arrow(ListOf(INT), ListOf(INT)))
        programs = {name: normalize(term) for name, term in state.solutions.items()
                    if str(self.tasks[name].request_type) == list_type}
        added = 0
        for task_name, task in self.tasks.items():
            if task_name in state.solutions:
                continue
            current = self.skeletons.setdefault(task_name, {})
            for name in [n for n in current if n.startswith("conj")]:
                del current[name]
            for sk in conjugate_skeletons(task.examples, programs, state.grammar.library,
                                          step_budget, fold):
                current[sk.name] = sk
                self.pathways.setdefault(f"decompose:{sk.name}", Pathway(
                    f"decompose:{sk.name}", "decompose", "designer", 0, status="dormant"))
                added += 1
        return added

    def add_behave_pathways(self, settings: dict, use_library: bool = True,
                            folds: bool = False, dual: bool = False) -> None:
        """One behavioural-search pathway per problem kind some task has (behave.py)."""
        from .behave import problems_for
        from .decompose import skeletons_for
        self.behave_settings = dict(settings)
        self.behave_library = bool(use_library)
        self.behave_known: dict = {}
        self.behave_problems = {}
        for name, task in self.tasks.items():
            problems = problems_for(task.examples, task.request_type,
                                    skeletons_for(task.examples, False),
                                    int(settings.get("max_unroll", 6)), folds)
            self.behave_problems[name] = problems
            for kind in problems:
                for prefix in (("behave", "behave0") if dual else ("behave",)):
                    self.pathways.setdefault(f"{prefix}:{kind}", Pathway(
                        f"{prefix}:{kind}", "behave", "designer", 0, status="dormant"))

    def add_invented_pathway(self) -> None:
        """A separate pathway searching with this generation's concepts at full weight."""
        self.pathways.setdefault("invented", Pathway("invented", "invented", "designer", 0,
                                                     status="dormant"))

    def base_grammar(self, state) -> Grammar:
        """The current prior, with this generation's invented concepts if any."""
        if not self.extra_library:
            return state.grammar
        weights = dict(state.grammar.weights)
        weights.update({name: self.concept_weight for name in self.extra_library})
        return Grammar(library={**state.grammar.library, **self.extra_library},
                       weights=weights, context_weights=state.grammar.context_weights)

    def library(self, state) -> dict:
        return {**state.grammar.library, **self.extra_library}

    def grammar(self, pid: str, task: str, state) -> Grammar:
        pathway = self.pathways[pid]
        if pathway.kind == "behave":
            # The pool builds from the whole current library (adopted entries
            # and this generation's concepts) and follows the fitted grammar;
            # the designer-only control uses neither.
            if not self.behave_library or pid.startswith("behave0:"):
                return Grammar()
            return Grammar(library=self.library(state), weights=state.grammar.weights,
                           context_weights=state.grammar.context_weights)
        if pathway.kind in ("invented", "decompose"):
            # Decomposition holes use the same grammar as the invented pathway:
            # the generation's concepts at full weight (none without invention).
            return Grammar(library=self.library(state), weights=state.grammar.weights,
                           context_weights=state.grammar.context_weights)
        if pathway.kind == "prior":
            return self.base_grammar(state) if self.concepts_in_prior else state.grammar
        if pathway.kind == "recognized":
            return state.condition(self.tasks[task], self.base_grammar(state))
        library = self.library(state)
        library_key = grammar_fingerprint(Grammar(library=library))
        cached = self._analog_grammar.get(pid)
        if cached is None or cached[0] != library_key:
            source = self.tasks[pathway.source_task]
            grammar = Grammar(library=library)
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
        if (cached is None or cached[0] != fingerprint) and self.pathways[pid].kind == "behave":
            from .behave import BehaviouralSearch
            settings = self.behave_settings
            search = BehaviouralSearch(
                self.behave_problems[task][pid.split(":", 1)[1]], grammar.library,
                self.tasks[task].examples, step_budget=self.search_config["step_budget"],
                max_size=int(settings.get("max_size", 10)),
                combo_limit=int(settings.get("combo_limit", 2_000_000)),
                known=self.behave_known.setdefault((task, pid), set()),
                weights=(grammar.weights if self.behave_library
                         and not pid.startswith("behave0:") else None))
            cached = (fingerprint, search)
            parked = self._parked.pop((task, pid), None)
            if parked is not None and parked[0] == fingerprint:
                search.fast_forward(*parked[1:5])
            self._live[(task, pid)] = cached
        if cached is None or cached[0] != fingerprint:
            public = self.tasks[task]
            skeleton = (self.skeletons[task][pid.split(":", 1)[1]]
                        if self.pathways[pid].kind == "decompose" else None)
            cached = (fingerprint, ResumableSearch(
                public.examples,
                public.request_type if skeleton is None else skeleton.hole_type, grammar,
                compose=None if skeleton is None else skeleton.compose,
                step_budget=self.search_config["step_budget"],
                max_size=self.search_config["max_size"],
                max_expansions=self.search_config["max_expansions"],
                known_failures=(None if self.failure_memory is None
                                else self.failure_memory.for_task(task)),
                near_misses=(None if self.near_miss_memory is None
                             else self.near_miss_memory.recorder(task))))
            parked = self._parked.pop((task, pid), None)
            if parked is not None and parked[0] == fingerprint:
                cached[1].fast_forward(*parked[1:5])
            self._live[(task, pid)] = cached
        pathway = self.pathways[pid]
        if pathway.status == "dormant":
            pathway.status = "active"
            pathway.awakened_generation = generation
        return cached

    def release_task(self, task: str) -> None:
        """Compact mode: release every live search of one task (after its turn)."""
        for key in [key for key in self._live if key[0] == task]:
            self.release(*key)

    def release(self, task: str, pid: str) -> None:
        """Compact mode: drop the live search, keeping what is needed to rebuild it."""
        cached = self._live.pop((task, pid), None)
        if cached is not None:
            fingerprint, search = cached
            self._parked[(task, pid)] = (fingerprint, search.position, search.evaluated,
                                         search.skipped_known, search.evaluation_steps,
                                         search.exhausted)

    def peek(self, task: str, pid: str, state) -> tuple[int, bool]:
        """Depth already searched and exhaustion under the *current* grammar."""
        cached = self._live.get((task, pid))
        if cached is None:
            parked = self._parked.get((task, pid))
            if parked is None:
                return 0, False
            fingerprint, _ = self.grammar_and_fingerprint(task, pid, state)
            return (parked[2], parked[5]) if parked[0] == fingerprint else (0, False)
        fingerprint, _ = self.grammar_and_fingerprint(task, pid, state)
        if cached[0] != fingerprint:
            return 0, False
        return cached[1].evaluated, cached[1].exhausted

    def drop_task(self, task: str) -> None:
        for key in [key for key in getattr(self, "behave_known", {}) if key[0] == task]:
            del self.behave_known[key]
        for key in [key for key in self._live if key[0] == task]:
            del self._live[key]
        for key in [key for key in self._parked if key[0] == task]:
            del self._parked[key]

    def summary(self) -> dict:
        counts = {"designer": 0, "genesis": 0, "dormant": 0, "active": 0}
        for pathway in self.pathways.values():
            counts[pathway.origin] += 1
            counts[pathway.status] += 1
        return counts
