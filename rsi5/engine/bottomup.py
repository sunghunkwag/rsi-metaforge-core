"""Bottom-up enumeration with observational equivalence over typed contexts.

**Programs** are built by size (number of symbols: a variable, constant, primitive or
lambda binder counts one; applications are free) from smaller programs, in **contexts**.
The top context has the task's inputs as its variables; a lambda argument of a
higher-order primitive is built in the child context that adds its binder(s). Every
context has **evaluation points** (environments): the top context's are the public
example inputs followed by the frozen probe inputs; a child context's pair each parent
point with a few sample values of the binder's type (``samples``). A context keeps one
program per behaviour on its points (``oe.py``).

**Evaluation.** A first-order construction is evaluated vectorially from its arguments'
output vectors (``VECTOR``). A higher-order construction (``map``, ``filter``, ``fold``,
``unfold``, ``fix1``, and ``rec e`` inside a ``fix1`` body) runs the lambda's compiled
closure (``closures.py``) on the actual values at each point. ``fix1`` bodies are
enumerated with *angelic recursion*: on the child context's points the recursive
variable is the public example table of the task (input -> expected output; anything
else fails), so bodies can be compared by behaviour before the knot is tied; the
``fix1`` program itself is evaluated for real at the top level. ``fix1`` is enumerated
in the top context only.

**Budget.** One candidate evaluation = one constructed term evaluated on its context's
points, whether or not observational equivalence then discards it. Terms the
normal-form filter refuses are never built and never counted. Within a size level the
construction shapes (primitive, type instance, argument-size split) are interleaved
round-robin, so a level the budget cuts short is spread across primitives.

**Matches.** A top-context program of the output type whose values on the public inputs
equal the expected outputs is re-checked on the public examples with the reference
interpreter (``rsi5/dsl/evaluator.py``); only then is it returned. Hidden examples are
never read here: verification is the frozen verifier's (``rsi5/verifier.py``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
import sys
import time

from ..dsl.evaluator import evaluate as reference_evaluate
from ..dsl.terms import App, Bool, Int, Lam, Prim, Term, Var, apply
from ..dsl.types import (BOOL, INT, ListOf, PairOf, Type, function_parts, instantiate,
                         is_ground, substitute, unify, TypeInferenceError)
from ..dsl.vocabulary import Vocabulary
from .closures import Fail, LIST_CAP, RECURSION_LIMIT, STEP_BUDGET, compile_term, raise_recursion_limit
from .normal_forms import normal
from .oe import ERR, OETable, freeze, key_of

INT_LIMIT = 1 << 4096
MAX_LAMBDA_DEPTH = 2          # a lambda body may itself contain one more lambda level
TOP_ONLY = ("fix1",)          # enumerated in the top context only
SAMPLE_CAP = {"int": 4, "bool": 2, "list": 2, "pair": 2}
CHILD_POINT_CAP = 64          # evaluation points of a lambda-body context


class StopSearch(Exception):
    pass


class Expr:
    """A pool program: its shape, type, size, behaviour and (lazily) its term and closure."""
    __slots__ = ("kind", "head", "args", "type", "size", "outputs", "key", "uses", "ident",
                 "has_err", "_term", "_body_fn")

    def __init__(self, kind, head, args, type_, size, outputs, key, uses, ident, has_err):
        self.kind, self.head, self.args, self.type, self.size = kind, head, args, type_, size
        self.outputs, self.key, self.uses, self.ident, self.has_err = outputs, key, uses, ident, has_err
        self._term = None
        self._body_fn = None

    @property
    def term(self) -> Term:
        if self._term is None:
            kind = self.kind
            if kind == "var":
                self._term = Var(self.head)
            elif kind == "const":
                self._term = Bool(self.head) if type(self.head) is bool else Int(self.head)
            elif kind == "prim":
                self._term = apply(Prim(self.head), *(a.term for a in self.args))
            elif kind == "lam":
                body = self.args[0].term
                for param in reversed(self.head):
                    body = Lam(param, body)
                self._term = body
            else:  # vapp
                self._term = App(Var(self.head), self.args[0].term)
        return self._term

    def __repr__(self):
        return str(self.term)


# ---- vectorised first-order primitives -------------------------------------------------
def _guarded(fn):
    """Per-element evaluation that turns a failure into ERR."""
    def run(*columns):
        out = []
        for values in zip(*columns):
            if ERR in values:
                out.append(ERR)
                continue
            try:
                out.append(fn(*values))
            except (Fail, ZeroDivisionError, IndexError, TypeError, ValueError, OverflowError):
                out.append(ERR)
        return out
    return run


def _head(xs):
    if not xs:
        raise Fail("head")
    return xs[0]


def _tail(xs):
    if not xs:
        raise Fail("tail")
    return xs[1:]


def _cons(h, t):
    if len(t) >= LIST_CAP:
        raise Fail("list")
    return [h] + t


def _range(n):
    if n > LIST_CAP:
        raise Fail("list")
    return list(range(max(0, n)))


def _index(i, xs):
    if not 0 <= i < len(xs):
        raise Fail("index")
    return xs[i]


def _mul(x, y):
    r = x * y
    if r and r.bit_length() > 4096:
        raise Fail("int")
    return r


def _is_prime(n):
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    if n.bit_length() > 64:
        raise Fail("int")
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def _is_square(n):
    import math
    return n >= 0 and math.isqrt(n) ** 2 == n


def _if(c, t, e):
    return t if c else e


VECTOR = {
    "add": _guarded(lambda x, y: x + y), "sub": _guarded(lambda x, y: x - y),
    "mul": _guarded(_mul), "div": _guarded(lambda x, y: x // y), "mod": _guarded(lambda x, y: x % y),
    "neg": _guarded(lambda x: -x), "abs": _guarded(abs),
    "eq": _guarded(lambda x, y: x == y), "lt": _guarded(lambda x, y: x < y),
    "le": _guarded(lambda x, y: x <= y), "gt": _guarded(lambda x, y: x > y),
    "ge": _guarded(lambda x, y: x >= y),
    "and": _guarded(lambda x, y: x and y), "or": _guarded(lambda x, y: x or y),
    "not": _guarded(lambda x: not x),
    "cons": _guarded(_cons), "head": _guarded(_head), "tail": _guarded(_tail),
    "is_empty": _guarded(lambda xs: not xs), "length": _guarded(len), "range": _guarded(_range),
    "index": _guarded(_index), "is_prime": _guarded(_is_prime), "is_square": _guarded(_is_square),
    "zip": _guarded(lambda xs, ys: list(zip(xs, ys))), "pair": _guarded(lambda a, b: (a, b)),
    "fst": _guarded(lambda p: p[0]), "snd": _guarded(lambda p: p[1]),
}


def _if_vector(c, t, e):
    """Lazy if: only the selected branch's failure matters."""
    out = []
    for cv, tv, ev in zip(c, t, e):
        if cv is ERR:
            out.append(ERR)
        elif cv:
            out.append(tv)
        else:
            out.append(ev)
    return out


