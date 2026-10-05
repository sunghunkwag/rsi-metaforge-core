"""Run autonomous evaluation refinement under the existing CPU watchdog."""
from __future__ import annotations

from .run import CPUController, POLL_SECONDS, _run_phase

import argparse
import json
from pathlib import Path
import time

from .engine import atomic_write


def _worker(kind, key, output, protocol, records, events):
    try:
        from .self_refinement import run as execute
        result = execute(protocol, Path(output))
        events.put({"key": key, "result": {"status": result["status"]}})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def run(protocol_path, output):
    protocol = json.loads(Path(protocol_path).read_text())
    registered = json.loads((Path(__file__).parent / "SELF_REFINEMENT_PROTOCOL.json").read_text())
    if json.dumps(protocol, sort_keys=True) != json.dumps(registered, sort_keys=True):
        raise ValueError("protocol differs from the registered autonomous comparison")
    output = Path(output)
    if output.exists():
        raise FileExistsError("use a new output directory")
    output.mkdir(parents=True)
    started = time.perf_counter()
    budget = CPUController(protocol["cpu_limit_seconds"])
    summary = {"status": "running", "protocol": protocol, "workers": 1}
    atomic_write(output / "summary.json", summary)
    phase = _run_phase("self_refinement", ["coordinator"], output, protocol,
                       budget, 1, worker_target=_worker)
    terminal = phase["results"].get("coordinator", {})
    checkpoint = output / "self_refinement.json"
    persisted = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    cpu_seconds = budget.spent()
    complete = (phase["reason"] is None
                and terminal.get("result", {}).get("status") == "complete"
                and persisted.get("status") == "complete"
                and cpu_seconds < protocol["cpu_limit_seconds"])
    summary.update({"status": "complete" if complete else "partial",
                    "cpu_seconds": cpu_seconds,
                    "wall_seconds": time.perf_counter() - started,
                    "cpu_poll_seconds": POLL_SECONDS,
                    "cpu_accounting": "parent_process_and_reaped_children_plus_live_proc_cpu",
                    "candidate_evaluations_scope": "all_completed_operations" if complete
                    else "completed_operations_lower_bound"})
    if not complete:
        summary["stop_reason"] = ("aggregate CPU ceiling reached" if cpu_seconds >= protocol["cpu_limit_seconds"]
                                  else phase["reason"] or "coordinator did not complete")
    atomic_write(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    if phase.get("exception") is not None:
        raise phase["exception"]
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=Path(__file__).parent / "SELF_REFINEMENT_PROTOCOL.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.protocol, args.output)


if __name__ == "__main__":
    main()
