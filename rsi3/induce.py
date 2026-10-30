"""Procedure induction: search skeletons the system derives from its own verified solutions.

The decomposition skeletons (``map h``, ``filter h``, ``fold h init``, ...)
and the conjugation move are designer-given search procedures. Here the
system writes new ones. Every pair of its verified solutions with the same
request type is anti-unified: the solutions are compared node by node, and
the smallest subterm that contains every difference becomes a typed hole.
The rest is a template the two solutions share.

For example, ``lambda l. reverse (cons 1 (reverse l))`` and
``lambda l. reverse (cons 4 (reverse l))`` give
``lambda l. reverse (cons [] (reverse l))`` with an ``int`` hole.

A template is a new search procedure. On a task of its request type, its
hole is enumerated by RSI-2's enumerator, exactly as a designer skeleton's
hole is (``decompose.Skeleton``). Variables bound above the hole that the
differing subterms use are passed to the hole as arguments (lambda
lifting), so the hole is a closed term.

**Adoption is gated by the frozen verifier.** Each generation the
best-supported templates are proposed. A template is adopted, and kept
across generations, only when a program found through it is verified on a
task that was unsolved. Solutions found through adopted templates are
anti-unified in later generations like any others. So a procedure can be
induced from solutions that an induced procedure found: its *depth* is one
more than the deepest procedure behind its source solutions. That depth is
how recursion in the system's own procedure growth is measured.

Names, request types and programs are public; nothing here reads a hidden
example.
"""
from __future__ import annotations

import hashlib

from rsi2.terms import App, Lam, Term, Var
from rsi2.types import INT, Type, arrows, infer

from .decompose import Skeleton

MAX_LIFTED = 2          # variables a hole may take as arguments
MIN_TEMPLATE = 3        # non-lambda nodes the template keeps outside the hole


def _ground(type_: Type) -> Type:
    if type_.is_variable:
        return INT
    if not type_.args:
        return type_
    return Type(type_.tag, tuple(_ground(a) for a in type_.args))


def _free_vars(term: Term, depth: int = 0) -> set:
    """de Bruijn indices free in ``term``, relative to its root."""
    if term.tag == "var":
        return {term.value - depth} if term.value >= depth else set()
    if term.tag == "lam":
        return _free_vars(term.children[0], depth + 1)
    found = set()
    for child in term.children:
        found |= _free_vars(child, depth)
    return found


def _remap(term: Term, mapping: dict, depth: int = 0) -> Term:
    """Rename free variables (relative index -> new relative index)."""
    if term.tag == "var":
        if term.value < depth:
            return term
        return Var(mapping[term.value - depth] + depth)
    if term.tag == "lam":
        return Lam(term.value, _remap(term.children[0], mapping, depth + 1))
    if term.tag == "app":
        return App(*(_remap(c, mapping, depth) for c in term.children))
    return term


def _differences(a: Term, b: Term, path=()) -> list:
    if a.tag != b.tag or a.value != b.value or len(a.children) != len(b.children):
        return [path]
    found = []
    for index, (x, y) in enumerate(zip(a.children, b.children)):
        found += _differences(x, y, path + (index,))
    return found


def _common_prefix(paths) -> tuple:
    prefix = list(paths[0])
    for path in paths[1:]:
        n = 0
        while n < min(len(prefix), len(path)) and prefix[n] == path[n]:
            n += 1
        prefix = prefix[:n]
    return tuple(prefix)


def _at(term: Term, path) -> Term:
    for index in path:
        term = term.children[index]
    return term


def _put(term: Term, path, new: Term) -> Term:
    if not path:
        return new
    children = list(term.children)
    children[path[0]] = _put(children[path[0]], path[1:], new)
    return Term(term.tag, term.value, tuple(children))


def _binders(term: Term, path) -> list:
    """Lambda parameter types above ``path``, outermost first."""
    found = []
    for index in path:
        if term.tag == "lam":
            found.append(term.value)
        term = term.children[index]
    return found


def _marker_path(term: Term, path=()):
    if term.tag == "hole":
        return path
    for index, child in enumerate(term.children):
        found = _marker_path(child, path + (index,))
        if found is not None:
            return found
    return None


