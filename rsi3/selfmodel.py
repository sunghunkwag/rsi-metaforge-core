"""Self-model and concept invention: the system rewrites its own language.

Across 21 registered RSI-3 runs, RSI-2's library learning adopted nothing: its
MDL rule needs a fragment to recur in at least two solutions and to shrink
the solution corpus, and 6 to 8 small solutions (sizes 2 to 8) never recur.
The language the system searches in was therefore the same at the end of
every run as at the start, and VALIDATION never moved. This module is the
missing step. It is not another check that the system did not get worse.

Each generation the system builds a model of itself from its own records:

* ABILITIES: its verified TRAIN programs (receipts from the frozen
  verifier) and what they are made of: every subterm, closed by lambda
  lifting, with and without its literal constants turned into parameters.
* VOCABULARY: the frozen primitives and constants, plus its library.
* BEHAVIOUR: what each candidate concept does on probe inputs drawn from
  TRAIN public inputs. Two concepts with the same behaviour are the same
  concept, and one that behaves like a primitive or an existing entry, or
  like the identity, is not new.

It then invents concepts from its own parts:

* ``part``      a lifted subterm of a verified program, e.g. ``tail (tail x)``
                from ``head (tail (tail x))``. One occurrence is enough;
                RSI-2's MDL rule needs two.
* ``power``     a part applied to its own output twice or three times
                (``tail . tail`` becomes ``tail . tail . tail . tail``).
* ``compose``   one part applied to another part's output.
* ``constant``  a closed integer the vocabulary cannot name directly: a
                closed integer part; an int -> int part applied to a constant,
                such as ``add 2 2`` = 4; or an int -> int -> int primitive the
                system has used in a verified program, applied to two
                constants it can already name, such as ``sub 2 -1`` = 3.
                Smallest magnitude first. The frozen grammar names only -1,
                0, 1 and 2.

Proposals are beta-eta normalized; eta-expanded primitives are dropped. Up to a
fixed number of each kind, smallest (most general) first, join the search
grammar for that generation as library entries. Their
weights are RSI-2's pseudocount, like any unused production. A concept is
ADOPTED, and becomes a permanent part of the system's language, only when a
program that uses it is accepted by the frozen verifier on a TRAIN task's
hidden examples. Concepts that earn nothing leave with the generation.
Adopted concepts are parts for the next generation's invention, so a concept
can be built from concepts the system invented before.

Concept names are derived from their content, so the same concept keeps one
name across generations and failure memory stays sound. Invention reads only
the system's own solutions, its library and TRAIN public inputs. It never
reads hidden examples, VALIDATION or TEST, and it adds no primitive: every
concept is a library body over the frozen DSL. Building the self-model
evaluates concepts on probe inputs, which is reported separately and is not a
candidate evaluation, as with the binding integrator's probes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from rsi2.abstraction import lift_subtree
from rsi2.evaluator import evaluate
from rsi2.terms import App, Lam, Term, Var, pretty, shift
from rsi2.types import (INT, PRIMITIVE_TYPES, Type, TypeInferenceError, function_parts,
                        infer, instantiate, unify)

KINDS = ("constant", "iterate", "power", "compose", "part")
BASE_CONSTANTS = (-1, 0, 1, 2)
DEFAULT_CAPS = {"constant": 4, "iterate": 3, "power": 6, "compose": 6, "part": 8}
MIN_PART_SIZE = 4
MIN_WHOLE_SIZE = 6
# Prior weight of a concept not yet adopted. RSI-2 gives an unused production
# pseudocount 1; at 1 the 14 concepts invented from the first six (trivial)
# solutions pushed index-k (k=3) from rank 273 to 820 under the generation-2
# grammar, at 0.1 to 317 (development measurement, PREDICTIONS_INVENTION.md).
# An adopted concept is refit by RSI-2's sleep like any library entry.
CONCEPT_WEIGHT = 0.1


@dataclass(frozen=True)
class Concept:
    name: str
    term: Term
    kind: str
    type: str
    saving: int            # nodes saved each time it is used: body size - 1
    sources: tuple         # TRAIN tasks whose verified programs supplied the parts
    value: object = None   # closed integer concepts only

    def to_record(self) -> dict:
        return {"name": self.name, "kind": self.kind, "type": self.type,
                "body": pretty(self.term), "saving": self.saving,
                "sources": list(self.sources), "value": self.value}


def concept_name(term: Term) -> str:
    return "c_" + hashlib.sha256(pretty(term).encode("utf-8")).hexdigest()[:10]


def _substitute(term: Term, index: int, replacement: Term) -> Term:
    if term.tag == "var":
        return replacement if term.value == index else term
    if term.tag == "lam":
        return Lam(term.value, _substitute(term.children[0], index + 1, shift(replacement, 1)))
    if term.tag == "app":
        return App(_substitute(term.children[0], index, replacement),
                   _substitute(term.children[1], index, replacement))
    return term


def _free(term: Term, index: int) -> bool:
    if term.tag == "var":
        return term.value == index
    return any(_free(child, index + (term.tag == "lam")) for child in term.children)


def normalize(term: Term) -> Term:
    """Beta-eta normal form (the DSL is simply typed, so this terminates)."""
    if term.tag == "lam":
        body = normalize(term.children[0])
        if (body.tag == "app" and body.children[1] == Var(0)
                and not _free(body.children[0], 0)):
            return shift(body.children[0], -1)
        return Lam(term.value, body)
    if term.tag != "app":
        return term
    function, argument = normalize(term.children[0]), normalize(term.children[1])
    if function.tag == "lam":
        body = _substitute(function.children[0], 0, shift(argument, 1))
        return normalize(shift(body, -1))
    return App(function, argument)


def canonical_types(term: Term) -> Term:
    """Rename type variables in lambda annotations in first-occurrence order.

    Inferred types carry globally fresh variable names; a concept's name is
    derived from its text, so the text must not depend on that counter.
    """
    names: dict[str, Type] = {}

    def rename(type_: Type) -> Type:
        if type_.is_variable:
            if type_.name not in names:
                names[type_.name] = Type("var", (f"_c{len(names)}",))
            return names[type_.name]
        return Type(type_.tag, tuple(rename(arg) for arg in type_.args))

    def visit(node: Term) -> Term:
        value = rename(node.value) if node.tag == "lam" else node.value
        return Term(node.tag, value, tuple(visit(child) for child in node.children))

    return visit(term)


def is_eta_atom(term: Term) -> bool:
    """``lambda ... lambda. p x_k ... x_0`` for a primitive or library atom p."""
    depth = 0
    while term.tag == "lam":
        term, depth = term.children[0], depth + 1
    arguments = []
    while term.tag == "app":
        arguments.append(term.children[1])
        term = term.children[0]
    if term.tag not in ("prim", "ref"):
        return False
    arguments.reverse()
    return arguments == [Var(depth - 1 - i) for i in range(depth)]


def _is_int_constant(name, library) -> bool:
    try:
        return infer(Term("ref", name), library=library).tag == "int"
    except (TypeInferenceError, RecursionError):
        return False


def _used_binary_int_ops(solutions: dict) -> list[tuple[str, tuple]]:
    binary = {name for name, signature in PRIMITIVE_TYPES.items()
              if str(signature) == "int -> int -> int"}
    used: dict[str, set] = {}
    for task in sorted(solutions):
        for node, _ in _walk(solutions[task]):
            if node.tag == "prim" and node.value in binary:
                used.setdefault(node.value, set()).add(task)
    return [(op, tuple(sorted(tasks))) for op, tasks in sorted(used.items())]


def _closed(term: Term) -> bool:
    return not any(_free(term, i) for i in range(_max_var(term) + 1))


def _max_var(term: Term, depth: int = 0) -> int:
    if term.tag == "var":
        return term.value - depth
    return max((_max_var(child, depth + (term.tag == "lam")) for child in term.children),
               default=-1)


def _repeated_functions(solutions: dict, library: dict) -> list[tuple[Term, tuple]]:
    """Closed functions applied to their own output: ``f (f x)``."""
    found: dict[str, list] = {}
    sources = [(task, term) for task, term in sorted(solutions.items())]
    sources += [(f"library:{name}", term) for name, term in sorted(library.items())]
    for origin, term in sources:
        for node, _ in _walk(term):
            if node.tag != "app" or node.children[1].tag != "app":
                continue
            outer, inner = node.children[0], node.children[1].children[0]
            if outer == inner and _closed(outer):
                key = pretty(outer)
                found.setdefault(key, [outer, set()])[1].add(origin)
    return [(term, tuple(sorted(origins))) for _, (term, origins) in sorted(found.items())]


def _walk(term, env=()):
    yield term, env
    for child in term.children:
        bindings = (term.value,) + env if term.tag == "lam" else env
        yield from _walk(child, bindings)


def _literal_paths(term, path=()):
    if term.tag in ("int", "bool"):
        yield path
    for index, child in enumerate(term.children):
        yield from _literal_paths(child, path + (index,))


def _unifies(left: Type, right: Type) -> bool:
    try:
        unify(instantiate(left, "_sm_l_"), instantiate(right, "_sm_r_"))
    except TypeInferenceError:
        return False
    return True


def _value_kind(value):
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if isinstance(value, (list, tuple)) and all(type(v) is int for v in value):
        return "list[int]"
    return None


def _type_kind(type_: Type):
    if type_.tag in ("int", "bool"):
        return type_.tag
    if type_.tag == "list" and type_.args[0].tag in ("int", "var"):
        return "list[int]"
    return None


class SelfModel:
    def __init__(self, public_tasks, *, caps=None, step_budget: int = 2000,
                 probes_per_kind: int = 12):
        self.caps = dict(DEFAULT_CAPS if caps is None else caps)
        self.step_budget = int(step_budget)
        self.probe_evaluations = 0
        pool = {"int": [], "bool": [], "list[int]": []}
        seen = set()
        for task in sorted(public_tasks, key=lambda t: t.name):
            for inputs, output in task.examples:
                for value in (*inputs, output):
                    kind = _value_kind(value)
                    key = (kind, json.dumps(value))
                    if kind is None or key in seen or len(pool[kind]) >= probes_per_kind:
                        continue
                    seen.add(key)
                    pool[kind].append(value)
        self.pool = pool

    # ---- behaviour -----------------------------------------------------
    def _run(self, term, inputs, library):
        self.probe_evaluations += 1
        result = evaluate(term, inputs, library=library, step_budget=self.step_budget)
        return result.value if result.ok else "!error"

    def behaviour(self, term, type_: Type, library):
        """Outputs on probe inputs for a one-argument first-order concept, else None."""
        arguments, _ = function_parts(type_)
        if len(arguments) != 1:
            return None
        kind = _type_kind(arguments[0])
        if kind is None or not self.pool[kind]:
            return None
        return json.dumps([self._run(term, (value,), library) for value in self.pool[kind]],
                          default=str)

    def _known_behaviours(self, library):
        known = set()
        for kind, inputs in self.pool.items():
            if inputs:        # the identity on every probe kind
                known.add(json.dumps(list(inputs), default=str))
        for name, signature in PRIMITIVE_TYPES.items():
            arguments, _ = function_parts(signature)
            if len(arguments) == 1:
                behaviour = self.behaviour(Term("prim", name), signature, library)
                if behaviour is not None:
                    known.add(behaviour)
        for name in sorted(library):
            try:
                type_ = infer(Term("ref", name), library=library)
            except (TypeInferenceError, RecursionError):
                continue
            behaviour = self.behaviour(Term("ref", name), type_, library)
            if behaviour is not None:
                known.add(behaviour)
        return known

    # ---- abilities -----------------------------------------------------
    def parts(self, solutions: dict, library: dict) -> list[tuple[Term, Type, tuple]]:
        """Every closed lifted subterm of every verified program, with its sources."""
        found: dict[str, list] = {}
        for task in sorted(solutions):
            for node, env in _walk(solutions[task]):
                if node.size < 2:
                    continue
                literals = tuple(_literal_paths(node))
                variants = [()] + ([literals] if literals else [])
                for holes in variants:
                    try:
                        entry, _ = lift_subtree(node, env, holes)
                        type_ = infer(entry, library=library)
                    except (TypeInferenceError, RecursionError):
                        continue
                    key = pretty(entry)
                    if key in found:
                        if task not in found[key][2]:
                            found[key][2] = found[key][2] + (task,)
                        continue
                    found[key] = [entry, type_, (task,)]
        return [tuple(item) for _, item in sorted(found.items())]

    # ---- invention -----------------------------------------------------
    def invent(self, solutions: dict, library: dict) -> list[Concept]:
        existing = {pretty(term) for term in library.values()}
        constants = set(BASE_CONSTANTS)
        for name in sorted(library):
            try:
                if infer(Term("ref", name), library=library).tag == "int":
                    value = self._run(Term("ref", name), (), library)
                    if type(value) is int:
                        constants.add(value)
            except (TypeInferenceError, RecursionError):
                continue
        known = self._known_behaviours(library)
        parts = self.parts(solutions, library)
        whole = {pretty(normalize(term)) for term in solutions.values()}
        unary = []          # (term, argument type, result type, sources)
        int_functions = []
        proposals = {kind: [] for kind in KINDS}

        for term, type_, sources in parts:
            arguments, result = function_parts(type_)
            if not arguments:
                if type_.tag == "int":
                    proposals["constant"].append((term, type_, sources))
                continue
            # A part is worth a production only if naming it saves search: at
            # least four nodes. A whole solved program is a part only if it is
            # not trivial (six nodes or more): knowing how to do one task is a
            # building block for another (index-k becomes a word inside
            # prepend-index-k), but ``cons 0`` or ``map (eq 1)`` named again
            # only widens the search.
            minimum = MIN_WHOLE_SIZE if pretty(normalize(term)) in whole else MIN_PART_SIZE
            if term.size >= minimum:
                proposals["part"].append((term, type_, sources))
            if len(arguments) == 1 and normalize(term) != Lam(arguments[0], Var(0)):
                unary.append((term, arguments[0], result, sources))
                if arguments[0].tag == "int" and result.tag == "int":
                    int_functions.append((term, sources))

        # Repetition the system has itself used, generalized: a closed
        # function applied to its own output inside a verified program or an
        # adopted concept (tail (tail x), or tail^4) becomes a loop over a
        # count, ``lambda n x. fold (lambda acc _. f acc) x (range n)``. The
        # count, fixed in every program it has, becomes an argument.
        for f, sources in _repeated_functions(solutions, library):
            try:
                f_type = infer(f, library=library)
            except (TypeInferenceError, RecursionError):
                continue
            arguments, result = function_parts(f_type)
            if len(arguments) != 1 or not _unifies(arguments[0], result):
                continue
            a = arguments[0]
            step = Lam(a, Lam(INT, App(f, Var(1))))
            loop = Lam(INT, Lam(a, App(App(App(Term("prim", "fold"), step), Var(0)),
                                       App(Term("prim", "range"), Var(1)))))
            proposals["iterate"].append((loop, None, sources))

        for term, argument, result, sources in unary:
            if not _unifies(argument, result):
                continue
            twice = Lam(argument, App(term, App(term, Var(0))))
            thrice = Lam(argument, App(term, App(term, App(term, Var(0)))))
            proposals["power"].extend([(twice, None, sources), (thrice, None, sources)])
        for f, f_argument, _, f_sources in unary:
            for g, g_argument, g_result, g_sources in unary:
                if f is g or not _unifies(f_argument, g_result):
                    continue
                composed = Lam(g_argument, App(f, App(g, Var(0))))
                proposals["compose"].append(
                    (composed, None, tuple(sorted(set(f_sources) | set(g_sources)))))
        for f, sources in int_functions:
            for value in sorted(constants):
                proposals["constant"].append((App(f, Term("int", value)), None, sources))
        # Arithmetic the system has itself used: an int -> int -> int primitive
        # that heads an application in a verified program, applied to two
        # constants it can already name (the frozen ones and its own).
        named = [Term("int", v) for v in BASE_CONSTANTS] + [
            Term("ref", name) for name in sorted(library)
            if _is_int_constant(name, library)]
        for op, sources in _used_binary_int_ops(solutions):
            for left in named:
                for right in named:
                    proposals["constant"].append(
                        (App(App(Term("prim", op), left), right), None, sources))

        chosen, seen_bodies, seen_behaviour = [], set(existing), set(known)
        seen_values = set(constants)
        for kind in KINDS:
            ranked = []
            for term, type_, sources in proposals[kind]:
                term = canonical_types(normalize(term))
                if is_eta_atom(term):
                    continue
                try:
                    type_ = infer(term, library=library)
                except (TypeInferenceError, RecursionError):
                    continue
                order = term.size
                if kind == "constant":
                    # Smallest magnitude first, as the frozen constants are.
                    value = self._run(term, (), library)
                    order = (abs(value), value < 0, term.size) if type(value) is int else None
                    if order is None:
                        continue
                ranked.append((order, pretty(term), term, type_, sources))
            # Most general first: smaller concepts are reused in more programs.
            ranked.sort(key=lambda item: item[:2])
            taken = 0
            for order, key, term, type_, sources in ranked:
                if taken >= self.caps.get(kind, 0):
                    break
                if key in seen_bodies or term.size < 2:
                    continue
                value = None
                if kind == "constant":
                    value = self._run(term, (), library)
                    if type(value) is not int or value in seen_values:
                        continue
                    seen_values.add(value)
                else:
                    behaviour = self.behaviour(term, type_, library)
                    if behaviour is not None:
                        if behaviour in seen_behaviour:
                            continue
                        seen_behaviour.add(behaviour)
                seen_bodies.add(key)
                chosen.append(Concept(concept_name(term), term, kind, str(type_),
                                      term.size - 1, tuple(sorted(sources)), value))
                taken += 1
        return chosen


def references(term: Term) -> set[str]:
    found = set()
    if term.tag == "ref":
        found.add(term.value)
    for child in term.children:
        found |= references(child)
    return found
