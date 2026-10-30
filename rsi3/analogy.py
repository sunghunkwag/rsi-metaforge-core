"""Analogical repair: solve a new task by editing one of the system's own verified programs.

Every other search here builds a program from the grammar and the
library. This one starts from the system's verified solutions to other
tasks and looks for the cheapest change to one of them that fits the new
task's public examples. It is transfer in the plain sense: a routine the
system has found once is reused, changed where it must be, on a task it
has never seen.

**Description length.** A candidate is coded relative to the system's own
past: which source program, which edit, and which small program fills the
edit's hole. Its cost is

    -log P(source) - log P(edit | source) - log P_grammar(hole)

and candidates are checked in increasing cost (best first, exact).

- ``P(source)``: a softmax over how close each source's outputs on the
  task's public inputs come to the public outputs (``similarity``).
- ``P(edit | source)``: uniform over the source's edits.
- ``P_grammar(hole)``: RSI-2's grammar, the same one the decomposition
  holes use, library included.

**Edits** of a source ``lambda x. body`` (``edits``):

- *replace*: a subterm becomes a typed hole. The hole takes as arguments
  the bound variables the subterm used (lambda lifting), so a constant
  becomes an ``int`` hole and ``x`` becomes ``list -> list``.
- *wrap*: a first-order subterm ``s`` becomes ``h s``, with
  ``h : T -> T``.
- *pre* and *post*: ``lambda x. source (h x)`` and
  ``lambda x. h (source x)``, a new stage before or after the whole
  program.

**Accounting.** Ranking runs the first ``max_ranked`` same-typed sources,
nearest by public task statistics (``SourceIndex``), once on the public
examples. That is a candidate check and costs one unit; a source that
already fits is returned at once. After that, every composed candidate
costs one unit. A composed program equal to one already checked is
skipped, and so is one in the task's shared failure set, as in
``ResumableSearch``. A constant hole is kept only for a value not seen
before, and a hole that fails to run alone is skipped; the hole is run on
no input, so this reads no example (``_new_value``).

**Sources.** Only verified programs: TRAIN solutions accepted by the frozen
verifier. On TRAIN, a task's own solution is never among its sources,
since the task is unsolved while it is searched. Nothing here reads a
hidden example.
"""
from __future__ import annotations

import heapq
import math
import time

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.terms import App, Lam, Term, Var
from rsi2.types import INT, Arrow, Type, arrows

from .decompose import Skeleton
from .resumable import WindowResult

MAX_SOURCES = 4          # sources whose edits are searched, by similarity
MAX_LIFTED = 2
TEMPERATURE = 0.125      # softmax temperature over source similarity


# ---- terms ---------------------------------------------------------------
def _ground(type_: Type) -> Type:
    if type_.is_variable:
        return INT
    if not type_.args:
        return type_
    return Type(type_.tag, tuple(_ground(a) for a in type_.args))


def _free_vars(term: Term, depth: int = 0) -> set:
    if term.tag == "var":
        return {term.value - depth} if term.value >= depth else set()
    if term.tag == "lam":
        return _free_vars(term.children[0], depth + 1)
    found = set()
    for child in term.children:
        found |= _free_vars(child, depth)
    return found


def _shift(term: Term, by: int, cutoff: int = 0) -> Term:
    if term.tag == "var":
        return Var(term.value + by) if term.value >= cutoff else term
    if term.tag == "lam":
        return Lam(term.value, _shift(term.children[0], by, cutoff + 1))
    if term.tag == "app":
        return App(*(_shift(c, by, cutoff) for c in term.children))
    return term


def _remap(term: Term, mapping: dict, depth: int = 0) -> Term:
    if term.tag == "var":
        if term.value < depth:
            return term
        return Var(mapping[term.value - depth] + depth)
    if term.tag == "lam":
        return Lam(term.value, _remap(term.children[0], mapping, depth + 1))
    if term.tag == "app":
        return App(*(_remap(c, mapping, depth) for c in term.children))
    return term


def _put(term: Term, path, new: Term) -> Term:
    if not path:
        return new
    children = list(term.children)
    children[path[0]] = _put(children[path[0]], path[1:], new)
    return Term(term.tag, term.value, tuple(children))


