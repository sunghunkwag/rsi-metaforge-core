"""Description-length compression of solved programs into named abstractions.

A corpus of solved programs (typed lambda terms with de Bruijn indices, see
``rsi5/dsl/terms.py``) is compressed into new named symbols, DreamCoder style:

* ``propose``  finds abstractions by typed anti-unification of pairs of subterms and
  takes them greedily by exact description-length gain;
* ``rewrite``  folds a term with a library (minimum-size rewriting);
* ``expand``   unfolds every abstraction again (the exact inverse of ``rewrite``);
* ``key``      is the canonical string of a fully expanded abstraction.

Size of a term: the number of prim, var, int, bool and lam nodes (a lambda binder
counts one, application nodes are free).

Conventions. An abstraction ``Lam(p1, Lam(p2, ... body))`` has its parameters outermost
first; inside ``body`` under ``d`` further binders parameter ``i`` (0-based) is the
index ``n - 1 - i + d``. A *pattern* is such a body. A subterm ``s`` is an instance of
the pattern when the body matches ``s`` node for node, every parameter occurrence
facing a subterm that mentions no binder of the pattern; the argument is that subterm
shifted down by the number of pattern binders above it.

Standard library only; deterministic (no result depends on dict/set iteration order or
on the hash seed).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import count
import re
import warnings

from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import App, Lam, Prim, Term, Var, apply, pretty, shift
from rsi5.dsl.types import (Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, TVar, Type,
                            TypeInferenceError, arrows, infer, substitute, unify)

__all__ = ["Abstraction", "GROUND_TYPES", "size", "key", "expand", "rewrite", "propose",
           "make_abstraction", "match_abstraction", "abstraction_type"]

#: The value types a parameter, a hole or a result may have.
GROUND_TYPES = (INT, BOOL, ListOf(INT), ListOf(BOOL))
_GROUND = frozenset(GROUND_TYPES)

#: Test hook: score every candidate exactly instead of stopping at the bound.
_EXHAUSTIVE = False

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_RESERVED = frozenset({"lambda", "true", "false", "int", "bool", "list"})


# --------------------------------------------------------------------------- basics

@dataclass(frozen=True)
class Abstraction:
    name: str
    params: tuple        # ground Types, outermost first
    result: Type         # a ground Type
    definition: Term     # closed: Lam(p1, Lam(p2, ... body)); may name earlier abstractions
    witness: Term        # the definition with every earlier abstraction inlined
    score: int
    tasks: tuple         # names of the tasks where it is used
    depth: int           # 1 + the largest depth among the abstractions it names (else 1)

    def __post_init__(self):
        object.__setattr__(self, "params", tuple(self.params))
        object.__setattr__(self, "tasks", tuple(self.tasks))

    @property
    def type(self) -> Type:
        return abstraction_type(self)

    @property
    def term(self) -> Term:
        """The definition. With ``type`` this makes a ``{name: Abstraction}`` dict a
        library that ``rsi5.dsl`` ``infer`` and ``evaluate`` accept as it is."""
        return self.definition

    def to_dict(self) -> dict:
        return {"name": self.name, "params": [p.to_dict() for p in self.params],
                "result": self.result.to_dict(), "definition": self.definition.to_dict(),
                "witness": self.witness.to_dict(), "score": self.score,
                "tasks": list(self.tasks), "depth": self.depth}

    @classmethod
    def from_dict(cls, data: dict) -> "Abstraction":
        return cls(data["name"], tuple(Type.from_dict(p) for p in data["params"]),
                   Type.from_dict(data["result"]), Term.from_dict(data["definition"]),
                   Term.from_dict(data["witness"]), data["score"], tuple(data["tasks"]),
                   data["depth"])

    def __str__(self):
        params = ", ".join(str(p) for p in self.params)
        return f"{self.name}({params}) -> {self.result} := {pretty(self.definition)}"


def abstraction_type(abstraction: Abstraction) -> Type:
    """``arrows(*params, result)``, or ``result`` for a nullary abstraction."""
    return arrows(*abstraction.params, abstraction.result)


def size(term: Term) -> int:
    """Prim, var, int, bool and lam nodes; applications are free."""
    total, pending = 0, [term]
    while pending:
        node = pending.pop()
        if node.tag == "app":
            pending.extend(node.children)
        else:
            total += 1
            if node.children:
                pending.append(node.children[0])
    return total


def _names(term: Term) -> set:
    """Primitive and abstraction names occurring in a term."""
    out, pending = set(), [term]
    while pending:
        node = pending.pop()
        if node.tag in ("prim", "ref"):
            out.add(node.value)
        else:
            pending.extend(node.children)
    return out


def _mentions_below(term: Term, bound: int, depth: int = 0) -> bool:
    """True when ``term`` has a free variable with index < ``bound``."""
    tag = term.tag
    if tag == "var":
        return depth <= term.value < depth + bound
    if tag == "app":
        return (_mentions_below(term.children[0], bound, depth)
                or _mentions_below(term.children[1], bound, depth))
    if tag == "lam":
        return _mentions_below(term.children[0], bound, depth + 1)
    return False


def _free_indices(term: Term, depth: int = 0, out=None) -> set:
    out = set() if out is None else out
    tag = term.tag
    if tag == "var":
        if term.value >= depth:
            out.add(term.value - depth)
    elif tag == "lam":
        _free_indices(term.children[0], depth + 1, out)
    elif tag == "app":
        _free_indices(term.children[0], depth, out)
        _free_indices(term.children[1], depth, out)
    return out


def _spine_head(term: Term) -> Term:
    while term.tag == "app":
        term = term.children[0]
    return term


def _head_key(term: Term):
    head = _spine_head(term)
    return (head.tag, head.value if head.tag in ("prim", "ref", "var", "int", "bool") else None)


def _subterm(term: Term, path) -> Term:
    for index in path:
        term = term.children[index]
    return term


def _strip_lambdas(term: Term, limit=None):
    types = []
    while term.tag == "lam" and (limit is None or len(types) < limit):
        types.append(term.value)
        term = term.children[0]
    return tuple(types), term


def _wrap_lambdas(types, body: Term) -> Term:
    for type_ in reversed(tuple(types)):
        body = Lam(type_, body)
    return body


def _beta(body: Term, argument: Term) -> Term:
    """``(lambda. body) argument`` reduced: capture-avoiding, de Bruijn correct."""
    def go(term, depth):
        tag = term.tag
        if tag == "var":
            if term.value == depth:
                return shift(argument, depth) if depth else argument
            return Var(term.value - 1) if term.value > depth else term
        if tag == "app":
            return App(go(term.children[0], depth), go(term.children[1], depth))
        if tag == "lam":
            return Lam(term.value, go(term.children[0], depth + 1))
        return term
    return go(body, 0)


# --------------------------------------------------------------------------- key

def _canonical_parameter_order(term: Term) -> Term:
    """Reorder the leading lambdas by first use in the body (unused ones last)."""
    types, body = _strip_lambdas(term)
    n = len(types)
    if n < 2:
        return term
    order = []          # parameter numbers (outermost = 0) by first occurrence
    pending = [(body, 0)]
    while pending:      # pre-order, function before argument
        node, depth = pending.pop()
        tag = node.tag
        if tag == "var":
            parameter = n - 1 - (node.value - depth)
            if 0 <= parameter < n and parameter not in order:
                order.append(parameter)
        elif tag == "lam":
            pending.append((node.children[0], depth + 1))
        elif tag == "app":
            pending.append((node.children[1], depth))
            pending.append((node.children[0], depth))
    order += [p for p in range(n) if p not in order]
    if order == list(range(n)):
        return term
    position = {parameter: slot for slot, parameter in enumerate(order)}

    def remap(node, depth):
        tag = node.tag
        if tag == "var":
            parameter = n - 1 - (node.value - depth)
            if 0 <= parameter < n:
                return Var(n - 1 - position[parameter] + depth)
            return node
        if tag == "app":
            return App(remap(node.children[0], depth), remap(node.children[1], depth))
        if tag == "lam":
            return Lam(node.value, remap(node.children[0], depth + 1))
        return node

    return _wrap_lambdas([types[p] for p in order], remap(body, 0))


def key(item, library=None) -> str:
    """Canonical string of the fully expanded witness.

    ``item`` is an ``Abstraction`` (its witness is used) or a ``Term`` (expanded with
    ``library`` when one is given). Leading parameters are put in order of first use, so
    two abstractions that differ only in the order of their parameters share a key.
    """
    if isinstance(item, Abstraction):
        term = item.witness
    elif isinstance(item, Term):
        term = expand(item, library) if library else item
    else:
        raise TypeError("key expects an Abstraction or a Term")
    return pretty(_canonical_parameter_order(term))


# --------------------------------------------------------------------------- expand

def expand(term: Term, library) -> Term:
    """Inline every abstraction of ``library`` (name -> Abstraction), recursively.

    An abstraction applied to arguments becomes its definition with the arguments
    substituted (the redexes created by inlining are beta-reduced; redexes the term
    already had are left alone). Applied to fewer arguments than it has parameters, the
    remaining lambdas stay.
    """
    if not library:
        return term
    cache, active = {}, set()

    def definition(name):
        done = cache.get(name)
        if done is None:
            if name in active:
                raise ValueError(f"abstraction {name!r} is defined in terms of itself")
            active.add(name)
            done = cache[name] = go(library[name].definition)
            active.discard(name)
        return done

    def go(node):
        tag = node.tag
        if tag in ("prim", "ref"):
            return definition(node.value) if node.value in library else node
        if tag == "lam":
            body = go(node.children[0])
            return node if body is node.children[0] else Lam(node.value, body)
        if tag != "app":
            return node
        head, arguments = node, []
        while head.tag == "app":
            arguments.append(head.children[1])
            head = head.children[0]
        if head.tag in ("prim", "ref") and head.value in library:
            function = definition(head.value)
            for argument in reversed(arguments):
                argument = go(argument)
                if function.tag == "lam":
                    function = _beta(function.children[0], argument)
                else:
                    function = App(function, argument)
            return function
        left, right = go(node.children[0]), go(node.children[1])
        if left is node.children[0] and right is node.children[1]:
            return node
        return App(left, right)

    return go(term)


# --------------------------------------------------------------------------- typing

def _annotate(term: Term, env, prim_types) -> dict:
    """In-context type of every node: ``{path: Type}``. Raises TypeInferenceError.

    ``env`` gives the types of the free variables (index zero the newest binder); free
    variables beyond it get a type variable that the context may or may not resolve.
    """
    env = tuple(env)
    fresh = count()
    substitutions = {}
    raw = {}
    free = {}

    def instantiate(type_, mapping):
        if type_.tag == "var":
            name = type_.args[0]
            if name not in mapping:
                mapping[name] = TVar(f"_c{next(fresh)}")
            return mapping[name]
        if not type_.args:
            return type_
        return Type(type_.tag, tuple(instantiate(a, mapping) for a in type_.args))

    def visit(node, bindings, path):
        nonlocal substitutions
        tag = node.tag
        if tag == "int":
            type_ = INT
        elif tag == "bool":
            type_ = BOOL
        elif tag == "var":
            if node.value < len(bindings):
                type_ = bindings[node.value]
            else:
                outer = node.value - len(bindings) + len(env)
                if outer not in free:
                    free[outer] = TVar(f"_c{next(fresh)}")
                type_ = free[outer]
        elif tag in ("prim", "ref"):
            declared = prim_types.get(node.value)
            if declared is None:
                raise TypeInferenceError(f"unknown symbol {node.value!r}")
            type_ = instantiate(declared, {})
        elif tag == "lam":
            body = visit(node.children[0], (node.value,) + bindings, path + (0,))
            type_ = Arrow(node.value, body)
        elif tag == "app":
            function = visit(node.children[0], bindings, path + (0,))
            argument = visit(node.children[1], bindings, path + (1,))
            type_ = TVar(f"_c{next(fresh)}")
            substitutions = unify(function, Arrow(argument, type_), substitutions)
        else:
            raise TypeInferenceError(f"cannot type a {tag!r} node")
        raw[path] = type_
        return type_

    try:
        visit(term, env, ())
    except (AttributeError, IndexError, KeyError, RecursionError) as exc:
        raise TypeInferenceError(f"malformed term: {exc}") from exc
    return {path: substitute(type_, substitutions) for path, type_ in raw.items()}


def _library_types(library) -> dict:
    types = dict(PRIMITIVE_TYPES)
    for name, abstraction in library.items():
        types[name] = abstraction_type(abstraction)
    return types


# --------------------------------------------------------------------------- matching

def _match(body: Term, params, term: Term, types: dict, base=()):
    """Match a pattern body against ``term`` (whose node types are ``types[base + rel]``).

    Returns one ``(rel, depth, argument)`` per parameter, ``rel`` the path of its first
    occurrence, ``depth`` the number of pattern binders above it and ``argument`` the
    subterm there shifted down by ``depth``; or None when ``term`` is not an instance.
    """
    n = len(params)
    binds = [None] * n

    def go(pattern, node, depth, rel):
        tag = pattern.tag
        if tag == "var":
            index = pattern.value
            if index < depth:                       # bound inside the pattern
                return node.tag == "var" and node.value == index
            parameter = n - 1 - (index - depth)
            if parameter < 0:
                return False
            if types.get(base + rel) != params[parameter]:
                return False
            if depth:
                if _mentions_below(node, depth):
                    return False
                node = shift(node, -depth)
            bound = binds[parameter]
            if bound is None:
                binds[parameter] = (rel, depth, node)
                return True
            return bound[2] == node
        if tag != node.tag:
            return False
        if tag == "app":
            return (go(pattern.children[0], node.children[0], depth, rel + (0,))
                    and go(pattern.children[1], node.children[1], depth, rel + (1,)))
        if tag == "lam":
            return (pattern.value == node.value
                    and go(pattern.children[0], node.children[0], depth + 1, rel + (0,)))
        return pattern.value == node.value

    if go(body, term, 0, ()) and all(bound is not None for bound in binds):
        return binds
    return None


def _prefer(current, option):
    """The smaller of two rewritings: by size, then fewer uses, then printed form."""
    left, right = (current[1], current[2]), (option[1], option[2])
    if left != right:
        return current if left < right else option
    return current if pretty(current[0]) <= pretty(option[0]) else option


def _optimal(term: Term, matcher):
    """Minimum-size rewriting of ``term``: ``(term, size, uses)``.

    ``matcher(path, node)`` yields ``(name, binds)`` for every pattern the application
    node at ``path`` is an instance of. Each node either stays (its children rewritten
    optimally) or becomes one pattern use whose arguments are rewritten optimally.
    """
    memo = {}

    def best(node, path):
        hit = memo.get(path)
        if hit is not None:
            return hit
        tag = node.tag
        if tag == "app":
            left, right = node.children
            f, x = best(left, path + (0,)), best(right, path + (1,))
            kept = node if (f[0] is left and x[0] is right) else App(f[0], x[0])
            result = (kept, f[1] + x[1], f[2] + x[2])
            for name, binds in matcher(path, node):
                arguments, total, uses = [], 1, 1
                for rel, depth, _ in binds:
                    inner = best(_subterm(node, rel), path + rel)
                    arguments.append(shift(inner[0], -depth) if depth else inner[0])
                    total += inner[1]
                    uses += inner[2]
                result = _prefer(result, (apply(Prim(name), *arguments), total, uses))
        elif tag == "lam":
            body = best(node.children[0], path + (0,))
            kept = node if body[0] is node.children[0] else Lam(node.value, body[0])
            result = (kept, 1 + body[1], body[2])
        else:
            result = (node, 1, 0)
        memo[path] = result
        return result

    return best(term, ())


def _usable_patterns(library):
    """``{head key: [(name, params, result, witness body)]}`` for rewriting."""
    table = {}
    for name in sorted(library):
        abstraction = library[name]
        params = tuple(abstraction.params)
        types, body = _strip_lambdas(abstraction.witness, len(params))
        if len(types) != len(params) or body.tag != "app":
            continue
        used = _free_indices(body)
        if used != set(range(len(params))):
            continue                     # an unused parameter cannot be recovered
        table.setdefault(_head_key(body), []).append((name, params, abstraction.result, body))
    return table


def rewrite(term: Term, library, *, env=()) -> Term:
    """Fold ``term`` with the abstractions of ``library``; inverse of ``expand``.

    The term is expanded first and the expansion is rewritten to minimum size: every
    subterm either stays or becomes ``apply(Prim(name), *args)`` for an abstraction it
    is an instance of (argument types must equal the parameter types), whichever makes
    the whole term smallest; ties go to fewer abstraction uses, then to the printed
    form. The result is therefore a fixed point. Guarantee:
    ``expand(rewrite(t, library), library) == expand(t, library)``.

    ``env`` gives the types of free variables of an open term (index zero the newest
    binder). A term that cannot be typed is returned unchanged.
    """
    if not library:
        return term
    expanded = expand(term, library)
    try:
        types = _annotate(expanded, env, PRIMITIVE_TYPES)
    except TypeInferenceError:
        return term
    table = _usable_patterns(library)

    def matcher(path, node):
        patterns = table.get(_head_key(node))
        if not patterns:
            return
        type_ = types.get(path)
        for name, params, result, body in patterns:
            if result != type_:
                continue
            binds = _match(body, params, node, types, path)
            if binds is not None:
                yield name, binds

    result, result_size, _ = _optimal(expanded, matcher)
    if expand(result, library) != expanded:      # safety net; not expected to trigger
        warnings.warn("compress.rewrite: round trip failed, returning the expansion")
        result, result_size = expanded, size(expanded)
    if size(term) < result_size:                 # e.g. a partially applied abstraction
        return term
    return result


def match_abstraction(abstraction: Abstraction, term: Term, *, env=()):
    """Arguments that make ``term`` an instance of the abstraction's witness, or None."""
    params = tuple(abstraction.params)
    types_, body = _strip_lambdas(abstraction.witness, len(params))
    if len(types_) != len(params):
        return None
    try:
        types = _annotate(term, env, PRIMITIVE_TYPES)
    except TypeInferenceError:
        return None
    if types.get(()) != abstraction.result:
        return None
    binds = _match(body, params, term, types)
    return None if binds is None else tuple(argument for _, _, argument in binds)


