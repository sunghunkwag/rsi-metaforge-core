"""Replayable failure history and exactly scoped development evaluation memory."""
from __future__ import annotations

import copy
import json
import time

from ..grammar import Grammar
from ..learning import State
from ..evaluator import evaluate
from ..search import solve
from ..recognition import Recognition
from ..terms import Term
from ..types import Type


def assess(tasks, grammar, heuristic, budget, searchconfig, conditioner=None):
    """Public-only search followed by a separate, counterexample-producing verifier."""
    started = time.perf_counter()
    records = []
    for task in tasks:
        conditional = conditioner(task, grammar) if conditioner is not None else grammar
        result = solve(task.examples, task.request_type, budget, conditional,
                       heuristic=heuristic, **searchconfig)
        accepted = result.term is not None and bool(task.hidden)
        failure = None
        verification_steps = verification_examples = 0
        if result.term is None:
            failure = {"stage": "search", "kind": "space_exhausted" if result.exhausted
                       else "candidate_budget", "attempted": result.candidates}
        else:
            for inputs, expected in task.hidden:
                verified = evaluate(result.term, inputs, library=conditional.library,
                                    step_budget=searchconfig["step_budget"])
                verification_steps += verified.steps
                verification_examples += 1
                if not verified.ok or verified.value != expected:
                    accepted = False
                    failure = {"stage": "verification", "inputs": inputs,
                               "expected": expected,
                               "actual": verified.value if verified.ok else None,
                               "error": verified.error}
                    break
        records.append({"name": task.name, "solved": accepted,
                        "public_matched": result.term is not None,
                        "candidates": result.candidates,
                        "candidates_to_solution": result.candidates if accepted else None,
                        "wall_seconds": result.wall_seconds,
                        "evaluation_steps": result.evaluation_steps,
                        "heuristic_calls": result.heuristic_calls,
                        "heuristic_evaluations": result.heuristic_evaluations,
                        "heuristic_steps": result.heuristic_steps,
                        "exhausted": result.exhausted,
                        "verification_examples": verification_examples,
                        "verification_steps": verification_steps, "failure": failure})
    solved = [r for r in records if r["solved"]]
    return {"tasks": len(records), "solved": len(solved),
            "solved_fraction": len(solved) / len(records) if records else 0.0,
            "mean_candidates_to_solution": sum(r["candidates"] for r in solved) / len(solved)
            if solved else None, "candidate_evaluations": sum(r["candidates"] for r in records),
            "budget": budget, "wall_seconds": time.perf_counter() - started,
            "records": records}


def snapshot(state):
    grammar = state.grammar
    return {
        "seed": state.seed, "generation": state.generation,
        "grammar": {
            "primitives": {k: v.to_dict() for k, v in grammar.primitives.items()},
            "constants": [t.to_dict() for t in grammar.constants],
            "library": {k: v.to_dict() for k, v in grammar.library.items()},
            "weights": dict(grammar.weights),
            "contexts": [[p, i, dict(w)] for (p, i), w in grammar.context_weights.items()],
        },
        "recognition": None if state.recognition is None else state.recognition.to_dict(),
        "heuristic": None if state.heuristic is None else state.heuristic.to_dict(),
        "solutions": {k: v.to_dict() for k, v in state.solutions.items()},
    }


def restore(record):
    g = record["grammar"]
    grammar = Grammar(
        library={k: Term.from_dict(v) for k, v in g["library"].items()},
        primitives={k: Type.from_dict(v) for k, v in g["primitives"].items()},
        constants=tuple(Term.from_dict(v) for v in g["constants"]),
        weights=g["weights"],
        context_weights={(p, i): w for p, i, w in g["contexts"]})
    state = State(record["seed"], grammar=grammar, generation=record["generation"],
                  heuristic=None if record["heuristic"] is None else
                  Term.from_dict(record["heuristic"]),
                  solutions={k: Term.from_dict(v) for k, v in record["solutions"].items()})
    if record["recognition"] is not None:
        state.recognition = Recognition.from_dict(record["recognition"])
    return state


def scope(state, tasks, heuristic, budget, searchconfig):
    state_record = snapshot(state)
    ordered_grammar = state_record["grammar"]
    # Tie order is executable behavior, not merely JSON presentation.
    ordered_grammar["primitives"] = list(ordered_grammar["primitives"].items())
    ordered_grammar["library"] = list(ordered_grammar["library"].items())
    # Incumbent and solution history do not affect the supplied fixed scorer.
    # Every actual search dependency does, including hidden verification data.
    return {
        "grammar": ordered_grammar,
        "recognition": state_record["recognition"],
        "heuristic": None if heuristic is None else heuristic.to_dict(),
        "tasks": [{"name": t.name, "type": t.request_type.to_dict(),
                   "examples": t.examples, "hidden": t.hidden} for t in tasks],
        "budget": budget, "search": dict(searchconfig),
    }


class EvaluationMemory:
    """A cache hit saves real work but cannot confer new improvement credit."""

    def __init__(self):
        self.entries = {}
        self.actual_candidate_evaluations = 0
        self.cache_hits = 0
        self.assessment_calls = 0

    def measure(self, state, tasks, heuristic, budget, searchconfig):
        tasks = list(tasks)
        key = json.dumps(scope(state, tasks, heuristic, budget, searchconfig),
                         sort_keys=True, separators=(",", ":"))
        self.assessment_calls += 1
        hit = key in self.entries
        if hit:
            self.cache_hits += 1
        else:
            report = assess(tasks, state.grammar, heuristic, budget, searchconfig,
                            conditioner=state.condition)
            self.actual_candidate_evaluations += report["candidate_evaluations"]
            self.entries[key] = copy.deepcopy(report)
        report = copy.deepcopy(self.entries[key])
        report["cache_hit"] = hit
        report["actual_candidate_evaluations"] = 0 if hit else report["candidate_evaluations"]
        return report

    def summary(self):
        return {"entries": len(self.entries), "cache_hits": self.cache_hits,
                "assessment_calls": self.assessment_calls,
                "actual_candidate_evaluations": self.actual_candidate_evaluations}
