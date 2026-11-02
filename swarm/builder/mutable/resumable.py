"""Generation-0 copy of rsi3/resumable.py (resumable windows, failure memory hooks); the Builder owns this file from generation 1.

Original docstring follows.

RSI-2's heuristic-free task search, split into resumable windows.

For a fixed grammar, RSI-2's enumeration order is deterministic. A search that
evaluated its first n distinct candidates without success never needs to
evaluate them again: the next window continues at candidate n + 1. Running
windows of sizes a, b, ... from a fresh search is equivalent to one
``rsi2.search.solve`` call with budget a + b + ... and no heuristic (tested in
``tests/test_resumable.py``), with one deliberate extension: a public match that
the caller's ``skip_match`` callback rejects is counted, skipped, and the search
continues. The binding integrator uses that callback to avoid spending a
verifier query on behaviour the verifier has already rejected.

The live search object (enumeration frontier plus the set of evaluated terms)
is the stored state of a pathway. Keeping it alive across generations is what
lets a dormant pathway resume rather than restart, as long as the grammar
fingerprint is unchanged; a changed grammar changes the order, so the owner
must discard the object and start a new one.

Optional failure memory (``known_failures``). A program that failed a task's
public examples fails them under every enumeration order: the examples, the
frozen evaluator, and every library entry it can reference are unchanged
(RSI-2 only ever adds library entries). A search given a shared per-task set
skips such programs without evaluating them and without charging the logical
budget, and adds each new public failure to the set. The set therefore
survives a grammar change and is shared by every pathway searching that task.
With ``known_failures=None`` the search is exactly the one described above.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from .enumeration import Frontier
from .types import Type
from .evaluator import evaluate


@dataclass
class WindowResult:
    term: object | None
    log_probability: float | None
    start: int
    evaluated: int
    exhausted: bool
    evaluation_steps: int
    skipped_matches: int
    wall_seconds: float
    skipped_known: int = 0


class ResumableSearch:
    def __init__(self, examples, request_type, grammar, *, step_budget=2000,
                 max_size=12, max_expansions=20000, known_failures=None, near_misses=None):
        self.examples = tuple(examples)
        self.library = grammar.library
        self.step_budget = int(step_budget)
        if not isinstance(request_type, Type):
            raise TypeError("request_type must be a Type")
        # SWARM addition: the heuristic-free frontier is held as an object
        # with explicit state (same order as ``enumerate_programs``), so
        # the search can be checkpointed (``state``) and resumed
        # (``restore``) across the Builder's per-generation processes.
        self._frontier = Frontier(request_type, grammar, max_size, None, max_expansions,
                                  None, None, partial_features_only=True)
        self._iterator = self._frontier
        self._seen: set = set()
        self.known_failures = known_failures
        # SWARM addition: callback(term, matched, total) for a failed
        # candidate, run on every public example so the match count is
        # known (the Builder's residue signal); the match decision is the
        # same as stopping at the first mismatch.
        self.near_misses = near_misses
        self.evaluated = 0
        self.skipped_known = 0
        self.exhausted = False
        self.evaluation_steps = 0

    @property
    def position(self) -> int:
        """Distinct programs passed in this grammar's order, evaluated or skipped."""
        return self.evaluated + self.skipped_known

    def fast_forward(self, position: int) -> int:
        """Advance past ``position`` distinct programs without evaluating them.

        SWARM addition: the wake runs in a fresh process every generation,
        so a search resumes by rebuilding the enumerator (same grammar,
        same order) and skipping what earlier windows already passed. The
        skip costs enumeration time and no logical budget; the skipped
        programs were evaluated (and remembered as failures) or skipped
        before. Returns the number of programs passed.
        """
        passed = 0
        while passed < int(position) and not self.exhausted:
            try:
                candidate = next(self._iterator)
            except StopIteration:
                self.exhausted = True
                break
            if candidate.term in self._seen:
                continue
            self._seen.add(candidate.term)
            passed += 1
        self.skipped_known += passed
        return passed

    def state(self) -> dict:
        """Picklable checkpoint of the search: frontier, distinct-term set and counters.

        SWARM addition. ``known_failures`` is not part of it (the caller
        owns and persists that shared set); ``examples`` and the grammar
        are not either, so a checkpoint is only valid for a search built
        with the same examples and the same grammar order.
        """
        return {"frontier": self._frontier.state(), "seen": set(self._seen),
                "evaluated": self.evaluated, "skipped_known": self.skipped_known,
                "exhausted": self.exhausted, "evaluation_steps": self.evaluation_steps}

    def restore(self, state: dict) -> "ResumableSearch":
        self._frontier.restore(state["frontier"])
        self._seen = set(state["seen"])
        self.evaluated = int(state["evaluated"])
        self.skipped_known = int(state["skipped_known"])
        self.exhausted = bool(state["exhausted"])
        self.evaluation_steps = int(state["evaluation_steps"])
        return self

    def _matches(self, term) -> bool:
        if self.near_misses is None:
            for inputs, expected in self.examples:
                result = evaluate(term, inputs, library=self.library, step_budget=self.step_budget)
                self.evaluation_steps += result.steps
                if not result.ok or result.value != expected:
                    return False
            return True
        matched = 0
        for inputs, expected in self.examples:
            result = evaluate(term, inputs, library=self.library, step_budget=self.step_budget)
            self.evaluation_steps += result.steps
            matched += bool(result.ok and result.value == expected)
        if matched == len(self.examples):
            return True
        self.near_misses(term, matched, len(self.examples))
        return False

    def run(self, budget: int, skip_match=None) -> WindowResult:
        """Evaluate up to ``budget`` new distinct candidates; stop at the first kept match."""
        if budget < 0:
            raise ValueError("window budget must be nonnegative")
        started = time.perf_counter()
        start, steps_before = self.evaluated, self.evaluation_steps
        used = skipped = known = 0
        found = None
        while used < budget and not self.exhausted:
            try:
                candidate = next(self._iterator)
            except StopIteration:
                self.exhausted = True
                break
            term = candidate.term
            if term in self._seen:
                continue
            self._seen.add(term)
            if self.known_failures is not None and term in self.known_failures:
                known += 1
                self.skipped_known += 1
                continue
            used += 1
            self.evaluated += 1
            if self._matches(term):
                if skip_match is not None and skip_match(term):
                    skipped += 1
                    continue
                found = candidate
                break
            if self.known_failures is not None:
                self.known_failures.add(term)
        return WindowResult(
            term=None if found is None else found.term,
            log_probability=None if found is None else found.log_probability,
            start=start, evaluated=used, exhausted=self.exhausted,
            evaluation_steps=self.evaluation_steps - steps_before,
            skipped_matches=skipped, wall_seconds=time.perf_counter() - started,
            skipped_known=known)