def make_abstraction(name: str, definition: Term, library=None, *, score: int = 0,
                     tasks=()) -> Abstraction:
    """Build an ``Abstraction`` from a closed definition, deriving the other fields."""
    library = dict(library or {})
    witness = expand(definition, library)
    params, body = _strip_lambdas(definition)
    type_ = infer(witness)
    result = type_
    for parameter in params:
        if result.tag != "arrow" or result.args[0] != parameter:
            raise TypeInferenceError(f"definition of {name!r} is not typed by its lambdas")
        result = result.args[1]
    if any(p not in _GROUND for p in params) or result not in _GROUND:
        raise TypeInferenceError(f"{name!r}: parameters and result must be ground, got {type_}")
    used = sorted(n for n in _names(definition) if n in library)
    depth = 1 + max((library[n].depth for n in used), default=0)
    return Abstraction(name, tuple(params), result, definition, witness, int(score),
                       tuple(tasks), depth)


# --------------------------------------------------------------------------- candidates

class _Site:
    """A class of identical ground-typed application subterms with identical context."""
    __slots__ = ("ident", "term", "type", "size", "types", "base", "occurrences", "weight")

    def __init__(self, ident, term, type_, types, base):
        self.ident = ident
        self.term = term
        self.type = type_
        self.size = size(term)
        self.types = types          # node types of the program of the first occurrence
        self.base = base            # path of the first occurrence in that program
        self.occurrences = {}       # program number -> number of occurrences
        self.weight = 0             # occurrences counted once per task


