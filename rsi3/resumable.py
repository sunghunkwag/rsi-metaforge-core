"""RSI-2's heuristic-free task search, split into resumable windows.

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

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate


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
                 max_size=12, max_expansions=20000, known_failures=None, near_misses=None,
                 compose=None):
        self.examples = tuple(examples)
        self.library = grammar.library
        self.step_budget = int(step_budget)
        self._iterator = enumerate_programs(
            request_type, grammar=grammar, max_size=max_size,
            max_expansions=max_expansions, partial_heuristic=None,
            partial_features_only=True)
        self._seen: set = set()
        self.known_failures = known_failures
        # Optional callback(term, matched, total): a failed candidate is then
        # run on every public example so its match count can be recorded. The
        # match decision is the same as stopping at the first mismatch.
        self.near_misses = near_misses
        # Optional skeleton (decompose.py): the enumerated program is a HOLE,
        # and ``compose(hole)`` is the candidate checked, remembered and returned.
        self.compose = compose
        self.evaluated = 0
        self.skipped_known = 0
        self.exhausted = False
        self.evaluation_steps = 0

    def fast_forward(self, position: int, evaluated: int, skipped_known: int,
                     evaluation_steps: int) -> None:
        """Re-create the state of a search that had passed ``position`` distinct programs.

        For a fixed grammar the enumeration order is deterministic, so passing
        the same number of distinct programs again, without evaluating them,
        rebuilds the same frontier and the same set of seen programs. Only
        the counters are restored; nothing is evaluated or charged. This lets
        the owner release a live search between windows (to bound memory)
        and resume it later exactly where it stopped.
        """
        passed = 0
        while passed < position:
            try:
                candidate = next(self._iterator)
            except StopIteration:
                self.exhausted = True
                break
            term = candidate.term if self.compose is None else self.compose(candidate.term)
            if term in self._seen:
                continue
            self._seen.add(term)
            passed += 1
        self.evaluated, self.skipped_known = evaluated, skipped_known
        self.evaluation_steps = evaluation_steps

    @property
    def position(self) -> int:
        """Distinct programs passed in this grammar's order, evaluated or skipped."""
        return self.evaluated + self.skipped_known

    def _matches(self, term) -> bool:
        if self.near_misses is None:
            for inputs, expected in self.examples:
                result = evaluate(term, inputs, library=self.library,
                                  step_budget=self.step_budget)
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
            term = candidate.term if self.compose is None else self.compose(candidate.term)
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
            term=None if found is None else (
                found.term if self.compose is None else self.compose(found.term)),
            log_probability=None if found is None else found.log_probability,
            start=start, evaluated=used, exhausted=self.exhausted,
            evaluation_steps=self.evaluation_steps - steps_before,
            skipped_matches=skipped, wall_seconds=time.perf_counter() - started,
            skipped_known=known)