def _template_size(term: Term) -> int:
    if term.tag == "hole":
        return 0
    own = 0 if term.tag == "lam" else 1
    return own + sum(_template_size(c) for c in term.children)


def matches(template: Term, program: Term) -> bool:
    """Whether ``program`` is the template with some subterm in the hole."""
    if template.tag == "hole":
        return True
    if (template.tag != program.tag or template.value != program.value
            or len(template.children) != len(program.children)):
        return False
    return all(matches(t, p) for t, p in zip(template.children, program.children))


class InducedSkeleton(Skeleton):
    """A template from anti-unification; the hole is applied to its lifted variables."""

    def __init__(self, name, template: Term, hole_type: Type, lifted: tuple, request: str):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "hole_type", hole_type)
        object.__setattr__(self, "template", template)
        object.__setattr__(self, "lifted", tuple(lifted))
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "support", 0)
        object.__setattr__(self, "sources", ())

    def build(self, hole: Term) -> Term:
        applied = hole
        for index in self.lifted:
            applied = App(applied, Var(index))
        return _put(self.template, _marker_path(self.template), applied)


def anti_unify(first: Term, second: Term, request: str, library=None):
    """The one-hole template two programs share, as an InducedSkeleton, or None."""
    diffs = _differences(first, second)
    if not diffs:
        return None
    path = _common_prefix(diffs)
    a, b = _at(first, path), _at(second, path)
    binders = _binders(first, path)
    lifted = sorted(_free_vars(a) | _free_vars(b), reverse=True)    # outermost first
    if len(lifted) > MAX_LIFTED or any(i >= len(binders) for i in lifted):
        return None
    env = tuple(reversed(binders))                                   # index 0: innermost
    try:
        sub_type = _ground(infer(a, env=env, library=library))
        if str(_ground(infer(b, env=env, library=library))) != str(sub_type):
            return None
    except Exception:
        return None
    hole_type = arrows(*[_ground(env[i]) for i in lifted], sub_type) if lifted else sub_type
    template = _put(first, path, Term("hole", hole_type))
    if _template_size(template) < MIN_TEMPLATE:
        return None
    name = "ind" + hashlib.blake2b(repr(template).encode(), digest_size=4).hexdigest()
    skeleton = InducedSkeleton(name, template, hole_type, tuple(lifted), request)
    # The template must give back both programs when their own subterm fills it.
    for program, sub in ((first, a), (second, b)):
        mapping = {i: len(lifted) - 1 - k for k, i in enumerate(lifted)}
        hole = _remap(sub, mapping)
        for index in reversed(lifted):
            hole = Lam(_ground(env[index]), hole)
        try:
            if skeleton.compose(hole) != skeleton.compose_target(program):
                return None
        except Exception:
            return None
    return skeleton


def _compose_target(self, program: Term) -> Term:
    from .selfmodel import canonical_types, normalize
    return canonical_types(normalize(program))


InducedSkeleton.compose_target = _compose_target


def induce_skeletons(solutions: dict, request_types: dict, library=None,
                     max_count: int = 8) -> list:
    """The best-supported templates from every same-typed pair of verified solutions.

    ``solutions``: task name -> verified program; ``request_types``: task name
    -> its request type (string). Ranked by support (how many solutions are
    instances of the template), then template size, then name.
    """
    by_type: dict = {}
    for name in sorted(solutions):
        by_type.setdefault(request_types[name], []).append(name)
    found: dict = {}
    for request, names in sorted(by_type.items()):
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                skeleton = anti_unify(solutions[left], solutions[right], request, library)
                if skeleton is None or skeleton.name in found:
                    continue
                sources = tuple(n for n in names if matches(skeleton.template, solutions[n]))
                object.__setattr__(skeleton, "support", len(sources))
                object.__setattr__(skeleton, "sources", sources)
                found[skeleton.name] = skeleton
    ranked = sorted(found.values(),
                    key=lambda s: (-s.support, -_template_size(s.template), s.name))
    return ranked[:max_count]
