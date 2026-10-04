"""Independent exact-reuse replication of the frozen procedure study.

The source runner remains reproducible at SOURCE_COMMIT. This entry point
changes only its evaluation-memory backend; engine.cycle and every scientific
setting are imported unchanged. Use a new output directory for each run.
"""
from __future__ import annotations

# Import the original controller first: it fixes NumPy thread environment
# before engine, learning, or the efficient backend imports NumPy.
from .run import (CPUController, POLL_SECONDS, _audit_lower_bound,
                  _records_after_selection, _run_phase, _selection_candidates)

import argparse
import json
from pathlib import Path
import time

from ..calibrate import load_calibration
from ..corpus import load_train, load_validation
from ..heuristics import zero_heuristic
from ..learning import State, wake_sleep
from ..terms import Term
from .diagnostics import audit_candidate, profile_from_tasks
from .efficient_memory import EfficientEvaluationMemory, SharedStore
from .engine import atomic_write, cycle, load_config
from .memory import restore, snapshot
from .proposals import ProposalPool
from .sealed_audit import load_audit
from .transfer import load_confirmation


SOURCE_COMMIT = "2562f564cb995fd9b6863d1fa4ef3de1d0d27a31"
INTERVENTION = "exact_evaluation_reuse"
CACHE_MODE = "shared_per_seed_task_measurements_and_budget_certificates"


def _metadata():
    return {"intervention": INTERVENTION, "source_commit": SOURCE_COMMIT,
            "cache_mode": CACHE_MODE}


def run_seed(seed, output):
    """Preserve the source seed procedure, sharing only completed assessments."""
    config = load_config()
    if seed not in config["seeds"]:
        raise ValueError("unregistered seed")
    path = Path(output) / f"seed{seed}.json"
    if path.exists():
        raise FileExistsError(path)
    started, cpu_started = time.perf_counter(), time.process_time()
    train, validation, confirmation = load_train(), load_validation(), load_confirmation()
    state = State(seed, heuristic=zero_heuristic())
    record = {"seed": seed, "config": config, "status": "running", "arms": {},
              **_metadata()}
    atomic_write(path, record)
    record["initial_learning"] = wake_sleep(state, train, {**load_calibration(), "dreams": 16})
    initial = snapshot(state)
    record["initial_state"] = initial
    store = SharedStore()
    initial_memory = EfficientEvaluationMemory(store)
    record["baseline_training"] = initial_memory.measure(
        state, train, state.heuristic, config["B_eval"], config["search"])
    states, pools, memories = {}, {}, {}
    for arm in config["arms"]:
        states[arm] = restore(initial)
        pools[arm] = ProposalPool(states[arm].grammar, seed, arm)
        memories[arm] = EfficientEvaluationMemory(store)
        record["arms"][arm] = {"cycles": []}
    for number in range(1, config["cycles"] + 1):
        for arm in config["arms"]:
            if time.process_time() - cpu_started > 0.75 * config["cpu_limit_seconds"] / len(config["seeds"]):
                record["status"] = "partial"
                record["stop_reason"] = "per-seed share of aggregate CPU cap"
                break
            report = cycle(states[arm], pools[arm], memories[arm], validation,
                           confirmation, number, config)
            target = record["arms"][arm]
            target["cycles"].append(report)
            target["final_state"] = snapshot(states[arm])
            target["proposal_memory"] = pools[arm].to_dict()
            target["evaluation_memory"] = memories[arm].summary()
            record["shared_evaluation_store"] = store.summary()
            record["cpu_seconds"] = time.process_time() - cpu_started
            atomic_write(path, record)
            print(json.dumps({"seed": seed, "arm": arm, "cycle": number,
                              "validation": report["validation"]["solved"],
                              "productive_proposals": report["proposal_productivity"]["verified"],
                              "adopted": report["adopted_index"] is not None}), flush=True)
        if record["status"] == "partial":
            break
    if record["status"] != "partial":
        record["status"] = "selection_frozen"
    record["cpu_seconds"] = time.process_time() - cpu_started
    record["wall_seconds"] = time.perf_counter() - started
    record["shared_evaluation_store"] = store.summary()
    record["actual_candidate_evaluations"] = (
        record["initial_learning"]["wake_candidate_evaluations"]
        + record["initial_learning"]["dream_candidate_evaluations"]
        + initial_memory.actual_candidate_evaluations
        + sum(memory.actual_candidate_evaluations for memory in memories.values())
        + sum(row["draw"]["new_raw_draws"] + row["draw"]["replay_draws"]
              + row["probe_program_evaluations"]
              for target in record["arms"].values() for row in target["cycles"]))
    atomic_write(path, record)
    return {"seed": seed, "status": record["status"], "cpu_seconds": record["cpu_seconds"]}