class _Candidate:
    __slots__ = ("definition", "params", "result", "body", "body_size", "matches",
                 "estimate", "programs", "score", "tasks", "rewritten", "witness",
                 "key", "text")

    def __init__(self, definition, params, result, body):
        self.definition = definition
        self.params = params
        self.result = result
        self.body = body
        self.body_size = size(body)
        self.matches = {}           # site ident -> binds
        self.estimate = 0
        self.programs = ()
        self.score = None
        self.tasks = ()
        self.rewritten = {}
        self.witness = None
        self.key = None
        self.text = None


def _anti_unify(a_site: _Site, b_site: _Site):
    """Typed anti-unification of two sites: ``(definition, params, body)`` or None.

    Agreeing nodes are kept. A difference, and every variable bound outside the
    pattern, becomes a hole when both instances have the same ground type and mention
    no binder of the pattern; otherwise the smallest enclosing subterm that can be a
    hole becomes one. Holes with the same pair of instances share a parameter.
    """
    a_types, a_base = a_site.types, a_site.base
    b_types, b_base = b_site.types, b_site.base

    def hole(a, b, depth, rel):
        type_ = a_types.get(a_base + rel)
        if type_ not in _GROUND or b_types.get(b_base + rel) != type_:
            return None
        if depth:
            if _mentions_below(a, depth) or _mentions_below(b, depth):
                return None
            a, b = shift(a, -depth), shift(b, -depth)
        return ("hole", a, b, type_)

    def go(a, b, depth, rel):
        tag = a.tag
        if tag == b.tag:
            if tag == "app":
                function = go(a.children[0], b.children[0], depth, rel + (0,))
                if function is not None:
                    argument = go(a.children[1], b.children[1], depth, rel + (1,))
                    if argument is not None:
                        return ("app", function, argument)
            elif tag == "lam":
                if a.value == b.value:
                    body = go(a.children[0], b.children[0], depth + 1, rel + (0,))
                    if body is not None:
                        return ("lam", a.value, body)
            elif tag == "var":
                if a.value == b.value and a.value < depth:
                    return ("leaf", a)
            elif a.value == b.value:
                return ("leaf", a)
        return hole(a, b, depth, rel)

    tree = go(a_site.term, b_site.term, 0, ())
    if tree is None or tree[0] != "app":
        return None
    holes, params = {}, []
    pending = [tree]
    while pending:                                  # pre-order, function before argument
        node = pending.pop()
        kind = node[0]
        if kind == "hole":
            if node[1:] not in holes:
                holes[node[1:]] = len(params)
                params.append(node[3])
        elif kind == "app":
            pending.append(node[2])
            pending.append(node[1])
        elif kind == "lam":
            pending.append(node[2])
    n = len(params)

    def build(node, depth):
        kind = node[0]
        if kind == "leaf":
            return node[1]
        if kind == "hole":
            return Var(n - 1 - holes[node[1:]] + depth)
        if kind == "app":
            return App(build(node[1], depth), build(node[2], depth))
        return Lam(node[1], build(node[2], depth + 1))

    body = build(tree, 0)
    return _wrap_lambdas(params, body), tuple(params), body


