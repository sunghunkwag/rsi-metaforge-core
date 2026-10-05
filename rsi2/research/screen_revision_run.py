"""Matched TRAIN-only causal screening diagnostic on a frozen pilot state."""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
import gzip
import json
from pathlib import Path
import time

from ..grammar import Grammar
from ..recognition import Recognition
from ..search import HEURISTIC_TYPE
from ..terms import Term
from ..types import infer, unify
from .budget_policy import solve_reserved_population
from .recursive_bootstrap import (
    CpuGuard, RecursiveState, _bank, _measure, _proof_cost, _work, atomic_write,
    population_kernel_factory,
)
from .compression import verify_solutions
from .run import CPUController, _run_phase


def restore_state(source):
    """Restore actual own-program learning state; do not invent ASTs or weights."""
    saved = source["final_state"]
    state = RecursiveState(saved["seed"], saved["arm"], saved["generation"])
    state.grammar = Grammar(
        library={name: Term.from_dict(term) for name, term in saved["library"].items()},
        weights=saved["grammar_weights"],
        context_weights={(r["parent"], r["argument"]): r["weights"]
                         for r in saved["grammar_context_weights"]})
    state.raw_solutions = {name: Term.from_dict(term) for name, term in saved["raw_solutions"].items()}
    state.solutions = {name: Term.from_dict(term) for name, term in saved["solutions"].items()}
    state.acceptance_records = copy.deepcopy(saved["acceptance_records"])
    state.library_history = copy.deepcopy(saved["library_history"])
    state.heuristic_history = copy.deepcopy(saved["heuristic_history"])
    if set(state.raw_solutions) != set(state.acceptance_records):
        raise ValueError("source bank has missing verification provenance")
    for record in state.acceptance_records.values():
        if record.get("verification", {}).get("passed") is not True:
            raise ValueError("source bank contains an unverified label")
    state.recognition = Recognition.from_dict(saved["recognition"]) if saved["recognition"] is not None else None
    state.heuristic = Term.from_dict(saved["heuristic"])
    return state


def reserved_kernel_factory():
    def call(examples, request_type, budget, grammar, *, bank, heuristic, seed, limits):
        return solve_reserved_population(examples, request_type, budget, grammar,
                                         accepted_seeds=bank, heuristic=heuristic,
                                         seed=seed, **limits)
    return call


def trial(source_path, output, config):
    started, cpu = time.perf_counter(), time.process_time()
    from ..corpus import load_train
    with (gzip.open(source_path, "rt") if str(source_path).endswith(".gz")
          else Path(source_path).open()) as stream:
        source = json.load(stream)
    if source.get("source") != "TRAIN only" or source.get("evaluation_partitions_opened") is not False:
        raise ValueError("source must be a TRAIN-only recursive checkpoint")
    state = restore_state(source)
    train = sorted(load_train(), key=lambda t: t.name)
    work, guard = _work(), CpuGuard(config["cpu_limit_seconds"] - 5)
    # Verify both executable library rewrites and the raw-bank programs before
    # using them. Source provenance alone is insufficient to bless a replay.
    proofs = []
    for solutions, library in ((state.solutions, state.grammar.library),
                               (state.raw_solutions, state.grammar.library)):
        guard.check()
        proof = verify_solutions(solutions, library, train)
        proofs.append(proof)
        _proof_cost(proof["cost"], work)
        if not proof["passed"]:
            raise ValueError("source solutions failed replay verification")
    proposals = source["in_progress"]["heuristic"]["candidates"]
    if len(proposals) != 6 or [r["index"] for r in proposals] != list(range(6)):
        raise ValueError("diagnostic requires the frozen six own-generated proposal slots")
    candidates = [("incumbent", state.heuristic)]
    for record in proposals:
        if record.get("term") is None:
            raise ValueError("diagnostic source has an unrun candidate slot")
        term = Term.from_dict(record["term"])
        unify(infer(term, library=state.grammar.library), HEURISTIC_TYPE)
        candidates.append((str(record["index"]), term))
    record = {"status": "running", "source": "TRAIN only", "source_path": str(source_path),
              "source_pilot_status": source["status"], "source_generation": state.generation,
              "config": config, "state": source["final_state"], "source_proposals": proposals,
              "replay_proofs": proofs, "work": work, "screens": [],
              "evaluation_partitions_opened": False, "rsi_success": False,
              "claim_scope": "causal evaluation-stage correction; capability gain unassessed"}
    path = Path(output) / "screens.json"

    def save():
        record.update(cpu_seconds=time.process_time() - cpu,
                      wall_seconds=time.perf_counter() - started)
        atomic_write(path, record)

    bank = _bank(state)
    for name, heuristic in candidates:
        row = {"candidate": name, "heuristic": heuristic, "original": {}, "reserved": {}}
        record["screens"].append(row)
        for method, factory in (("original", population_kernel_factory),
                                ("reserved", reserved_kernel_factory)):
            _measure(state, train[:4], 16, heuristic, bank, state.generation,
                     source["config"], factory, guard, work, save, destination=row[method])
    reference = record["screens"][0]
    result = []
    for row in record["screens"]:
        item = {"candidate": row["candidate"]}
        for method in ("original", "reserved"):
            measurement = row[method]
            searches = [r["search"] for r in measurement["records"]]
            actual = [[trial["term"] for trial in s["trials"]] for s in searches]
            baseline = [[trial["term"] for trial in r["search"]["trials"]]
                        for r in reference[method]["records"]]
            item[method] = {"solved": measurement["solved"],
                            "solved_names": measurement["solved_names"],
                            "candidates": sum(s["candidates"] for s in searches),
                            "descendants": sum(s["repair_candidates"] for s in searches),
                            "parent_selections": sum(len(s["parent_selections"]) for s in searches),
                            "sequence_differs_from_incumbent": actual != baseline,
                            "kernel_cpu_seconds": sum(s["cpu_seconds"] for s in searches)}
        result.append(item)
        item["verified_gains"] = sorted(set(item["reserved"]["solved_names"]) -
                                        set(item["original"]["solved_names"]))
        item["verified_losses"] = sorted(set(item["original"]["solved_names"]) -
                                         set(item["reserved"]["solved_names"]))
    eligible = {str(r["index"]) for r in proposals
                if all((r.get(key) or {}).get("valid") is True and
                       (r.get(key) or {}).get("informative") is True
                       for key in ("semantic_probe", "train_probe"))}
    rankings = {method: [r["candidate"] for r in sorted(
        (r for r in result if r["candidate"] in eligible),
        key=lambda r: (-r[method]["solved"], int(r["candidate"])))[:2]]
                for method in ("original", "reserved")}
    record.update(status="complete", outcomes=result,
                  eligible_source_proposals=sorted(eligible, key=int),
                  selected_confirmation_indices=rankings,
                  full_confirmations="unrun in screening diagnostic",
                  candidate_evaluations_scope="exact_completed_operations")
    save()
    return {"status": record["status"], "outcomes": result}


