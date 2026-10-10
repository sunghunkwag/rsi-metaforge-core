"""Prospective generic application contexts around own typed subexpressions.

No task examples, target outputs or primitive-specific rules enter this module.
A context retains its source at every jointly compatible grammar argument role;
the remaining holes use a metered, typed best-first grammar enumeration. Shared
constraints flow across all holes, and original de Bruijn binder origins remain.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
from itertools import count

from ..grammar import Grammar, ROOT_CONTEXT, _spine
from ..terms import Term
from ..types import Type, TypeInferenceError, infer, substitute, unify
from .derivation_neighborhood import DerivationNeighbor, NeighborhoodMeter, _eta_view
from .repair_search import typed_locations


@dataclass(frozen=True)
class _Hole:
    type: Type
    env: tuple
    context: tuple


@dataclass(frozen=True)
class _Node:
    tag: str
    value: object = None
    children: tuple = ()


def _minimum_size(tree, meter):
    meter.compiler()
    if isinstance(tree, _Hole):
        return 1
    if isinstance(tree, Term):
        return tree.size
    return 1 + sum(_minimum_size(child, meter) for child in tree.children)


def _first_hole(tree, meter, path=()):
    meter.compiler()
    if isinstance(tree, _Hole):
        return path, tree
    if isinstance(tree, Term):
        return None
    for index, child in enumerate(tree.children):
        found = _first_hole(child, meter, path + (index,))
        if found is not None:
            return found
    return None


def _replace(tree, path, replacement, meter):
    meter.compiler()
    if not path:
        return replacement
    children = list(tree.children)
    children[path[0]] = _replace(children[path[0]], path[1:], replacement, meter)
    return _Node(tree.tag, tree.value, tuple(children))


def _materialize(tree, constraints, meter):
    meter.compiler()
    if isinstance(tree, _Hole):
        raise ValueError("cannot materialize an incomplete argument context")
    if tree.tag == "lam":
        meter.typewalk(tree.value)
    if isinstance(tree, Term):
        # Apply inferred substitutions to annotations in retained source trees,
        # but never shift indices: holes remain under the original environment.
        value = substitute(tree.value, constraints) if tree.tag == "lam" else tree.value
    else:
        value = substitute(tree.value, constraints) if tree.tag == "lam" else tree.value
    return Term(tree.tag, value, tuple(_materialize(c, constraints, meter)
                                      for c in tree.children))


def _expand(choice, hole, meter):
    meter.compiler()
    if choice.is_lambda:
        return _Node("lam", choice.parameter, (_Hole(
            choice.arguments[0], (choice.parameter,) + hole.env, (choice.name, 0)),))
    tree = choice.head
    for index, argument in enumerate(choice.arguments):
        meter.compiler()
        tree = _Node("app", None, (tree, _Hole(argument, hole.env, (choice.name, index))))
    return tree


def _choices(goal, env, grammar, constraints, context, meter, priority):
    meter.typewalk(goal)
    for binding in env:
        meter.typewalk(binding)
    for binding in constraints.values():
        meter.typewalk(binding)
    meter.compiler()
    meter.grammar_queries += 1
    choices = grammar.productions(goal, env, constraints, context)
    meter.production_choices_created += len(choices)
    meter.check()
    if priority:
        # Stable sort: a cold uniform grammar preserves definition order.
        for _ in choices:
            meter.compiler()
        choices = tuple(sorted(choices, key=lambda p: -p.log_probability))
    return choices


def derivation_contexts(parent, meter):
    """Recover the parent-production/argument context of maximal AST nodes."""
    contexts = {}
    pending = [(parent, (), ROOT_CONTEXT)]
    while pending:
        node, path, context = pending.pop()
        meter.compiler()
        contexts[path] = context
        head, args = _spine(node)
        # Count traversed application spine nodes explicitly.
        for _ in args:
            meter.compiler()
        if head.tag == "lam" and not args:
            pending.append((head.children[0], path + (0,), ("lambda", 0)))
        elif head.tag != "lam":
            name = (f"var:{head.value}" if head.tag == "var" else
                    f"int:{head.value}" if head.tag == "int" else
                    f"bool:{str(head.value).lower()}" if head.tag == "bool" else str(head.value))
            for index, argument in enumerate(args):
                argpath = path + (0,) * (len(args) - index - 1) + (1,)
                pending.append((argument, argpath, (name, index)))
    return contexts


def application_context_neighbors(parent, request_type, grammar, *, max_size=12,
                                  meter=None, eta_exposure=True,
                                  production_priority=False):
    """Yield generic arity>=2 insertion edges under one caller-owned meter.

    Each agenda expansion yields control before another expansion. Therefore a
    difficult location, production or argument role cannot exhaust the whole
    structural quota before other contexts receive an opportunity.
    """
    if not isinstance(parent, Term) or not isinstance(request_type, Type) or not isinstance(grammar, Grammar):
        raise TypeError("application contexts require a typed Term and Grammar")
    if type(max_size) is not int or not 1 <= max_size <= 12:
        raise ValueError("max_size must be an integer in 1..12")
    if type(eta_exposure) is not bool or type(production_priority) is not bool:
        raise TypeError("context switches must be bools")
    meter = NeighborhoodMeter() if meter is None else meter
    meter.check_type(parent, request_type, grammar)
    meter.prewalk(parent)
    meter.compiler()
    locations = typed_locations(parent, request_type, grammar.library)
    contexts = derivation_contexts(parent, meter)
    by_path = {location.path: location for location in locations}
    seen = {parent}

    def completions(location, body, parameters, goal, env, context, choice, role):
        meter.structural()
        meter.prewalk(body)
        meter.compiler()
        try:
            retained_type = infer(body, env=env, library=grammar.library)
            constraints = unify(retained_type, choice.arguments[role], choice.substitutions)
        except (TypeInferenceError, ValueError):
            meter.ill_typed += 1
            yield None
            return
        allowance = max_size - (parent.size - location.term.size) - len(parameters)
        tree = choice.head
        for index, argument in enumerate(choice.arguments):
            meter.compiler()
            child = body if index == role else _Hole(argument, env, (choice.name, index))
            tree = _Node("app", None, (tree, child))
        if _minimum_size(tree, meter) > allowance:
            meter.oversized += 1
            yield None
            return

        def emit_complete(tree, constraints):
            completed = _materialize(tree, constraints, meter)
            replacement = meter.wrap(completed, parameters)
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
            head, arguments = _spine(completed)
            metadata = {
                "schema_version": 1, "operator": "application_context",
                "path": list(location.path), "source": location.term.to_dict(),
                "eta_parameters": [parameter.to_dict() for parameter in parameters],
                "production_head": head.to_dict(), "production_name": choice.name,
                "production_arity": choice.arity, "retained_argument": role,
                "argument_mapping": ["source" if i == role else "enumerated" for i in range(choice.arity)],
                "arguments": [arg.to_dict() for arg in arguments],
                "context": list(context), "replacement": replacement.to_dict(),
                "candidate": candidate.to_dict(),
            }
            return DerivationNeighbor(candidate, location.path, replacement, metadata)

        # First enumerate the generic finite atomic-filler layer. This gives
        # existing grammar leaves and bound variables an opportunity before
        # larger filler trees consume the compiler quota. No head-specific
        # priorities, supplied constants, donor solutions or examples are used.
        atomic = deque(((tree, constraints),))
        while atomic:
            meter.structural()
            partial, current = atomic.popleft()
            pending = _first_hole(partial, meter)
            if pending is None:
                yield emit_complete(partial, current)
                continue
            path, hole = pending
            for filler in _choices(hole.type, hole.env, grammar, current,
                                   hole.context, meter, production_priority):
                meter.structural()
                if filler.is_lambda or filler.arity:
                    yield None
                    continue
                changed = _replace(partial, path, filler.head, meter)
                if _first_hole(changed, meter) is None:
                    yield emit_complete(changed, filler.substitutions)
                else:
                    atomic.append((changed, filler.substitutions))
                    yield None

        # Then enumerate arbitrary jointly constrained filler derivations with
        # the grammar's unchanged probabilities. Atomic duplicates remain
        # charged and are rejected by the shared full-root novelty check.
        serial = count()
        frontier = []

        def push(tree, constraints, log_probability):
            if _minimum_size(tree, meter) <= allowance:
                heapq.heappush(frontier, (-log_probability, next(serial), tree, constraints))
            else:
                meter.oversized += 1

        push(tree, constraints, 0.0)
        yield None
        while frontier:
            meter.structural()
            negative, _, partial, current = heapq.heappop(frontier)
            pending = _first_hole(partial, meter)
            if pending is not None:
                path, hole = pending
                for filler in _choices(hole.type, hole.env, grammar, current,
                                       hole.context, meter, production_priority):
                    meter.structural()
                    changed = _replace(partial, path, _expand(filler, hole, meter), meter)
                    push(changed, filler.substitutions, -negative + filler.log_probability)
                    yield None
            else:
                yield emit_complete(partial, current)

    # Global round-robin gives every source view progress. Individual heads are
    # also separate agendas, avoiding starvation by a head's infinite fillers.
    agenda = deque()
    for location in locations:
        if (location.path and location.path[-1] == 0 and
                by_path[location.path[:-1]].term.tag == "app"):
            continue
        views = [(location.term, (), location.type, location.env,
                  contexts.get(location.path, ROOT_CONTEXT))]
        if eta_exposure and location.term.tag != "lam":
            residual, number = location.type, 0
            while residual.tag == "arrow" and number < max_size:
                meter.structural()
                number += 1
                body, parameters, goal = _eta_view(location.term, location.type, number, meter)
                meter.eta_views += 1
                views.append((body, parameters, goal, tuple(reversed(parameters)) + location.env,
                              ("lambda", 0)))
                residual = residual.args[1]
        for body, parameters, goal, env, context in views:
            for choice in _choices(goal, env, grammar, {}, context, meter, production_priority):
                meter.structural()
                if choice.is_lambda or choice.arity < 2:
                    continue
                for role in range(choice.arity):
                    agenda.append(completions(location, body, parameters, goal, env, context, choice, role))
    while agenda:
        iterator = agenda.popleft()
        try:
            result = next(iterator)
        except StopIteration:
            continue
        agenda.append(iterator)
        if result is not None:
            yield result


def arity_neighbors(parent, request_type, grammar, *, max_size=12, meter=None,
                    eta_exposure=True, arity_context=False, production_priority=False):
    """Independently switch learned production order and the structural kernel."""
    from .priority_neighborhood import priority_derivation_neighbors
    if type(arity_context) is not bool or type(production_priority) is not bool:
        raise TypeError("arity_context and production_priority must be bools")
    meter = NeighborhoodMeter() if meter is None else meter
    baseline = priority_derivation_neighbors(parent, request_type, grammar,
        max_size=max_size, meter=meter, eta_exposure=eta_exposure,
        production_priority=production_priority)
    if not arity_context:
        yield from baseline
        return
    agenda = deque((iter(baseline), iter(application_context_neighbors(
        parent, request_type, grammar, max_size=max_size, meter=meter,
        eta_exposure=eta_exposure, production_priority=production_priority))))
    seen = set()
    while agenda:
        iterator = agenda.popleft()
        try:
            result = next(iterator)
        except StopIteration:
            continue
        agenda.append(iterator)
        if result.term in seen:
            meter.duplicates += 1
            continue
        seen.add(result.term)
        yield result


def reconstruct_application_context(parent, request_type, grammar, metadata, *, meter=None):
    """Replay source retention and independent joint whole-root type checks."""
    if metadata.get("operator") != "application_context":
        raise ValueError("not an application-context edge")
    meter = NeighborhoodMeter() if meter is None else meter
    meter.prewalk(parent)
    meter.compiler()
    locations = {loc.path: loc for loc in typed_locations(parent, request_type, grammar.library)}
    path = tuple(metadata["path"])
    location = locations[path]
    if location.term.to_dict() != metadata["source"]:
        raise ValueError("context source differs from parent")
    parameters = tuple(Type.from_dict(v) for v in metadata["eta_parameters"])
    if parameters:
        body, expected, goal = _eta_view(location.term, location.type, len(parameters), meter)
        if expected != parameters:
            raise ValueError("context eta parameters differ from source")
    else:
        body, goal = location.term, location.type
    env = tuple(reversed(parameters)) + location.env
    head = Term.from_dict(metadata["production_head"])
    arguments = tuple(Term.from_dict(arg) for arg in metadata["arguments"])
    role = metadata["retained_argument"]
    if type(role) is not int or not 0 <= role < len(arguments) or len(arguments) < 2:
        raise ValueError("invalid retained argument role")
    choices = meter.choices(goal, env, grammar)
    choice = next((c for c in choices if not c.is_lambda and c.head == head and
                   c.arity == len(arguments) and c.name == metadata["production_name"]), None)
    if choice is None or metadata["production_arity"] != len(arguments):
        raise ValueError("unavailable context production")
    constraints = dict(choice.substitutions)
    for argument, expected in zip(arguments, choice.arguments):
        meter.prewalk(argument)
        meter.compiler()
        constraints = unify(infer(argument, env=env, library=grammar.library), expected, constraints)
    # Independently replay every filler against the supplied frozen grammar.
    # Typechecking alone would accept a forged out-of-inventory literal.
    resolved_env = tuple(substitute(binding, constraints) for binding in env)
    for argument, expected in zip(arguments, choice.arguments):
        meter.prewalk(argument)
        meter.typewalk(expected)
        for binding in resolved_env:
            meter.typewalk(binding)
        meter.compiler()
        grammar.log_probability(argument, substitute(expected, constraints), env=resolved_env)
        meter.check()
    # Inference can specialize lambda annotations, but cannot alter syntax or
    # binder origins. Compare source after those exact joint substitutions.
    if _materialize(body, constraints, meter) != _materialize(arguments[role], constraints, meter):
        raise ValueError("context did not retain its source argument")
    context = derivation_contexts(parent, meter).get(path, ROOT_CONTEXT) if not parameters else ("lambda", 0)
    if list(context) != metadata["context"]:
        raise ValueError("context parent/argument provenance differs")
    expected_mapping = ["source" if i == role else "enumerated" for i in range(len(arguments))]
    if metadata["argument_mapping"] != expected_mapping:
        raise ValueError("context argument provenance differs")
    replacement = meter.wrap(meter.apply(head, arguments), parameters)
    candidate = meter.replace(parent, path, replacement)
    if replacement.to_dict() != metadata["replacement"] or candidate.to_dict() != metadata["candidate"]:
        raise ValueError("context reconstruction differs from saved AST")
    meter.check_type(candidate, request_type, grammar)
    return candidate
