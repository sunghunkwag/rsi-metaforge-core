"""Behavioural search: bottom-up synthesis by observational equivalence, with deduction.

RSI-2's enumerator searches programs in order of probability, top down. Two
programs that compute the same values on a task's public inputs are searched,
and charged, separately. The two have the same behaviour, so the second
teaches the search nothing. Behavioural search instead builds programs bottom
up and keeps one program per behaviour: the vector of its values on the
public inputs (observational equivalence: Udupa et al. 2013, TRANSIT;
Albarghouthi et al. 2013, Escher). Every new program is made by applying a
primitive, or a library entry, to programs already kept, so its behaviour is
computed from theirs.

The target is reached by deduction where the output's shape allows it, in the
style of lambda-squared (Feser et al. 2015) and FlashMeta (Polozov and
Gulwani 2015):

- **cons.** A list output is ``cons h r``. The heads of all outputs form one
  target vector and their tails another. So a list target splits into
  element targets plus a shorter list target, up to ``max_unroll`` levels.
  Fixed-length outputs such as "the slice from k of length n" become n
  element targets.
- **not.** A boolean target is also met by a program with the negated
  behaviour, wrapped in ``not``.
- **Pointwise holes.** A skeleton whose hole is constrained pointwise
  (``map``, ``filter``, ``map_list``, ``filter_list``, ``map_const``;
  decompose.py) gives the hole a target vector over the elements. ``any``,
  ``all`` and ``any_list`` give a predicate over the hole's boolean vector.

What it builds from:

- the hole's variables;
- RSI-2's constants;
- RSI-2's first-order primitives (no ``if``, ``range`` or ``fold``);
- ``map`` and ``filter`` with a function argument that is a unary library
  entry or a partially applied primitive;
- every first-order library entry the system has. These are RSI-2's MDL
  abstractions and the self-model's concepts, so what the system learned
  makes behavioural search shorter.

**Accounting.** Every behaviour added to the pool is charged one logical
candidate evaluation. So is every assembled program checked on the public
examples, and every program whose behaviour equals a target (kept as an
alternative, because a target-equal behaviour the verifier rejects must not
hide its siblings). Programs with a behaviour already in the pool cost no
logical budget; the CPU they took is reported. Behaviours examined under an
earlier library (``known``) are free, as failure memory makes known failures
free. The search reads public examples only. A public match is checked with
RSI-2's own evaluator before it is returned.
"""
from __future__ import annotations

import hashlib
import time

from rsi2.evaluator import evaluate
from rsi2.terms import App, Lam, Term, Var
from rsi2.types import BOOL, INT, ListOf, Type, function_parts, infer

from .resumable import WindowResult

LIST = ListOf(INT)
BLIST = ListOf(BOOL)
_TYPES = {"i": INT, "b": BOOL, "l": LIST, "lb": BLIST}
_ERR = object()
_MAX_BITS = 4096
_ELEMENT = {"l": "i", "lb": "b"}
_LIST_OF = {"i": "l", "b": "lb"}


def tag_of(type_: Type):
    for tag, known in _TYPES.items():
        if type_ == known:
            return tag
    return None


def _ground(type_: Type) -> Type:
    if type_.is_variable:
        return INT
    if not type_.args:
        return type_
    return Type(type_.tag, tuple(_ground(a) for a in type_.args))


def value_tag(value):
    if type(value) is bool:
        return "b"
    if type(value) is int:
        return "i"
    if isinstance(value, (list, tuple)):
        if any(type(v) is bool for v in value):
            return "lb"
        if all(type(v) is int for v in value):
            return "l"
    return None


def frozen(value):
    if isinstance(value, list):
        return tuple(frozen(v) for v in value)
    return value


def thawed(value):
    if isinstance(value, tuple):
        return [thawed(v) for v in value]
    return value


def _int(v) -> bool:
    return type(v) is int


