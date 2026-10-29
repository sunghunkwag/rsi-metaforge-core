"""Backward decomposition: search a small typed hole inside a structural skeleton.

Ported from the backward-decomposition channel of the owner's
``verified-code-rsi`` (``vcrsi/decompose.py``) to RSI-2's DSL. When the
forward enumeration cannot reach a task, a skeleton fixes the combinator
scaffold (a ``map``, a ``filter``, an "any"/"all" test, a prepend) and leaves
a small typed HOLE. A skeleton applies to a task only when the task's PUBLIC
examples have the skeleton's shape: for ``map``, every output list is as long
as its input; for ``filter``, every output is an ordered subsequence of its
input; and so on. The hole's programs are then enumerated with RSI-2's own
enumerator under the current grammar (with the generation's invented concepts
when invention is on). Each hole candidate is put into the skeleton and the
composite is checked on the task's public examples. Every such check is one
logical candidate evaluation, charged to the task's wake budget. A public match
goes to the frozen verifier like any other candidate.

The skeletons are designer-given generic list combinators, the same kind
``verified-code-rsi`` uses. They name no task and contain no task's solution:
every skeleton has a hole that must be found by search, and none is a
complete program. Anything decomposition solves is reported as decomposition's
gain, separately from self-invention (PREDICTIONS_DECOMPOSITION.md).

Hole variants: ``elem`` holes see one element (``int -> T``); ``list`` holes
also see the whole input list (``list[int] -> int -> T``), which covers tasks
such as "replace every element with element k" or "does the head occur in
the tail".
"""
from __future__ import annotations

from dataclasses import dataclass

from rsi2.terms import App, Lam, Term, Var
from rsi2.types import BOOL, INT, Arrow, ListOf

LIST = ListOf(INT)


def _prim(name: str) -> Term:
    return Term("prim", name)


def _is_int_list(value) -> bool:
    return isinstance(value, (list, tuple)) and all(type(v) is int for v in value)


def _subsequence(small, large) -> bool:
    iterator = iter(large)
    return all(any(x == y for y in iterator) for x in small)


# ---- skeleton preconditions (public examples only) ----------------------
def _same_length(examples) -> bool:
    return all(len(inputs) == 1 and _is_int_list(inputs[0]) and isinstance(out, (list, tuple))
               and len(out) == len(inputs[0]) for inputs, out in examples)


def _elementwise_function(examples) -> bool:
    """Equal input elements map to equal output elements in every example."""
    seen = {}
    for (xs,), ys in examples:
        for x, y in zip(xs, ys):
            if seen.setdefault(x, y) != y:
                return False
    return True


def _is_filter(examples) -> bool:
    return all(len(inputs) == 1 and _is_int_list(inputs[0]) and _is_int_list(out)
               and _subsequence(out, inputs[0]) for inputs, out in examples)


def _filter_consistent(examples) -> bool:
    """No value is kept in one place and dropped in another."""
    kept, dropped = set(), set()
    for (xs,), ys in examples:
        remaining = list(ys)
        for x in xs:
            if remaining and remaining[0] == x:
                kept.add(x)
                remaining.pop(0)
            else:
                dropped.add(x)
    return not (kept & dropped)


def _constant_per_example(examples) -> bool:
    return _same_length(examples) and all(len(set(out)) <= 1 for _, out in examples) and any(
        len(out) > 0 for _, out in examples)


def _prepends_one(examples) -> bool:
    return all(len(inputs) == 1 and _is_int_list(inputs[0]) and _is_int_list(out)
               and len(out) == len(inputs[0]) + 1 and list(out[1:]) == list(inputs[0])
               for inputs, out in examples)


def _bool_of_list(examples) -> bool:
    return all(len(inputs) == 1 and _is_int_list(inputs[0]) and type(out) is bool
               for inputs, out in examples)


def _element_type(examples):
    for _, out in examples:
        for value in out:
            return BOOL if type(value) is bool else INT
    return INT


# ---- skeletons -----------------------------------------------------------
@dataclass(frozen=True)
class Skeleton:
    name: str
    hole_type: object

    def build(self, hole: Term) -> Term:
        raise NotImplementedError

    def compose(self, hole: Term) -> Term:
        """The skeleton with the hole filled, in beta-eta normal form.

        A lambda hole applied inside the skeleton leaves a beta-redex; RSI-2's
        grammar scores (and its sleep fits) beta-normal programs only.
        """
        from .selfmodel import canonical_types, normalize
        return canonical_types(normalize(self.build(hole)))