def _is_renaming(body: Term, n: int) -> bool:
    """One primitive or abstraction applied to the parameters in order, nothing else."""
    arguments = []
    while body.tag == "app":
        arguments.append(body.children[1])
        body = body.children[0]
    if body.tag not in ("prim", "ref") or len(arguments) != n:
        return False
    arguments.reverse()
    return all(a.tag == "var" and a.value == n - 1 - i for i, a in enumerate(arguments))


def _collect_sites(programs, annotations, task_counts):
    """Site classes of the distinct programs, and the class of every site path."""
    sites, by_key, site_at = [], {}, []
    for number, program in enumerate(programs):
        located = {}
        site_at.append(located)
        types = annotations[number]
        if types is None:
            continue
        pending = [(program, (), ())]
        while pending:                               # pre-order
            node, path, env = pending.pop()
            tag = node.tag
            if tag == "lam":
                pending.append((node.children[0], path + (0,), (node.value,) + env))
                continue
            if tag != "app":
                continue
            pending.append((node.children[1], path + (1,), env))
            pending.append((node.children[0], path + (0,), env))
            type_ = types[path]
            if type_ not in _GROUND:
                continue
            free = sorted(_free_indices(node))
            identity = (node, type_, tuple((i, env[i]) for i in free))
            site = by_key.get(identity)
            if site is None:
                site = by_key[identity] = _Site(len(sites), node, type_, types, path)
                sites.append(site)
            site.occurrences[number] = site.occurrences.get(number, 0) + 1
            site.weight += task_counts[number]
            located[path] = site.ident
    return sites, site_at