def reporting_audit(output, records, config):
    """The source reporting phase with only the evaluation backend replaced."""
    if any(record["status"] != "selection_frozen" for record in records):
        return {"status": "unrun", "reason": "selection incomplete",
                "cpu_seconds": 0.0, "candidate_evaluations": 0}
    started = time.process_time()
    tasks, train = load_audit(), load_train()
    profile = profile_from_tasks(tasks)
    store = SharedStore()
    memory = EfficientEvaluationMemory(store)
    probe_evaluations = probe_examples = probe_steps = 0
    for record in records:
        for arm in config["arms"]:
            target = record["arms"][arm]
            state = restore(target["final_state"])
            target["audit"] = memory.measure(state, tasks, state.heuristic,
                                              config["B_eval"], config["search"])
            target["training"] = memory.measure(state, train, state.heuristic,
                                                 config["B_eval"], config["search"])
            for row in target["cycles"]:
                audits = [audit_candidate(Term.from_dict(row["candidates"][i]["term"]),
                                          state.grammar.library, profile=profile,
                                          step_budget=config["search"]["step_budget"])
                          for i in row["selected_indices"]
                          if row["candidates"][i]["term"] is not None]
                counts = {"selected": len(row["selected_indices"]),
                          "attempted": len(audits),
                          "verified": sum(audit["valid"] and audit["informative"] for audit in audits),
                          "program_evaluations": sum(audit["program_evaluations"] for audit in audits),
                          "example_evaluations": sum(audit["example_evaluations"] for audit in audits),
                          "evaluator_steps": sum(audit["evaluator_steps"] for audit in audits)}
                row["audit_productivity"] = counts
                probe_evaluations += counts["program_evaluations"]
                probe_examples += counts["example_evaluations"]
                probe_steps += counts["evaluator_steps"]
            print(json.dumps({"phase": "reporting-only audit", "seed": record["seed"],
                              "arm": arm, "audit_solved": target["audit"]["solved"],
                              "training_solved": target["training"]["solved"]}), flush=True)
            atomic_write(Path(output) / f"seed{record['seed']}.json", record)
        record["status"] = "complete"
        atomic_write(Path(output) / f"seed{record['seed']}.json", record)
    return {"status": "complete", "cpu_seconds": time.process_time() - started,
            "candidate_evaluations": memory.actual_candidate_evaluations + probe_evaluations,
            "memory": memory.summary(), "shared_evaluation_store": store.summary(),
            "probe_program_evaluations": probe_evaluations,
            "probe_example_evaluations": probe_examples, "probe_evaluator_steps": probe_steps}


