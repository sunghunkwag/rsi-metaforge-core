"""TRAIN-solution-derived callable compression with independent verification.

The frozen compressor's lifting, type inference, non-overlap planning and AST
description-length accounting remain unchanged. This alternative considers
subtrees of size two or greater and admits every closed callable body, including
an application returning a function. It never constructs a task-specific body:
every proposal is lifted from an explicitly supplied solved-program AST.

Every profitable proposal is separately evaluated on ALL supplied accepted
TRAIN solutions' public and hidden examples, without early exit. A shorter AST
is compression evidence only; this module measures no new task or heuristic
search ability. It opens no corpus, TEST, validation or audit files.
"""
from __future__ import annotations

import time

from ..abstraction import (
    MAX_ADOPTIONS, MAX_PROPOSALS, _Match, _canonical_annotations, _literal_paths,
    _occurrences, _plan, _specialize_parameters, description_length,
    free_variables, learn_abstractions, lift_subtree,
)
from ..evaluator import evaluate
from ..terms import Term, Var, pretty
from ..types import TypeInferenceError, infer, unify


MIN_SUBTREE_SIZE = 2
CLAIM_SCOPE = "verified TRAIN compression; task, heuristic and RSI gains unmeasured"
_WORK_FIELDS = (
    "program_evaluations", "example_evaluations", "evaluator_steps",
    "public_example_evaluations", "hidden_example_evaluations",
    "public_evaluator_steps", "hidden_evaluator_steps",
)


def _zero_cost():
    return {**dict.fromkeys(_WORK_FIELDS, 0), "cpu_seconds": 0.0,
            "wall_seconds": 0.0}


def _add_cost(target, source):
    for field in target:
        target[field] += source[field]