def _single_tasks(site, program_tasks):
    """The only task a site occurs in, or None when it occurs in several."""
    if len(site.occurrences) != 1:
        return None
    (number,) = site.occurrences
    tasks = program_tasks[number]
    return tasks[0] if len(tasks) == 1 else None


def _best_candidate(current, order, library, name, tabu, max_params, min_tasks, typing):
    """The best admissible abstraction for the rewritten corpus ``current``, or None."""
    program_tasks, programs = {}, []
    for task in order:
        term = current[task]
        if term not in program_tasks:
            program_tasks[term] = []
            programs.append(term)
        program_tasks[term].append(task)
    program_tasks = [program_tasks[p] for p in programs]
    task_counts = [len(tasks) for tasks in program_tasks]
    prim_types = _library_types(library)
    annotations = []
    for program in programs:
        if program not in typing:
            try:
                typing[program] = (None if _free_indices(program)
                                   else _annotate(program, (), prim_types))
            except TypeInferenceError:
                typing[program] = None      # untypable programs give no candidates
        annotations.append(typing[program])
    sites, site_at = _collect_sites(programs, annotations, task_counts)
    lonely = [_single_tasks(site, program_tasks) for site in sites]

    grouped = _generate(sites, lonely, max_params)

    ranked = []
    for group, members in grouped:
        for candidate in members:
            estimate, touched = -candidate.body_size, set()
            for site in group:
                binds = _match(candidate.body, candidate.params, site.term, site.types, site.base)
                if binds is None:
                    continue
                candidate.matches[site.ident] = binds
                saving = site.size - 1 - sum(size(argument) for _, _, argument in binds)
                estimate += saving * site.weight
                touched.update(site.occurrences)
            candidate.estimate = estimate
            candidate.programs = sorted(touched)
            if estimate > 0 and sum(task_counts[n] for n in touched) >= min_tasks:
                ranked.append(candidate)
    ranked.sort(key=lambda c: -c.estimate)           # stable: deterministic

    library_keys = {key(abstraction) for abstraction in library.values()}
    program_sizes = {}
    best, best_rank = None, None
    for candidate in ranked:
        # The estimate counts every matching site, so it bounds the exact score: once
        # it falls below the best exact score no later candidate can win.
        if best is not None and candidate.estimate < best.score and not _EXHAUSTIVE:
            break
        witness = expand(candidate.definition, library)
        try:
            if infer(witness) != arrows(*candidate.params, candidate.result):
                continue
        except TypeInferenceError:
            continue
        candidate.witness = witness
        candidate.key = key(witness)
        if candidate.key in tabu or candidate.key in library_keys:
            continue
        if not candidate.params:
            outcome = evaluate(witness, ())
            if not outcome.ok or type(outcome.value) is not int:
                continue
        score, tasks = -candidate.body_size, []
        for number in candidate.programs:
            located = site_at[number]
            matches = candidate.matches

            def matcher(path, node, located=located, matches=matches):
                binds = matches.get(located.get(path))
                if binds is not None:
                    yield name, binds

            program = programs[number]
            if number not in program_sizes:
                program_sizes[number] = size(program)
            term, new_size, uses = _optimal(program, matcher)
            if uses:
                candidate.rewritten[number] = term
                score += (program_sizes[number] - new_size) * task_counts[number]
                tasks.extend(program_tasks[number])
        candidate.score = score
        candidate.tasks = tuple(sorted(tasks, key=str))
        if score <= 0 or len(tasks) < min_tasks:
            continue
        candidate.text = pretty(candidate.definition)
        rank = (-score, -len(tasks), candidate.body_size, candidate.key, candidate.text)
        if best is None or rank < best_rank:
            best, best_rank = candidate, rank
    if best is None:
        return None
    return best, programs, program_tasks