HIGHER_ORDER = ("map", "filter", "fold", "unfold", "fix1")


# ---- type instances -----------------------------------------------------------------------
def element_types(request_type: Type) -> list[Type]:
    """The element types the task's request type mentions (always including int)."""
    found = [INT]

    def visit(t):
        if t.tag == "list":
            if t.args[0] not in found and t.args[0].tag in ("int", "bool"):
                found.append(t.args[0])
        for a in t.args:
            if isinstance(a, Type):
                visit(a)
    visit(request_type)
    return found


def ground_types(vocabulary: Vocabulary, elements=(INT,)) -> list[Type]:
    """The value types a search builds programs of. Pairs are instantiated over the
    task's element types only (a pair of anything else has no use in a list task)."""
    types = [INT, BOOL, ListOf(INT), ListOf(BOOL)]
    if "pair" in vocabulary.primitives or "zip" in vocabulary.primitives:
        pairs = [PairOf(s, t) for s in elements for t in elements]
        types += pairs + [ListOf(p) for p in pairs]
    return types


def _type_variables(type_: Type) -> list[str]:
    found = []

    def visit(t):
        if t.is_variable:
            if t.name not in found:
                found.append(t.name)
        for a in t.args:
            if isinstance(a, Type):
                visit(a)
    visit(type_)
    return found


