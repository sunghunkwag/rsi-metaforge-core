"""Bounded autonomous refinement of an evaluation procedure from development evidence.

One registered procedure hypothesis is available: reuse identical per-task work.
The coordinator diagnoses, verifies, preserves or rejects, and applies its own
accepted memory factory on the next cycle. It neither synthesizes arbitrary code
nor changes solver scores, task learning, or scientific admission policies.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

from ..corpus import load_validation
from ..heuristics import zero_heuristic
from ..terms import Term
from . import memory
from .efficient_memory import EfficientEvaluationMemory, SharedStore, _key
from .transfer import load_confirmation


SEEDS = (11, 22, 33)
WORK = ("candidate_evaluations", "evaluation_steps", "heuristic_calls",
        "heuristic_evaluations", "heuristic_steps", "verification_examples", "verification_steps")
TOP_TELEMETRY = {"wall_seconds", "actual_wall_seconds", "cache_hit"} | {
    f"actual_{name}" for name in WORK}
RECORD_TELEMETRY = TOP_TELEMETRY | {"source_budget", "requested_budget", "reuse_kind",
                                     "source_wall_seconds"}
FIELDS = ("current_performance", "failure_clusters", "bottleneck",
          "previous_attempt_insufficiency", "intervention", "mechanism",
          "verification_plan", "regression_risks", "result", "keep_revert_revise", "updated_rule")


def scientific(report):
    """Remove only explicitly registered telemetry, retaining every other field."""
    output = {key: copy.deepcopy(value) for key, value in report.items() if key not in TOP_TELEMETRY}
    output["records"] = [{key: copy.deepcopy(value) for key, value in row.items()
                          if key not in RECORD_TELEMETRY} for row in report["records"]]
    return output


def _work(report):
    hit = report.get("cache_hit") is True
    result = {}
    for name in WORK:
        actual = f"actual_{name}"
        if actual in report:
            result[name] = report[actual]
        elif hit:
            result[name] = 0
        elif name == "candidate_evaluations":
            result[name] = report[name]
        else:
            result[name] = sum(row[name] for row in report["records"])
    if any(type(value) is not int or value < 0 for value in result.values()):
        raise ValueError("actual work requires nonnegative integer counters")
    return result


def _context(state):
    full = memory.scope(state, [], None, 0, {})
    return {name: full[name] for name in ("grammar", "recognition")}


def _facts(state_ref, tasks, heuristic, budget, searchconfig):
    return {"state_ref": state_ref,
            "tasks": [{"name": task.name, "type": task.request_type.to_dict(),
                       "examples": task.examples, "hidden": task.hidden} for task in tasks],
            "heuristic": None if heuristic is None else heuristic.to_dict(),
            "budget": budget, "search": dict(searchconfig)}


def _proof(verification, name):
    proof = verification.get(name, {})
    tests, count = proof.get("tests"), proof.get("count")
    return (proof.get("status") == "passed" and type(count) is int and count > 0
            and isinstance(tests, list) and bool(tests) and count == len(tests)
            and all(isinstance(test, str) and test.startswith("rsi2.tests.") for test in tests))


class _PolicyStore(SharedStore):
    def __init__(self, certificates=False):
        super().__init__()
        self.certificates_enabled = certificates

    def _lookup(self, task_scope):
        found = super()._lookup(task_scope)
        if found is not None and found[2] == "early_termination_certificate" and not self.certificates_enabled:
            return None
        return found


class Coordinator:
    """A finite diagnosis/proposal/verification/admission/application state machine."""

    def __init__(self, history, verification):
        supplied = copy.deepcopy(history)
        self._contexts = supplied.get("contexts", {}) if isinstance(supplied, dict) else {}
        self._context_keys = {ref: _key(value) for ref, value in self._contexts.items()}
        self.history = []
        for call in supplied.get("calls", []) if isinstance(supplied, dict) else supplied:
            scoped = call.get("scope", {})
            if "grammar" in scoped and "recognition" in scoped:
                context = {name: scoped[name] for name in ("grammar", "recognition")}
                context_key = _key(context)
                ref = scoped.get("state_ref")
                if ref is None:
                    ref = next((r for r, key in self._context_keys.items() if key == context_key),
                               f"context{len(self._contexts)}")
                if ref in self._context_keys and self._context_keys[ref] != context_key:
                    raise ValueError("state_ref was reused with a different frozen context")
                self._contexts[ref], self._context_keys[ref] = context, context_key
                scoped = {**{name: scoped[name] for name in ("tasks", "heuristic", "budget", "search")},
                          "state_ref": ref}
            if scoped.get("state_ref") not in self._contexts:
                raise ValueError("call scope lacks a registered immutable state context")
            self.history.append({**call, "scope": scoped})
        self.verification = copy.deepcopy(verification)
        self.cycles = []
        self.active = False
        self.certificates = False
        self._stores = {}
        self._proposal = None
        self._last_verification = None

    @property
    def contexts(self):
        """Export copies; context references cannot be rebound by callers."""
        return copy.deepcopy(self._contexts)

    def diagnose(self):
        seen, repeats, terminations = {}, [], []
        calls = 0
        for call_index, call in enumerate(self.history):
            report = call.get("measurement", {})
            if report.get("cache_hit") is True or call.get("alias") is True:
                continue
            task_scope = call.get("scope")
            if not isinstance(task_scope, dict) or len(task_scope.get("tasks", ())) != len(report.get("records", ())):
                continue
            calls += 1
            for task_index, row in enumerate(report["records"]):
                singleton = {**task_scope, "tasks": [task_scope["tasks"][task_index]]}
                key = (call["seed"], _key(singleton))
                reference = {"seed": call["seed"], "call": call_index, "task_index": task_index,
                             "name": row["name"], "budget": task_scope["budget"],
                             "candidates": row["candidates"]}
                if key in seen:
                    repeats.append({"first": seen[key], "repeated": reference})
                else:
                    seen[key] = reference
                budget, candidates = task_scope["budget"], row["candidates"]
                if (row.get("public_matched") is False and row.get("exhausted") is True
                        and type(budget) is int and type(candidates) is int and candidates < budget):
                    terminations.append(reference)
        return {"actual_group_calls": calls, "unique_per_task_scopes": len(seen),
                "repeated_per_task_scopes": len(repeats), "repeated_evidence": repeats,
                "early_termination_patterns": len(terminations), "termination_evidence": terminations,
                "termination_limit": "Below-budget termination does not distinguish finite space from the scoped expansion cap."}

    def propose(self):
        diagnosis = self.diagnose()
        exact = diagnosis["repeated_per_task_scopes"] > 0
        certificate = (diagnosis["early_termination_patterns"] > 0
                       and _proof(self.verification, "exhaustion_certificate"))
        self._proposal = {"available": exact, "backend": "shared_per_task" if exact else "original",
                          "certificate_hypothesis": exact and certificate,
                          "diagnosis": diagnosis,
                          "action": "Share exact per-task evaluation scopes" if exact else
                                    "Retain original evaluation; no repeated-scope evidence"}
        return copy.deepcopy(self._proposal)

    def nextmemory(self, seed=None):
        """Apply only a rule preserved from complete preceding-cycle verification."""
        if not self.active:
            return memory.EvaluationMemory()
        if seed not in self._stores:
            self._stores[seed] = _PolicyStore(self.certificates)
        return EfficientEvaluationMemory(self._stores[seed])

    def verify(self, cases, progress=None, next_cycle=False):
        """Run paired fresh backends, then demand typed scientific equality per call.

        Cases are registered explicitly supplied state/task/scorer/budget/limit
        objects; no measured outcomes choose the queries. Stores are fresh for
        each seed and backend. Work components are compared individually rather
        than combining heterogeneous units into an improvement score.
        """
        proposal = self._proposal or self.propose()
        result = {"decision": "UNKNOWN", "paired_seeds": [], "complete": False,
                  "reason": "missing registered evidence", "proposal": copy.deepcopy(proposal),
                  "next_cycle": next_cycle, "active_backend_during_cycle": (
                      "shared_per_task" if next_cycle and self.active else "original"),
                  "proof": {name: copy.deepcopy(self.verification.get(name))
                            for name in ("exact_reuse", "exhaustion_certificate")}}
        self._last_verification = result
        if not proposal["available"] or not _proof(self.verification, "exact_reuse"):
            return copy.deepcopy(result)
        if set(cases) != set(SEEDS) or any(not cases[seed] for seed in SEEDS):
            result["reason"] = "all three registered seeds require nonempty paired cases"
            return copy.deepcopy(result)
        refs = {}
        for seed in SEEDS:
            for index, case in enumerate(cases[seed]):
                state = case.get("state")
                limits = case.get("searchconfig", {})
                if (type(getattr(state, "seed", None)) is not int or state.seed != seed
                        or type(case.get("budget")) is not int or case["budget"] <= 0
                        or set(limits) != {"max_size", "max_expansions", "step_budget"}
                        or any(type(value) is not int or value < (0 if name == "max_expansions" else 1)
                               for name, value in limits.items())):
                    result["reason"] = "cases must bind their actual registered seed and valid frozen search limits"
                    return copy.deepcopy(result)
                context_key = _key(_context(state))
                ref = case.get("state_ref") or next((r for r, key in self._context_keys.items()
                                                     if key == context_key), None)
                if ref not in self._contexts or self._context_keys[ref] != context_key:
                    result["reason"] = "counterfactual state differs from its registered immutable context"
                    return copy.deepcopy(result)
                refs[seed, index] = ref
        result["reason"] = "awaiting complete paired evidence for all three seeds"
        # Accepted stores for this new cycle must not inherit verification work.
        if next_cycle:
            self._stores = {}
        for seed in SEEDS:
            old = memory.EvaluationMemory()
            candidate = (self.nextmemory(seed) if next_cycle else EfficientEvaluationMemory(
                _PolicyStore(proposal["certificate_hypothesis"])))
            totals = {name: 0 for name in WORK}
            newer = {name: 0 for name in WORK}
            pair = {"seed": seed, "calls": [], "scientific_equal": True,
                    "backend": type(candidate).__name__}
            for index, case in enumerate(cases[seed]):
                initial = memory.snapshot(case["state"])
                old_state, new_state = memory.restore(initial), memory.restore(initial)
                tasks, heuristic = list(case["tasks"]), case["heuristic"]
                budget, limits = case["budget"], dict(case["searchconfig"])
                counterfactuals, costs = {}, {}
                for label, backend, state in (("original", old, old_state), ("candidate", candidate, new_state)):
                    cpu, wall = time.process_time(), time.perf_counter()
                    counterfactuals[label] = backend.measure(state, tasks, heuristic, budget, limits)
                    costs[label] = {"cpu_seconds": time.process_time() - cpu,
                                    "wall_seconds": time.perf_counter() - wall}
                baseline, changed = counterfactuals["original"], counterfactuals["candidate"]
                equal = _key(scientific(baseline)) == _key(scientific(changed))
                pair["scientific_equal"] &= equal
                old_work, new_work = _work(baseline), _work(changed)
                for name in WORK:
                    totals[name] += old_work[name]
                    newer[name] += new_work[name]
                task_scope = _facts(refs[seed, index], tasks, heuristic, budget, limits)
                pair["calls"].append({"index": index, "scope": task_scope,
                                      "typed_scope": json.loads(_key(task_scope)),
                                      "original": baseline, "candidate": changed,
                                      "scientific_equal": equal, "actual_work": {
                                          "original": old_work, "candidate": new_work}, "physical_cost": costs})
            pair.update({"actual_work": {"original": totals, "candidate": newer},
                         "no_work_increase": all(newer[name] <= totals[name] for name in WORK),
                         "strict_work_saving": any(newer[name] < totals[name] for name in WORK),
                         "original_memory": old.summary(), "candidate_memory": candidate.summary()})
            result["paired_seeds"].append(pair)
            if progress is not None:
                progress(copy.deepcopy(result))
        result["complete"] = True
        safe = all(row["scientific_equal"] and row["no_work_increase"] for row in result["paired_seeds"])
        strict = all(row["strict_work_saving"] for row in result["paired_seeds"])
        result["decision"] = "KEEP" if safe and strict else "REVISE" if safe else "REVERT"
        result["reason"] = ("Every seed preserves science and strictly saves actual work" if safe and strict else
                            "No per-seed strict work gain" if safe else "Scientific difference or actual-work regression")
        result["certificate_verified"] = bool(proposal["certificate_hypothesis"] and any(
            record.get("reuse_kind") == "early_termination_certificate"
            for pair in result["paired_seeds"] for call in pair["calls"] for record in call["candidate"]["records"]))
        return copy.deepcopy(result)

    def _fields(self, result):
        paired = result["paired_seeds"]
        diagnosis = result["proposal"]["diagnosis"]
        performance = []
        for pair in paired:
            queries = [{"query_index": call["index"], "role": "full" if index == len(pair["calls"]) - 1 else "prefix",
                        **{label: {name: call[label][name] for name in ("solved", "tasks", "solved_fraction")}
                           for label in ("original", "candidate")}}
                       for index, call in enumerate(pair["calls"])]
            performance.append({"seed": pair["seed"], "actual_work": pair["actual_work"],
                                "queries": queries, "interpretation": "Unchanged task results are separate from evaluation-work savings"})
        failures = {**diagnosis, "planning_failure": "unknown", "tool_failure": "unknown",
                    "model_failure": "unknown", "unobserved_causes": "not inferred from repeated evaluation work"}
        return {"current_performance": performance,
                "failure_clusters": failures,
                "bottleneck": "Repeated exact per-task assessments" if diagnosis["repeated_per_task_scopes"] else
                              "No supported repeated-work bottleneck",
                "previous_attempt_insufficiency": "Whole-group caching cannot reuse a repeated task inside a different group; executability is not solver fitness.",
                "intervention": result["proposal"]["action"],
                "mechanism": "Preserve scientific outcomes while avoiding exact repeated interpreter/search work.",
                "verification_plan": "Fresh paired registered calls for all three seeds; typed equality, no work-component increase and strict per-seed work saving plus real verifier proof.",
                "regression_risks": "Changed scope, unsafe budget extrapolation, container aliasing, and physical cache overhead.",
                "result": copy.deepcopy(result),
                "keep_revert_revise": result["decision"],
                "updated_rule": {"active": result["decision"] == "KEEP", "backend": "shared_per_task" if result["decision"] == "KEEP" else "original",
                                 "scope": "One demonstrated evaluation-procedure refinement; no solver capability claim",
                                 "lesson": "Identical task-scope overlap permits preserving verified per-task evidence; changed state, caps or examples require revalidation",
                                 "certificate_enabled": result.get("certificate_verified", False)}}

    def preserve(self, cycle=None):
        """Preserve this coordinator's own verified result and update its factory."""
        if self._last_verification is None:
            raise ValueError("verification must precede preservation")
        result = self._last_verification
        self.active = result["complete"] and result["decision"] == "KEEP"
        self.certificates = self.active and result.get("certificate_verified", False)
        self._stores = {}
        row = {"cycle": len(self.cycles) + 1 if cycle is None else cycle, **self._fields(result)}
        self.cycles.append(copy.deepcopy(row))
        # New measurements become next-cycle evidence only after this decision.
        for pair in result["paired_seeds"]:
            for call in pair["calls"]:
                self.history.append({"seed": pair["seed"], "scope": copy.deepcopy(call["scope"]),
                                     "measurement": copy.deepcopy(call["original"])})
        return copy.deepcopy(row)

    def to_dict(self, include_contexts=True):
        return {"active": self.active, "certificates": self.certificates,
                **({"contexts": copy.deepcopy(self._contexts)} if include_contexts else
                   {"context_refs": list(self._contexts), "context_registry": "initial_states"}),
                "history": copy.deepcopy(self.history), "cycles": copy.deepcopy(self.cycles),
                "verification": {name: copy.deepcopy(self.verification.get(name))
                                 for name in ("exact_reuse", "exhaustion_certificate")}}


