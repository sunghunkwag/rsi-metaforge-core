"""Prospective matched TRAIN-only check of generic arity context insertion.

The existing coordinate diagnostic is immutable. This runner reuses its
verified record contract with separately labelled implementation variants;
all new records live in a new output directory. It opens TRAIN only.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
import json
from pathlib import Path
import time

from .coordinate_diagnostic_run import (
    REGISTERED_CONFIG as ORIGINAL_CONFIG, _complete_record, condition_spec,
    load_source, run_condition, training_names,
)
from .coordinate_population import solve_coordinate_population
from .journal_checkpoint import reconstruct
from .recursive_bootstrap import atomic_write
from .run import CPUController, _run_phase


CONFIG = {
    **copy.deepcopy(ORIGINAL_CONFIG),
    "protocol": "ARITY_CONTEXT_PROTOCOL.md",
    "cpu_limit_seconds": 600,
    "production_priority": False,
    "claim_scope": "TRAIN candidate-generation engineering only",
}
ORDER = ("cold_baseline", "cold_arity", "bank_baseline", "bank_arity")


def variant_spec(key):
    if key not in ORDER:
        raise ValueError("unregistered arity diagnostic variant")
    memory, variant = key.split("_")
    return {
        "key": key, "memory": memory, "arity_context": variant == "arity",
        "production_priority": False, "budget": 64,
        "common_condition": f"{memory}_coordinates_B64",
    }


def diagnostic_worker(kind, key, output, config, records, events):
    try:
        started = time.process_time()
        from ..corpus import load_train
        from .arity_population import solve_arity_population
        spec = variant_spec(key)
        tasks, source = load_train(), load_source(config["source_path"])

        def solver(*args, **kwargs):
            if not spec["arity_context"]:
                return solve_coordinate_population(*args, **kwargs)
            return solve_arity_population(*args, arity_context=True,
                                         production_priority=False, **kwargs)

        result = run_condition(
            tasks, source, spec["common_condition"],
            Path(output) / f"{key}.checkpoint.json", config,
            kernels={"coordinates": solver},
            initial_cpu_seconds=time.process_time() - started,
        )
        events.put({"key": key, "result": result})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def compare(conditions, memory):
    baseline = conditions.get(f"{memory}_baseline", {})
    arity = conditions.get(f"{memory}_arity", {})
    if baseline.get("status") != "complete" or arity.get("status") != "complete":
        return {"memory": memory, "status": "UNKNOWN", "strict_expansion": False}
    before, after = set(baseline["solved_names"]), set(arity["solved_names"])
    return {"memory": memory, "status": "complete", "strict_expansion": before < after,
            "baseline_solved": sorted(before), "arity_solved": sorted(after),
            "gains": sorted(after - before), "losses": sorted(before - after)}


def variant_matches(record, spec):
    """Check the returned implementation, not just its requested config."""
    try:
        for row in record["tasks"]:
            search = row["search"]
            work = search["neighborhood_work"]
            if spec["arity_context"]:
                if (search.get("edit_mode") != "arity_coordinates"
                        or work.get("arity_context") is not True
                        or work.get("production_priority") is not False):
                    return False
            elif (search.get("edit_mode") != "coordinates"
                    or work.get("arity_context", False) is not False
                    or work.get("production_priority", False) is not False
                    or any(trial.get("edit_provenance", {}).get("operator") == "application_context"
                           for trial in search["trials"])):
                return False
            if work.get("eta_exposure") is not True:
                return False
        return bool(record["tasks"])
    except (KeyError, TypeError, AttributeError):
        return False


def finalize_comparisons(summary):
    complete = summary["status"] == "complete"
    summary["comparisons"] = [compare(summary["conditions"], memory) if complete else
        {"memory": memory, "status": "UNKNOWN", "strict_expansion": False,
         "reason": "aggregate campaign incomplete or over its CPU ceiling"}
        for memory in ("cold", "bank")]
    summary["kernel_candidate_eligible"] = complete and any(
        row["strict_expansion"] for row in summary["comparisons"])


def run_diagnostic(source, output, *, worker_target=diagnostic_worker):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    watchdog = CPUController(CONFIG["cpu_limit_seconds"])
    config = dict(copy.deepcopy(CONFIG), source_path=str(Path(source).resolve()))
    names = training_names()
    if len(names) != 36 or len(set(names)) != 36:
        raise ValueError("expected the frozen TRAIN36 task names")
    conditions, phases = {}, []
    summary = {
        "status": "running", "source": "TRAIN only", "config": config,
        "evaluation_partitions_opened": False, "rsi_success": False,
        "conditions": conditions, "phases": phases,
        "other_seeds": "UNKNOWN; unrun", "stop_reason": None,
    }
    atomic_write(output / "summary.json", summary)
    for key in ORDER:
        spec = variant_spec(key)
        if summary["stop_reason"] or watchdog.exhausted():
            summary["stop_reason"] = summary["stop_reason"] or "aggregate CPU ceiling reached"
            conditions[key] = {"status": "unrun", "variant": spec, "solved_names": []}
            continue
        payload = dict(config, implementation_variant=spec,
                       worker_cpu_allowance_seconds=max(
                           0, watchdog.limit - watchdog.spent() - watchdog.cleanup_margin))
        phase = _run_phase("arity_diagnostic", [key], output, payload, watchdog,
                           workers=1, worker_target=worker_target)
        phase.pop("exception", None)
        phases.append({"variant": key, **phase})
        event = phase["results"].get(key, {})
        worker = event.get("result", {})
        path = output / f"{key}.checkpoint.json"
        record, recovery_error = None, None
        try:
            if path.exists():
                recovered = reconstruct(path)
                record = recovered.record
                if recovered.interrupted or recovered.ignored_bytes:
                    recovery_error = "interrupted journal"
        except Exception as error:
            recovery_error = f"{type(error).__name__}: {error}"
        complete = (
            phase["reason"] is None and "error" not in event and recovery_error is None
            and worker.get("status") == "complete" and worker.get("tasks_completed") == 36
            and record is not None
            and _complete_record(record, payload, condition_spec(spec["common_condition"]), names)
            and variant_matches(record, spec)
        )
        conditions[key] = {
            "status": "complete" if complete else "partial", "variant": spec,
            "tasks_completed": sum(row.get("solved") is not None for row in record["tasks"]) if record else 0,
            "solved_names": sorted(row["name"] for row in record["tasks"] if row.get("solved") is True) if record else [],
            "work": record.get("work") if record else None,
            "persistence": worker.get("persistence"),
            "artifact": path.name,
            "stop_reason": phase["reason"] or event.get("error") or recovery_error or worker.get("stop_reason"),
        }
        if not complete:
            summary["stop_reason"] = conditions[key]["stop_reason"] or "persisted completion gate failed"
        summary["cpu_seconds"] = watchdog.spent()
        atomic_write(output / "summary.json", summary)
    summary.update(
        status="complete" if all(row["status"] == "complete" for row in conditions.values()) else "partial",
        cpu_seconds=watchdog.spent(), wall_seconds=time.perf_counter() - started,
        cpu_scope="parent plus reaped/live workers including source, proofs, journals and reconstruction",
        learned_improvement=False,
    )
    finalize_comparisons(summary)
    atomic_write(output / "summary.json", summary)
    summary["cpu_seconds"] = watchdog.spent()
    if summary["cpu_seconds"] >= watchdog.limit:
        summary.update(status="partial", stop_reason="aggregate CPU ceiling reached including final metadata")
    finalize_comparisons(summary)
    atomic_write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_diagnostic(args.source, args.output)
    print(json.dumps({key: result[key] for key in ("status", "cpu_seconds", "comparisons", "rsi_success")}))


if __name__ == "__main__":
    main()
