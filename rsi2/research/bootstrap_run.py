"""TRAIN-only diagnostic entry point; never opens an evaluation partition."""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
from dataclasses import is_dataclass
import json
from pathlib import Path
import time

from ..abstraction import learn_abstractions
from ..corpus import load_train
from ..evaluator import evaluate
from ..grammar import Grammar
from .. import search as frozen_search
from ..terms import Term
from .adaptive_sampling import SamplingResult, solve_sampling


def enumeration_probe(examples, request_type, budget, grammar, max_cpu_seconds=10, **limits):
    """Instrument the unchanged frozen zero-scorer traversal in one process.

    Production requests count partial pops; a semantic-zero complete callback
    counts complete pops without reordering. Evaluator wrapping records all
    interpreter calls. The original functions are restored even after failure.
    """
    original_enum, original_eval = frozen_search.enumerate_programs, frozen_search.evaluate
    counters = {"expansions": 0, "evaluator_calls": 0, "evaluation_steps": 0}
    attempted = set()
    cpu = time.process_time()

    class CpuLimit(Exception):
        pass

    def check():
        if time.process_time() - cpu >= max_cpu_seconds:
            raise CpuLimit

    class Proxy:
        def productions(self, *args, **kwargs):
            check()
            counters["expansions"] += 1
            return grammar.productions(*args, **kwargs)

        def __getattr__(self, key):
            return getattr(grammar, key)

    def complete(state):
        check()
        if state.complete:
            counters["expansions"] += 1
        return 0.0

    def iterator(*args, **kwargs):
        kwargs.update(partial_heuristic=complete, partial_features_only=True)
        return original_enum(*args, **kwargs)

    def interpreter(*args, **kwargs):
        check()
        counters["evaluator_calls"] += 1
        attempted.add(args[0])
        evaluated = original_eval(*args, **kwargs)
        counters["evaluation_steps"] += evaluated.steps
        check()
        return evaluated

    try:
        frozen_search.enumerate_programs, frozen_search.evaluate = iterator, interpreter
        try:
            result = frozen_search.solve(examples, request_type, budget, Proxy(), **limits)
        except CpuLimit:
            result = SamplingResult(candidates=len(attempted),
                                    evaluation_steps=counters["evaluation_steps"],
                                    stop_reason="cpu_budget")
    finally:
        frozen_search.enumerate_programs, frozen_search.evaluate = original_enum, original_eval
    result.expansions = counters["expansions"]
    result.evaluator_calls = counters["evaluator_calls"]
    result.cpu_seconds = time.process_time() - cpu
    return result


def _jsonable(value):
    if isinstance(value, Term):
        return value.to_dict()
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in vars(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def atomic_write(path, record):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(_jsonable(record), indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def search(method, task, budget, grammar, seed):
    limits = {"max_size": 12, "max_expansions": 20000, "step_budget": 2000}
    if method == "enumeration":
        return enumeration_probe(task.examples, task.request_type, budget, grammar, **limits)
    if method in ("sampling", "adaptive"):
        return solve_sampling(task.examples, task.request_type, budget, grammar,
                              seed=seed, adaptive=method == "adaptive", **limits)
    if method in ("repair", "repair_normalized"):
        from .repair_search import solve_repair
        return solve_repair(task.examples, task.request_type, budget, grammar,
                            max_cpu_seconds=10, beta_normalize=method == "repair_normalized",
                            **limits)
    if method == "observational":
        from .observational_search import solve_observational
        return solve_observational(task.examples, task.request_type, budget, grammar,
                                   max_cpu_seconds=10, **limits)
    if method == "decomposition":
        from .decomposition_search import solve_decomposition
        return solve_decomposition(task.examples, task.request_type, budget, grammar,
                                   max_cpu_seconds=10, **limits)
    if method == "stratified":
        from .stratified_search import solve_stratified
        return solve_stratified(task.examples, task.request_type, budget, grammar,
                                max_cpu_seconds=10, **limits)
    if method == "stratified_decomposition":
        from .stratified_decomposition import solve_stratified_decomposition
        return solve_stratified_decomposition(task.examples, task.request_type, budget,
                                              grammar, max_cpu_seconds=10, **limits)
    raise ValueError("unregistered method")


def run(method, seed, budget, output):
    if seed not in (11, 22, 33) or budget not in (64, 640):
        raise ValueError("unregistered seed or budget")
    path = Path(output) / f"{method}_seed{seed}_B{budget}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    started, cpu = time.perf_counter(), time.process_time()
    record = {"method": method, "seed": seed, "budget": budget,
              "source": "TRAIN only", "status": "running", "tasks": []}
    grammar, solutions = Grammar(), {}
    tasks = sorted(load_train(), key=lambda task: task.name)
    for number, task in enumerate(tasks):
        if time.process_time() - cpu > 1800:
            record["status"] = "partial_cpu_cap"
            break
        result = search(method, task, budget, grammar, seed * 1000003 + number)
        verified, verification_calls, verification_steps, failure = False, 0, 0, None
        if result.term is not None:
            verified = bool(task.hidden)
            for inputs, expected in task.hidden:
                checked = evaluate(result.term, inputs, library=grammar.library,
                                   step_budget=2000)
                verification_calls += 1
                verification_steps += checked.steps
                if not checked.ok or checked.value != expected:
                    verified = False
                    failure = {"inputs": inputs, "expected": expected,
                               "actual": checked.value if checked.ok else None,
                               "error": checked.error}
                    break
        if verified:
            solutions[task.name] = result.term
        record["tasks"].append({"name": task.name, "verified": verified,
                                "search": _jsonable(result),
                                "verification_calls": verification_calls,
                                "verification_steps": verification_steps,
                                "verification_failure": failure})
        record["cpu_seconds"] = time.process_time() - cpu
        record["wall_seconds"] = time.perf_counter() - started
        atomic_write(path, record)
    else:
        record["status"] = "complete"
    rewritten, library, compression = learn_abstractions(solutions, {}, 1)
    record["solutions"] = solutions
    record["compression"] = {"records": compression, "library": library,
                              "rewritten_solutions": rewritten}
    record["verified_solved"] = len(solutions)
    record["cpu_seconds"] = time.process_time() - cpu
    record["wall_seconds"] = time.perf_counter() - started
    atomic_write(path, record)
    return {k: v for k, v in record.items()
            if k in ("method", "seed", "budget", "status", "verified_solved", "cpu_seconds")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("enumeration", "sampling", "adaptive",
                                            "repair", "repair_normalized",
                                            "observational", "decomposition", "stratified",
                                            "stratified_decomposition"),
                        required=True)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--budget", type=int, default=64)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.method, args.seed, args.budget, args.output)))


if __name__ == "__main__":
    main()
