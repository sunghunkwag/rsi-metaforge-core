"""Development-only improvement cycles; reporting-only data is inaccessible here."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import time

from ..calibrate import load_calibration
from ..corpus import load_train, load_validation
from ..heuristics import zero_heuristic
from ..learning import State, wake_sleep
from ..terms import pretty
from .diagnostics import audit_candidate, clusters, profile_from_tasks
from .memory import EvaluationMemory, restore, snapshot
from .proposals import ProposalPool
from .transfer import load_confirmation


REGISTERED_CONFIG = {
    "schema_version": 1, "seeds": [11, 22, 33],
    "arms": ["original", "static", "learned"], "cycles": 3,
    "raw_enumeration_slots": 32, "mutation_slots": 2, "screen_slots": 6,
    "confirmation_slots": 2, "B_eval": 64, "screen_budget": 16, "screen_tasks": 4,
    "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000},
    "cpu_limit_seconds": 7200, "max_workers": 3, "numpy_threads": 1,
}


def load_config():
    supplied = json.loads((Path(__file__).parent / "config.json").read_text())
    if json.dumps(supplied, sort_keys=True) != json.dumps(REGISTERED_CONFIG, sort_keys=True):
        raise ValueError("research configuration differs from the registered protocol")
    return copy.deepcopy(supplied)


def atomic_write(path, record):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def admissible(audit, incumbent_full, candidate_full, incumbent_confirmation,
               candidate_confirmation):
    """A proxy, faster tie or apparent constant-offset gain cannot replace search."""
    if not audit.get("valid") or not audit.get("informative"):
        return False
    if candidate_full["solved_fraction"] <= incumbent_full["solved_fraction"]:
        return False
    previous = {r["name"] for r in incumbent_confirmation["records"] if r["solved"]}
    current = {r["name"] for r in candidate_confirmation["records"] if r["solved"]}
    return previous <= current


def _empty_audit():
    return {"valid": False, "informative": False, "failures": [],
            "program_evaluations": 0, "example_evaluations": 0, "evaluator_steps": 0}


def cycle(state, pool, memory, validation, confirmation, number, config):
    started, cpu_started = time.perf_counter(), time.process_time()
    limits = config["search"]
    previous = state.heuristic
    incumbent_full = memory.measure(state, validation, previous, config["B_eval"], limits)
    incumbent_confirmation = memory.measure(state, confirmation, previous,
                                             config["B_eval"], limits)
    records = pool.draw(previous, number, limits)
    raw_records = copy.deepcopy(records)
    audits = [audit_candidate(r["term"], state.grammar.library,
                             step_budget=limits["step_budget"])
              if r["term"] is not None else _empty_audit() for r in records]
    selected = pool.select(records, audits, quota=config["screen_slots"])
    # Fresh-family profiles verify proposal productivity; they never fit the model.
    profile = profile_from_tasks(confirmation)
    confirmation_audits = {
        i: audit_candidate(records[i]["term"], state.grammar.library, profile=profile,
                           step_budget=limits["step_budget"]) for i in selected
        if records[i]["term"] is not None}
    screened = []
    for i in selected:
        record = records[i]
        record.update({"selected": True, "screen": None, "full": None,
                       "confirmation": None, "adopted": False})
        if record["term"] is None or record.get("rejection"):
            continue
        record["screen"] = memory.measure(
            state, sorted(validation, key=lambda t: t.name)[:config["screen_tasks"]],
            record["term"], config["screen_budget"], limits)
        screened.append(i)
    priority = {index: rank for rank, index in enumerate(selected)}
    # Keep the proposer's learned ordering when task screening ties. Replacing
    # it with raw enumeration indices would discard the selection intervention.
    screened.sort(key=lambda i: (-records[i]["screen"]["solved_fraction"], priority[i]))
    confirmed = screened[:config["confirmation_slots"]]
    best = incumbent_full
    adopted_index = None
    for i in confirmed:
        record = records[i]
        full = memory.measure(state, validation, record["term"], config["B_eval"], limits)
        record["full"] = full
        if (full["solved_fraction"] > best["solved_fraction"]
                and audits[i]["valid"] and audits[i]["informative"]):
            check = memory.measure(state, confirmation, record["term"], config["B_eval"], limits)
            record["confirmation"] = check
            if admissible(audits[i], incumbent_full, full, incumbent_confirmation, check):
                best, adopted_index = full, i
    if adopted_index is not None:
        state.heuristic = records[adopted_index]["term"]
        records[adopted_index]["adopted"] = True
    current_confirmation = (incumbent_confirmation if adopted_index is None else
                            records[adopted_index]["confirmation"])
    # Fit after selecting and measuring. This model is a tested candidate policy,
    # not an automatically accepted solver improvement.
    model = pool.observe(raw_records, audits)
    evidence = clusters(incumbent_full, records, audits)
    productive = sum(audits[i]["valid"] and audits[i]["informative"] for i in selected)
    confirmed_productive = sum(a["valid"] and a["informative"]
                              for a in confirmation_audits.values())
    serialized = []
    for i, r in enumerate(records):
        serialized.append({**r, "term": None if r["term"] is None else r["term"].to_dict(),
                           "readable": None if r["term"] is None else pretty(r["term"]),
                           "audit": audits[i], "selected": i in selected,
                           "confirmation_audit": confirmation_audits.get(i)})
    all_audits = audits + list(confirmation_audits.values())
    decision = "keep verified task heuristic" if adopted_index is not None else "reject task candidates; retain incumbent"
    online_report = {
        "current_performance": {"validation": best["solved_fraction"],
                                "confirmation": current_confirmation["solved_fraction"]},
        "failure_clusters": evidence,
        "bottleneck": "Repeated/invalid/input-constant proposals and tied screening are measured separately from task-search limits.",
        "previous_attempt_insufficiency": "Executable proposal quality alone has not established a downstream task gain; only preceding-cycle labels may rank this cycle.",
        "intervention": {"original": "Restarted four-prefix/two-mutation control",
                         "static": "Persistent frontier, semantic eligibility and AST novelty",
                         "learned": "Static procedure plus a prior-cycle fitted proposal ranker"}[pool.mode],
        "mechanism": "Change the generation and confirmation priority of improvement candidates using verified outcomes, without changing primitives or task search.",
        "verification_plan": "Common semantic probes, six fresh-family public probe profiles, fixed-budget screens/full hidden verification and per-task confirmation nonloss.",
        "regression_risks": "Productivity proxy mismatch, limited coverage, constant-score queue artifacts and stale or order-insensitive cached measurements.",
        "result": {"selected": len(selected), "verified": productive,
                   "fresh_family_verified": confirmed_productive,
                   "task_heuristic_adopted": adopted_index is not None},
        "keep_revert_revise": decision + "; procedure comparison remains provisional until all matched seeds/cycles finish",
        "updated_rule": {"status": "measured history; unaccepted procedure hypothesis",
                         "verified_training_rows": model["observed_count"],
                         "use_next_cycle": "Carry verified rejections, selected ASTs and prior-label ranking state; never carry a task update rejected by the strict gate"},
    }
    return {"cycle": number, "arm": pool.mode, "seed": state.seed,
            "incumbent": previous.to_dict(), "selected_indices": selected,
            "confirmed_indices": confirmed, "adopted_index": adopted_index,
            "incumbent_validation": incumbent_full, "validation": best,
            "incumbent_confirmation": incumbent_confirmation,
            "confirmation": current_confirmation, "failure_clusters": evidence,
            "proposal_productivity": {"selected": len(selected), "verified": productive,
                                      "fresh_family_verified": confirmed_productive},
            "draw": copy.deepcopy(pool.draw_report),
            "selection": copy.deepcopy(pool.selection_report), "model": model,
            "candidates": serialized,
            "probe_program_evaluations": sum(a["program_evaluations"] for a in all_audits),
            "probe_example_evaluations": sum(a["example_evaluations"] for a in all_audits),
            "probe_evaluator_steps": sum(a["evaluator_steps"] for a in all_audits),
            "online_report": online_report,
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started,
            "decision": decision + "; continue procedure test",
            "memory": memory.summary()}


def run_seed(seed, output):
    config = load_config()
    if seed not in config["seeds"]:
        raise ValueError("unregistered seed")
    path = Path(output) / f"seed{seed}.json"
    if path.exists():
        raise FileExistsError(path)
    started, cpu_started = time.perf_counter(), time.process_time()
    train, validation, confirmation = load_train(), load_validation(), load_confirmation()
    state = State(seed, heuristic=zero_heuristic())
    record = {"seed": seed, "config": config, "status": "running", "arms": {}}
    atomic_write(path, record)
    record["initial_learning"] = wake_sleep(state, train, {**load_calibration(), "dreams": 16})
    initial = snapshot(state)
    record["initial_state"] = initial
    initial_memory = EvaluationMemory()
    record["baseline_training"] = initial_memory.measure(
        state, train, state.heuristic, config["B_eval"], config["search"])
    states, pools, memories = {}, {}, {}
    for arm in config["arms"]:
        states[arm] = restore(initial)
        pools[arm] = ProposalPool(states[arm].grammar, seed, arm)
        memories[arm] = EvaluationMemory()
        record["arms"][arm] = {"cycles": []}
    for number in range(1, config["cycles"] + 1):
        for arm in config["arms"]:
            # Reserve a quarter of the aggregate ceiling for reporting checks.
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
    record["actual_candidate_evaluations"] = (
        record["initial_learning"]["wake_candidate_evaluations"]
        + record["initial_learning"]["dream_candidate_evaluations"]
        + initial_memory.actual_candidate_evaluations
        + sum(m.actual_candidate_evaluations for m in memories.values())
        + sum(r["draw"]["new_raw_draws"] + r["draw"]["replay_draws"] + r["probe_program_evaluations"]
              for a in record["arms"].values() for r in a["cycles"]))
    atomic_write(path, record)
    return {"seed": seed, "status": record["status"], "cpu_seconds": record["cpu_seconds"]}
