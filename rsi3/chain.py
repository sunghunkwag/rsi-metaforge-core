"""Residual decomposition: put one of the system's own programs first, then solve what is left.

Every other action searches for a whole program, or for a hole in a
single skeleton. A task that is two routines in sequence (drop k, then
add 1) is beyond them at 64 candidates. Each routine alone may be within
reach, but the pair is not. This action splits such a task:

1. **Stage.** Take a list program ``f`` the system already has: a
   verified solution of a TRAIN task, an adopted library concept, or the
   primitive ``tail``.
2. **Residual.** Run ``f`` on the task's public inputs. The residual task
   maps ``f(x)`` to ``y``.
3. **Solve.** Search the residual with the system's own behavioural
   search (behave.py: the whole-program problem and each pointwise
   problem whose shape the residual has). The library and fitted weights
   are the same as the behavioural actions'.
4. **Compose.** A residual solution ``h`` gives the candidate
   ``lambda x. h (f x)``.

**Ranking stages.** A stage's own run is a candidate check. It costs one
unit, and a stage that already fits is returned at once. Stages are
ranked by how much of the output's structure their result already has
(``relevance``): equal lengths, edit distance, and whether the residual
has a pointwise map shape or a filter shape. Stages are run in a fixed
order, at most ``max_ranked`` of them:

- adopted library concepts, smallest first;
- ``tail``;
- solutions, nearest first by public task statistics (as in analogy.py).

A stage whose run gives the same outputs as an earlier stage, or the
inputs unchanged, is skipped at no cost. That check runs the stage on the
inputs and reads no output.

**Searching residuals.** The ``max_stages`` best stages get residual
searches. Stages share the units by deficit round robin, with weights
halving by rank, so the best stage gets about half. Inside a stage its
problems share the stage's units the same way, in slices of ``SLICE``
units, weighted by the meta-policy's own estimate of each behavioural
action on the residual's shape (``policy_router``): the learned
controller is applied to the subtask it helped create.
Every unit a residual search charges (a new behaviour, as in behave.py)
is one unit of this search.

The search is deterministic. ``fast_forward`` rebuilds a released search
by replaying it, uncharged. Nothing here reads a hidden example.
"""
from __future__ import annotations

import time

from rsi2.evaluator import evaluate
from rsi2.terms import App, Lam, Prim, Term, Var
from rsi2.types import INT, Arrow, ListOf

from .analogy import _levenshtein
from .resumable import WindowResult

LIST = ListOf(INT)
SLICE = 4
MAX_RANKED = 8
MAX_STAGES = 3


def _same_value(value, expected) -> bool:
    if isinstance(expected, (list, tuple)):
        return _is_list(value) and list(value) == list(expected)
    return value == expected


def _is_list(value) -> bool:
    return isinstance(value, (list, tuple)) and all(type(v) is int for v in value)


def relevance(outputs, examples) -> float:
    """How much of the outputs' structure a stage's results already have, in [0, 1.5]."""
    from .decompose import _elementwise_function, _filter_consistent, _is_filter, _same_length
    score = 0.0
    for value, (_, expected) in zip(outputs, examples):
        if isinstance(expected, (list, tuple)):
            longest = max(len(value), len(expected), 1)
            score += 0.5 * (len(value) == len(expected))
            score += 0.5 * (1.0 - _levenshtein(list(value), list(expected)) / longest)
    score /= max(len(examples), 1)
    residual = [((value,), expected) for value, (_, expected) in zip(outputs, examples)]
    if all(isinstance(e, (list, tuple)) for _, e in residual):
        if _same_length(residual) and _elementwise_function(residual):
            score += 0.25
        if _is_filter(residual) and _filter_consistent(residual):
            score += 0.25
    return score


def stage_candidates(solutions: dict, request_types: dict, library: dict, index=None,
                     examples=None) -> dict:
    """The system's list -> list programs, in the fixed ranking order (module docstring)."""
    from rsi2.types import infer
    list_type = str(Arrow(LIST, LIST))
    found = {}
    concepts = []
    for name in sorted(library):
        try:
            if str(infer(Term("ref", name), library=library)) == list_type:
                concepts.append((library[name].size, name))
        except Exception:
            continue
    for _, name in sorted(concepts):
        found[f"concept:{name}"] = Term("ref", name)
    found["prim:tail"] = Prim("tail")
    names = [n for n in solutions if str(request_types.get(n)) == list_type]
    if index is not None and examples is not None:
        from .analogy import nearest_first
        ordered = nearest_first({n: solutions[n] for n in sorted(names)}, index.features,
                                index.vector(examples))
        names = list(ordered)
    else:
        names = sorted(names, key=lambda n: (solutions[n].size, n))
    for name in names:
        found[f"solution:{name}"] = solutions[name]
    return found


