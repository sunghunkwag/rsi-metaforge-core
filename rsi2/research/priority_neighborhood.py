"""Probability-ordered coordinate edits of existing typed derivations.

The optional ordering uses the supplied Grammar's current probabilities and
replays its typed derivation to recover parent/argument contexts. It adds no
productions or task information. Disabled ordering delegates to the original
iterator; equal probabilities preserve its exact order and provenance. Extra
context traversal, grammar queries and sort comparisons debit the same meter.
Thus equal-weight streams have equal prefixes when both reach them, but an
enabled run may exhaust a compiler cap earlier.
"""
from __future__ import annotations

from collections import deque
from functools import cmp_to_key
from itertools import permutations

from ..grammar import Grammar, ROOT_CONTEXT, _spine
from ..terms import Term
from ..types import Type, TypeInferenceError
from .derivation_neighborhood import (
    DerivationNeighbor, NeighborhoodMeter, _eta_view, derivation_neighbors,
)
from .repair_search import typed_locations


def _contextual_choices(type_, env, grammar, meter, *, context=ROOT_CONTEXT,
                        substitutions=None):
    """The legacy grammar-query debit, with the full derivation context."""
    meter.typewalk(type_)
    for binding in env:
        meter.typewalk(binding)
    for binding in (substitutions or {}).values():
        meter.typewalk(binding)
    meter.compiler()
    meter.grammar_queries += 1
    choices = grammar.productions(type_, env, substitutions, context)
    meter.production_choices_created += len(choices)
    meter.check()
    return choices


def _priority_choices(type_, env, grammar, meter, *, context=ROOT_CONTEXT):
    """Stable descending probabilities; debit every actual sort comparison."""
    choices = _contextual_choices(type_, env, grammar, meter, context=context)

    def compare(first, second):
        meter.compiler()
        return ((first.log_probability < second.log_probability) -
                (first.log_probability > second.log_probability))

    ordered = tuple(sorted(choices, key=cmp_to_key(compare)))
    meter.check()
    return ordered


def _production_contexts(parent, request_type, grammar, meter):
    """Map maximal-spine AST paths through a typed grammar derivation.

    Polymorphic constraints flow left-to-right between sibling arguments,
    exactly as in Grammar._derivation. Non-grammar subtrees (for example a
    beta-redex supplied by a caller) retain the root-context fallback; they
    cannot claim a recovered descendant production context.
    """
    contexts = {}

    def visit(node, target, env, substitutions, context, path):
        meter.compiler()
        contexts[path] = context
        head, head_path, children = node, path, []
        while head.tag == "app":
            meter.compiler()
            children.append((head.children[1], head_path + (1,)))
            head, head_path = head.children[0], head_path + (0,)
        children.reverse()
        if head.tag == "lam":
            if children:
                return substitutions
            name, arity = "lambda", 1
        elif head.tag in ("prim", "ref"):
            name, arity = str(head.value), len(children)
        elif head.tag == "var":
            name, arity = f"var:{head.value}", len(children)
        elif head.tag in ("int", "bool"):
            value = str(head.value).lower() if head.tag == "bool" else head.value
            name, arity = f"{head.tag}:{value}", len(children)
        else:
            return substitutions
        available = _contextual_choices(
            target, env, grammar, meter, context=context,
            substitutions=substitutions)
        selected = None
        for choice in available:
            meter.compiler()
            if (choice.name == name and choice.arity == arity and
                    (choice.is_lambda or choice.head == head)):
                selected = choice
                break
        if selected is None:
            return substitutions
        updated = selected.substitutions
        if selected.is_lambda:
            return visit(head.children[0], selected.arguments[0],
                         (selected.parameter,) + tuple(env), updated,
                         (name, 0), head_path + (0,))
        for index, ((child, child_path), child_type) in enumerate(
                zip(children, selected.arguments)):
            updated = visit(child, child_type, env, updated,
                            (name, index), child_path)
        return updated

    visit(parent, request_type, (), {}, ROOT_CONTEXT, ())
    return contexts


def priority_derivation_neighbors(parent, request_type, grammar, *, max_size=12,
                                  meter=None, eta_exposure=True,
                                  production_priority=False):
    """Round-robin operator/location agendas, yielding only typed full roots.

    A caller shares one meter across parents and separately charges every
    emitted root it actually evaluates. Failed/duplicate/oversized structural
    states remain charged. The grammar, source program and task type are the
    only inputs; no examples, task names or target outputs enter this module.
    """
    if type(production_priority) is not bool:
        raise TypeError("production_priority must be a bool")
    if not production_priority:
        yield from derivation_neighbors(
            parent, request_type, grammar, max_size=max_size, meter=meter,
            eta_exposure=eta_exposure)
        return
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
    contexts = _production_contexts(parent, request_type, grammar, meter)
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

    def choices(location, parameters, goal, env):
        # Eta expansion introduces lambda productions above the exposed body.
        context = ("lambda", 0) if parameters else contexts.get(
            location.path, ROOT_CONTEXT)
        return _priority_choices(goal, env, grammar, meter, context=context)

    def head_changes(location, body, parameters, goal, env):
        old_head, arguments = _spine(body)
        if old_head.tag == "lam":
            return
        for choice in choices(location, parameters, goal, env):
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
        for choice in choices(location, parameters, goal, env):
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

