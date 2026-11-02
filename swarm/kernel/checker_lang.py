"""The frozen checker language: a small dynamically checked functional language with bounded recursion.

Kernel piece (OWNER_DIRECTIVE.md §2). Programs are JSON values:

- ``int``, ``bool`` literals; ``["str", "text"]`` a string literal;
  ``["list", e, ...]`` and ``["tuple", e, ...]`` constructors;
- a bare string is a variable, or a primitive name when unbound;
- ``["lambda", ["x", "y"], body]``; ``["rec", "f", ["n"], body]`` a
  recursive function value (depth-bounded); ``["let", "x", e, body]``;
  ``["if", c, a, b]``; ``["and", a, b]`` and ``["or", a, b]`` short-circuit;
- ``[f, arg, ...]`` application of a lambda, a recursive function or a
  primitive.

Values are ints, bools, strings, lists and tuples; functions are values
too. Types are checked at run time and strictly (a bool is never an int,
lists are not coerced). Every evaluation step costs one unit of the step
budget, list and string operations cost their length, and a program that
exceeds the budget, the recursion depth, the integer size or the list and
string lengths fails with an error. Errors never escape ``run``.

The language is deliberately richer than the Builder's generation-0 DSL
(strings, tuples, sort, zip, slicing, bounded recursion), so the Breaker
can pose tasks the Builder cannot yet express; the Builder reaches them by
forging primitives whose bodies are written in this language.

Provenance: the checker-as-program discipline is Phase K's
(``docs/ASCENT_K_SPEC.md`` §3); the language itself is new, written for
RSI-2's value domain plus strings and tuples.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

MAX_STEPS = 20000
MAX_DEPTH = 64            # nested calls of recursive functions
MAX_AST_DEPTH = 64
MAX_INT_BITS = 512
MAX_LENGTH = 4096         # lists and strings
SPECIAL = ("lambda", "rec", "let", "if", "and", "or", "list", "tuple", "str")


class CheckerError(Exception):
    """Any failure of a checker-language program: type, budget, depth, size, lookup."""


@dataclass(frozen=True)
class Result:
    ok: bool
    value: object = None
    error: str | None = None
    steps: int = 0


class _Closure:
    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params, body, env, name=None):
        self.params, self.body, self.env, self.name = tuple(params), body, env, name


class _Prim:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


def _is_int(v) -> bool:
    return type(v) is int


def _is_bool(v) -> bool:
    return type(v) is bool


def _is_str(v) -> bool:
    return type(v) is str


def _is_list(v) -> bool:
    return type(v) is list


def _is_tuple(v) -> bool:
    return type(v) is tuple


def _kind(v) -> str:
    if _is_bool(v):
        return "bool"
    if _is_int(v):
        return "int"
    if _is_str(v):
        return "str"
    if _is_list(v):
        return "list"
    if _is_tuple(v):
        return "tuple"
    if isinstance(v, (_Closure, _Prim)):
        return "function"
    return "invalid"


def _need(v, kind, where):
    if _kind(v) != kind:
        raise CheckerError(f"{where}: expected {kind}, got {_kind(v)}")
    return v


def _int_ok(v: int) -> int:
    if v.bit_length() > MAX_INT_BITS:
        raise CheckerError("integer too large")
    return v


def _len_ok(v):
    if len(v) > MAX_LENGTH:
        raise CheckerError("sequence too long")
    return v


def _equal(a, b) -> bool:
    if _kind(a) != _kind(b):
        return False
    if _is_list(a) or _is_tuple(a):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    if _kind(a) == "function":
        raise CheckerError("cannot compare functions")
    return a == b


def _order_key(v):
    """Total order for sort/comparison over ints and strings (and lists/tuples of them)."""
    kind = _kind(v)
    if kind == "int":
        return (0, v)
    if kind == "str":
        return (1, v)
    if kind == "bool":
        return (2, int(v))
    if kind in ("list", "tuple"):
        return (3, tuple(_order_key(x) for x in v))
    raise CheckerError("not orderable")


class _Interpreter:
    def __init__(self, step_budget: int):
        self.budget = int(step_budget)
        self.steps = 0
        self.depth = 0

    def tick(self, amount: int = 1) -> None:
        self.steps += amount
        if self.steps > self.budget:
            raise CheckerError("step budget exhausted")

    # -- evaluation ----------------------------------------------------------
    def eval(self, expr, env: dict):
        self.tick()
        if _is_bool(expr) or _is_int(expr):
            return expr
        if _is_str(expr):
            if expr in env:
                return env[expr]
            if expr in PRIMITIVES:
                return _Prim(expr)
            raise CheckerError(f"unbound symbol {expr!r}")
        if not _is_list(expr) or not expr:
            raise CheckerError("malformed expression")
        head = expr[0]
        if _is_str(head) and head in SPECIAL and head not in env:
            return self.special(head, expr, env)
        function = self.eval(head, env)
        arguments = [self.eval(a, env) for a in expr[1:]]
        return self.apply(function, arguments)

    def special(self, head, expr, env):
        if head == "str":
            if len(expr) != 2 or not _is_str(expr[1]):
                raise CheckerError("malformed string literal")
            return _len_ok(expr[1])
        if head == "list":
            return _len_ok([self.eval(e, env) for e in expr[1:]])
        if head == "tuple":
            return _len_ok(tuple(self.eval(e, env) for e in expr[1:]))
        if head == "if":
            if len(expr) != 4:
                raise CheckerError("malformed if")
            test = _need(self.eval(expr[1], env), "bool", "if")
            return self.eval(expr[2] if test else expr[3], env)
        if head == "and":
            if len(expr) != 3:
                raise CheckerError("malformed and")
            left = _need(self.eval(expr[1], env), "bool", "and")
            return left and _need(self.eval(expr[2], env), "bool", "and")
        if head == "or":
            if len(expr) != 3:
                raise CheckerError("malformed or")
            left = _need(self.eval(expr[1], env), "bool", "or")
            return left or _need(self.eval(expr[2], env), "bool", "or")
        if head == "let":
            if len(expr) != 4 or not _is_str(expr[1]):
                raise CheckerError("malformed let")
            value = self.eval(expr[2], env)
            return self.eval(expr[3], {**env, expr[1]: value})
        if head == "lambda":
            if len(expr) != 3 or not _is_list(expr[1]) or not all(_is_str(p) for p in expr[1]):
                raise CheckerError("malformed lambda")
            return _Closure(expr[1], expr[2], env)
        if head == "rec":
            if (len(expr) != 4 or not _is_str(expr[1]) or not _is_list(expr[2])
                    or not all(_is_str(p) for p in expr[2])):
                raise CheckerError("malformed rec")
            closure = _Closure(expr[2], expr[3], env, name=expr[1])
            closure.env = {**env, expr[1]: closure}
            return closure
        raise CheckerError(f"unknown special form {head!r}")

    def apply(self, function, arguments: list):
        self.tick()
        if isinstance(function, _Prim):
            return PRIMITIVES[function.name](self, arguments)
        if isinstance(function, _Closure):
            if len(arguments) != len(function.params):
                raise CheckerError(f"arity: expected {len(function.params)} arguments")
            self.depth += 1
            if self.depth > MAX_DEPTH:
                raise CheckerError("recursion depth exceeded")
            try:
                return self.eval(function.body, {**function.env, **dict(zip(function.params, arguments))})
            finally:
                self.depth -= 1
        raise CheckerError("application of a non-function")


# ---- primitives -------------------------------------------------------------
def _arity(n):
    def wrap(fn):
        def run(interp, args):
            if len(args) != n:
                raise CheckerError(f"arity: expected {n} arguments")
            return fn(interp, *args)
        return run
    return wrap


def _arith(op):
    @_arity(2)
    def run(interp, a, b):
        _need(a, "int", op)
        _need(b, "int", op)
        if op == "+":
            return _int_ok(a + b)
        if op == "-":
            return _int_ok(a - b)
        if op == "*":
            if a and b and a.bit_length() + b.bit_length() > MAX_INT_BITS:
                raise CheckerError("integer too large")
            return _int_ok(a * b)
        if b == 0:
            raise CheckerError("division by zero")
        return a // b if op == "div" else a % b
    return run


def _compare(op):
    @_arity(2)
    def run(interp, a, b):
        if op in ("=", "!="):
            equal = _equal(a, b)
            return equal if op == "=" else not equal
        ka, kb = _kind(a), _kind(b)
        if ka != kb or ka not in ("int", "str"):
            raise CheckerError(f"{op}: incomparable")
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    return run


def _seq(v, where):
    if not (_is_list(v) or _is_str(v)):
        raise CheckerError(f"{where}: expected a list or string")
    return v


@_arity(1)
def _p_neg(interp, a):
    return _int_ok(-_need(a, "int", "neg"))


@_arity(1)
def _p_abs(interp, a):
    return abs(_need(a, "int", "abs"))


@_arity(2)
def _p_min(interp, a, b):
    return min(_need(a, "int", "min"), _need(b, "int", "min"))


@_arity(2)
def _p_max(interp, a, b):
    return max(_need(a, "int", "max"), _need(b, "int", "max"))


@_arity(1)
def _p_not(interp, a):
    return not _need(a, "bool", "not")


@_arity(1)
def _p_empty(interp, a):
    return len(_seq(a, "empty?")) == 0


@_arity(2)
def _p_cons(interp, a, b):
    _need(b, "list", "cons")
    interp.tick(len(b))
    return _len_ok([a] + b)


@_arity(1)
def _p_head(interp, a):
    _seq(a, "head")
    if not a:
        raise CheckerError("head of empty")
    return a[0]


@_arity(1)
def _p_tail(interp, a):
    _seq(a, "tail")
    if not a:
        raise CheckerError("tail of empty")
    interp.tick(len(a))
    return a[1:]


@_arity(1)
def _p_len(interp, a):
    return len(_seq(a, "len"))


@_arity(2)
def _p_nth(interp, a, i):
    _seq(a, "nth")
    _need(i, "int", "nth")
    if not 0 <= i < len(a):
        raise CheckerError("nth out of range")
    return a[i]


@_arity(2)
def _p_append(interp, a, b):
    if _is_str(a) and _is_str(b):
        interp.tick(len(a) + len(b))
        return _len_ok(a + b)
    _need(a, "list", "append")
    _need(b, "list", "append")
    interp.tick(len(a) + len(b))
    return _len_ok(a + b)


@_arity(1)
def _p_reverse(interp, a):
    _seq(a, "reverse")
    interp.tick(len(a))
    return a[::-1]


@_arity(2)
def _p_map(interp, f, xs):
    _need(xs, "list", "map")
    return [interp.apply(f, [x]) for x in xs]


@_arity(2)
def _p_filter(interp, f, xs):
    _need(xs, "list", "filter")
    return [x for x in xs if _need(interp.apply(f, [x]), "bool", "filter")]


@_arity(3)
def _p_fold(interp, f, init, xs):
    _need(xs, "list", "fold")
    acc = init
    for x in xs:
        acc = interp.apply(f, [acc, x])
    return acc


@_arity(1)
def _p_range(interp, n):
    _need(n, "int", "range")
    if n > MAX_LENGTH:
        raise CheckerError("range too long")
    interp.tick(max(n, 0))
    return list(range(max(n, 0)))


@_arity(2)
def _p_take(interp, n, a):
    _need(n, "int", "take")
    _seq(a, "take")
    interp.tick(max(min(n, len(a)), 0))
    return a[:max(n, 0)]


@_arity(2)
def _p_drop(interp, n, a):
    _need(n, "int", "drop")
    _seq(a, "drop")
    interp.tick(len(a))
    return a[max(n, 0):]


@_arity(3)
def _p_slice(interp, a, i, j):
    _seq(a, "slice")
    _need(i, "int", "slice")
    _need(j, "int", "slice")
    interp.tick(len(a))
    return a[max(i, 0):max(j, 0)]


@_arity(1)
def _p_sort(interp, a):
    _need(a, "list", "sort")
    interp.tick(len(a) * max(1, len(a).bit_length()))
    return sorted(a, key=_order_key)


@_arity(1)
def _p_sum(interp, a):
    _need(a, "list", "sum")
    total = 0
    for x in a:
        total = _int_ok(total + _need(x, "int", "sum"))
    interp.tick(len(a))
    return total


@_arity(2)
def _p_contains(interp, a, x):
    _seq(a, "contains")
    interp.tick(len(a))
    if _is_str(a):
        return _need(x, "str", "contains") in a
    return any(_equal(y, x) for y in a)


@_arity(2)
def _p_index_of(interp, a, x):
    _need(a, "list", "index-of")
    interp.tick(len(a))
    for i, y in enumerate(a):
        if _equal(y, x):
            return i
    return -1


@_arity(2)
def _p_zip(interp, a, b):
    _need(a, "list", "zip")
    _need(b, "list", "zip")
    interp.tick(min(len(a), len(b)))
    return [(x, y) for x, y in zip(a, b)]


@_arity(1)
def _p_concat(interp, a):
    _need(a, "list", "concat")
    out = []
    for x in a:
        _need(x, "list", "concat")
        out.extend(x)
        interp.tick(len(x))
    return _len_ok(out)


@_arity(1)
def _p_unique(interp, a):
    _need(a, "list", "unique")
    out = []
    for x in a:
        interp.tick()
        if not any(_equal(x, y) for y in out):
            out.append(x)
    return out


@_arity(1)
def _p_last(interp, a):
    _seq(a, "last")
    if not a:
        raise CheckerError("last of empty")
    return a[-1]


@_arity(2)
def _p_count(interp, a, x):
    _need(a, "list", "count")
    interp.tick(len(a))
    return sum(1 for y in a if _equal(y, x))


@_arity(1)
def _p_chars(interp, s):
    _need(s, "str", "chars")
    interp.tick(len(s))
    return list(s)


@_arity(1)
def _p_str_join(interp, a):
    _need(a, "list", "str-join")
    out = "".join(_need(x, "str", "str-join") for x in a)
    interp.tick(len(out))
    return _len_ok(out)


@_arity(2)
def _p_str_split(interp, s, sep):
    _need(s, "str", "str-split")
    _need(sep, "str", "str-split")
    if not sep:
        raise CheckerError("empty separator")
    interp.tick(len(s))
    return s.split(sep)


@_arity(1)
def _p_str_upper(interp, s):
    interp.tick(len(_need(s, "str", "str-upper")))
    return s.upper()


@_arity(1)
def _p_str_lower(interp, s):
    interp.tick(len(_need(s, "str", "str-lower")))
    return s.lower()


@_arity(1)
def _p_to_str(interp, v):
    if _is_bool(v):
        return "true" if v else "false"
    if _is_int(v):
        return str(v)
    raise CheckerError("to-str: expected int or bool")


@_arity(1)
def _p_to_int(interp, s):
    _need(s, "str", "to-int")
    text = s.strip()
    if not text or not (text.lstrip("-").isdigit()) or len(text) > 160:
        raise CheckerError("to-int: not an integer")
    return _int_ok(int(text))


@_arity(2)
def _p_nth_tuple(interp, t, i):
    _need(t, "tuple", "nth-tuple")
    _need(i, "int", "nth-tuple")
    if not 0 <= i < len(t):
        raise CheckerError("nth-tuple out of range")
    return t[i]


@_arity(1)
def _p_fst(interp, t):
    _need(t, "tuple", "fst")
    if not t:
        raise CheckerError("fst of empty tuple")
    return t[0]


@_arity(1)
def _p_snd(interp, t):
    _need(t, "tuple", "snd")
    if len(t) < 2:
        raise CheckerError("snd of short tuple")
    return t[1]


@_arity(1)
def _p_tuple_len(interp, t):
    return len(_need(t, "tuple", "tuple-len"))


def _predicate(kind):
    @_arity(1)
    def run(interp, v):
        return _kind(v) == kind
    return run


PRIMITIVES = {
    "+": _arith("+"), "-": _arith("-"), "*": _arith("*"), "div": _arith("div"), "mod": _arith("mod"),
    "neg": _p_neg, "abs": _p_abs, "min": _p_min, "max": _p_max,
    "=": _compare("="), "!=": _compare("!="), "<": _compare("<"), "<=": _compare("<="),
    ">": _compare(">"), ">=": _compare(">="), "not": _p_not,
    "empty?": _p_empty, "cons": _p_cons, "head": _p_head, "tail": _p_tail, "len": _p_len,
    "nth": _p_nth, "append": _p_append, "reverse": _p_reverse, "map": _p_map, "filter": _p_filter,
    "fold": _p_fold, "range": _p_range, "take": _p_take, "drop": _p_drop, "slice": _p_slice,
    "sort": _p_sort, "sum": _p_sum, "contains": _p_contains, "index-of": _p_index_of,
    "zip": _p_zip, "concat": _p_concat, "unique": _p_unique, "last": _p_last, "count": _p_count,
    "chars": _p_chars, "str-join": _p_str_join, "str-split": _p_str_split,
    "str-upper": _p_str_upper, "str-lower": _p_str_lower, "to-str": _p_to_str, "to-int": _p_to_int,
    "nth-tuple": _p_nth_tuple, "fst": _p_fst, "snd": _p_snd, "tuple-len": _p_tuple_len,
    "int?": _predicate("int"), "bool?": _predicate("bool"), "str?": _predicate("str"),
    "list?": _predicate("list"), "tuple?": _predicate("tuple"),
}
PRIMITIVE_NAMES = tuple(sorted(PRIMITIVES))


# ---- programs as data ---------------------------------------------------------
def validate(program, depth: int = 0) -> None:
    """Structural check of a program: literal kinds, special forms, bounded AST depth."""
    if depth > MAX_AST_DEPTH:
        raise CheckerError("program too deep")
    if _is_bool(program) or _is_int(program):
        _int_ok(program) if _is_int(program) else None
        return
    if _is_str(program):
        return
    if not _is_list(program) or not program:
        raise CheckerError("malformed expression")
    head = program[0]
    if head == "str":
        if len(program) != 2 or not _is_str(program[1]):
            raise CheckerError("malformed string literal")
        return
    if head == "lambda":
        if len(program) != 3 or not _is_list(program[1]) or not all(_is_str(p) for p in program[1]):
            raise CheckerError("malformed lambda")
        validate(program[2], depth + 1)
        return
    if head == "rec":
        if (len(program) != 4 or not _is_str(program[1]) or not _is_list(program[2])
                or not all(_is_str(p) for p in program[2])):
            raise CheckerError("malformed rec")
        validate(program[3], depth + 1)
        return
    if head == "let":
        if len(program) != 4 or not _is_str(program[1]):
            raise CheckerError("malformed let")
        validate(program[2], depth + 1)
        validate(program[3], depth + 1)
        return
    for child in program:
        validate(child, depth + 1)


def size(program) -> int:
    """Node count of a program."""
    if _is_list(program):
        if program and program[0] == "str":
            return 1
        return 1 + sum(size(c) for c in program)
    return 1


def canonical(program) -> str:
    return json.dumps(program, sort_keys=True, separators=(",", ":"))


def digest(program) -> str:
    return hashlib.sha256(canonical(program).encode("utf-8")).hexdigest()[:24]


def to_jsonable(value):
    """Tuples become ``{"tuple": [...]}`` so that JSON round-trips preserve kinds."""
    if _is_tuple(value):
        return {"tuple": [to_jsonable(v) for v in value]}
    if _is_list(value):
        return [to_jsonable(v) for v in value]
    if _kind(value) == "function":
        raise CheckerError("functions are not values of a task")
    return value


def from_jsonable(value):
    if isinstance(value, dict):
        if set(value) == {"tuple"}:
            return tuple(from_jsonable(v) for v in value["tuple"])
        raise CheckerError("malformed value")
    if _is_list(value):
        return [from_jsonable(v) for v in value]
    return value


def run(program, arguments, step_budget: int = MAX_STEPS) -> Result:
    """Apply ``program`` (a function expression) to ``arguments``; failures never escape."""
    interp = _Interpreter(step_budget)
    try:
        validate(program)
        function = interp.eval(program, {})
        if _kind(function) != "function":
            raise CheckerError("program is not a function")
        value = interp.apply(function, list(arguments))
        to_jsonable(value)
        return Result(True, value, None, interp.steps)
    except CheckerError as exc:
        return Result(False, None, str(exc), interp.steps)
    except RecursionError:
        return Result(False, None, "recursion depth exceeded", interp.steps)
    except (TypeError, ValueError, KeyError, IndexError, OverflowError, MemoryError) as exc:
        return Result(False, None, f"runtime: {type(exc).__name__}", interp.steps)


def check(checker, x, y, step_budget: int = MAX_STEPS) -> Result:
    """Run a checker ``(lambda (x y) bool)`` on one instance; ``value`` is the verdict."""
    result = run(checker, [x, y], step_budget)
    if result.ok and not _is_bool(result.value):
        return Result(False, None, "checker must return a bool", result.steps)
    return result