def _arrow_ok(type_: Type, ground: set, nested: bool) -> bool:
    params, ret = function_parts(type_)
    if ret not in ground:
        return False
    for p in params:
        if p in ground:
            continue
        if nested and p.tag == "arrow" and _arrow_ok(p, ground, False):
            continue
        return False
    return True


def instances(vocabulary: Vocabulary, ground: list[Type]) -> dict:
    """prim -> [(argument types, result type)], ground instantiations over ``ground``."""
    gset = set(ground)
    table = {}
    for name in sorted(vocabulary.primitives):
        signature = vocabulary.type_of(name)
        variables = _type_variables(signature)
        found = []
        for assignment in product(ground, repeat=len(variables)):
            concrete = substitute(signature, dict(zip(variables, assignment)))
            params, result = function_parts(concrete)
            if result not in gset:
                continue
            ok = True
            for p in params:
                if p in gset:
                    continue
                if p.tag == "arrow" and _arrow_ok(p, gset, nested=(name == "fix1")):
                    continue
                ok = False
                break
            if ok:
                found.append((params, result))
        found.sort(key=lambda pr: (str(pr[1]), tuple(str(p) for p in pr[0])))
        table[name] = found
    return table


# ---- contexts ------------------------------------------------------------------------------
def _compositions(total: int, mins: tuple[int, ...]):
    """All tuples of sizes >= mins summing to total, in lexicographic order."""
    k = len(mins)
    if k == 0:
        if total == 0:
            yield ()
        return
    if k == 1:
        if total >= mins[0]:
            yield (total,)
        return
    rest_min = sum(mins[1:])
    for first in range(mins[0], total - rest_min + 1):
        for rest in _compositions(total - first, mins[1:]):
            yield (first,) + rest


class Context:
    def __init__(self, engine, env_types: tuple, points: list, depth: int, path: tuple):
        self.engine = engine
        self.env_types = env_types          # index 0 innermost
        self.points = points                # list of environment tuples
        self.depth = depth
        self.path = path                    # binder types from the top context down
        self.oe = OETable()
        self.pools: dict = {}               # type -> [Expr] in insertion order
        self.by_size: dict = {}             # type -> {size: [Expr]}
        self.children: dict = {}            # binder type -> Context
        self.lambdas: dict = {}             # (params, body ident) -> Expr
        self.completed_size = 0
        self.added_at_level = 0

    # -- pools --
    def add(self, expr: Expr) -> bool:
        if not self.oe.admit(expr.type, expr.key, expr):
            return False
        self.pools.setdefault(expr.type, []).append(expr)
        self.by_size.setdefault(expr.type, {}).setdefault(expr.size, []).append(expr)
        self.added_at_level += 1
        return True

    def sized(self, type_: Type, size: int) -> list:
        return self.by_size.get(type_, {}).get(size, ())

    def has_sized(self, type_: Type, low: int, high: int) -> bool:
        table = self.by_size.get(type_)
        if not table:
            return False
        return any(s in table for s in range(low, high + 1))

    # -- children --
    def child(self, binder: Type) -> "Context":
        found = self.children.get(binder)
        if found is None:
            points = []
            for point in self.points:
                for value in self.engine.samples(binder, point, self.env_types):
                    points.append((value,) + point)
            if len(points) > CHILD_POINT_CAP:
                stride = len(points) / CHILD_POINT_CAP
                points = [points[int(i * stride)] for i in range(CHILD_POINT_CAP)]
            found = Context(self.engine, (binder,) + self.env_types, points, self.depth + 1,
                            self.path + (binder,))
            self.children[binder] = found
            self.engine.contexts.append(found)
        return found

    def chain(self, params: tuple) -> "Context":
        context = self
        for p in params:
            context = context.child(p)
        return context

    def ensure(self, size: int) -> None:
        """Enumerate this context's levels up to ``size`` (memoised; children on demand)."""
        while self.completed_size < size:
            level = self.completed_size + 1
            if level == 1:
                self.engine._level_one(self)
            else:
                self.engine._level(level, self)
            self.completed_size = level

    def lambda_of(self, params: tuple, body: Expr) -> Expr:
        key = (params, body.ident)
        found = self.lambdas.get(key)
        if found is None:
            uses = frozenset(u - len(params) for u in body.uses if u >= len(params))
            found = Expr("lam", params, (body,), None, body.size + len(params), None, None,
                         uses, self.engine.next_ident(), body.has_err)
            self.lambdas[key] = found
        return found