def _nodes(term: Term, path=(), binders=()):
    """Every subterm with its path and the lambda types above it (outermost first)."""
    yield path, term, binders
    if term.tag == "lam":
        yield from _nodes(term.children[0], path + (0,), binders + (term.value,))
    else:
        for index, child in enumerate(term.children):
            yield from _nodes(child, path + (index,), binders)


def eta_expand(program: Term, request: Type) -> Term:
    """``lambda x. body`` for a one-argument request, whatever the program's form."""
    if program.tag == "lam":
        return program
    return Lam(request.args[0], App(_shift(program, 1), Var(0)))


# ---- edits ----------------------------------------------------------------
class EditSkeleton(Skeleton):
    """One edit of a source program; plain data, so a run can be checkpointed."""

    def __init__(self, name, hole_type, mode, source, path=(), lifted=(), subterm=None,
                 request=None):
        for key, value in (("name", name), ("hole_type", hole_type), ("mode", mode),
                           ("source", source), ("path", tuple(path)),
                           ("lifted", tuple(lifted)), ("subterm", subterm),
                           ("request", request)):
            object.__setattr__(self, key, value)

    def build(self, hole: Term) -> Term:
        if self.mode == "pre":
            return Lam(self.request.args[0], App(self.source, App(hole, Var(0))))
        if self.mode == "post":
            return Lam(self.request.args[0], App(hole, App(self.source, Var(0))))
        applied = hole
        for index in self.lifted:
            applied = App(applied, Var(index))
        if self.mode == "wrap":
            applied = App(hole, self.subterm)
        return _put(self.source, self.path, applied)


def edits(source: Term, request: Type, library=None) -> list[EditSkeleton]:
    """Every replace and wrap edit of ``source`` (eta-expanded), plus pre and post."""
    from rsi2.types import infer
    program = eta_expand(source, request)
    found = []
    output = request.args[1]
    found.append(EditSkeleton("pre", Arrow(request.args[0], request.args[0]), "pre", program,
                              request=request))
    found.append(EditSkeleton("post", Arrow(output, output), "post", program,
                              request=request))
    for path, sub, binders in _nodes(program):
        if len(path) < 2 or sub.tag == "lam":
            continue                 # the whole body: that is plain search, not an edit
        env = tuple(reversed(binders))
        try:
            sub_type = _ground(infer(sub, env=env, library=library))
        except Exception:
            continue
        lifted = sorted(_free_vars(sub), reverse=True)
        if len(lifted) <= MAX_LIFTED and all(i < len(env) for i in lifted):
            hole_type = (arrows(*[_ground(env[i]) for i in lifted], sub_type) if lifted
                         else sub_type)
            found.append(EditSkeleton(f"replace{list(path)}", hole_type, "replace", program,
                                      path, lifted, request=request))
        if sub_type.tag != "arrow" and sub.tag not in ("int", "bool", "var"):
            found.append(EditSkeleton(f"wrap{list(path)}", Arrow(sub_type, sub_type), "wrap",
                                      program, path, subterm=sub, request=request))
    return found


# ---- similarity -------------------------------------------------------------
def _levenshtein(a, b) -> int:
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def similarity(value, expected) -> float:
    """1 for equal outputs, 0 for a failed run; lists by normalized edit distance."""
    if value is None:
        return 0.0
    if isinstance(expected, (list, tuple)):
        if not isinstance(value, (list, tuple)):
            return 0.0
        longest = max(len(value), len(expected), 1)
        return 1.0 - _levenshtein(list(value), list(expected)) / longest
    if type(value) is not type(expected):
        return 0.0
    if type(expected) is int:
        return 1.0 / (1.0 + abs(value - expected))
    return 1.0 if value == expected else 0.0


# ---- search -------------------------------------------------------------------
def same_typed(solutions: dict, request_types: dict, request) -> dict:
    """The verified programs whose task has exactly this request type, smallest first."""
    names = sorted((n for n in solutions if str(request_types[n]) == str(request)),
                   key=lambda n: (solutions[n].size, n))
    return {name: solutions[name] for name in names}


def nearest_first(sources: dict, features: dict, target) -> dict:
    """``sources`` reordered by cosine similarity of public task features to ``target``.

    ``features``: source task name -> feature vector; ``target``: the new
    task's vector, standardized the same way. Ties keep the given order.
    """
    import numpy as np

    def cosine(a, b):
        norm = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(a @ b / norm) if norm > 0 else 0.0

    order = sorted(enumerate(sources), key=lambda p: (-cosine(features[p[1]], target), p[0]))
    return {name: sources[name] for _, name in order}


