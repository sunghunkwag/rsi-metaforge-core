"""Compiled closures: a term becomes nested Python functions once, then runs on any input.

``compile_term(term)`` returns ``f(env, budget)``: ``env`` is the de Bruijn environment
(index 0 innermost), ``budget`` a one-element list of remaining steps. Function values
are Python callables ``g(value, budget)``. Steps are charged where work repeats: one per
element visited by ``map``, ``filter``, ``fold``, ``zip`` and ``range``, one per
``unfold`` iteration and one per ``fix1`` recursive call; list values are capped at
``LIST_CAP`` elements and integers at ``INT_BITS`` bits. Any failure raises ``Fail`` (or a
host arithmetic/index error), which the caller turns into ``ERR`` for that point.

This is the engine's fast semantics. The reference semantics is the interpreter in
``rsi5/dsl/evaluator.py``; every public match found with these closures is re-checked
with the interpreter before it is reported (``bottomup.py``).
"""
from __future__ import annotations

import math
import sys

from ..dsl.terms import Term
from ..dsl.types import PRIMITIVE_TYPES, function_parts

LIST_CAP = 1024
INT_BITS = 4096
STEP_BUDGET = 2000
ARITY = {name: len(function_parts(t)[0]) for name, t in PRIMITIVE_TYPES.items()}


class Fail(Exception):
    """A runtime failure or an exhausted step budget inside a compiled closure."""


def _spine(term):
    args = []
    while term.tag == "app":
        args.append(term.children[1])
        term = term.children[0]
    args.reverse()
    return term, args


def _charge(budget, amount):
    budget[0] -= amount
    if budget[0] < 0:
        raise Fail("budget")


def _mul(x, y):
    r = x * y
    if r and r.bit_length() > INT_BITS:
        raise Fail("int")
    return r


def _is_prime(n, budget):
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    d = 3
    while d * d <= n:
        _charge(budget, 1)
        if n % d == 0:
            return False
        d += 2
    return True


def _check_list(xs):
    if len(xs) > LIST_CAP:
        raise Fail("list")
    return xs


def _prim_closure(name, args, env_depth):
    """A closure for a fully applied primitive; ``args`` are compiled argument closures."""
    a = args
    if name == "add":
        return lambda env, b: a[0](env, b) + a[1](env, b)
    if name == "sub":
        return lambda env, b: a[0](env, b) - a[1](env, b)
    if name == "mul":
        return lambda env, b: _mul(a[0](env, b), a[1](env, b))
    if name == "div":
        return lambda env, b: a[0](env, b) // a[1](env, b)
    if name == "mod":
        return lambda env, b: a[0](env, b) % a[1](env, b)
    if name == "neg":
        return lambda env, b: -a[0](env, b)
    if name == "abs":
        return lambda env, b: abs(a[0](env, b))
    if name == "eq":
        return lambda env, b: a[0](env, b) == a[1](env, b)
    if name == "lt":
        return lambda env, b: a[0](env, b) < a[1](env, b)
    if name == "le":
        return lambda env, b: a[0](env, b) <= a[1](env, b)
    if name == "gt":
        return lambda env, b: a[0](env, b) > a[1](env, b)
    if name == "ge":
        return lambda env, b: a[0](env, b) >= a[1](env, b)
    if name == "and":
        return lambda env, b: a[0](env, b) and a[1](env, b)
    if name == "or":
        return lambda env, b: a[0](env, b) or a[1](env, b)
    if name == "not":
        return lambda env, b: not a[0](env, b)
    if name == "if":
        return lambda env, b: a[1](env, b) if a[0](env, b) else a[2](env, b)
    if name == "cons":
        def cons(env, b):
            tail = a[1](env, b)
            if len(tail) >= LIST_CAP:
                raise Fail("list")
            return [a[0](env, b)] + tail
        return cons
    if name == "head":
        def head(env, b):
            xs = a[0](env, b)
            if not xs:
                raise Fail("head")
            return xs[0]
        return head
    if name == "tail":
        def tail(env, b):
            xs = a[0](env, b)
            if not xs:
                raise Fail("tail")
            return xs[1:]
        return tail
    if name == "is_empty":
        return lambda env, b: not a[0](env, b)
    if name == "length":
        return lambda env, b: len(a[0](env, b))
    if name == "range":
        def range_(env, b):
            n = a[0](env, b)
            if n > LIST_CAP:
                raise Fail("list")
            _charge(b, max(n, 0))
            return list(range(max(n, 0)))
        return range_
    if name == "map":
        def map_(env, b):
            f, xs = a[0](env, b), a[1](env, b)
            _charge(b, len(xs))
            return [f(v, b) for v in xs]
        return map_
    if name == "filter":
        def filter_(env, b):
            f, xs = a[0](env, b), a[1](env, b)
            _charge(b, len(xs))
            return [v for v in xs if f(v, b)]
        return filter_
    if name == "fold":
        def fold(env, b):
            f, acc, xs = a[0](env, b), a[1](env, b), a[2](env, b)
            _charge(b, len(xs))
            for v in xs:
                acc = f(acc, b)(v, b)
            return acc
        return fold
    if name == "unfold":
        def unfold(env, b):
            stop, emit, step, state = a[0](env, b), a[1](env, b), a[2](env, b), a[3](env, b)
            out = []
            while True:
                _charge(b, 1)
                if stop(state, b):
                    return out
                if len(out) >= LIST_CAP:
                    raise Fail("list")
                out.append(emit(state, b))
                state = step(state, b)
        return unfold
    if name == "index":
        def index(env, b):
            i, xs = a[0](env, b), a[1](env, b)
            if not 0 <= i < len(xs):
                raise Fail("index")
            return xs[i]
        return index
    if name == "fix1":
        def fix1(env, b):
            seed, body = a[0](env, b), a[1](env, b)

            def rec(v, b2):
                _charge(b2, 1)
                return body(rec, b2)(v, b2)
            return rec(seed, b)
        return fix1
    if name == "is_prime":
        return lambda env, b: _is_prime(a[0](env, b), b)
    if name == "is_square":
        def is_square(env, b):
            n = a[0](env, b)
            return n >= 0 and math.isqrt(n) ** 2 == n
        return is_square
    if name == "zip":
        def zip_(env, b):
            xs, ys = a[0](env, b), a[1](env, b)
            _charge(b, min(len(xs), len(ys)))
            return list(zip(xs, ys))
        return zip_
    if name == "pair":
        return lambda env, b: (a[0](env, b), a[1](env, b))
    if name == "fst":
        return lambda env, b: a[0](env, b)[0]
    if name == "snd":
        return lambda env, b: a[0](env, b)[1]
    raise ValueError(f"no closure for primitive {name!r}")


