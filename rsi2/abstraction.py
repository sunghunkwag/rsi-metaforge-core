"""Corpus-guided lambda lifting and strict description-length compression.

Proposals come exclusively from the supplied solved-program ASTs. Shared free
variables become explicit arguments; optional literal holes generalize similar
subtrees without inventing a primitive or a library body. A proposal is adopted
only when its library AST plus rewritten solutions strictly reduce total size.
"""
from __future__ import annotations

from dataclasses import dataclass

from .terms import Lam, Ref, Term, Var, apply, pretty, term_to_dict
from .types import (Type, TypeInferenceError, function_parts, infer, substitute,
                    unify)


MAX_PROPOSALS = 256
MAX_ADOPTIONS = 8


@dataclass(frozen=True)
class _Occurrence:
    solution: str
    path: tuple[int, ...]
    node: Term
    env: tuple[Type, ...]


@dataclass(frozen=True)
class _Match:
    occurrence: _Occurrence
    arguments: tuple[Term, ...]


def description_length(solutions, library) -> int:
    return sum(term.size for term in library.values()) + sum(term.size for term in solutions.values())


def _occurrences(term, solution, env=(), path=()):
    yield _Occurrence(solution, path, term, env)
    for index, child in enumerate(term.children):
        bindings = (term.value,) + env if term.tag == "lam" else env
        yield from _occurrences(child, solution, bindings, path + (index,))


def free_variables(term: Term) -> tuple[int, ...]:
    """Return outside binders, in first-occurrence order relative to this root."""
    found = {}

    def visit(node, depth):
        if node.tag == "var" and node.value >= depth:
            found.setdefault(node.value - depth, None)
        for child in node.children:
            visit(child, depth + (node.tag == "lam"))

    visit(term, 0)
    return tuple(found)


def _literal_paths(term, path=()):
    if term.tag in ("int", "bool"):
        yield path
    for index, child in enumerate(term.children):
        yield from _literal_paths(child, path + (index,))


def _at_path(term, path):
    for index in path:
        term = term.children[index]
    return term


def _canonical_type(current, names):
    if current.tag == "var":
        if current.name not in names:
            names[current.name] = Type("var", (f"_abs_{len(names)}",))
        return names[current.name]
    arguments = tuple(_canonical_type(arg, names) for arg in current.args)
    return current if arguments == current.args else Type(current.tag, arguments)


def _canonical_annotations(term):
    """Alpha-normalize annotation variables; concrete types stay unchanged."""
    names = {}

    def visit(node):
        value = _canonical_type(node.value, names) if isinstance(node.value, Type) else node.value
        children = tuple(visit(child) for child in node.children)
        return Term(node.tag, value, children)

    return visit(term)


def lift_subtree(term: Term, env=(), literal_paths=()) -> tuple[Term, tuple[Term, ...]]:
    """Close a subtree by lambda-lifting external variables and literal holes.

    Arguments remain in the occurrence's original scope. A nested lambda's
    internal indices are untouched; indices for lifted arguments include the
    nested binder depth. This makes replacing the occurrence beta-equivalent.
    """
    outside = free_variables(term)
    literal_paths = tuple(sorted(set(tuple(path) for path in literal_paths)))
    if any(index >= len(env) for index in outside):
        raise TypeInferenceError("subtree has an unbound outside variable")
    arguments = tuple(Var(index) for index in outside) + tuple(_at_path(term, p) for p in literal_paths)
    if any(node.tag not in ("int", "bool") for node in arguments[len(outside):]):
        raise TypeInferenceError("literal holes must select int or bool leaves")
    parameters = tuple(env[index] for index in outside) + tuple(infer(node) for node in arguments[len(outside):])
    positions = {index: position for position, index in enumerate(outside)}
    holes = {path: len(outside) + position for position, path in enumerate(literal_paths)}
    count = len(parameters)

    def visit(node, depth=0, path=()):
        if path in holes:
            return Var(depth + count - 1 - holes[path])
        if node.tag == "var" and node.value >= depth:
            return Var(depth + count - 1 - positions[node.value - depth])
        children = tuple(visit(child, depth + (node.tag == "lam"), path + (index,))
                         for index, child in enumerate(node.children))
        return Term(node.tag, node.value, children)

    result = visit(term)
    for parameter in reversed(parameters):
        result = Lam(parameter, result)
    return result, arguments


def _specialize_parameters(term, parameter_count, library):
    """Use the inferred concrete parameter types for grouping compatible scopes."""
    inferred = infer(term, library=library)
    actual, _ = function_parts(inferred)
    originals, body = [], term
    for _ in range(parameter_count):
        originals.append(body.value)
        body = body.children[0]
    substitutions = {}
    for original, resolved in zip(originals, actual):
        substitutions = unify(original, resolved, substitutions)

    def update(node):
        value = substitute(node.value, substitutions) if isinstance(node.value, Type) else node.value
        return Term(node.tag, value, tuple(update(child) for child in node.children))

    return _canonical_annotations(update(term))