class SourceIndex:
    """Orders the system's verified programs as sources for a task, from public data only.

    Built once from the public TRAIN tasks: their request types, and RSI-2's
    32 public task statistics (``rsi2.recognition.task_features``),
    standardized over TRAIN. For a task, the same-typed solutions are
    ordered by cosine similarity of those statistics, nearest first. This
    ordering is free: it runs no program. ``AnalogySearch`` then runs the
    first ``max_ranked`` of them, and each run costs one unit.
    """

    def __init__(self, public_tasks):
        import numpy as np
        from rsi2.recognition import task_features
        tasks = list(public_tasks)
        raw = np.stack([task_features(t) for t in tasks])
        self.mean, self.scale = raw.mean(axis=0), raw.std(axis=0)
        self.scale[self.scale < 1e-8] = 1.0
        self.features = {t.name: self._standardize(raw[i]) for i, t in enumerate(tasks)}
        self.request = {t.name: t.request_type for t in tasks}

    def _standardize(self, raw):
        import numpy as np
        return np.clip((raw - self.mean) / self.scale, -10.0, 10.0)

    def vector(self, examples):
        from types import SimpleNamespace
        from rsi2.recognition import task_features
        return self._standardize(task_features(SimpleNamespace(examples=tuple(examples))))

    def sources(self, solutions: dict, request, examples, exclude=None) -> dict:
        usable = {n: t for n, t in solutions.items() if n != exclude and n in self.request}
        return nearest_first(same_typed(usable, self.request, request), self.features,
                             self.vector(examples))