@dataclass
class SearchResult:
    term: Term | None
    candidates: int
    candidates_to_solution: int | None
    wall_seconds: float
    exhausted: bool
    pruned: int
    spurious: int
    completed_size: int
    pool_size: int
    contexts: int
    error: str | None = None
    detail: dict = field(default_factory=dict)


class Engine:
    """One search over one task; construct a fresh engine per task."""

    def __init__(self, vocabulary: Vocabulary, *, max_size: int = 20, step_budget: int = STEP_BUDGET,
                 max_lambda_depth: int = MAX_LAMBDA_DEPTH):
        self.vocabulary = vocabulary
        self.max_size = max_size
        self.step_budget = step_budget
        self.max_lambda_depth = max_lambda_depth
        self.ground = ground_types(vocabulary)
        self.instances = instances(vocabulary, self.ground)
        self._instances_for: dict = {}
        self.contexts: list = []
        self._ident = 0
        self.compile_cache: dict = {}
        self.candidates = 0
        self.budget = 0
        self.example_table = {}
        self.task_type = None
        self.output_type = None
        self.top: Context | None = None

    def next_ident(self) -> int:
        self._ident += 1
        return self._ident

    # -- samples for lambda binders ------------------------------------------------------
    def samples(self, binder: Type, point: tuple, env_types: tuple) -> list:
        """Sample values of ``binder`` for one parent point: drawn from the point's own
        values so the child's behaviours are compared where the parent will use them."""
        if binder.tag == "arrow":
            return [self._angelic(binder)]
        found, seen = [], set()

        def take(v):
            k = freeze(v)
            if k not in seen:
                seen.add(k)
                found.append(v)
        if binder == INT:
            for value, type_ in zip(point, env_types):
                if value is ERR:
                    continue
                if type_ == INT:
                    take(value)
                elif type_ == ListOf(INT):
                    for v in value[:4]:
                        take(v)
            take(0)
            take(1)
            return found[:SAMPLE_CAP["int"]]
        if binder == BOOL:
            return [False, True]
        if binder.tag == "list":
            for value, type_ in zip(point, env_types):
                if value is ERR:
                    continue
                if type_ == binder:
                    take(value)
                    if value:
                        take(value[1:])
            if binder == ListOf(INT):
                for value, type_ in zip(point, env_types):
                    if type_ == INT and value is not ERR and 0 <= value <= 8:
                        take(list(range(value)))
            take([])
            return found[:SAMPLE_CAP["list"]]
        if binder.tag == "pair":
            first, second = binder.args
            if first == INT and second == INT:
                for value, type_ in zip(point, env_types):
                    if type_ == ListOf(INT) and value is not ERR and len(value) >= 2:
                        take((value[0], value[1]))
                take((0, 0))
            elif first == INT:
                take((0, False))
                take((1, True))
            elif second == INT:
                take((False, 0))
                take((True, 1))
            else:
                take((False, True))
            return found[:SAMPLE_CAP["pair"]]
        return [ERR]

    def _angelic(self, binder: Type):
        table = self.example_table.get(binder)

        def rec(v, budget, table=table):
            if table is None:
                raise Fail("rec")
            try:
                return table[freeze(v)]
            except (KeyError, TypeError):
                raise Fail("rec")
        return rec

    # -- evaluation of a new construction -------------------------------------------------
    def _lambda_body_fn(self, lam: Expr):
        if lam._body_fn is None:
            lam._body_fn = compile_term(lam.args[0].term, self.compile_cache)
        return lam._body_fn

    def _higher_order(self, name: str, args: tuple, points: list) -> list:
        budget_size = self.step_budget
        out = []
        if name == "map" or name == "filter":
            body = self._lambda_body_fn(args[0])
            is_map = name == "map"
            for xs, env in zip(args[1].outputs, points):
                if xs is ERR:
                    out.append(ERR)
                    continue
                b = [budget_size]
                try:
                    b[0] -= len(xs)
                    if b[0] < 0:
                        raise Fail("budget")
                    if is_map:
                        out.append([body((v,) + env, b) for v in xs])
                    else:
                        out.append([v for v in xs if body((v,) + env, b)])
                except (Fail, ZeroDivisionError, IndexError, TypeError, ValueError, OverflowError,
                        RecursionError):
                    out.append(ERR)
            return out
        if name == "fold":
            body = self._lambda_body_fn(args[0])
            for acc0, xs, env in zip(args[1].outputs, args[2].outputs, points):
                if xs is ERR or acc0 is ERR:
                    out.append(ERR)
                    continue
                b = [budget_size]
                try:
                    b[0] -= len(xs)
                    if b[0] < 0:
                        raise Fail("budget")
                    acc = acc0
                    for v in xs:
                        acc = body((v, acc) + env, b)
                    out.append(acc)
                except (Fail, ZeroDivisionError, IndexError, TypeError, ValueError, OverflowError,
                        RecursionError):
                    out.append(ERR)
            return out
        if name == "unfold":
            stop, emit, step = (self._lambda_body_fn(a) for a in args[:3])
            for state, env in zip(args[3].outputs, points):
                if state is ERR:
                    out.append(ERR)
                    continue
                b = [budget_size]
                try:
                    result = []
                    while True:
                        b[0] -= 1
                        if b[0] < 0:
                            raise Fail("budget")
                        if stop((state,) + env, b):
                            break
                        if len(result) >= LIST_CAP:
                            raise Fail("list")
                        result.append(emit((state,) + env, b))
                        state = step((state,) + env, b)
                    out.append(result)
                except (Fail, ZeroDivisionError, IndexError, TypeError, ValueError, OverflowError,
                        RecursionError):
                    out.append(ERR)
            return out
        if name == "fix1":
            body = self._lambda_body_fn(args[1])
            for seed, env in zip(args[0].outputs, points):
                if seed is ERR:
                    out.append(ERR)
                    continue
                b = [budget_size]

                def rec(v, b2, env=env):
                    b2[0] -= 1
                    if b2[0] < 0:
                        raise Fail("budget")
                    return body((v, rec) + env, b2)
                try:
                    out.append(rec(seed, b))
                except (Fail, ZeroDivisionError, IndexError, TypeError, ValueError, OverflowError,
                        RecursionError):
                    out.append(ERR)
            return out
        raise ValueError(name)

    def _vapp(self, index: int, arg: Expr, points: list) -> list:
        out = []
        for value, env in zip(arg.outputs, points):
            if value is ERR:
                out.append(ERR)
                continue
            try:
                out.append(env[index](value, [self.step_budget]))
            except (Fail, ZeroDivisionError, IndexError, TypeError, ValueError, OverflowError,
                    RecursionError):
                out.append(ERR)
        return out

    # -- the search ---------------------------------------------------------------------------
    def search(self, examples, request_type: Type, probe_inputs, budget: int,
               wall_cap: float | None = None) -> SearchResult:
        started = time.perf_counter()
        self.budget = budget
        self.candidates = 0
        input_types, output_type = function_parts(request_type)
        self.output_type = output_type
        arity = len(input_types)
        if arity == 0:
            raise ValueError("a task needs at least one input")
        elements = tuple(element_types(request_type))
        if elements not in self._instances_for:
            ground = ground_types(self.vocabulary, elements)
            self._instances_for[elements] = (ground, instances(self.vocabulary, ground))
        self.ground, self.instances = self._instances_for[elements]
        public = [tuple(inputs) for inputs, _ in examples]
        expected = [output for _, output in examples]
        seen_inputs = {freeze(list(inp)) for inp in public}
        probes = [tuple(p) for p in probe_inputs if freeze(list(p)) not in seen_inputs]
        inputs = public + probes
        env_types = tuple(reversed(input_types))
        points = [tuple(reversed(inp)) for inp in inputs]
        self.task_type = (input_types[0], output_type) if arity == 1 else None
        if arity == 1:
            self.example_table[Arrow_(input_types[0], output_type)] = {
                freeze(inp[0]): out for inp, out in zip(public, expected)}
        n_public = len(public)
        expected_key = key_of(expected)
        self.contexts = []
        self._record = None
        top = Context(self, env_types, points, 0, ())
        self.top = top
        self.contexts.append(top)
        self.compile_cache = {}
        spurious = 0
        exhausted = False
        solution = None
        candidates_to_solution = None

        def record(context, kind, head, args, type_, size, outputs, uses):
            """Count, prune and store one constructed program; return it if it matched."""
            nonlocal solution, candidates_to_solution, spurious
            if self.candidates >= budget:
                raise StopSearch()
            self.candidates += 1
            if wall_cap is not None and (self.candidates & 1023) == 0 \
                    and time.perf_counter() - started > wall_cap:
                raise StopSearch()
            key = key_of(outputs)
            has_err = ERR in outputs
            expr = Expr(kind, head, args, type_, size, outputs, key, uses, self.next_ident(), has_err)
            if not context.add(expr):
                return
            if context is top and type_ == output_type and key[:n_public] == expected_key:
                term = expr.term
                for t in input_types:
                    term = Lam(t, term)
                if self._reference_ok(term, examples):
                    solution = term
                    candidates_to_solution = self.candidates
                    raise StopSearch()
                spurious += 1

        self._record = record
        previous_limit = raise_recursion_limit()
        try:
            for size in range(1, self.max_size + 1):
                for context in list(self.contexts):
                    context.added_at_level = 0
                top.ensure(size)
                if all(c.added_at_level == 0 for c in self.contexts):
                    exhausted = True
                    break
        except StopSearch:
            pass
        finally:
            if previous_limit < RECURSION_LIMIT:
                sys.setrecursionlimit(previous_limit)
        wall = time.perf_counter() - started
        return SearchResult(solution, self.candidates, candidates_to_solution, wall, exhausted,
                            sum(c.oe.pruned for c in self.contexts), spurious,
                            top.completed_size, sum(c.oe.size() for c in self.contexts),
                            len(self.contexts),
                            detail={"pool_by_context": [(list(map(str, c.path)), c.oe.size(),
                                                         c.completed_size, len(c.points))
                                                        for c in self.contexts]})

    def _reference_ok(self, term, examples) -> bool:
        for inputs, expected in examples:
            result = reference_evaluate(term, tuple(inputs), step_budget=self.step_budget)
            if not result.ok or result.value != expected:
                return False
        return True

    # -- levels ------------------------------------------------------------------------------
    def _level_one(self, context: Context) -> None:
        record = self._record
        for index, type_ in enumerate(context.env_types):
            if type_.tag == "arrow":
                continue
            outputs = [point[index] for point in context.points]
            record(context, "var", index, (), type_, 1, outputs, frozenset([index]))
        for value in self.vocabulary.integer_constants:
            record(context, "const", value, (), INT, 1, [value] * len(context.points), frozenset())
        for value in self.vocabulary.boolean_constants:
            record(context, "const", value, (), BOOL, 1, [value] * len(context.points), frozenset())
        if "nil" in self.vocabulary.primitives:
            for params, result in self.instances["nil"]:
                record(context, "prim", "nil", (), result, 1, [[] for _ in context.points], frozenset())

    def _shapes(self, size: int, context: Context):
        """Generators of constructions of ``size`` in ``context``, one per (prim, instance, split)."""
        n = size - 1
        for name, found in self.instances.items():
            if name == "nil" or (name in TOP_ONLY and context.depth > 0):
                continue
            for params, result in found:
                if name == "fix1" and (params[0], result) != self.task_type:
                    continue          # angelic recursion needs the task's own example table
                mins = []
                slots = []
                for p in params:
                    if p.tag == "arrow":
                        binders, ret = function_parts(p)
                        if context.depth + 1 > self.max_lambda_depth:
                            mins = None
                            break
                        child = context.chain(binders)
                        mins.append(len(binders) + 1)
                        slots.append(("lam", child, binders, ret))
                    else:
                        mins.append(1)
                        slots.append(("ground", context, None, p))
                if mins is None or sum(mins) > n:
                    continue
                total_min = sum(mins)
                # A ground slot with no program of a feasible size makes the shape empty;
                # skip it before any child context is enumerated for it.
                if any(kind == "ground" and not context.has_sized(ret, 1, n - (total_min - m))
                       for (kind, _, _, ret), m in zip(slots, mins)):
                    continue
                for (kind, child, binders, ret), m in zip(slots, mins):
                    if kind == "lam":
                        child.ensure(n - (total_min - m) - len(binders))
                for split in _compositions(n, tuple(mins)):
                    yield self._shape(context, name, params, result, slots, split), result
        # application of a function-typed variable (fix1 bodies)
        for index, type_ in enumerate(context.env_types):
            if type_.tag == "arrow":
                binders, ret = function_parts(type_)
                if len(binders) == 1:
                    yield self._vapp_shape(context, index, binders[0], ret, n), ret

    def _shape(self, context, name, params, result, slots, split):
        lists = []
        for (kind, where, binders, ret), s in zip(slots, split):
            if kind == "ground":
                lists.append(where.sized(ret, s))
            else:
                bodies = where.sized(ret, s - len(binders))
                lists.append([context.lambda_of(binders, b) for b in bodies])
            if not lists[-1]:
                return iter(())
        return self._construct(context, name, result, lists, sum(split) + 1)

    def _construct(self, context, name, result, lists, size):
        vector = VECTOR.get(name)
        points = context.points
        for args in product(*lists):
            if not normal(name, args):
                continue
            uses = frozenset().union(*(a.uses for a in args))
            if name == "if":
                outputs = _if_vector(args[0].outputs, args[1].outputs, args[2].outputs)
            elif vector is not None:
                outputs = vector(*(a.outputs for a in args))
            else:
                outputs = self._higher_order(name, args, points)
            yield ("prim", name, args, result, size, outputs, uses)

    def _vapp_shape(self, context, index, arg_type, ret, n):
        for arg in context.sized(arg_type, n):
            outputs = self._vapp(index, arg, context.points)
            yield ("vapp", index, (arg,), ret, n + 1, outputs, arg.uses | frozenset([index]))

    def _level(self, size: int, context: Context) -> None:
        """One size level of one context: goal-typed shapes first, then the rest, each
        group interleaved round-robin (``NORMAL_FORMS.md`` has the construction order)."""
        record = self._record
        goal, rest = [], []
        for shape, result in self._shapes(size, context):
            (goal if context.depth == 0 and result == self.output_type else rest).append((context, shape))
        for active in (goal, rest):
            while active:
                still = []
                for context_, shape in active:
                    try:
                        kind, head, args, type_, s, outputs, uses = next(shape)
                    except StopIteration:
                        continue
                    record(context_, kind, head, args, type_, s, outputs, uses)
                    still.append((context_, shape))
                active = still


def Arrow_(a, b):
    from ..dsl.types import Arrow
    return Arrow(a, b)
