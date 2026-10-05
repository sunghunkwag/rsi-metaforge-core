"""Matched TRAIN-only population/coordinate diagnostic with one CPU watchdog.

Execution order, limits and development-only B640 selection are registered in
DERIVATION_NEIGHBORHOOD_PROTOCOL.md. This runner never loads heldout partitions.
Search journals contain exact candidate/provenance evidence and independent
public/hidden TRAIN proofs. Human-designed operators are engineering candidates;
no result from this diagnostic establishes recursive self-improvement.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
import gzip
import json
import math
from pathlib import Path
import time

from ..grammar import Grammar
from ..heuristics import zero_heuristic
from ..terms import Term
from ..types import Type, infer, unify
from .budget_policy import POLICY_NAME, allocate_roots
from .compression import verify_solutions
from .coordinate_population import solve_coordinate_population
from .journal_checkpoint import JournalCheckpoint, JournalCorruption, reconstruct
from .population_search import solve_population
from .recursive_bootstrap import CpuGuard, CpuStop, atomic_write, jsonable
from .repair_search import RepairSeed
from .run import CPUController, _run_phase


REGISTERED_CONFIG = {
    "schema_version": 1, "protocol": "DERIVATION_NEIGHBORHOOD_PROTOCOL.md",
    "seed": 11, "train_tasks": 36, "cpu_limit_seconds": 600,
    "max_cpu_seconds_per_search": 10, "initial_fresh_prefix": 16,
    "root_policy": POLICY_NAME, "grammar": "fresh frozen default; no fit/library/recognition",
    "heuristic": "frozen zero", "search": {
        "max_size": 12, "max_expansions": 20000, "step_budget": 2000,
        "max_normalization_steps": 20000, "beta_normalize": True,
        "force_wrapper_lambdas": True,
    },
}
B64_ORDER = ("cold_population_B64", "cold_coordinates_B64",
             "bank_population_B64", "bank_coordinates_B64")
SEARCH_WORK = ("candidates", "evaluator_calls", "evaluation_steps", "heuristic_calls",
               "heuristic_evaluations", "heuristic_steps", "heuristic_failures",
               "expansions", "normalization_steps", "beta_reductions", "canonicalization_steps")
NEIGHBORHOOD_WORK = ("structural_states", "compiler_steps", "grammar_queries",
                     "production_choices_created", "type_checks", "generated", "duplicates",
                     "oversized", "ill_typed", "eta_views")
PROOF_WORK = ("program_evaluations", "example_evaluations", "evaluator_steps",
              "public_example_evaluations", "hidden_example_evaluations",
              "public_evaluator_steps", "hidden_evaluator_steps")


def condition_spec(key):
    if key not in B64_ORDER + tuple(f"{memory}_{method}_B640"
                                   for memory in ("cold", "bank")
                                   for method in ("population", "coordinates")):
        raise ValueError(f"unregistered diagnostic condition: {key}")
    memory, method, budget = key.split("_")
    return {"key": key, "memory": memory, "method": method, "budget": int(budget[1:])}


def load_source(path):
    path = Path(path)
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz"
          else path.open("r", encoding="utf-8")) as stream:
        return json.load(stream)


def raw_bank(source):
    """Restore only original verifier-attributed raw programs, never fitted state."""
    if (source.get("source") != "TRAIN only" or source.get("evaluation_partitions_opened") is not False
            or type(source.get("seed")) is not int or source["seed"] != 11):
        raise ValueError("source must be the seed11 TRAIN-only frozen pilot")
    saved = source["final_state"]
    solutions, evidence = saved["raw_solutions"], saved["acceptance_records"]
    if not solutions or set(solutions) != set(evidence):
        raise ValueError("source bank must contain raw programs and exact acceptance provenance")
    bank, programs = [], []
    for name in sorted(solutions):
        proof, term = evidence[name], Term.from_dict(solutions[name])
        identifier = proof.get("id")
        if (not isinstance(identifier, str) or not identifier or proof.get("task") != name
                or proof.get("verification", {}).get("passed") is not True):
            raise ValueError("source raw program has missing or failed acceptance proof")
        bank.append(RepairSeed(term, identifier))
        programs.append({"task": name, "term": term, "source_record_id": identifier,
                         "original_generation": proof.get("generation")})
    if len({entry.training_record for entry in bank}) != len(bank):
        raise ValueError("source proof IDs must be unique")
    return tuple(bank), programs


def _work():
    return {**dict.fromkeys(SEARCH_WORK, 0),
            **{f"neighborhood_{key}": 0 for key in NEIGHBORHOOD_WORK},
            **{f"verification_{key}": 0 for key in PROOF_WORK},
            "root_policy_cpu_seconds": 0.0, "kernel_cpu_seconds": 0.0,
            "verification_cpu_seconds": 0.0}


def _charge_proof(work, proof):
    for key in PROOF_WORK:
        work[f"verification_{key}"] += proof["cost"][key]
    work["verification_cpu_seconds"] += proof["cost"]["cpu_seconds"]


def _check_search(search, budget, limits):
    for key in SEARCH_WORK:
        if key not in search:
            raise ValueError(f"missing actual search counter: {key}")
        value = search[key]
        if type(value) is not int or value < 0:
            raise ValueError(f"invalid actual search counter: {key}")
    candidates = search.get("candidates", 0)
    logical = search.get("logical_evaluations", candidates)
    if type(logical) is not int or not 0 <= candidates <= logical <= budget:
        raise ValueError("complete/helper candidate budget exceeded or mistyped")
    if (search.get("expansions", 0) > limits["max_expansions"] or
            search.get("normalization_steps", 0) > limits["max_normalization_steps"]):
        raise ValueError("shared structural/compiler budget exceeded")
    trials = search.get("trials")
    if (not isinstance(trials, list) or len(trials) != candidates
            or any(type(trial.get("id")) is not int or trial["id"] != index
                   for index, trial in enumerate(trials))):
        raise ValueError("candidate trial genealogy is incomplete or misordered")
    if search.get("term") is not None and not any(
            trial.get("public_match") is True and trial.get("term") == search["term"] for trial in trials):
        raise ValueError("selected term has no charged public-match trial")
    for key in NEIGHBORHOOD_WORK:
        value = search.get("neighborhood_work", {}).get(key, 0)
        if type(value) is not int or value < 0:
            raise ValueError(f"invalid neighborhood counter: {key}")
    return logical


def run_condition(tasks, source, key, path, config, *, kernels=None, initial_cpu_seconds=0.0):
    """Run one condition; injected kernels support corpus-free verification tests."""
    spec = condition_spec(key)
    train = sorted(tuple(tasks), key=lambda task: task.name)
    if len(train) != config["train_tasks"] or len({task.name for task in train}) != len(train):
        raise ValueError("condition requires the complete unique registered TRAIN task list")
    started, wall = time.process_time(), time.perf_counter()
    guard = CpuGuard(max(0.0, config["worker_cpu_allowance_seconds"] - initial_cpu_seconds))
    work = _work()
    record = {"condition": spec, "config": config, "seed": config["seed"],
              "status": "running", "source": "TRAIN only", "source_path": config["source_path"],
              "source_pilot_status": source.get("status"), "tasks": [], "work": work,
              "task_order": [task.name for task in train], "source_bank": {},
              "evaluation_partitions_opened": False, "rsi_success": False,
              "candidate_evaluations_scope": "completed_operations_lower_bound",
              "input_setup_cpu_seconds": initial_cpu_seconds,
              "cpu_scope": "worker body/source loading; interpreter startup additionally in parent ledger"}
    solvers = kernels or {"population": solve_population, "coordinates": solve_coordinate_population}
    with JournalCheckpoint(path) as writer:
        def save():
            record.update(cpu_seconds=initial_cpu_seconds + time.process_time() - started,
                          wall_seconds=time.perf_counter() - wall)
            writer(record)

        try:
            record["in_progress"] = {"stage": "source_bank_restore"}
            save()
            guard.check()
            bank, programs = raw_bank(source)
            record["source_bank"].update(programs=programs, proof=None,
                                         used_for_search=spec["memory"] == "bank")
            record["in_progress"]["stage"] = "source_bank_independent_verification"
            save()
            proof = verify_solutions({program["task"]: entry.term
                                      for program, entry in zip(programs, bank)}, {}, train,
                                     step_budget=config["search"]["step_budget"])
            _charge_proof(work, proof)
            record["source_bank"]["proof"] = proof
            save()
            if not proof["passed"]:
                raise ValueError("raw source bank failed fresh empty-library public/hidden verification")
            supplied = bank if spec["memory"] == "bank" else ()
            for number, task in enumerate(train):
                guard.check()
                record["in_progress"] = {"name": task.name, "stage": "public_search"}
                save()
                task_cpu = time.process_time()
                allocation = allocate_roots(spec["budget"], supplied,
                                            seed_prefix=config["initial_fresh_prefix"])
                policy_cpu = time.process_time() - task_cpu
                maximum_cpu = min(config["max_cpu_seconds_per_search"], guard.remaining())
                limits = dict(config["search"], max_cpu_seconds=max(0.0, maximum_cpu - policy_cpu))
                result = solvers[spec["method"]](
                    task.examples, task.request_type, spec["budget"], Grammar(),
                    accepted_seeds=allocation.selected_bank, seed_prefix=allocation.fresh_prefix,
                    heuristic=zero_heuristic(), seed=config["seed"] * 1000003 + number,
                    **limits)
                total_cpu = time.process_time() - task_cpu
                search = jsonable(result)
                if not isinstance(search, dict):
                    raise ValueError("task kernel must return a structured actual search result")
                term = result.get("term") if isinstance(result, dict) else result.term
                row = {"name": task.name, "request_type": task.request_type.to_dict(),
                       "search": search, "root_allocation": allocation.to_record(),
                       "public_selected": term is not None, "verification": None, "solved": None,
                       "root_policy_cpu_seconds": policy_cpu,
                       "kernel_call_cpu_seconds": total_cpu - policy_cpu,
                       "policy_deadline_exceeded": total_cpu >= maximum_cpu}
                record["tasks"].append(row)
                # Preserve even malformed returned evidence. Only known,
                # nonnegative actual counters enter the monotone lower bound;
                # a contract failure vetoes completion rather than fabricating
                # missing charges or discarding the returned candidate trace.
                for field in SEARCH_WORK:
                    value = search.get("logical_evaluations", search.get(field, 0)) if field == "candidates" else search.get(field, 0)
                    if type(value) is int and value >= 0:
                        work[field] += value
                for field in NEIGHBORHOOD_WORK:
                    value = search.get("neighborhood_work", {}).get(field, 0)
                    if type(value) is int and value >= 0:
                        work[f"neighborhood_{field}"] += value
                work["root_policy_cpu_seconds"] += policy_cpu
                work["kernel_cpu_seconds"] += total_cpu - policy_cpu
                record["in_progress"]["stage"] = "search_contract_verification"
                save()
                _check_search(search, spec["budget"], config["search"])
                if not isinstance(term, (Term, type(None))):
                    raise ValueError("kernel selected term must be an actual own-language Term")
                record["in_progress"]["stage"] = "independent_verification"
                guard.check()
                if term is not None:
                    proof = verify_solutions({task.name: term}, {}, [task],
                                             step_budget=config["search"]["step_budget"])
                    _charge_proof(work, proof)
                    row["verification"] = proof
                    row["solved"] = (proof["passed"] and term.size <= config["search"]["max_size"]
                                     and not row["policy_deadline_exceeded"])
                else:
                    row["solved"] = False
                save()
            record.pop("in_progress", None)
            record.update(status="complete", candidate_evaluations_scope="exact_completed_operations")
        except CpuStop:
            record.update(status="partial", stop_reason="worker remaining CPU allowance exhausted")
        except Exception as error:
            record.update(status="failed", stop_reason=f"{type(error).__name__}: {error}")
            save()
            raise
        record["solved_names"] = sorted(row["name"] for row in record["tasks"] if row["solved"] is True)
        save()
        return {"status": record["status"], "tasks_completed": sum(row["solved"] is not None for row in record["tasks"]),
                "stop_reason": record.get("stop_reason"), "persistence": writer.metrics}


def diagnostic_worker(kind, key, output, config, records, events):
    try:
        started = time.process_time()
        from ..corpus import load_train
        tasks, source = load_train(), load_source(config["source_path"])
        result = run_condition(tasks, source, key, Path(output) / f"{key}.checkpoint.json", config,
                               initial_cpu_seconds=time.process_time() - started)
        events.put({"key": key, "result": result})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def _valid_proof(proof, names, step_budget):
    if (type(proof.get("passed")) is not bool or type(proof.get("step_budget")) is not int
            or proof["step_budget"] != step_budget
            or [row["name"] for row in proof["tasks"]] != sorted(names)):
        return False
    cost = proof["cost"]
    if any(type(cost.get(key)) is not int or cost[key] < 0 for key in PROOF_WORK):
        return False
    rows = proof["tasks"]
    if any(type(row.get("passed")) is not bool
           or any(type(row.get(key)) is not int or row[key] < 1 for key in ("public_examples", "hidden_examples"))
           or type(row.get("evaluator_steps")) is not int or row["evaluator_steps"] < 0 for row in rows):
        return False
    return (proof["passed"] == all(row["passed"] for row in rows)
            and cost["program_evaluations"] == len(rows)
            and cost["public_example_evaluations"] == sum(row["public_examples"] for row in rows)
            and cost["hidden_example_evaluations"] == sum(row["hidden_examples"] for row in rows)
            and cost["example_evaluations"] == cost["public_example_evaluations"] + cost["hidden_example_evaluations"]
            and cost["evaluator_steps"] == sum(row["evaluator_steps"] for row in rows)
            and cost["evaluator_steps"] == cost["public_evaluator_steps"] + cost["hidden_evaluator_steps"]
            and type(cost.get("cpu_seconds")) in (int, float)
            and math.isfinite(cost["cpu_seconds"]) and cost["cpu_seconds"] >= 0)


def _reconciled_work(record):
    expected = _work()
    _charge_proof(expected, record["source_bank"]["proof"])
    for row in record["tasks"]:
        search = row["search"]
        for key in SEARCH_WORK:
            expected[key] += search.get("logical_evaluations", search[key]) if key == "candidates" else search[key]
        for key in NEIGHBORHOOD_WORK:
            expected[f"neighborhood_{key}"] += search.get("neighborhood_work", {}).get(key, 0)
        if row["verification"] is not None:
            _charge_proof(expected, row["verification"])
        for key, source_key in (("root_policy_cpu_seconds", "root_policy_cpu_seconds"),
                                ("kernel_cpu_seconds", "kernel_call_cpu_seconds")):
            value = row[source_key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                return False
            expected[key] += value
    for key, value in expected.items():
        actual = record["work"].get(key)
        if type(value) is int:
            if type(actual) is not int or actual != value:
                return False
        elif (type(actual) not in (int, float) or not math.isfinite(actual)
              or not math.isclose(actual, value, rel_tol=1e-12, abs_tol=1e-9)):
            return False
    return True


def _complete_record(record, config, spec, expected_names):
    """Parent gate: an event cannot manufacture a complete persisted measurement."""
    try:
        if (record["status"] != "complete" or record["source"] != "TRAIN only"
                or record["evaluation_partitions_opened"] is not False
                or record["rsi_success"] is not False
                or type(record["seed"]) is not int or record["seed"] != 11
                or json.dumps(record["config"], sort_keys=True) != json.dumps(config, sort_keys=True)
                or json.dumps(record["condition"], sort_keys=True) != json.dumps(spec, sort_keys=True)
                or record["task_order"] != expected_names
                or len(record["tasks"]) != 36
                or [row["name"] for row in record["tasks"]] != expected_names):
            return False
        bank = record["source_bank"]
        programs, proof = bank["programs"], bank["proof"]
        if (not programs or proof.get("passed") is not True
                or not _valid_proof(proof, [p["task"] for p in programs], config["search"]["step_budget"])
                or proof["cost"]["program_evaluations"] != len(programs)
                or sorted(row["name"] for row in proof["tasks"]) != sorted(p["task"] for p in programs)
                or any(row["passed"] is not True or row["public_examples"] < 1 or row["hidden_examples"] < 1
                       for row in proof["tasks"])):
            return False
        supplied = tuple(RepairSeed(Term.from_dict(p["term"]), p["source_record_id"]) for p in programs)
        if spec["memory"] == "cold":
            supplied = ()
        allocation = allocate_roots(spec["budget"], supplied,
                                    seed_prefix=config["initial_fresh_prefix"]).to_record()
        for number, row in enumerate(record["tasks"]):
            _check_search(row["search"], spec["budget"], config["search"])
            if (type(row["solved"]) is not bool or type(row["public_selected"]) is not bool
                    or type(row["policy_deadline_exceeded"]) is not bool
                    or type(row["search"].get("seed")) is not int
                    or row["search"]["seed"] != config["seed"] * 1000003 + number
                    or json.dumps(row["root_allocation"], sort_keys=True) != json.dumps(allocation, sort_keys=True)):
                return False
            selected = row["search"].get("term")
            if selected is None:
                if row["public_selected"] or row["solved"] or row["verification"] is not None:
                    return False
            else:
                term = Term.from_dict(selected)
                unify(infer(term, library={}), Type.from_dict(row["request_type"]))
                verification = row["verification"]
                if (not row["public_selected"] or term.size > config["search"]["max_size"]
                        or verification is None
                        or not _valid_proof(verification, [row["name"]], config["search"]["step_budget"])
                        or verification["cost"]["program_evaluations"] != 1
                        or [r["name"] for r in verification["tasks"]] != [row["name"]]
                        or verification["tasks"][0]["public_examples"] < 1
                        or verification["tasks"][0]["hidden_examples"] < 1):
                    return False
                if row["solved"] != (verification["passed"] is True and not row["policy_deadline_exceeded"]):
                    return False
        return (record["solved_names"] == sorted(row["name"] for row in record["tasks"] if row["solved"])
                and _reconciled_work(record))
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
        return False


def _comparison(conditions, memory, budget):
    left = conditions.get(f"{memory}_population_B{budget}", {})
    right = conditions.get(f"{memory}_coordinates_B{budget}", {})
    if left.get("status") != "complete" or right.get("status") != "complete":
        return {"memory": memory, "budget": budget, "status": "UNKNOWN", "strict_expansion": False}
    old, new = set(left["solved_names"]), set(right["solved_names"])
    return {"memory": memory, "budget": budget, "status": "complete",
            "population_solved": sorted(old), "coordinates_solved": sorted(new),
            "gains": sorted(new - old), "losses": sorted(old - new), "strict_expansion": old < new}


def select_b640(conditions):
    bank, cold = _comparison(conditions, "bank", 64), _comparison(conditions, "cold", 64)
    if bank["strict_expansion"]:
        return "bank", "complete bank B64 strict verified expansion without loss"
    if cold["strict_expansion"]:
        return "cold", "complete cold B64 strict verified expansion without loss"
    return "cold", "registered search-space diagnostic fallback; no qualifying B64 gain"


def _condition_summary(key, phase, config, expected_names, output):
    event = phase["results"].get(key, {})
    worker = event.get("result", {})
    path = Path(output) / f"{key}.checkpoint.json"
    record, reconstruction, corruption = None, None, None
    if path.exists():
        try:
            recovery = reconstruct(path)
            record = recovery.record
            reconstruction = {"cpu_seconds": recovery.cpu_seconds, "wall_seconds": recovery.wall_seconds,
                              "interrupted": recovery.interrupted, "ignored_bytes": recovery.ignored_bytes}
        except JournalCorruption as error:
            corruption = str(error)
    complete = (phase["reason"] is None and "error" not in event and
                worker.get("status") == "complete" and worker.get("tasks_completed") == 36 and
                record is not None and _complete_record(record, config, condition_spec(key), expected_names))
    started = key in phase["started"]
    status = "complete" if complete else "partial" if started else "unrun"
    return {"condition": condition_spec(key), "status": status,
            "stop_reason": phase["reason"] or event.get("error") or corruption or worker.get("stop_reason")
            or ("persisted/task/type/budget completion gate failed" if started and not complete else None),
            "tasks_completed": sum(row.get("solved") is not None for row in record["tasks"]) if record else 0,
            "solved_names": sorted(row["name"] for row in record["tasks"] if row.get("solved") is True) if record else [],
            "work": record.get("work") if record else "UNKNOWN",
            "kernel_cpu_seconds": record.get("work", {}).get("kernel_cpu_seconds") if record else None,
            "persistence": worker.get("persistence", "UNKNOWN if worker interrupted before terminal telemetry"),
            "reconstruction": reconstruction, "source_bank": record.get("source_bank") if record else None,
            "accounting_scope": "exact_completed_operations" if complete else "completed_operations_lower_bound" if started else "UNKNOWN",
            "worker_observed_cpu_seconds": phase["observed_cpu"].get(key),
            "failures": [{"name": row["name"],
                          "stage": "verification" if row.get("verification") and not row["verification"]["passed"] else "search",
                          "termination": row["search"].get("termination"),
                          "proof_failures": row.get("verification", {}).get("tasks", []) if row.get("verification") else [],
                          "candidates": row["search"].get("candidates"),
                          "expansions": row["search"].get("expansions"),
                          "normalization_steps": row["search"].get("normalization_steps")}
                         for row in record["tasks"] if row.get("solved") is not True] if record else "UNKNOWN",
            "artifact": str(path) if path.exists() else None}


def _cycle_report(conditions, selected_memory):
    comparisons = [_comparison(conditions, memory, 64) for memory in ("cold", "bank")]
    comparisons.append(_comparison(conditions, selected_memory, 640))
    gains = [pair for pair in comparisons if pair["strict_expansion"]]
    return {
        "current_performance_summary": {key: {"status": row["status"], "solved": len(row["solved_names"]),
                                               "tasks_completed": row["tasks_completed"]}
                                        for key, row in conditions.items()},
        "main_failure_clusters": {key: "UNKNOWN" if row["status"] != "complete" else
                                  {"unsolved": 36 - len(row["solved_names"]),
                                   "task_failures": row.get("failures", "UNKNOWN")}
                                  for key, row in conditions.items()},
        "deep_bottleneck_abstraction": "Whole-subtree replacement discards sibling evidence; typed coordinate edits preserve head/argument structure while exploring orientations.",
        "why_previous_improvement_attempts_were_insufficient": "The frozen recursive pilot completed only generation0; identity MDL and repeated local repairs did not verify cumulative capability gains.",
        "proposed_intervention": "Generic typed head substitutions, compatible permutations, unary insertions/removals and eta exposure under the same population controller.",
        "expected_mechanism_of_improvement": "Reach structurally related programs by changing existing derivation coordinates, using only own enumerated or independently verified raw parents.",
        "verification_plan": "Matched frozen grammar/root allocation/zero scorer/candidate caps; independent public and hidden TRAIN checks; strict solved-set expansion without any lost task.",
        "regression_risks": "Structural units differ from heap pops; bank-prefix fairness is limited; finite TRAIN examples; common CPU ceiling can leave comparisons unknown; engineering gain cannot establish RSI.",
        "result_after_testing": {"cold_and_bank_comparisons": comparisons,
                                 "other_seeds": "UNKNOWN; unrun", "heldout": "unopened",
                                 "original_a_e": "FAIL from original study; diagnostic cannot reassess"},
        "keep_revert_revise_decision": "Retain only as a candidate kernel for a separately registered recursive campaign" if gains
                                      else "No qualifying verified kernel gain; revise using measured failures, leaving prior source/evidence intact",
        "updated_rule_for_future_improvement_cycles": "Compare candidate generators using the same cold/bank state and budget; admit only complete independently verified solved-set expansions and keep compiler/persistence work explicit.",
    }


def training_names():
    """Read permitted TRAIN names without acquiring evaluation capabilities."""
    train_path = Path(__file__).resolve().parents[1] / "data" / "train.json"
    return sorted(row["name"] for row in json.loads(train_path.read_text()))


def run_diagnostic(source, output, *, worker_target=diagnostic_worker):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    budget = CPUController(REGISTERED_CONFIG["cpu_limit_seconds"])
    config = dict(copy.deepcopy(REGISTERED_CONFIG), source_path=str(Path(source).resolve()))
    # Metadata only, from the permitted TRAIN file; no evaluation partition is
    # acquired. Workers alone construct tasks and provide their hidden verifiers.
    expected_names = training_names()
    if len(expected_names) != 36 or len(set(expected_names)) != 36:
        raise ValueError("frozen TRAIN metadata must contain 36 unique task names")
    conditions, phases, stop_reason = {}, [], None
    initial = {"status": "running", "source": "TRAIN only", "config": config,
               "evaluation_partitions_opened": False, "rsi_success": False,
               "other_seeds": "UNKNOWN; unrun", "original_a_e": "FAIL from original study"}
    atomic_write(output / "summary.json", initial)

    def execute(key):
        nonlocal stop_reason
        if stop_reason is not None or budget.exhausted():
            conditions[key] = {"condition": condition_spec(key), "status": "unrun",
                               "stop_reason": stop_reason or "aggregate CPU ceiling reached before phase",
                               "tasks_completed": 0, "solved_names": [], "work": "UNKNOWN",
                               "accounting_scope": "UNKNOWN"}
            return
        payload = dict(config, worker_cpu_allowance_seconds=max(0.0, budget.limit - budget.spent() - budget.cleanup_margin))
        phase = _run_phase("coordinate_diagnostic", [key], output, payload, budget,
                           workers=1, worker_target=worker_target)
        phase.pop("exception", None)
        phases.append({"condition": key, **phase})
        conditions[key] = _condition_summary(key, phase, payload, expected_names, output)
        if conditions[key]["status"] != "complete":
            stop_reason = conditions[key]["stop_reason"] or "condition incomplete"
        if budget.spent() >= budget.limit:
            stop_reason = "aggregate CPU ceiling reached including reconstruction"
        atomic_write(output / "summary.json", {**initial, "conditions": conditions,
                                                "cpu_seconds": budget.spent(), "phases": phases})

    for key in B64_ORDER:
        execute(key)
    memory, selection_reason = select_b640(conditions)
    for method in ("population", "coordinates"):
        execute(f"{memory}_{method}_B640")
    complete = all(row["status"] == "complete" for row in conditions.values()) and budget.spent() < budget.limit
    summary = {**initial, "status": "complete" if complete else "partial", "conditions": conditions,
               "phases": phases, "b640_selection": {"memory": memory, "reason": selection_reason},
               "cycle_report": _cycle_report(conditions, memory), "stop_reason": stop_reason,
               "cpu_seconds": budget.spent(), "wall_seconds": time.perf_counter() - started,
               "cpu_accounting": "parent plus reaped/live workers; source evidence, journal writes/reconstruction included; sampled before final metadata commit",
               "cpu_cleanup_margin_seconds": budget.cleanup_margin,
               "accounting_scope": "exact_completed_operations" if complete else "completed_operations_lower_bound",
               "claim_scope": "TRAIN candidate-kernel engineering; RSI/generalization unverified"}
    atomic_write(output / "summary.json", summary)
    final_cpu = budget.spent()
    if final_cpu >= budget.limit:
        summary.update(status="partial", stop_reason="aggregate CPU ceiling reached including final metadata",
                       accounting_scope="completed_operations_lower_bound")
    summary["cpu_seconds"] = final_cpu
    summary["wall_seconds"] = time.perf_counter() - started
    atomic_write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_diagnostic(args.source, args.output)
    print(json.dumps({key: result[key] for key in ("status", "cpu_seconds", "stop_reason", "rsi_success")}))


if __name__ == "__main__":
    main()