def _generate(sites, lonely, max_params):
    """Distinct candidate patterns: every site alone, and every pair of sites with the
    same head and type that can come from two different tasks."""
    groups = {}
    for site in sites:
        groups.setdefault((_head_key(site.term), site.type), []).append(site)
    candidates, grouped = {}, []
    for group in groups.values():                    # insertion order: deterministic
        members = []
        for i, a_site in enumerate(group):
            a_task = lonely[a_site.ident]
            for b_site in group[i:]:
                if (b_site is not a_site and a_task is not None
                        and lonely[b_site.ident] == a_task):
                    continue                          # both only in the same single task
                made = _anti_unify(a_site, b_site)
                if made is None:
                    continue
                definition, params, body = made
                if len(params) > max_params:
                    continue
                if not params and a_site.type != INT:
                    continue                          # nullary: int constants only
                if _is_renaming(body, len(params)):
                    continue
                identity = (definition, a_site.type)
                if identity not in candidates:
                    candidate = _Candidate(definition, params, a_site.type, body)
                    candidates[identity] = candidate
                    members.append(candidate)
        grouped.append((group, members))
    return grouped


# --------------------------------------------------------------------------- propose

def _fresh_name(prefix: str, start: int, taken) -> tuple:
    number = start
    while True:
        number += 1
        name = f"{prefix}{number}"
        if name not in taken:
            return name, number