class ChainSearch:
    """Stage, residual, compose (module docstring); the ResumableSearch interface."""

    def __init__(self, examples, request_type, stages: dict, library: dict, *, weights=None,
                 behave_settings=None, folds=False, step_budget=2000, max_ranked=MAX_RANKED,
                 max_stages=MAX_STAGES, max_evaluations=None, router=None):
        self.examples = tuple(examples)
        self.request = request_type
        self.library = dict(library)
        self.weights = weights
        self.settings = dict(behave_settings or {})
        self.folds = bool(folds)
        self.step_budget = int(step_budget)
        self.max_ranked = int(max_ranked)
        self.max_stages = int(max_stages)
        # router(kind, residual examples) -> weight of a residual problem: the
        # meta-policy's own success estimate for that behavioural action on
        # the residual's shape (``policy_router``); None: halving by order.
        self.router = router
        self.max_evaluations = None if max_evaluations is None else int(max_evaluations)
        lists = all(len(i) == 1 and _is_list(i[0]) for i, _ in self.examples)
        self.stages = list(stages.items()) if lists and request_type.tag == "arrow" else []
        self._stage_index = 0
        self._behaviours: set = set()
        self._ranked: list = []          # (relevance, order, name, term, outputs)
        self._queue: list = []           # [stage name, stage term, kind, search]
        self._turns: dict = {}           # stage rank -> problem turn
        self._used: dict = {}            # stage rank -> units in the current slice
        self._spent: dict = {}           # stage rank -> units spent
        self._started = False
        self.evaluated = 0
        self.skipped_known = 0
        self.evaluation_steps = 0
        self.exhausted = not self.stages
        self.found_from = None           # (stage, residual problem) of the match returned

    @property
    def position(self) -> int:
        return self.evaluated

    # -- stages ------------------------------------------------------------------
    def _outputs(self, term):
        values = []
        for inputs, _ in self.examples:
            result = evaluate(term, inputs, library=self.library, step_budget=self.step_budget)
            self.evaluation_steps += result.steps
            if not result.ok or not _is_list(result.value):
                return None
            values.append(list(result.value))
        return values

    def _next_stage(self):
        """The next stage with new behaviour (free to find), or None."""
        while self._stage_index < len(self.stages) and len(self._ranked) < self.max_ranked:
            name, term = self.stages[self._stage_index]
            self._stage_index += 1
            outputs = self._outputs(term)
            if outputs is None:
                continue
            key = repr(outputs)
            if key in self._behaviours or all(list(o) == list(i[0])
                                               for o, (i, _) in zip(outputs, self.examples)):
                continue
            self._behaviours.add(key)
            return name, term, outputs
        return None

    def _start_residuals(self) -> None:
        from .behave import BehaviouralSearch, problems_for
        from .decompose import skeletons_for
        self._started = True
        chosen = sorted(self._ranked, key=lambda r: (-r[0], r[1]))[:self.max_stages]
        output = self.request.args[1]
        for rank, (score, _, name, term, outputs) in enumerate(chosen):
            residual = tuple(((value,), expected)
                             for value, (_, expected) in zip(outputs, self.examples))
            try:
                problems = problems_for(residual, Arrow(LIST, output),
                                        skeletons_for(residual, False),
                                        int(self.settings.get("max_unroll", 6)), self.folds)
            except Exception:
                continue
            kinds = sorted(problems, key=lambda k: (k != "whole", k))
            for order, kind in enumerate(kinds):
                weight = (self.router(kind, residual) if self.router is not None
                          else 2.0 ** -order)
                search = BehaviouralSearch(
                    problems[kind], self.library, residual, step_budget=self.step_budget,
                    max_size=int(self.settings.get("max_size", 10)),
                    combo_limit=int(self.settings.get("combo_limit", 2_000_000)),
                    weights=self.weights)
                self._queue.append([name, term, kind, search, rank, max(weight, 1e-3), 0])

    def _step(self, budget: int):
        """Spend up to ``budget`` units; return (units, program or None)."""
        if len(self._ranked) < self.max_ranked and not self._started:
            stage = self._next_stage()
            if stage is not None:
                name, term, outputs = stage
                self._ranked.append((relevance(outputs, self.examples), len(self._ranked),
                                     name, term, outputs))
                if all(o == list(y) if isinstance(y, (list, tuple)) else False
                       for o, (_, y) in zip(outputs, self.examples)):
                    self.found_from = (name, "stage")
                    return 1, term
                return 1, None
        if not self._started:
            self._start_residuals()
        stage = self._pick_stage()
        if stage is None:
            self.exhausted = True
            return 0, None
        entries = [e for e in self._queue if e[4] == stage and not e[3].exhausted]
        current = self._turns.get(stage)
        if current is None or current not in [id(e) for e in entries]:
            entry = self._pick_problem(entries)
            self._turns[stage] = id(entry)
            self._used[stage] = 0
        else:
            entry = next(e for e in entries if id(e) == current)
        window = min(budget, SLICE - self._used.get(stage, 0))
        if self.max_evaluations is not None:
            # Every slice is clamped to the remaining capacity, with one unit
            # kept for the composition check below; nothing starts when none
            # remains. (The residual's own completion checks may still run
            # past the window, as BehaviouralSearch documents and charges.)
            window = min(window, self.max_evaluations - self.evaluated - 1)
            if window <= 0:
                self.exhausted = True
                return 0, None
        result = entry[3].run(window)
        self.evaluation_steps += result.evaluation_steps
        self._spent[stage] = self._spent.get(stage, 0) + max(result.evaluated, 1)
        entry[6] += max(result.evaluated, 1)
        self._used[stage] = self._used.get(stage, 0) + result.evaluated
        if self._used[stage] >= SLICE or result.exhausted or result.evaluated == 0:
            self._turns[stage] = None
            self._used[stage] = 0
        if result.term is None:
            return result.evaluated, None
        name, term, kind = entry[0], entry[1], entry[2]
        from .selfmodel import canonical_types, normalize
        program = canonical_types(normalize(Lam(LIST, App(result.term, App(term, Var(0))))))
        # The pieces were checked apart; the whole composition is checked on
        # every public example at the same step budget, charged one unit.
        # When it fails (the stage plus the residual exceed the budget the
        # pieces met separately) the search goes on.
        units = result.evaluated + 1
        for inputs, expected in self.examples:
            check = evaluate(program, inputs, library=self.library, step_budget=self.step_budget)
            self.evaluation_steps += check.steps
            if not check.ok or not _same_value(check.value, expected):
                return units, None
        self.found_from = (name, kind)
        return units, program

    def _pick_stage(self):
        """Deficit round robin over stages, weights halving with rank; None when all are spent.

        The best-ranked stage gets about half of the residual units, the
        next a quarter, and so on; inside a stage, its problems take turns.
        """
        live = sorted({e[4] for e in self._queue if not e[3].exhausted})
        if not live:
            return None
        total = sum(self._spent.get(r, 0) for r in live) + 1
        weights = {r: 2.0 ** -r for r in live}
        norm = sum(weights.values())
        return max(live, key=lambda r: (weights[r] / norm * total - self._spent.get(r, 0), -r))

    @staticmethod
    def _pick_problem(entries):
        """Deficit round robin over a stage's residual problems, by weight."""
        total = sum(e[6] for e in entries) + 1
        norm = sum(e[5] for e in entries) or 1.0
        return max(entries, key=lambda e: (e[5] / norm * total - e[6], -entries.index(e)))

    def _capped(self) -> bool:
        return self.max_evaluations is not None and self.evaluated >= self.max_evaluations

    def fast_forward(self, position: int, evaluated: int, skipped_known: int,
                     evaluation_steps: int) -> None:
        """Rebuild a released search by replaying ``position`` units, uncharged."""
        while self.evaluated < position and not self.exhausted:
            units, _ = self._step(position - self.evaluated)
            self.evaluated += units
            if units == 0 and self.exhausted:
                break
        self.evaluated, self.skipped_known = evaluated, skipped_known
        self.evaluation_steps = evaluation_steps
        if self._capped():
            self.exhausted = True

    def run(self, budget: int, skip_match=None) -> WindowResult:
        started = time.perf_counter()
        start, steps_before = self.evaluated, self.evaluation_steps
        used = skipped = 0
        found = None
        idle = 0
        while used < budget and not self.exhausted:
            if self._capped():
                self.exhausted = True
                break
            units, program = self._step(budget - used)
            used += units
            self.evaluated += units
            idle = idle + 1 if units == 0 else 0
            if idle > 4 * max(len(self._queue), 1) + 8:
                self.exhausted = True          # every residual search is spent
                break
            if program is not None:
                if skip_match is not None and skip_match(program):
                    skipped += 1
                    continue
                found = program
                break
        return WindowResult(term=found, log_probability=None, start=start, evaluated=used,
                            exhausted=self.exhausted,
                            evaluation_steps=self.evaluation_steps - steps_before,
                            skipped_matches=skipped,
                            wall_seconds=time.perf_counter() - started, skipped_known=0)


class PolicyRouter:
    """Weights for residual problems: the policy's probability for ``behave:<kind>``.

    A plain object, not a closure, so a runtime holding one can be
    checkpointed.
    """

    def __init__(self, metapolicy, extended: bool, fixed_length: bool):
        self.metapolicy = metapolicy
        self.extended = bool(extended)
        self.fixed_length = bool(fixed_length)

    def __call__(self, kind, examples) -> float:
        from .metarl import context, shape_features
        shape = shape_features(examples, self.extended, self.fixed_length)
        return self.metapolicy.probability(f"behave:{kind}", context(shape, 0, 0))


def policy_router(metapolicy, extended: bool, fixed_length: bool) -> PolicyRouter:
    return PolicyRouter(metapolicy, extended, fixed_length)