class AnalogySearch:
    """Best-first search over edits of the system's verified programs (module docstring)."""

    def __init__(self, examples, request_type, sources: dict, grammar, *, step_budget=2000,
                 max_size=12, max_expansions=20000, known_failures=None,
                 max_sources=MAX_SOURCES, max_ranked=None):
        self.examples = tuple(examples)
        self.request = request_type
        self.grammar = grammar
        self.library = grammar.library
        self.step_budget = int(step_budget)
        self.max_size = int(max_size)
        self.max_expansions = max_expansions
        self.known_failures = known_failures
        self.max_sources = int(max_sources)
        # Sources in the caller's order (a dict's insertion order), one per
        # program; at most ``max_ranked`` are run to rank them.
        unique = {}
        for name in sources:
            term = self._normal(sources[name])
            unique.setdefault(term, name)
        self.sources = [(name, term) for term, name in unique.items()]
        if max_ranked is not None:
            self.sources = self.sources[:int(max_ranked)]
        self._ranked: list = []          # (similarity, name, term)
        self._heap: list = []
        self._edits: list = []
        self._iterators: dict = {}
        self._pending: dict = {}
        self._seen: set = set()
        self._values: dict = {}
        self._sequence = 0
        self.evaluated = 0
        self.skipped_known = 0
        self.evaluation_steps = 0
        self.exhausted = False
        self.chosen: list = []           # the sources whose edits are searched

    @property
    def position(self) -> int:
        return self.evaluated + self.skipped_known

    @staticmethod
    def _normal(term: Term) -> Term:
        from .selfmodel import canonical_types, normalize
        return canonical_types(normalize(term))

    def fast_forward(self, position: int, evaluated: int, skipped_known: int,
                     evaluation_steps: int) -> None:
        """Rebuild a released search: replay ``position`` steps without charging them."""
        passed = 0
        while passed < position and not self.exhausted:
            step = self._next()
            if step is None:
                break
            passed += 1
        self.evaluated, self.skipped_known = evaluated, skipped_known
        self.evaluation_steps = evaluation_steps

    # -- one step: the next distinct candidate, in cost order -------------------
    def _outputs(self, term):
        values = []
        for inputs, _ in self.examples:
            result = evaluate(term, inputs, library=self.library, step_budget=self.step_budget)
            self.evaluation_steps += result.steps
            values.append(result.value if result.ok else None)
        return values

    def _start_edits(self) -> None:
        ranked = sorted(self._ranked, key=lambda r: (-r[0], r[2].size, r[1]))
        self.chosen = ranked[:self.max_sources]
        if not self.chosen:
            return
        top = max(r[0] for r in self.chosen)
        weights = [math.exp((r[0] - top) / TEMPERATURE) for r in self.chosen]
        total = sum(weights)
        for (score, name, term), weight in zip(self.chosen, weights):
            source_cost = -math.log(weight / total)
            items = edits(term, self.request, self.library)
            edit_cost = math.log(max(len(items), 1))
            for skeleton in items:
                index = len(self._edits)
                self._edits.append((name, skeleton))
                self._push(source_cost + edit_cost, index, None)

    def _push(self, cost, index, candidate) -> None:
        self._sequence += 1
        heapq.heappush(self._heap, (cost, self._sequence, index, candidate))

    def _next(self):
        """("source" | "edit", term) for the next distinct program, or None when done."""
        while len(self._ranked) < len(self.sources):
            name, term = self.sources[len(self._ranked)]
            self._seen.add(term)
            outputs = self._outputs(term)
            score = sum(similarity(v, y) for v, (_, y) in zip(outputs, self.examples))
            self._ranked.append((score / max(len(self.examples), 1), name, term))
            if len(self._ranked) == len(self.sources):
                self._start_edits()
            return ("source", term)
        while self._heap:
            cost, _, index, candidate = heapq.heappop(self._heap)
            name, skeleton = self._edits[index]
            if candidate is None:
                iterator = self._iterators.get(index)
                if iterator is None:
                    iterator = enumerate_programs(
                        skeleton.hole_type, grammar=self.grammar, max_size=self.max_size,
                        max_expansions=self.max_expansions, partial_heuristic=None,
                        partial_features_only=True)
                    self._iterators[index] = iterator
                    self._pending[index] = cost
                try:
                    hole = next(iterator)
                except StopIteration:
                    continue
                if not self._new_value(index, hole.term, skeleton.hole_type.tag != "arrow"):
                    self._push(self._pending[index], index, None)
                    continue
                self._push(self._pending[index] - hole.log_probability, index, hole)
                continue
            # A candidate's turn; queue the edit's next hole before evaluating.
            self._push(self._pending[index], index, None)
            try:
                term = self._normal(skeleton.build(candidate.term))
            except Exception:
                continue
            if term in self._seen:
                continue
            self._seen.add(term)
            return ("edit", term)
        self.exhausted = True
        return None

    def _new_value(self, index, hole, first_order: bool) -> bool:
        """Whether a hole can give a new composite, judged from the hole alone.

        The hole is a closed term and is run alone, on no input: this reads
        no example and costs no unit. A hole that fails to run (``head nil``)
        is skipped, since its composite could only fail. A first-order hole
        (a constant) is also skipped when its value was seen before
        (``add 1 1`` after ``2``).
        """
        result = evaluate(hole, (), library=self.library, step_budget=self.step_budget)
        if not result.ok:
            return False
        if not first_order:
            return True
        seen = self._values.setdefault(index, set())
        key = repr(result.value)
        if key in seen:
            return False
        seen.add(key)
        return True

    def _matches(self, term) -> bool:
        for inputs, expected in self.examples:
            result = evaluate(term, inputs, library=self.library, step_budget=self.step_budget)
            self.evaluation_steps += result.steps
            if not result.ok or result.value != expected:
                return False
        return True

    def run(self, budget: int, skip_match=None) -> WindowResult:
        started = time.perf_counter()
        start, steps_before = self.evaluated, self.evaluation_steps
        used = skipped = known = 0
        found = None
        while used < budget and not self.exhausted:
            step = self._next()
            if step is None:
                break
            kind, term = step
            if kind == "edit" and self.known_failures is not None and term in self.known_failures:
                known += 1
                self.skipped_known += 1
                continue
            used += 1
            self.evaluated += 1
            if kind == "source":
                fits = self._ranked[-1][0] == 1.0 and self._matches(term)
            else:
                fits = self._matches(term)
            if fits:
                if skip_match is not None and skip_match(term):
                    skipped += 1
                    continue
                found = term
                break
            if self.known_failures is not None:
                self.known_failures.add(term)
        return WindowResult(term=found, log_probability=None, start=start, evaluated=used,
                            exhausted=self.exhausted,
                            evaluation_steps=self.evaluation_steps - steps_before,
                            skipped_matches=skipped,
                            wall_seconds=time.perf_counter() - started, skipped_known=known)