def _groups(solutions, library):
    raw = {}
    for name in sorted(solutions):
        for occurrence in _occurrences(solutions[name], name):
            if occurrence.node.size < 4:
                continue
            literals = tuple(_literal_paths(occurrence.node))
            variants = [()] + [(path,) for path in literals]
            if len(literals) > 1:
                variants.append(literals)
            for variant in variants:
                entry, arguments = lift_subtree(occurrence.node, occurrence.env, variant)
                if entry.tag != "lam" or occurrence.node.size <= 1 + 2 * len(arguments):
                    continue
                entry = _canonical_annotations(entry)
                raw.setdefault((entry, len(arguments)), []).append(_Match(occurrence, arguments))
    groups = {}
    existing = {_canonical_annotations(term) for term in library.values()}
    for (entry, arity), matches in raw.items():
        if len(matches) < 2:
            continue
        try:
            entry = _specialize_parameters(entry, arity, library)
        except (TypeInferenceError, RecursionError):
            continue
        if entry in existing:
            continue
        groups.setdefault(entry, []).extend(matches)
    # Different literal variants can describe the same beta-equivalent match.
    for entry, matches in list(groups.items()):
        unique = {}
        for match in matches:
            unique.setdefault((match.occurrence.solution, match.occurrence.path), match)
        groups[entry] = tuple(unique.values())
    return groups


def _rewrite(term, replacements, path=()):
    if path in replacements:
        return replacements[path]
    children = tuple(_rewrite(child, replacements, path + (index,))
                     for index, child in enumerate(term.children))
    return term if children == term.children else Term(term.tag, term.value, children)


def _plan(solutions, library, entry, matches, name):
    replacements, selected = {}, []
    # Taking an outer occurrence first avoids overlapping replacements.
    for match in sorted(matches, key=lambda m: (m.occurrence.solution, len(m.occurrence.path), m.occurrence.path)):
        occurrence = match.occurrence
        paths = replacements.setdefault(occurrence.solution, {})
        if any(occurrence.path[:len(path)] == path for path in paths):
            continue
        replacement = apply(Ref(name), *match.arguments)
        if replacement.size >= occurrence.node.size:
            continue
        paths[occurrence.path] = replacement
        selected.append(match)
    rewritten = {task: _rewrite(term, replacements.get(task, {})) for task, term in solutions.items()}
    updated_library = {**library, name: entry}
    before = description_length(solutions, library)
    after = description_length(rewritten, updated_library)
    if after >= before:
        return None
    try:
        entry_type = infer(entry, library=library)
        for task, term in rewritten.items():
            unify(infer(solutions[task], library=library), infer(term, library=updated_library))
    except (TypeInferenceError, RecursionError):
        return None
    return rewritten, updated_library, {
        "name": name, "type": str(_canonical_type(entry_type, {})), "readable_term": pretty(entry),
        "term_dict": term_to_dict(entry), "cost_before": before, "cost_after": after,
        "delta": before - after, "support": len(selected),
        "source_tasks": sorted({match.occurrence.solution for match in selected}),
    }


def learn_abstractions(solutions: dict[str, Term], library: dict[str, Term], generation: int):
    """Greedily adopt at most eight data-derived entries, examining 256 proposals.

    The proposal cap counts distinct lifted bodies during one call. Previously
    examined proposals may be reconsidered after a rewrite, using their current
    support and costs. Supplied dictionaries and prior library entries remain
    unchanged. New entries therefore reference only earlier library entries.
    """
    current, entries = dict(solutions), dict(library)
    for term in current.values():
        infer(term, library=entries)
    records, examined = [], set()
    serial = 0
    for _ in range(MAX_ADOPTIONS):
        while f"learned_g{generation}_{serial}" in entries:
            serial += 1
        name = f"learned_g{generation}_{serial}"
        groups = _groups(current, entries)

        def potential(item):
            entry, matches = item
            benefit = sum(m.occurrence.node.size - (1 + 2 * len(m.arguments)) for m in matches)
            return benefit - entry.size

        ranked = sorted(groups.items(), key=lambda item: (-potential(item), pretty(item[0])))
        best = None
        for entry, matches in ranked:
            if potential((entry, matches)) <= 0:
                continue
            if entry not in examined:
                if len(examined) >= MAX_PROPOSALS:
                    continue
                examined.add(entry)
            plan = _plan(current, entries, entry, matches, name)
            if plan is not None and (best is None or plan[2]["delta"] > best[2]["delta"]):
                best = plan
        if best is None:
            break
        current, entries, record = best
        record["generation"] = generation
        records.append(record)
        serial += 1
    return current, entries, records
