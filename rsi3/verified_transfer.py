"""Typed, memory-driven program transfer using only frozen RSI-2 productions.

Generate local discrete perturbations of *verified TRAIN programs*, not
handwritten task templates. All candidate evaluations still use the frozen
public-example search and external hidden verifier. This targets the actual
symbolic-search bottleneck: high-probability donor programs can be reused and
mutated before the generic grammar enumeration reaches equivalent terms.

The algorithm cannot inspect task names, hidden examples, VALIDATION or TEST.
No primitives, library entries, or raw integer constants are invented. New
integer expressions are assembled solely from the grammar's existing finite
constants and frozen primitive operators, with the same AST size ceiling.
"""
from __future__ import annotations

from rsi2.terms import Term, Prim, apply, replace_subterm, subterms
from rsi2.types import TypeInferenceError, infer, instantiate, unify


def integer_replacements(grammar, *, max_size=7):
    """Enumerate small, typed integer terms from existing grammar productions.

    Include literals and simple compositions; deduplicate by output integer,
    keeping a small AST. This is generation of legal expressions, not injection
    of out-of-grammar integer constants.
    """
    constants = sorted((x for x in grammar.constants if x.tag == "int"),
                       key=lambda x: (x.size, x.value))
    options = {x.value: x for x in constants}
    for op in ("add", "sub", "mul"):
        if op not in grammar.primitives:
            continue
        for left in constants:
            for right in constants:
                try:
                    value = {"add": lambda a, b: a + b,
                             "sub": lambda a, b: a - b,
                             "mul": lambda a, b: a * b}[op](left.value, right.value)
                except (ArithmeticError, OverflowError):
                    continue
                candidate = apply(Prim(op), left, right)
                if candidate.size <= max_size and (
                    value not in options or (candidate.size, str(candidate)) <
                    (options[value].size, str(options[value]))):
                    options[value] = candidate
    # Compose one additional legal operation with a literal: values outside
    # the original finite constant set can still be expressed without changing
    # the DSL. Keep the smallest expression for each integer, bounded by size.
    first = tuple(options.values())
    for expr in first:
        for constant in constants:
            for op in ("add", "sub", "mul"):
                if op not in grammar.primitives:
                    continue
                candidate = apply(Prim(op), expr, constant)
                if candidate.size > max_size:
                    continue
                if op == "add":
                    value = (next((v for v, t in options.items() if t == expr), None))
                    if value is None:
                        continue
                    value += constant.value
                elif op == "sub":
                    value = next((v for v, t in options.items() if t == expr), None)
                    if value is None:
                        continue
                    value -= constant.value
                else:
                    value = next((v for v, t in options.items() if t == expr), None)
                    if value is None:
                        continue
                    value *= constant.value
                if value not in options or (candidate.size, str(candidate)) < (
                        options[value].size, str(options[value])):
                    options[value] = candidate
    return tuple(x for _, x in sorted(options.items(),
                                     key=lambda item: (item[1].size, abs(item[0]),
                                                       item[0], str(item[1]))))


def verified_program_mutations(task, donor_programs, grammar, *, max_size=12,
                               max_proposals=64):
    """Return at most max_proposals well-typed, legal donor variants.

    Candidate order prefers small programs and nearby donors as ordered by
    the caller's public-feature similarity. The caller budgets *all* execution
    attempts as logical candidate evaluations.
    """
    replacements = integer_replacements(grammar, max_size=7)
    seen, result = set(), []
    for donor in donor_programs:
        sites = [(path, child) for path, child in subterms(donor)
                 if child.tag in ("int", "bool")]
        proposals = [donor]
        for path, child in sites:
            if child.tag == "int":
                possibilities = (other for other in replacements if other != child)
            else:
                possibilities = (other for other in grammar.constants
                                 if other.tag == "bool" and other != child)
            for replacement in possibilities:
                term = replace_subterm(donor, path, replacement)
                if term.size <= max_size:
                    proposals.append(term)
        for term in sorted(set(proposals), key=lambda t: (t.size, str(t))):
            if term in seen or term.size > max_size:
                continue
            seen.add(term)
            try:
                unify(instantiate(infer(term, library=grammar.library), "_transfer_"),
                      instantiate(task.request_type, "_request_"))
                # Only accept candidates expressible in frozen grammar.
                grammar.log_probability(term, task.request_type)
            except (TypeInferenceError, ValueError, KeyError):
                continue
            result.append(term)
            if len(result) >= max_proposals:
                return tuple(result)
    return tuple(result)