def _curry(name, given, arity):
    """A partial application as a function value (not produced by the engine; for
    terms written by hand or by RSI-2's enumerator)."""
    def value(env, b):
        got = [g(env, b) for g in given]

        def take(v, b2, got=got):
            new = got + [v]
            if len(new) == arity:
                consts = [(lambda env2, b3, c=c: c) for c in new]
                return _prim_closure(name, consts, 0)((), b2)
            return lambda v2, b3: take(v2, b3, new)
        return take
    return value


def compile_term(term: Term, cache: dict | None = None):
    """Compile a closed or open term to ``f(env, budget)``. Library references are
    not supported here (C1 has no library; admitted primitives are inlined)."""
    if cache is not None:
        hit = cache.get(term)
        if hit is not None:
            return hit
    tag = term.tag
    if tag in ("int", "bool"):
        v = term.value
        fn = lambda env, b: v
    elif tag == "var":
        i = term.value
        fn = lambda env, b: env[i]
    elif tag == "lam":
        body = compile_term(term.children[0], cache)
        fn = lambda env, b: (lambda v, b2: body((v,) + env, b2))
    elif tag == "prim":
        name = term.value
        if name not in PRIMITIVE_TYPES:
            raise ValueError(f"unknown primitive {name!r}")
        if name == "nil":
            fn = lambda env, b: []
        elif ARITY[name] == 0:
            raise ValueError(f"nullary primitive {name!r} without a value")
        else:
            fn = _curry(name, [], ARITY[name])
    elif tag == "app":
        head, args = _spine(term)
        compiled = [compile_term(arg, cache) for arg in args]
        if head.tag == "prim" and head.value in PRIMITIVE_TYPES and head.value != "nil":
            name, arity = head.value, ARITY[head.value]
            if len(compiled) == arity:
                fn = _prim_closure(name, compiled, 0)
            elif len(compiled) < arity:
                fn = _curry(name, compiled, arity)
            else:
                base = _prim_closure(name, compiled[:arity], 0)
                rest = compiled[arity:]

                def over(env, b, base=base, rest=rest):
                    value = base(env, b)
                    for g in rest:
                        value = value(g(env, b), b)
                    return value
                fn = over
        else:
            head_fn = compile_term(head, cache)

            def applied(env, b, head_fn=head_fn, compiled=compiled):
                value = head_fn(env, b)
                for g in compiled:
                    value = value(g(env, b), b)
                return value
            fn = applied
    else:
        raise ValueError(f"cannot compile term tag {tag!r}")
    if cache is not None:
        cache[term] = fn
    return fn


RECURSION_LIMIT = 20000


def raise_recursion_limit() -> int:
    """Lift the host recursion limit so the step budget, not the host, ends deep
    recursion (the reference interpreter does the same); returns the previous limit."""
    previous = sys.getrecursionlimit()
    if previous < RECURSION_LIMIT:
        sys.setrecursionlimit(RECURSION_LIMIT)
    return previous


def run_closure(fn, env, step_budget: int = STEP_BUDGET):
    """Apply a compiled closure at one point; failures become ``None`` with a reason."""
    budget = [step_budget]
    previous = raise_recursion_limit()
    try:
        return fn(env, budget), None
    except (Fail, ZeroDivisionError, IndexError, TypeError, RecursionError, OverflowError) as exc:
        return None, type(exc).__name__
    finally:
        if previous < RECURSION_LIMIT:
            sys.setrecursionlimit(previous)