def _phase_worker(kind, key, output, config, records, events):
    try:
        result = (run_seed(key, output) if kind == "selection"
                  else reporting_audit(output, records, config))
        events.put({"key": key, "result": result})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def run(output, workers=3):
    """Preserve the source watchdog and freeze-before-audit scheduling."""
    config = load_config()
    if type(workers) is not int or not 1 <= workers <= config["max_workers"]:
        raise ValueError("use one through three workers")
    output = Path(output)
    if output.exists():
        raise FileExistsError("use a new output directory; previous evidence cannot be overwritten")
    output.mkdir(parents=True)
    started = time.perf_counter()
    budget = CPUController(config["cpu_limit_seconds"])
    summary = {"status": "running", "config": config, "workers": workers,
               "selection_frozen_before_audit": False, "seeds": [], **_metadata()}
    atomic_write(output / "summary.json", summary)
    phase = _run_phase("selection", config["seeds"], output, config, budget, workers,
                       worker_target=_phase_worker)
    records = _records_after_selection(output, config, phase)
    for record in records:
        record.update(_metadata())
        atomic_write(output / f"seed{record['seed']}.json", record)
    summary["seeds"] = [{"seed": record["seed"], "status": record["status"],
                         "cpu_seconds": record.get("cpu_seconds", 0.0)} for record in records]
    summary["selection_frozen_before_audit"] = all(record["status"] == "selection_frozen" for record in records)
    atomic_write(output / "summary.json", summary)
    audit_phase = None
    if phase["reason"] is not None or not summary["selection_frozen_before_audit"]:
        audit = {"status": "unrun", "reason": phase["reason"] or "selection incomplete",
                 "cpu_seconds": 0.0, "candidate_evaluations": 0}
    elif budget.exhausted():
        audit = {"status": "unrun", "reason": "aggregate CPU ceiling reached before audit",
                 "cpu_seconds": 0.0, "candidate_evaluations": 0}
    else:
        before_audit = budget.spent()
        audit_phase = _run_phase("audit", ["audit"], output, config, budget, 1, records,
                                 worker_target=_phase_worker)
        records = [json.loads((output / f"seed{seed}.json").read_text())
                   for seed in config["seeds"]]
        event = audit_phase["results"].get("audit", {})
        if audit_phase["reason"] is None and "result" in event:
            audit = event["result"]
        else:
            audit = {"status": "partial", "reason": audit_phase["reason"] or "audit incomplete",
                     **_audit_lower_bound(records)}
        audit["worker_cpu_seconds"] = audit.get("cpu_seconds", 0.0)
        audit["cpu_seconds"] = budget.spent() - before_audit
    summary["audit"] = audit
    summary["audit_cpu_seconds"] = audit["cpu_seconds"]
    summary["cpu_seconds"] = budget.spent()
    summary["wall_seconds"] = time.perf_counter() - started
    summary["actual_candidate_evaluations"] = sum(_selection_candidates(record) for record in records) + audit["candidate_evaluations"]
    summary["seeds"] = [{"seed": record["seed"], "status": record["status"],
                         "cpu_seconds": record.get("cpu_seconds", 0.0)} for record in records]
    summary["status"] = ("complete" if audit["status"] == "complete"
                         and all(record["status"] == "complete" for record in records) else "partial")
    summary["cpu_accounting"] = "parent_process_and_reaped_children_plus_live_proc_cpu"
    summary["cpu_poll_seconds"] = POLL_SECONDS
    summary["cpu_cleanup_margin_seconds"] = budget.cleanup_margin
    summary["candidate_evaluations_scope"] = ("all_completed_operations" if summary["status"] == "complete"
                                              else "completed_operations_lower_bound")
    if summary["status"] != "complete":
        summary["stop_reason"] = audit.get("reason", "study incomplete")
    if summary["cpu_seconds"] >= config["cpu_limit_seconds"]:
        summary["status"] = "partial"
        summary["candidate_evaluations_scope"] = "completed_operations_lower_bound"
        summary["stop_reason"] = "aggregate CPU ceiling reached; no complete positive comparison"
    atomic_write(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    interrupted = phase.get("exception") or (audit_phase or {}).get("exception")
    if interrupted is not None:
        raise interrupted
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    run(args.output, args.workers)


if __name__ == "__main__":
    main()