def _arith(name):
    def run(a, b):
        if not (_int(a) and _int(b)):
            return _ERR
        if name == "mul" and a and b and a.bit_length() + b.bit_length() - 1 > _MAX_BITS:
            return _ERR
        try:
            r = (a + b if name == "add" else a - b if name == "sub" else a * b if name == "mul"
                 else a // b if name == "div" else a % b)
        except ZeroDivisionError:
            return _ERR
        return _ERR if r.bit_length() > _MAX_BITS else r
    return run


def _compare(name):
    def run(a, b):
        if not (_int(a) and _int(b)):
            return _ERR
        return (a == b if name == "eq" else a < b if name == "lt" else a <= b if name == "le"
                else a > b if name == "gt" else a >= b)
    return run


def _unary(name):
    def run(a):
        if name in ("neg", "abs"):
            if not _int(a):
                return _ERR
            r = -a if name == "neg" else abs(a)
            return _ERR if r.bit_length() > _MAX_BITS else r
        if name == "not":
            return (not a) if type(a) is bool else _ERR
        if name == "head":
            return a[0] if a else _ERR
        if name == "tail":
            return a[1:] if a else _ERR
        if name == "length":
            return len(a)
        if name == "is_empty":
            return len(a) == 0
        raise KeyError(name)
    return run


def _boolean(name):
    def run(a, b):
        if type(a) is not bool or type(b) is not bool:
            return _ERR
        return (a and b) if name == "and" else (a or b)
    return run


def _cons(a, rest):
    return (a,) + rest


# (name, argument tags, result tag, implementation); lists of either element
# type share the list primitives.
FIRST_ORDER = (
    [("head", (t,), _ELEMENT[t], _unary("head")) for t in ("l", "lb")]
    + [("tail", (t,), t, _unary("tail")) for t in ("l", "lb")]
    + [("length", (t,), "i", _unary("length")) for t in ("l", "lb")]
    + [("is_empty", (t,), "b", _unary("is_empty")) for t in ("l", "lb")]
    + [("neg", ("i",), "i", _unary("neg")), ("abs", ("i",), "i", _unary("abs")),
       ("not", ("b",), "b", _unary("not"))]
    + [(n, ("i", "i"), "i", _arith(n)) for n in ("add", "sub", "mul", "div", "mod")]
    + [(n, ("i", "i"), "b", _compare(n)) for n in ("eq", "lt", "le", "gt", "ge")]
    + [(n, ("b", "b"), "b", _boolean(n)) for n in ("and", "or")]
    + [("cons", ("i", "l"), "l", _cons), ("cons", ("b", "lb"), "lb", _cons)]
)
COMMUTATIVE = {"add", "mul", "eq", "and", "or"}
# Binary primitives that can be partially applied to make a map/filter function.
PARTIAL = [(n, "i", _arith(n)) for n in ("add", "sub", "mul", "div", "mod")] + [
    (n, "b", _compare(n)) for n in ("eq", "lt", "le", "gt", "ge")]


def _digest(*parts) -> int:
    return int.from_bytes(hashlib.blake2b(repr(parts).encode(), digest_size=8).digest(), "big")


def _prim(name: str) -> Term:
    return Term("prim", name)


def _apply(head: Term, *args: Term) -> Term:
    for a in args:
        head = App(head, a)
    return head


def _splits(total: int, k: int):
    if k == 1:
        if total >= 1:
            yield (total,)
        return
    for first in range(1, total - k + 2):
        for rest in _splits(total - first, k - 1):
            yield (first,) + rest


# ---- problems -------------------------------------------------------------
class Problem:
    """What behaviour is wanted, over which inputs, and how a match becomes a program.

    ``variables``: (term, tag) for each variable the pool may use;
    ``envs``: one tuple of variable values per input point;
    ``targets``: (tag, vector) -> list of roles, for lookup problems;
    ``groups``/``quantifier``: for any/all problems, (positions, expected) per
    example and "any" or "all";
    ``binders``: the lambda binder types around the body, outermost first;
    ``skeleton``: the skeleton the hole goes into, or None for a whole program.
    Plain data, so a runtime holding problems can be checkpointed.
    """

    def __init__(self, name, variables, envs, binders, *, skeleton=None, targets=None,
                 unroll=0, groups=None, quantifier=None):
        self.name = name
        self.variables = variables
        self.envs = envs
        self.binders = tuple(binders)
        self.skeleton = skeleton
        self.targets = targets or {}
        self.unroll = unroll       # number of cons levels for list targets
        self.groups = groups
        self.quantifier = quantifier

    def wrap(self, body):
        for binder in reversed(self.binders):
            body = Lam(binder, body)
        return body if self.skeleton is None else self.skeleton.compose(body)

    @property
    def has_predicate(self) -> bool:
        return self.groups is not None

    def predicate(self, vector) -> bool:
        test = any if self.quantifier == "any" else all
        return all(test(vector[i] for i in idx) == y for idx, y in self.groups)

    def relevant(self) -> set:
        """Value types that can contribute to a target (backward reachability).

        Without ``if``, a boolean reaches an int or int list only through
        ``filter`` functions, which are built directly, not taken from the
        pool; a boolean list reaches an int only as its length, which equals
        the length of the int list it was mapped from. Pruning those types
        loses no behaviour a target can use.
        """
        tags = {tag for tag, _ in self.targets} | ({"b"} if self.has_predicate else set())
        if "lb" in tags:
            return {"i", "b", "l", "lb"}
        if "b" in tags:
            return {"i", "b", "l"}
        return {"i", "l"}

    def wanted(self, tag, vector) -> list:
        roles = list(self.targets.get((tag, vector), ()))
        if tag == "b":
            roles += [("not",) + role
                      for role in self.targets.get(("b", tuple(not v for v in vector)), ())]
            if self.has_predicate and self.predicate(vector):
                roles.append(("pred",))
        return roles


def whole_problem(examples, request_type, max_unroll: int = 6):
    """The whole program, with cons deduction for list outputs."""
    arguments, result = function_parts(request_type)
    tags = [tag_of(_ground(a)) for a in arguments]
    out_tag = tag_of(_ground(result))
    if not arguments or None in tags or out_tag is None:
        return None
    n = len(arguments)
    variables = [(Var(n - 1 - i), tags[i]) for i in range(n)]
    envs = [tuple(frozen(v) for v in inputs) for inputs, _ in examples]
    outputs = [frozen(out) for _, out in examples]
    targets: dict = {}
    unroll = 0
    if out_tag in ("l", "lb"):
        rest = outputs
        for level in range(max_unroll + 1):
            targets.setdefault((out_tag, tuple(rest)), []).append(("R", level))
            if level == max_unroll or not all(len(r) > 0 for r in rest):
                break
            targets.setdefault((_ELEMENT[out_tag], tuple(r[0] for r in rest)), []).append(
                ("H", level))
            rest = [r[1:] for r in rest]
            unroll = level + 1
    else:
        targets[(out_tag, tuple(outputs))] = [("R", 0)]

    return Problem("whole", variables, envs, [_ground(a) for a in arguments],
                   targets=targets, unroll=unroll)


def hole_problem(skeleton, examples):
    """A pointwise (or any/all) problem for a skeleton's hole, or None."""
    name = skeleton.name
    pairs = [(frozen(inputs[0]), frozen(out)) for inputs, out in examples]
    x_only = [(Var(0), "i")]
    with_list = [(Var(1), "l"), (Var(0), "i")]
    lam_x, lam_lx, lam_l = [INT], [LIST, INT], [LIST]

    if name == "map":
        table = {}
        for xs, ys in pairs:
            for a, b in zip(xs, ys):
                table[a] = b
        keys = sorted(table)
        if not keys:
            return None
        out = tuple(table[k] for k in keys)
        return Problem(name, x_only, [(k,) for k in keys], lam_x, skeleton=skeleton,
                       targets={(value_tag(out[0]), out): [("R", 0)]})
    if name == "filter":
        kept, dropped = set(), set()
        for xs, ys in pairs:
            remaining = list(ys)
            for a in xs:
                if remaining and remaining[0] == a:
                    kept.add(a)
                    remaining.pop(0)
                else:
                    dropped.add(a)
        keys = sorted(kept | dropped)
        if not keys:
            return None
        return Problem(name, x_only, [(k,) for k in keys], lam_x, skeleton=skeleton,
                       targets={("b", tuple(k in kept for k in keys)): [("R", 0)]})
    if name in ("any", "all"):
        keys = sorted({a for xs, _ in pairs for a in xs})
        position = {k: i for i, k in enumerate(keys)}
        groups = [([position[a] for a in xs], y) for xs, y in pairs]
        return Problem(name, x_only, [(k,) for k in keys], lam_x, skeleton=skeleton,
                       groups=groups, quantifier=name)
    if name in ("map_list", "filter_list"):
        table = {}
        for xs, ys in pairs:
            remaining = list(ys)
            for index, a in enumerate(xs):
                if name == "map_list":
                    value = ys[index]
                else:
                    value = bool(remaining and remaining[0] == a)
                    if value:
                        remaining.pop(0)
                if table.setdefault((xs, a), value) != value:
                    return None
        keys = list(table)
        if not keys:
            return None
        out = tuple(table[k] for k in keys)
        return Problem(name, with_list, keys, lam_lx, skeleton=skeleton,
                       targets={(value_tag(out[0]) if name == "map_list" else "b", out):
                                [("R", 0)]})
    if name == "any_list":
        envs, groups = [], []
        for xs, y in pairs:
            idx = []
            for a in xs:
                idx.append(len(envs))
                envs.append((xs, a))
            groups.append((idx, y))
        return Problem(name, with_list, envs, lam_lx, skeleton=skeleton,
                       groups=groups, quantifier="any")
    if name == "map_const":
        rows = [(xs, ys[0]) for xs, ys in pairs if ys]
        if not rows:
            return None
        out = tuple(y for _, y in rows)
        return Problem(name, [(Var(0), "l")], [(xs,) for xs, _ in rows], lam_l,
                       skeleton=skeleton, targets={("i", out): [("R", 0)]})
    return None


POINTWISE = ("map", "filter", "any", "all", "map_list", "filter_list", "any_list", "map_const")


# ---- witness functions (inverse semantics) --------------------------------
def _choose(candidates, constants):
    usable = sorted((c for c in candidates if c in constants), key=lambda c: (abs(c), c))
    return usable[:1]


def _int_witness(a, t, constants) -> list:
    """(op, c, swapped) with op(a, c) == t (or op(c, a) when swapped), c available."""
    from math import gcd
    out = []
    for op, values, swapped in (("add", {ti - ai for ai, ti in zip(a, t)}, False),
                                ("sub", {ai - ti for ai, ti in zip(a, t)}, False),
                                ("sub", {ti + ai for ai, ti in zip(a, t)}, True)):
        if len(values) == 1:
            out += [(op, c, swapped) for c in _choose(values, constants) if c != 0]
    if all(ai != 0 or ti == 0 for ai, ti in zip(a, t)) and all(
            ti % ai == 0 for ai, ti in zip(a, t) if ai != 0):
        ratios = {ti // ai for ai, ti in zip(a, t) if ai != 0}
        if len(ratios) == 1:
            out += [("mul", c, False) for c in _choose(ratios, constants) if c not in (0, 1)]
    if all(ti >= 0 for ti in t):
        g = 0
        for ai, ti in zip(a, t):
            g = gcd(g, ai - ti)
        if g:
            divisors = [c for c in constants if c > max(t) and c > 0 and g % c == 0
                        and all(ai % c == ti for ai, ti in zip(a, t))]
            out += [("mod", c, False) for c in _choose(divisors, constants)]
    quotients = [c for c in constants if c not in (0, 1)
                 and all(ai // c == ti for ai, ti in zip(a, t))]
    out += [("div", c, False) for c in _choose(quotients, constants)]
    return out


def _bool_witness(a, t, constants) -> list:
    """(op, c, False) with the comparison op(a, c) == t, c available."""
    true = [ai for ai, ti in zip(a, t) if ti]
    false = [ai for ai, ti in zip(a, t) if not ti]
    if not true or not false:
        return []
    out = []
    if len(set(true)) == 1 and true[0] not in set(false):
        out += [("eq", c, False) for c in _choose({true[0]}, constants)]
    hi_t, lo_t, hi_f, lo_f = max(true), min(true), max(false), min(false)
    out += [("lt", c, False) for c in _choose({c for c in constants if hi_t < c <= lo_f},
                                              constants)]
    out += [("gt", c, False) for c in _choose({c for c in constants if hi_f <= c < lo_t},
                                              constants)]
    return out


def _quantifier_witness(problem, a, constants) -> list:
    """(op, c, False) whose comparison vector satisfies an any/all problem."""
    out = []
    groups = problem.groups or []
    if problem.quantifier == "all":
        must = [a[i] for idx, y in groups if y for i in idx]
        if must:
            hi, lo = max(must), min(must)
            candidates = []
            if len(set(must)) == 1:
                candidates += [("eq", c) for c in _choose({must[0]}, constants)]
            candidates += [("lt", c) for c in _choose({c for c in constants if c > hi},
                                                     constants)]
            candidates += [("gt", c) for c in _choose({c for c in constants if c < lo},
                                                     constants)]
            out += [(op, c, False) for op, c in candidates]
    else:
        never = {a[i] for idx, y in groups if not y for i in idx}
        sets = [{a[i] for i in idx} for idx, y in groups if y]
        if sets:
            common = set.intersection(*sets) - never
            out += [("eq", c, False) for c in _choose(common, constants)]
    return [w for w in out if problem.predicate(_apply_witness(a, w))]


_WITNESS_FN = {**{n: _arith(n) for n in ("add", "sub", "mul", "div", "mod")},
               **{n: _compare(n) for n in ("eq", "lt", "le", "gt", "ge")}}


def _apply_witness(a, witness):
    op, c, swapped = witness
    fn = _WITNESS_FN[op]
    return tuple(fn(c, ai) if swapped else fn(ai, c) for ai in a)


def witnesses(problem, a, constants) -> list:
    """Every (tag, op, c, swapped) the problem's targets deduce from int behaviour ``a``.

    A witness function inverts one binary operation with a constant argument:
    from ``a`` and a target it computes which available constant c, if any,
    makes op(a, c) meet the target, in one pass over the vectors. Only the
    programs it proposes are charged.
    """
    if len(set(a)) <= 1:
        return []
    found = []
    for (tag, target) in problem.targets:
        if tag == "i":
            found += [("i",) + w for w in _int_witness(a, target, constants)]
        elif tag == "b":
            found += [("b",) + w for w in _bool_witness(a, target, constants)]
            found += [("b",) + w for w in _bool_witness(a, tuple(not v for v in target),
                                                       constants)]
    if problem.has_predicate:
        found += [("b",) + w for w in _quantifier_witness(problem, a, constants)]
    unique = []
    for w in found:
        if w not in unique:
            unique.append(w)
    return unique


# ---- the pool -------------------------------------------------------------
def library_components(library: dict):
    """First-order library entries: (name, argument tags, result tag), sorted by name."""
    found = []
    for name in sorted(library):
        try:
            type_ = _ground(infer(Term("ref", name), library=library))
        except Exception:
            continue
        arguments, result = function_parts(type_)
        tags = [tag_of(a) for a in arguments]
        if None in tags or tag_of(result) is None:
            continue
        found.append((name, tuple(tags), tag_of(result)))
    return found


class BehaviouralSearch:
    """A resumable behavioural search for one problem (the ResumableSearch interface)."""

    def __init__(self, problem: Problem, library: dict, examples, *, step_budget: int = 2000,
                 max_size: int = 10, known: set | None = None, combo_limit: int = 2_000_000,
                 weights: dict | None = None, witnesses: bool = True):
        self.problem = problem
        self.witnesses = bool(witnesses)
        # RSI-2's fitted production weights (``name/arity`` -> count), fitted
        # on the system's own solutions; within a size, operations the system
        # has used more are tried first. None: a fixed order.
        self.weights = dict(weights or {})
        self.library = dict(library)
        self.examples = tuple(examples)
        self.step_budget = int(step_budget)
        self.max_size = int(max_size)
        self.known = known
        self.combo_limit = int(combo_limit)
        self.evaluated = 0
        self.skipped_known = 0
        self.exhausted = False
        self.evaluation_steps = 0
        self.combinations = 0       # programs built, duplicates included (reported)
        self.found: dict = {}        # role -> first program with that behaviour
        self._events = self._generate()

    @property
    def position(self) -> int:
        return self.evaluated + self.skipped_known

    # -- vectors ------------------------------------------------------
    def _library_vector(self, name, vectors):
        ref = Term("ref", name)
        out = []
        columns = zip(*vectors) if vectors else [()] * len(self.problem.envs)
        for column in columns:
            result = evaluate(ref, tuple(thawed(v) for v in column), library=self.library,
                              step_budget=self.step_budget)
            self.evaluation_steps += result.steps
            if not result.ok or value_tag(result.value) is None and result.value != []:
                return None
            out.append(frozen(result.value))
        return tuple(out)

    def _call_library(self, name, value):
        result = evaluate(Term("ref", name), (thawed(value),), library=self.library,
                          step_budget=self.step_budget)
        self.evaluation_steps += result.steps
        return frozen(result.value) if result.ok else _ERR

    def _weight(self, name, arity) -> float:
        return float(self.weights.get(f"{name}/{arity}", self.weights.get(name, 1.0)))

    def _generate(self):
        """Yield (tag, term, vector, kind) by size, then grammar weight, then a fixed order.

        ``kind`` is "new" (a behaviour added to the pool), "duplicate" (a
        target-equal behaviour already in the pool, kept as an alternative) or
        "derived" (a witness's proposal: not added to the pool, not charged).
        """
        problem = self.problem
        relevant = problem.relevant()
        pool: dict[tuple[str, int], list] = {}
        seen: set = set()
        library = library_components(self.library)
        lib_ops = [(name, args, res) for name, args, res in library
                   if args and res in relevant and all(a in relevant for a in args)]
        lib_leaves = [(name, res) for name, args, res in library if not args and res in relevant]
        lib_unary = [(name, args[0], res) for name, args, res in library
                     if len(args) == 1 and args[0] == "i" and res in ("i", "b")]
        operations = [(_prim(n), args, res, fn, n) for n, args, res, fn in FIRST_ORDER
                      if res in relevant and all(a in relevant for a in args)]
        operations += [(Term("ref", n), args, res, None, n) for n, args, res in lib_ops]
        order = {id(op): i for i, op in enumerate(operations)}
        operations.sort(key=lambda op: (-self._weight(op[4], len(op[1])), order[id(op)]))
        partials = sorted(PARTIAL, key=lambda item: -self._weight(item[0], 2))
        higher_order = sorted(["map", "filter"], key=lambda n: -self._weight(n, 2))

        constants: dict = {}            # value -> the first program with that constant behaviour

        def admit(tag, size, term, vector):
            if vector is None:
                return []
            key = (tag, vector)
            if key in seen:
                return [(tag, term, vector, "duplicate")] if problem.wanted(tag, vector) else []
            seen.add(key)
            pool.setdefault((tag, size), []).append((term, vector))
            events = [(tag, term, vector, "new")]
            if tag == "i" and envs:
                if len(set(vector)) == 1:
                    constants.setdefault(vector[0], term)
                elif self.witnesses:
                    for wtag, op, c, swapped in witnesses(problem, vector, constants):
                        args = (constants[c], term) if swapped else (term, constants[c])
                        events.append((wtag, _apply(_prim(op), *args),
                                       _apply_witness(vector, (op, c, swapped)), "derived"))
            return events

        def count():
            self.combinations += 1
            return self.combinations > self.combo_limit

        envs = problem.envs
        # size 1: variables, then constants, nil and library constants by weight
        leaves = [(term, tag, tuple(env[i] for env in envs))
                  for i, (term, tag) in enumerate(problem.variables) if tag in relevant]
        constant_leaves = [(Term("int", v), "i", tuple(v for _ in envs), f"int:{v}")
                           for v in (-1, 0, 1, 2)]
        constant_leaves += [(Term("bool", v), "b", tuple(v for _ in envs),
                             f"bool:{str(v).lower()}") for v in (False, True)]
        constant_leaves += [(_prim("nil"), t, tuple(() for _ in envs), "nil")
                            for t in ("l", "lb")]
        for name, tag in lib_leaves:
            vector = self._library_vector(name, [])
            if vector is not None:
                constant_leaves.append((Term("ref", name), tag, vector, name))
        constant_leaves = [c for c in constant_leaves if c[1] in relevant]
        rank = {id(c): i for i, c in enumerate(constant_leaves)}
        constant_leaves.sort(key=lambda c: (-self._weight(c[3], 0), rank[id(c)]))
        # Constants first, so witnesses see them; variables follow at size 1.
        for term, tag, vector in [c[:3] for c in constant_leaves] + leaves:
            yield from admit(tag, 1, term, vector)
        for size in range(2, self.max_size + 1):
            for head, args, res, fn, name in operations:
                for split in _splits(size - 1, len(args)):
                    groups = [pool.get((args[i], split[i]), []) for i in range(len(args))]
                    if any(not g for g in groups):
                        continue
                    for combo in _product(groups):
                        if (name in COMMUTATIVE and fn is not None and len(combo) == 2
                                and split[0] == split[1] and combo[0][1] > combo[1][1]):
                            continue
                        if count():
                            self.exhausted = True
                            return
                        vectors = [c[1] for c in combo]
                        if fn is not None:
                            out = []
                            for column in zip(*vectors):
                                value = fn(*column)
                                if value is _ERR:
                                    out = None
                                    break
                                out.append(value)
                            vector = None if out is None else tuple(out)
                        else:
                            vector = self._library_vector(name, vectors)
                        yield from admit(res, size, _apply(head, *[c[0] for c in combo]), vector)
            # map and filter with a unary function: a library entry (size 1)
            # or a partially applied primitive (size 1 + argument size)
            for function_size in range(1, size - 1):
                list_size = size - 1 - function_size
                functions = []
                if function_size == 1:
                    for name, _, res in lib_unary:
                        functions.append((Term("ref", name), res, ("lib", name)))
                for argument_size in ([function_size - 1] if function_size >= 2 else []):
                    for term, vector in pool.get(("i", argument_size), []):
                        for name, res, fn in partials:
                            functions.append((App(_prim(name), term), res, ("partial", fn, vector)))
                if not functions:
                    continue
                for list_term, list_vector in pool.get(("l", list_size), []):
                    for function, res, how in functions:
                        for higher in higher_order:
                            if higher == "filter" and res != "b":
                                continue
                            if higher == "map" and _LIST_OF[res] not in relevant:
                                continue
                            if count():
                                self.exhausted = True
                                return
                            out = []
                            for index, sequence in enumerate(list_vector):
                                values = []
                                for element in sequence:
                                    if how[0] == "lib":
                                        value = self._call_library(how[1], element)
                                    else:
                                        value = how[1](how[2][index], element)
                                    if value is _ERR or (res == "b") != (type(value) is bool):
                                        values = None
                                        break
                                    values.append(value)
                                if values is None:
                                    out = None
                                    break
                                out.append(tuple(values) if higher == "map" else
                                           tuple(e for e, keep in zip(sequence, values) if keep))
                            vector = None if out is None else tuple(out)
                            tag = (_LIST_OF[res] if higher == "map" else "l")
                            yield from admit(tag, size, _apply(_prim(higher), function,
                                                               list_term), vector)
        self.exhausted = True

    # -- assembly -------------------------------------------------------
    def _record(self, tag, term, vector) -> list:
        """Remember which roles this program fills; return candidate bodies it completes."""
        bodies = []
        for role in self.problem.wanted(tag, vector):
            filled = term if role[0] != "not" else App(_prim("not"), term)
            base = role if role[0] != "not" else role[1:]
            if base == ("pred",):
                bodies.append(filled)
                continue
            self.found.setdefault(base, filled)
            bodies.extend(self._assemble(base, filled))
        return bodies

    def _assemble(self, role, term) -> list:
        """Bodies that use ``term`` for ``role`` and the first program found for the rest."""
        bodies = []
        for level in range(self.problem.unroll + 1):
            if ("R", level) not in self.found and role != ("R", level):
                continue
            needed = [("H", i) for i in range(level)] + [("R", level)]
            if role not in needed:
                continue
            if not all(r in self.found or r == role for r in needed):
                continue
            body = term if role == ("R", level) else self.found[("R", level)]
            for i in reversed(range(level)):
                head = term if role == ("H", i) else self.found[("H", i)]
                body = App(App(_prim("cons"), head), body)
            bodies.append(body)
        return bodies

    def _public_match(self, program) -> bool:
        for inputs, expected in self.examples:
            result = evaluate(program, inputs, library=self.library, step_budget=self.step_budget)
            self.evaluation_steps += result.steps
            if not result.ok or result.value != expected:
                return False
        return True

    # -- the ResumableSearch interface -----------------------------------
    def fast_forward(self, position: int, evaluated: int, skipped_known: int,
                     evaluation_steps: int) -> None:
        """Rebuild the pool through ``position`` events without charging or checking."""
        passed = 0
        while passed < position:
            try:
                tag, term, vector, kind = next(self._events)
            except StopIteration:
                self.exhausted = True
                break
            self._record(tag, term, vector)
            passed += kind != "derived"
        self.evaluated, self.skipped_known = evaluated, skipped_known
        self.evaluation_steps = evaluation_steps

    def run(self, budget: int, skip_match=None) -> WindowResult:
        if budget < 0:
            raise ValueError("window budget must be nonnegative")
        started = time.perf_counter()
        start, steps_before = self.evaluated, self.evaluation_steps
        used = skipped = known = 0
        found = None
        while used < budget and not self.exhausted and found is None:
            try:
                tag, term, vector, kind = next(self._events)
            except StopIteration:
                self.exhausted = True
                break
            if kind != "derived":
                key = _digest(self.problem.name, tag, vector,
                              None if kind == "new" else repr(term))
                if self.known is not None and key in self.known:
                    known += 1
                    self.skipped_known += 1
                else:
                    used += 1
                    self.evaluated += 1
                    if self.known is not None:
                        self.known.add(key)
            # Programs a new behaviour completes are all checked, even past
            # the window (the excess is charged), so none is lost.
            for body in self._record(tag, term, vector):
                program = self.problem.wrap(body)
                program_key = _digest("program", repr(program))
                if self.known is not None and program_key in self.known:
                    continue
                used += 1
                self.evaluated += 1
                if self.known is not None:
                    self.known.add(program_key)
                if not self._public_match(program):
                    continue
                if skip_match is not None and skip_match(program):
                    skipped += 1
                    continue
                found = program
                break
        return WindowResult(term=found, log_probability=None, start=start, evaluated=used,
                            exhausted=self.exhausted and found is None,
                            evaluation_steps=self.evaluation_steps - steps_before,
                            skipped_matches=skipped, wall_seconds=time.perf_counter() - started,
                            skipped_known=known)


def _product(groups):
    if not groups:
        yield ()
        return
    for first in groups[0]:
        for rest in _product(groups[1:]):
            yield (first,) + rest


def problems_for(examples, request_type, skeletons, max_unroll: int = 6) -> dict:
    """Behavioural problems for a task: the whole program, and each pointwise hole."""
    found = {}
    whole = whole_problem(examples, request_type, max_unroll)
    if whole is not None:
        found["whole"] = whole
    for skeleton in skeletons:
        if skeleton.name in POINTWISE:
            problem = hole_problem(skeleton, examples)
            if problem is not None:
                found[skeleton.name] = problem
    return found