def _same_value(actual, expected):
    # Python equality alone conflates True/1, including inside containers.
    if type(actual) is not type(expected):
        return False
    if type(actual) in (list, tuple):
        return len(actual) == len(expected) and all(
            _same_value(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _tasks_by_name(tasks, solutions):
    indexed = {}
    for task in tasks:
        if task.name in indexed:
            raise ValueError(f"duplicate TRAIN task: {task.name}")
        indexed[task.name] = task
    missing = sorted(set(solutions) - indexed.keys())
    if missing:
        raise ValueError(f"accepted solutions lack supplied TRAIN tasks: {missing}")
    return indexed


def verify_solutions(solutions, library, train_tasks, *, step_budget=2000):
    """Check all examples of all accepted solutions, including after failures.

    One program evaluation is one task/solution check. One example evaluation
    is one interpreter call; evaluator_steps are the interpreter's real charged
    steps. CPU includes inference and the complete independent verification.
    Missing public/hidden evidence fails closed. No hidden data drives proposal
    extraction, ranking, literal selection or parameter specialization.
    """
    if type(step_budget) is not int or step_budget < 1:
        raise ValueError("step_budget must be a positive integer")
    tasks = _tasks_by_name(train_tasks, solutions)
    started, cpu = time.perf_counter(), time.process_time()
    cost, checked = _zero_cost(), []
    for name in sorted(solutions):
        task, term = tasks[name], solutions[name]
        failures, task_steps = [], 0
        if not task.examples or not task.hidden:
            failures.append({"partition": "task", "reason": "missing_public_or_hidden"})
        try:
            unify(infer(term, library=library), task.request_type)
        except (TypeInferenceError, RecursionError) as error:
            failures.append({"partition": "type", "reason": str(error)})
        cost["program_evaluations"] += 1
        for partition, examples in (("public", task.examples), ("hidden", task.hidden)):
            for index, (inputs, expected) in enumerate(examples):
                result = evaluate(term, inputs, library=library, step_budget=step_budget)
                cost["example_evaluations"] += 1
                cost[f"{partition}_example_evaluations"] += 1
                cost["evaluator_steps"] += result.steps
                cost[f"{partition}_evaluator_steps"] += result.steps
                task_steps += result.steps
                if not result.ok or not _same_value(result.value, expected):
                    failures.append({"partition": partition, "index": index,
                                     "reason": result.error or "output_mismatch"})
        checked.append({"name": name, "passed": not failures,
                        "public_examples": len(task.examples),
                        "hidden_examples": len(task.hidden),
                        "evaluator_steps": task_steps, "failures": failures})
    cost["cpu_seconds"] = time.process_time() - cpu
    cost["wall_seconds"] = time.perf_counter() - started
    return {"passed": all(row["passed"] for row in checked),
            "step_budget": step_budget, "tasks": checked, "cost": cost}


def _callable_groups(solutions, library):
    """Generate only extracted/lifted ASTs; no output-based proposal fitting."""
    raw = {}
    for name in sorted(solutions):
        for occurrence in _occurrences(solutions[name], name):
            if occurrence.node.size < MIN_SUBTREE_SIZE:
                continue
            literals = tuple(_literal_paths(occurrence.node))
            variants = [()] + [(path,) for path in literals]
            if len(literals) > 1:
                variants.append(literals)
            for variant in variants:
                entry, arguments = lift_subtree(occurrence.node, occurrence.env, variant)
                if occurrence.node.size <= 1 + 2 * len(arguments):
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
            if free_variables(entry) or infer(entry, library=library).tag != "arrow":
                continue
        except (TypeInferenceError, RecursionError):
            continue
        if entry not in existing:
            groups.setdefault(entry, []).extend(matches)
    return {entry: tuple({(m.occurrence.solution, m.occurrence.path): m
                          for m in matches}.values())
            for entry, matches in groups.items()}


def _potential(entry, matches):
    return sum(m.occurrence.node.size - (1 + 2 * len(m.arguments))
               for m in matches) - entry.size


def _classification(entry):
    identity = entry.tag == "lam" and entry.children[0] == Var(0)
    return {"closed_callable_application": entry.tag == "app",
            "identity_macro": identity, "tiny_entry": entry.size < 4,
            "claim_scope": CLAIM_SCOPE}


def compress_verified(solutions: dict[str, Term], library: dict[str, Term],
                      generation: int, train_tasks, *, step_budget=2000,
                      max_proposals=MAX_PROPOSALS, max_adoptions=MAX_ADOPTIONS):
    """Greedy strict-MDL compression, independently checking every plan.

    Hidden TRAIN examples can only veto a proposal. Among passing proposals,
    selection uses strict AST savings and deterministic AST order. Evaluation
    step counts may increase; acceptance requires preservation within the same
    fixed step budget, and measured step changes are reported explicitly.
    Input dictionaries are unchanged. Return dictionaries contain Term objects.
    """
    if any(type(limit) is not int or limit < 0 for limit in (max_proposals, max_adoptions)):
        raise ValueError("proposal/adoption limits must be nonnegative integers")
    tasks = tuple(train_tasks)
    current, entries = dict(solutions), dict(library)
    started, cpu = time.perf_counter(), time.process_time()
    baseline = verify_solutions(current, entries, tasks, step_budget=step_budget)
    total = _zero_cost()
    _add_cost(total, baseline["cost"])
    result = {"status": "complete" if baseline["passed"] else "invalid_baseline",
              "solutions": current, "library": entries, "records": [],
              "proposals": [], "baseline_verification": baseline,
              "cost": total, "claim_scope": CLAIM_SCOPE,
              "limits": {"minimum_subtree_size": MIN_SUBTREE_SIZE,
                         "max_distinct_proposals": max_proposals,
                         "max_adoptions": max_adoptions, "step_budget": step_budget},
              "description_length_before": description_length(current, entries)}
    examined, serial = set(), 0
    current_verification = baseline
    if baseline["passed"]:
        for _ in range(max_adoptions):
            while f"verified_g{generation}_{serial}" in entries:
                serial += 1
            name = f"verified_g{generation}_{serial}"
            groups = _callable_groups(current, entries)
            ranked = sorted(groups.items(), key=lambda item: (-_potential(*item), pretty(item[0])))
            best = None
            for entry, matches in ranked:
                if _potential(entry, matches) <= 0:
                    continue
                if entry not in examined:
                    if len(examined) >= max_proposals:
                        continue
                    examined.add(entry)
                plan = _plan(current, entries, entry, matches, name)
                if plan is None:
                    continue
                rewritten, proposed_library, record = plan
                # Recompute complete cost; no claimed delta can bypass strict MDL.
                before = description_length(current, entries)
                after = description_length(rewritten, proposed_library)
                if after >= before:
                    continue
                verification = verify_solutions(rewritten, proposed_library, tasks,
                                                step_budget=step_budget)
                _add_cost(total, verification["cost"])
                proposal = {**record, "generation": generation,
                            "cost_before": before, "cost_after": after,
                            "delta": before - after, **_classification(entry),
                            "verification": verification,
                            "evaluator_steps_before": current_verification["cost"]["evaluator_steps"],
                            "evaluator_steps_after": verification["cost"]["evaluator_steps"],
                            "decision": "verified_unselected" if verification["passed"] else "rejected_verification"}
                result["proposals"].append(proposal)
                if verification["passed"] and (best is None or proposal["delta"] > best[2]["delta"]):
                    best = (rewritten, proposed_library, proposal)
            if best is None:
                break
            current, entries, selected = best
            selected["decision"] = "adopt"
            result["records"].append(selected)
            current_verification = selected["verification"]
            serial += 1
    result.update(solutions=current, library=entries,
                  description_length_after=description_length(current, entries),
                  distinct_entries_examined=len(examined),
                  final_verification=current_verification,
                  cpu_seconds=time.process_time() - cpu,
                  wall_seconds=time.perf_counter() - started)
    return result


def compare_compressors(solutions, library, generation, train_tasks, *, step_budget=2000):
    """Run frozen and alternative compressors on exactly the same raw ASTs.

    The frozen result gets independent final verification; its intermediate
    adoptions are not instrumented or changed. The alternative verifies each
    proposed plan. These differently scoped verifier costs are stated explicitly
    and cannot be interpreted as a matched compression-throughput experiment.
    """
    tasks = tuple(train_tasks)
    baseline = verify_solutions(solutions, library, tasks, step_budget=step_budget)
    original_cost = _zero_cost()
    _add_cost(original_cost, baseline["cost"])
    started, cpu = time.perf_counter(), time.process_time()
    if baseline["passed"]:
        rewritten, entries, records = learn_abstractions(solutions, library, generation)
        final = verify_solutions(rewritten, entries, tasks, step_budget=step_budget)
        _add_cost(original_cost, final["cost"])
        status = "complete" if final["passed"] else "failed_final_verification"
    else:
        rewritten, entries, records = dict(solutions), dict(library), []
        final, status = baseline, "invalid_baseline"
    original = {"status": status, "solutions": rewritten, "library": entries,
                "records": records, "baseline_verification": baseline,
                "final_verification": final, "cost": original_cost,
                "description_length_before": description_length(solutions, library),
                "description_length_after": description_length(rewritten, entries),
                "verification_scope": "baseline and final output only",
                "cpu_seconds_excluding_baseline_verification": time.process_time() - cpu,
                "wall_seconds_excluding_baseline_verification": time.perf_counter() - started}
    improved = compress_verified(solutions, library, generation, tasks, step_budget=step_budget)
    return {"original": original, "improved": improved, "claim_scope": CLAIM_SCOPE,
            "comparison_scope": "same supplied raw verified TRAIN solutions; AST MDL and preserved examples",
            "original_intermediate_adoptions_independently_verified": False}
