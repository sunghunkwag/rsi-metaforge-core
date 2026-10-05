"""Score-blind single-worker watchdog for the registered TRAIN-only pilot."""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
import json
from pathlib import Path
import time

from .recursive_bootstrap import REGISTERED_CONFIG, atomic_write, run_arm
from .run import CPUController, _run_phase


def pilot_worker(kind, key, output, config, records, events):
    """Only compact terminal metadata crosses the parent event channel."""
    path = Path(output) / f"FULL_seed{key}.json"
    try:
        from ..corpus import load_train
        result = run_arm(load_train(), key, "FULL", config,
                         checkpoint=lambda record: atomic_write(path, record))
        events.put({"key": key, "result": {
            "status": result["status"], "completed_rows": len(result["generations"]),
            "stop_reason": result.get("stop_reason")}})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def run_pilot(output, *, worker_target=pilot_worker):
    config = copy.deepcopy(REGISTERED_CONFIG)
    if config["cpu_limit_seconds"] != 600 or config["generations"] != 8:
        raise ValueError("pilot differs from registered CPU/generation caps")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    budget = CPUController(config["cpu_limit_seconds"])
    initial = {"status": "running", "source": "TRAIN only", "config": config,
               "pilot_seeds": [11], "pilot_arms": ["FULL"],
               "other_seeds_and_controls": "unrun", "original_a_e": "NOT ASSESSED"}
    atomic_write(output / "summary.json", initial)
    phase = _run_phase("recursive_bootstrap", [11], output, config, budget,
                       workers=1, worker_target=worker_target)
    path = output / "FULL_seed11.json"
    record = json.loads(path.read_text()) if path.exists() else None
    event = phase["results"].get(11, {})
    worker = event.get("result", {})
    config_matches = record is not None and json.dumps(record.get("config"), sort_keys=True) == json.dumps(config, sort_keys=True)
    complete = (phase["reason"] is None and "error" not in event and
                worker.get("status") == "complete" and config_matches and
                record.get("status") == "complete" and
                json.dumps([row["generation"] for row in record["generations"]]) == json.dumps(list(range(9))))
    cpu = budget.spent()
    complete = complete and cpu < config["cpu_limit_seconds"]
    reason = phase["reason"] or event.get("error") or worker.get("stop_reason")
    if not complete and record is not None:
        reason = reason or "incomplete pilot or persisted checkpoint"
        record.update(status="partial", stop_reason=reason,
                      candidate_evaluations_scope="completed_operations_lower_bound")
        atomic_write(path, record)
    summary = {**initial, "status": "complete" if complete else "partial",
               "cpu_seconds": budget.spent(), "wall_seconds": time.perf_counter() - started,
               "cpu_accounting": "parent_process_and_reaped_children_plus_live_proc_cpu",
               "cpu_cleanup_margin_seconds": budget.cleanup_margin,
               "cpu_poll_seconds": 0.25, "phase": phase, "stop_reason": reason,
               "completed_rows": len(record["generations"]) if record else 0,
               "work": record.get("work") if record else None,
               "candidate_evaluations_scope": "exact_completed_operations" if complete
               else "completed_operations_lower_bound",
               "rsi_success": False,
               "rsi_status": "Original a-e failed; new sealed causal evaluation unrun"}
    phase.pop("exception", None)
    atomic_write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_pilot(args.output)
    print(json.dumps({key: result[key] for key in
                      ("status", "completed_rows", "cpu_seconds", "stop_reason", "rsi_success")}))


if __name__ == "__main__":
    main()