class MapElem(Skeleton):          # map h
    def build(self, h):
        return App(_prim("map"), h)


class MapList(Skeleton):          # lambda l. map (h l) l
    def build(self, h):
        return Lam(LIST, App(App(_prim("map"), App(h, Var(0))), Var(0)))


class MapConst(Skeleton):         # lambda l. map (lambda _. h l) l
    def build(self, h):
        return Lam(LIST, App(App(_prim("map"), Lam(INT, App(h, Var(1)))), Var(0)))


class FilterElem(Skeleton):       # filter h
    def build(self, h):
        return App(_prim("filter"), h)


class FilterList(Skeleton):       # lambda l. filter (h l) l
    def build(self, h):
        return Lam(LIST, App(App(_prim("filter"), App(h, Var(0))), Var(0)))


class PrependOf(Skeleton):        # lambda l. cons (h l) l
    def build(self, h):
        return Lam(LIST, App(App(_prim("cons"), App(h, Var(0))), Var(0)))


class AnyElem(Skeleton):          # lambda l. not (is_empty (filter h l))
    def build(self, h):
        return Lam(LIST, App(_prim("not"), App(_prim("is_empty"),
                                               App(App(_prim("filter"), h), Var(0)))))


class AnyList(Skeleton):          # lambda l. not (is_empty (filter (h l) l))
    def build(self, h):
        return Lam(LIST, App(_prim("not"), App(_prim("is_empty"),
                                               App(App(_prim("filter"), App(h, Var(0))),
                                                   Var(0)))))


class AllElem(Skeleton):          # lambda l. is_empty (filter (lambda x. not (h x)) l)
    def build(self, h):
        return Lam(LIST, App(_prim("is_empty"), App(App(
            _prim("filter"), Lam(INT, App(_prim("not"), App(h, Var(0))))), Var(0))))


class Fold(Skeleton):
    """fold h init: a catamorphism over the input list (lambda-squared style).

    The hole ``h : acc -> element -> acc`` is the step; ``init`` is the
    empty-list answer of the output type (nil, 0, true or false).
    """

    def __init__(self, name, hole_type, init: Term):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "hole_type", hole_type)
        object.__setattr__(self, "init", init)

    def build(self, h):
        return App(App(_prim("fold"), h), self.init)


def _list_to(examples, kind) -> bool:
    return all(len(inputs) == 1 and _is_int_list(inputs[0]) and kind(out)
               for inputs, out in examples)


def fold_skeletons(examples) -> list[Skeleton]:
    """Fold skeletons for every list-input task, keyed by output type."""
    found = []
    if _list_to(examples, _is_int_list):
        found.append(Fold("fold_nil", Arrow(LIST, Arrow(INT, LIST)), _prim("nil")))
    if _list_to(examples, lambda o: type(o) is int):
        found.append(Fold("fold_zero", Arrow(INT, Arrow(INT, INT)), Term("int", 0)))
    if _list_to(examples, lambda o: type(o) is bool):
        found.append(Fold("fold_true", Arrow(BOOL, Arrow(INT, BOOL)), Term("bool", True)))
        found.append(Fold("fold_false", Arrow(BOOL, Arrow(INT, BOOL)), Term("bool", False)))
    return found


def skeletons_for(examples, fold: bool = False) -> list[Skeleton]:
    """The skeletons whose shape the public examples have, in a fixed order.

    ``fold=True`` adds the fold skeletons (``fold_skeletons``), which fit
    every list-input task; arms without the flag see exactly the earlier set.
    """
    found = fold_skeletons(examples) if fold else []
    if _same_length(examples):
        element = _element_type(examples)
        if _elementwise_function(examples):
            found.append(MapElem("map", Arrow(INT, element)))
        if _constant_per_example(examples) and element == INT:
            found.append(MapConst("map_const", Arrow(LIST, INT)))
        found.append(MapList("map_list", Arrow(LIST, Arrow(INT, element))))
    if _is_filter(examples):
        if _filter_consistent(examples):
            found.append(FilterElem("filter", Arrow(INT, BOOL)))
        found.append(FilterList("filter_list", Arrow(LIST, Arrow(INT, BOOL))))
    if _prepends_one(examples):
        found.append(PrependOf("prepend_of", Arrow(LIST, INT)))
    if _bool_of_list(examples):
        found.append(AnyElem("any", Arrow(INT, BOOL)))
        found.append(AllElem("all", Arrow(INT, BOOL)))
        found.append(AnyList("any_list", Arrow(LIST, Arrow(INT, BOOL))))
    return found