def history_from_artifacts(artifacts, tasks, searchconfig):
    """Rebuild actual development call scopes, excluding result aliases and hits.

    Only known supplied task names are eligible. Initial learner state is fixed
    in this study; logged scorer terms are used as scope facts, never installed
    as the counterfactual solver's incumbent.
    """
    by_name = {task.name: task for task in tasks}
    calls, contexts = [], {}
    for seed, artifact in artifacts.items():
        state = memory.restore(artifact["initial_state"])
        if _key(artifact.get("config", {}).get("search")) != _key(searchconfig):
            raise ValueError("source development search configuration differs from registered limits")
        ref = f"seed{seed}"
        contexts[ref] = _context(state)
        context_key = _key(contexts[ref])
        for arm, target in artifact.get("arms", {}).items():
            if "final_state" in target and _key(_context(memory.restore(target["final_state"]))) != context_key:
                raise ValueError("source development context changed after initial task learning")
            for row in target.get("cycles", []):
                measured = [("incumbent_validation", row.get("incumbent_validation"), row.get("incumbent"))]
                for candidate in row.get("candidates", []):
                    measured.extend((f"candidate_{candidate['index']}_{stage}", candidate.get(stage), candidate.get("term"))
                                    for stage in ("screen", "full"))
                for label, report, term in measured:
                    if not report or report.get("cache_hit") is True:
                        continue
                    names = [record["name"] for record in report["records"]]
                    if not all(name in by_name for name in names):
                        continue
                    scorer = None if term is None else Term.from_dict(term)
                    tasks_ = [by_name[name] for name in names]
                    calls.append({"seed": seed, "source": {"arm": arm, "cycle": row["cycle"], "call": label},
                                  "scope": _facts(ref, tasks_, scorer, report["budget"], searchconfig),
                                  "measurement": copy.deepcopy(report)})
    return {"contexts": contexts, "calls": calls}