def worker(kind, key, output, config, records, events):
    try:
        events.put({"key": key, "result": trial(config["source_path"], output, config)})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def complete_screen_record(record):
    """A terminal event cannot certify a missing or truncated persisted run."""
    if not isinstance(record, dict) or record.get("status") != "complete":
        return False
    rows = record.get("screens", [])
    if [row.get("candidate") for row in rows] != ["incumbent", "0", "1", "2", "3", "4", "5"]:
        return False
    expected_names = None
    for row in rows:
        for method in ("original", "reserved"):
            measurement = row.get(method, {})
            tasks = measurement.get("records", [])
            if (measurement.get("status") != "complete" or
                    measurement.get("tasks_completed") != 4 or len(tasks) != 4 or
                    any(type(task.get("solved")) is not bool for task in tasks)):
                return False
            names = [task.get("name") for task in tasks]
            if len(set(names)) != 4 or any(type(name) is not str for name in names):
                return False
            if expected_names is None:
                expected_names = names
            if names != expected_names:
                return False
    return True


def run(source_path, output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=True)
    config = {"source_path": str(Path(source_path).resolve()), "cpu_limit_seconds": 600,
              "screen_tasks": 4, "screen_budget": 16,
              "method": "matched frozen-state causal root reservation diagnostic"}
    budget = CPUController(config["cpu_limit_seconds"])
    phase = _run_phase("screen_revision", [11], output, config, budget, workers=1, worker_target=worker)
    event = phase["results"].get(11, {})
    path = output / "screens.json"
    record = json.loads(path.read_text()) if path.exists() else None
    complete = (phase["reason"] is None and event.get("result", {}).get("status") == "complete"
                and complete_screen_record(record) and budget.spent() < config["cpu_limit_seconds"])
    if not complete and path.exists():
        record.update(status="partial", candidate_evaluations_scope="completed_operations_lower_bound")
        atomic_write(path, record)
    summary = {"status": "complete" if complete else "partial", "config": config,
               "phase": phase, "cpu_seconds": budget.spent(), "rsi_success": False,
               "stop_reason": phase["reason"] or event.get("error"),
               "candidate_evaluations_scope": "exact_completed_operations" if complete
               else "completed_operations_lower_bound"}
    phase.pop("exception", None)
    atomic_write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.source, args.output)
    print(json.dumps({k: result[k] for k in ("status", "cpu_seconds", "rsi_success", "stop_reason")}))


if __name__ == "__main__":
    main()
