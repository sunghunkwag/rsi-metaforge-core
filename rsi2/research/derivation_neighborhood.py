"""Generic, metered neighborhoods of typed grammar derivations.

Unlike arbitrary subtree re-enumeration, these operators retain a program's
already generated argument trees. Heads and unary contexts come exclusively
from the supplied frozen Grammar. Permutations use no primitive-specific law.
Eta views expose missing bound arguments without separately evaluating the
equivalent intermediate. This module neither evaluates nor loads tasks.

Structural units are examined grammar choices/permutations/removals and eta
views. Compiler units are actual reconstruction/shift/prewalk AST and type
visits, plus invocation charges for inference, unification and grammar queries.
These are explicit algorithmic units, not a claim to count Python instructions;
physical compiler/query/serialization CPU also belongs to the caller's guard.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import permutations
import time

from ..grammar import Grammar, _spine
from ..terms import App, Lam, Term, Var
from ..types import Type, TypeInferenceError, infer, unify
from .repair_search import typed_locations


class NeighborhoodLimit(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


@dataclass
class NeighborhoodMeter:
    """A shared meter may serve all parent iterators in one task search.

    Optional callbacks debit the enclosing search's counters and check its
    physical deadline. A callback must charge before the operation and return
    normally on acceptance; exceptions propagate to the enclosing controller.
    The local caps still apply, including when no callbacks are supplied.
    """
    structural_limit: int = 20000
    compiler_limit: int = 20000
    max_cpu_seconds: float | None = None
    structural_callback: object = None
    compiler_callback: object = None
    check_callback: object = None
    structural_states: int = 0
    compiler_steps: int = 0
    grammar_queries: int = 0
    production_choices_created: int = 0
    type_checks: int = 0
    generated: int = 0
    duplicates: int = 0
    oversized: int = 0
    ill_typed: int = 0
    eta_views: int = 0
    _cpu_started: float = field(default_factory=time.process_time, repr=False)

    def __post_init__(self):
        for value in (self.structural_limit, self.compiler_limit):
            if type(value) is not int or value < 0:
                raise ValueError("neighborhood caps must be nonnegative integers")
        if (self.max_cpu_seconds is not None and
                (type(self.max_cpu_seconds) not in (int, float) or
                 not 0 <= self.max_cpu_seconds < float("inf"))):
            raise ValueError("CPU limit must be finite and nonnegative")

    def check(self):
        if self.check_callback is not None:
            self.check_callback()
        if (self.max_cpu_seconds is not None and
                time.process_time() - self._cpu_started >= self.max_cpu_seconds):
            raise NeighborhoodLimit("cpu_budget")

    def structural(self):
        self.check()
        if self.structural_states >= self.structural_limit:
            raise NeighborhoodLimit("expansion_budget")
        if self.structural_callback is not None:
            self.structural_callback()
        self.structural_states += 1

    def compiler(self):
        self.check()
        if self.compiler_steps >= self.compiler_limit:
            raise NeighborhoodLimit("normalization_budget")
        if self.compiler_callback is not None:
            self.compiler_callback()
        self.compiler_steps += 1

    def prewalk(self, term):
        pending = [term]
        while pending:
            node = pending.pop()
            self.compiler()
            pending.extend(node.children)
            if node.tag in ("lam", "hole"):
                self.typewalk(node.value)

    def typewalk(self, type_):
        pending = [type_]
        while pending:
            current = pending.pop()
            self.compiler()
            if not current.is_variable:
                pending.extend(current.args)

    def shift(self, term, amount, cutoff=0):
        self.compiler()
        if term.tag == "var":
            return Var(term.value + amount) if term.value >= cutoff else term
        if not term.children:
            return term
        return Term(term.tag, term.value, tuple(
            self.shift(child, amount, cutoff + (term.tag == "lam"))
            for child in term.children))

    def apply(self, head, arguments):
        for argument in arguments:
            self.compiler()
            head = App(head, argument)
        return head

    def wrap(self, term, parameters):
        for parameter in reversed(parameters):
            self.compiler()
            term = Lam(parameter, term)
        return term

    def replace(self, term, path, replacement):
        self.compiler()
        if not path:
            return replacement
        index, *remaining = path
        children = list(term.children)
        children[index] = self.replace(children[index], tuple(remaining), replacement)
        return Term(term.tag, term.value, tuple(children))

    def check_type(self, term, request_type, grammar):
        self.prewalk(term)
        self.typewalk(request_type)
        self.compiler()  # One inference/unification invocation.
        self.type_checks += 1
        unify(infer(term, library=grammar.library), request_type)
        self.check()

    def choices(self, type_, env, grammar):
        self.typewalk(type_)
        for binding in env:
            self.typewalk(binding)
        self.compiler()  # One typed Grammar.productions invocation.
        self.grammar_queries += 1
        choices = grammar.productions(type_, env)
        self.production_choices_created += len(choices)
        self.check()
        return choices


@dataclass(frozen=True)
class DerivationNeighbor:
    term: Term
    path: tuple
    replacement: Term
    metadata: dict


def _eta_view(node, type_, count, meter):
    """Expose count arguments, retaining all original free-variable origins."""
    parameters, result = [], type_
    for _ in range(count):
        if result.tag != "arrow":
            raise ValueError("eta exposure exceeds the source's arrow arity")
        meter.typewalk(result.args[0])
        parameters.append(result.args[0])
        result = result.args[1]
    shifted = meter.shift(node, count)
    variables = []
    for index in reversed(range(count)):
        meter.compiler()
        variables.append(Var(index))
    return meter.apply(shifted, variables), tuple(parameters), result


def derivation_neighbors(parent, request_type, grammar, *, max_size=12,
                         meter=None, eta_exposure=True):
    """Round-robin operator/location agendas, yielding only typed full roots.

    A caller shares one meter across parents and separately charges every
    emitted root it actually evaluates. Failed/duplicate/oversized structural
    states remain charged. The grammar, source program and task type are the
    only inputs; no examples, task names or target outputs enter this module.
    """
    if not isinstance(parent, Term) or not isinstance(grammar, Grammar):
        raise TypeError("derivation neighborhoods require a Term and Grammar")
    if not isinstance(request_type, Type):
        raise TypeError("request_type must be a Type")
    if type(max_size) is not int or not 1 <= max_size <= 12:
        raise ValueError("max_size must be an integer in 1..12")
    if type(eta_exposure) is not bool:
        raise TypeError("eta_exposure must be a bool")
    meter = NeighborhoodMeter() if meter is None else meter
    if not isinstance(meter, NeighborhoodMeter):
        raise TypeError("meter must be a NeighborhoodMeter")
    meter.check_type(parent, request_type, grammar)
    meter.prewalk(parent)
    meter.compiler()
    locations = typed_locations(parent, request_type, grammar.library)
    meter.check()
    by_path = {location.path: location for location in locations}
    seen = {parent}

    def emit(location, body, parameters, operation, *, head=None, mapping=None):
        replacement = meter.wrap(body, parameters)
        candidate = meter.replace(parent, location.path, replacement)
        meter.generated += 1
        if candidate.size > max_size:
            meter.oversized += 1
            return None
        if candidate in seen:
            meter.duplicates += 1
            return None
        try:
            meter.check_type(candidate, request_type, grammar)
        except (TypeInferenceError, ValueError):
            meter.ill_typed += 1
            return None
        seen.add(candidate)
        metadata = {
            "schema_version": 1, "operator": operation,
            "path": list(location.path), "source": location.term.to_dict(),
            "eta_parameters": [parameter.to_dict() for parameter in parameters],
            "production_head": None if head is None else head.to_dict(),
            "argument_mapping": None if mapping is None else list(mapping),
            "replacement": replacement.to_dict(), "candidate": candidate.to_dict(),
        }
        meter.check()
        return DerivationNeighbor(candidate, location.path, replacement, metadata)

    def head_changes(location, body, parameters, goal, env):
        old_head, arguments = _spine(body)
        if old_head.tag == "lam":
            return
        for choice in meter.choices(goal, env, grammar):
            meter.structural()
            neighbor = None
            if choice.is_lambda or choice.arity != len(arguments) or choice.head == old_head:
                yield None
            else:
                changed = meter.apply(choice.head, arguments)
                neighbor = emit(location, changed, parameters, "head", head=choice.head)
                yield neighbor

    def argument_changes(location, body, parameters, goal, env):
        head, arguments = _spine(body)
        if len(arguments) < 2:
            return
        original = tuple(range(len(arguments)))
        for mapping in permutations(original):
            meter.structural()
            if mapping == original:
                yield None
            else:
                changed = meter.apply(head, tuple(arguments[i] for i in mapping))
                yield emit(location, changed, parameters, "permutation", mapping=mapping)

    def unary_insertions(location, body, parameters, goal, env):
        for choice in meter.choices(goal, env, grammar):
            meter.structural()
            if choice.is_lambda or choice.arity != 1:
                yield None
            else:
                changed = meter.apply(choice.head, (body,))
                yield emit(location, changed, parameters, "unary_insert", head=choice.head)

    def unary_removals(location, body, parameters, goal, env):
        _, arguments = _spine(body)
        if len(arguments) == 1:
            meter.structural()
            yield emit(location, arguments[0], parameters, "unary_remove")

    operator_factories = (head_changes, argument_changes, unary_insertions, unary_removals)
    agenda = deque()
    for location in locations:
        # The function child belongs to its enclosing maximal application spine.
        if (location.path and location.path[-1] == 0 and
                by_path[location.path[:-1]].term.tag == "app"):
            continue
        direct = (location, location.term, (), location.type, location.env)
        agenda.extend(operator(*direct) for operator in operator_factories)
        if eta_exposure and location.term.tag != "lam":
            residual, count = location.type, 0
            while residual.tag == "arrow" and count < max_size:
                meter.structural()
                count += 1
                body, parameters, goal = _eta_view(location.term, location.type, count, meter)
                meter.eta_views += 1
                env = tuple(reversed(parameters)) + location.env
                view = (location, body, parameters, goal, env)
                agenda.extend(operator(*view) for operator in operator_factories)
                residual = residual.args[1]
    while agenda:
        meter.check()
        iterator = agenda.popleft()
        try:
            neighbor = next(iterator)
        except StopIteration:
            continue
        agenda.append(iterator)
        if neighbor is not None:
            yield neighbor


def reconstruct_neighbor(parent, request_type, grammar, metadata, *, meter=None):
    """Reconstruct an edge from its source, production and argument mapping.

    This checks recorded syntax and final typing; it is not public/hidden
    verification. The recorded final candidate is compared, never trusted as
    the construction source. Provenance must originate with the generator.
    """
    meter = NeighborhoodMeter() if meter is None else meter
    path = tuple(metadata["path"])
    meter.prewalk(parent)
    meter.compiler()
    locations = {location.path: location for location in
                 typed_locations(parent, request_type, grammar.library)}
    if path not in locations:
        raise ValueError("unknown source path")
    location = locations[path]
    if location.term.to_dict() != metadata["source"]:
        raise ValueError("recorded source differs from its parent")
    parameters = tuple(Type.from_dict(value) for value in metadata["eta_parameters"])
    if parameters:
        body, expected, goal = _eta_view(location.term, location.type, len(parameters), meter)
        if parameters != expected:
            raise ValueError("recorded eta parameters differ from source type")
    else:
        body = location.term
        goal = location.type
    old_head, arguments = _spine(body)
    operation = metadata["operator"]
    if operation in ("head", "unary_insert"):
        head = Term.from_dict(metadata["production_head"])
        arity = len(arguments) if operation == "head" else 1
        env = tuple(reversed(parameters)) + location.env
        available = meter.choices(goal, env, grammar)
        if not any(not choice.is_lambda and choice.head == head and choice.arity == arity
                   for choice in available):
            raise ValueError("recorded head/arity is unavailable in supplied grammar")
        body = meter.apply(head, arguments if operation == "head" else (body,))
    elif operation == "permutation":
        mapping = metadata["argument_mapping"]
        if (any(type(i) is not int for i in mapping) or
                sorted(mapping) != list(range(len(arguments)))):
            raise ValueError("argument mapping is not a permutation")
        body = meter.apply(old_head, tuple(arguments[i] for i in mapping))
    elif operation == "unary_remove":
        if len(arguments) != 1:
            raise ValueError("source is not a unary spine")
        body = arguments[0]
    else:
        raise ValueError("unknown derivation operator")
    replacement = meter.wrap(body, parameters)
    candidate = meter.replace(parent, path, replacement)
    if (replacement.to_dict() != metadata["replacement"] or
            candidate.to_dict() != metadata["candidate"]):
        raise ValueError("recorded result differs from reconstructed edge")
    meter.check_type(candidate, request_type, grammar)
    return candidate