def _write(path, record):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def run(protocol, output):
    """Run the two registered procedure cycles; a parent bounds aggregate CPU."""
    registered = {"schema_version": 1, "id": "autonomous_evaluation_refinement", "seeds": list(SEEDS),
                  "B_eval": 64, "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000},
                  "cycles": [{"cycle": 1, "partition": "validation", "prefix_tasks": 4, "full_tasks": 12},
                             {"cycle": 2, "partition": "confirmation", "prefix_tasks": 3, "full_tasks": 6}]}
    if _key({name: protocol.get(name) for name in registered}) != _key(registered):
        raise ValueError("autonomous protocol differs from the registered two-cycle trace")
    output = Path(output)
    source = Path(protocol["source_results"])
    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("autonomous artifacts must not change source development results")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "self_refinement.json"
    if path.exists():
        raise FileExistsError(path)
    artifacts = {seed: json.loads((source / f"seed{seed}.json").read_text()) for seed in SEEDS}
    states = {seed: memory.restore(artifacts[seed]["initial_state"]) for seed in SEEDS}
    if any(state.heuristic != zero_heuristic() for state in states.values()):
        raise ValueError("registered counterfactual uses the unchanged zero incumbent")
    verification = json.loads(Path(protocol["verification"]).read_text())
    validation = sorted(load_validation(), key=lambda task: task.name)
    if len(validation) != 12:
        raise ValueError("registered validation partition requires twelve tasks")
    history = history_from_artifacts(artifacts, validation, protocol["search"])
    coordinator = Coordinator(history, verification)
    coordinator.propose()
    started, cpu = time.perf_counter(), time.process_time()
    record = {"schema_version": 1, "protocol": copy.deepcopy(protocol), "status": "running",
              "initial_states": {f"seed{seed}": memory.snapshot(state) for seed, state in states.items()},
              "coordinator": coordinator.to_dict(include_contexts=False), "pending_cycle": None,
              "limits": "Bounded autonomous refinement of one evaluation procedure; no score synthesis or capability claim",
              "cpu_scope": "Local timer excludes initial artifact loading, history reconstruction and proposal diagnosis; parent watchdog accounts total process CPU. Paired physical_cost measures backend operations only."}
    _write(path, record)

    def checkpoint(partial):
        record["pending_cycle"] = {"cycle": 1 if not coordinator.cycles else 2,
                                   **coordinator._fields(partial)}
        record["cpu_seconds"] = time.process_time() - cpu
        record["wall_seconds"] = time.perf_counter() - started
        _write(path, record)

    def cases(tasks, prefix):
        return {seed: [{"state": state, "state_ref": f"seed{seed}", "tasks": group, "heuristic": state.heuristic,
                        "budget": protocol["B_eval"], "searchconfig": protocol["search"]}
                       for group in (tasks[:prefix], tasks)] for seed, state in states.items()}

    coordinator.verify(cases(validation, 4), progress=checkpoint)
    coordinator.preserve(1)
    record.update({"status": "admission_saved", "coordinator": coordinator.to_dict(include_contexts=False), "pending_cycle": None})
    _write(path, record)  # Admission is durable before opening the next partition.
    if coordinator.active:
        confirmation = load_confirmation()
        if len(confirmation) != 6:
            raise ValueError("registered confirmation partition requires six tasks")
        coordinator.verify(cases(confirmation, 3), progress=checkpoint, next_cycle=True)
        coordinator.preserve(2)
    else:
        record["next_cycle_skipped"] = "No accepted factory; fresh confirmation was not loaded"
    record.update({"status": "complete" if len(coordinator.cycles) == 2 else "no_activation",
                   "coordinator": coordinator.to_dict(include_contexts=False), "pending_cycle": None,
                   "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - started})
    _write(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(json.loads(args.protocol.read_text()), args.output)


if __name__ == "__main__":
    main()