def propose(corpus, library, *, tabu=frozenset(), max_new=3, max_params=3, min_tasks=2,
            name_prefix="a"):
    """Greedy description-length compression of ``corpus`` (task name -> Term).

    Every program is first rewritten with ``library`` (name -> Abstraction). Then, up to
    ``max_new`` times: generate candidate patterns from the rewritten corpus (typed
    anti-unification of pairs of ground-typed subterms with the same head and type from
    two different tasks, and every such subterm alone), score them, admit the best one,
    rewrite the corpus with it. A candidate's score is the total size it removes from
    the corpus over the best set of non-overlapping uses, minus the size of its body.

    Admitted: positive score, at most ``max_params`` parameters, used in at least
    ``min_tasks`` tasks, ``key`` not in ``tabu`` and not the key of a library member,
    not a renaming of one existing symbol, nullary only for int constants that
    evaluate. Returns the new abstractions in the order they were admitted.
    """
    if not re.fullmatch(_NAME, name_prefix) or re.fullmatch(r"x\d*", name_prefix):
        raise ValueError(f"unusable name prefix {name_prefix!r}")
    library = dict(library or {})
    tabu = frozenset(k if isinstance(k, str) else key(k) for k in tabu)
    order = sorted(corpus, key=str)
    taken = set(library) | set(PRIMITIVE_TYPES) | _RESERVED
    for task in order:
        taken |= _names(corpus[task])

    done = {}
    current = {}
    for task in order:
        term = corpus[task]
        if term not in done:
            done[term] = rewrite(term, library)
        current[task] = done[term]

    proposals, number, typing = [], 0, {}
    for _ in range(max(0, max_new)):
        name, number = _fresh_name(name_prefix, number, taken)
        found = _best_candidate(current, order, library, name, tabu, max_params,
                                min_tasks, typing)
        if found is None:
            break
        candidate, programs, program_tasks = found
        used = sorted(n for n in _names(candidate.definition) if n in library)
        depth = 1 + max((library[n].depth for n in used), default=0)
        abstraction = Abstraction(name, candidate.params, candidate.result,
                                  candidate.definition, candidate.witness,
                                  int(candidate.score), candidate.tasks, depth)
        library[name] = abstraction
        taken.add(name)
        proposals.append(abstraction)
        for index, program in enumerate(programs):
            folded = rewrite(candidate.rewritten.get(index, program), library)
            for task in program_tasks[index]:
                current[task] = folded
    return proposals
