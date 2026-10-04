"""Run separate procedure research; open reporting capability after selection freezes."""
from __future__ import annotations

import os

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import json
import multiprocessing
from pathlib import Path
import queue
import resource
import time

from ..corpus import load_train
from ..terms import Term
from .diagnostics import audit_candidate, profile_from_tasks
from .engine import atomic_write, load_config, run_seed
from .memory import EvaluationMemory, restore
from .sealed_audit import load_audit


POLL_SECONDS = 0.25


def process_cpu_seconds(pid):
    """Read this unreaped process's CPU, including a readable zombie's CPU."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return 0.0
    # The command name can contain spaces and parentheses. Fields after the last
    # ')' begin at field 3; utime/stime are fields 14/15.
    fields = stat.rsplit(")", 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")


def _children_cpu_seconds():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


class CPUController:
    """Score-blind aggregate CPU watchdog for the parent and all phase workers."""

    def __init__(self, limit):
        self.limit = float(limit)
        if self.limit <= 0:
            raise ValueError("CPU ceiling must be positive")
        self.cleanup_margin = min(2.0, self.limit * 0.05)
        self.parent_started = time.process_time()
        self.children_started = _children_cpu_seconds()
        self.observed = 0.0
        self.live_observations = {}

    def spent(self, processes=()):
        # Callers reap before entering this method and never reap during it.
        # Exit during /proc reading leaves an unreaped zombie; after a later
        # reap its CPU moves to RUSAGE_CHILDREN rather than being added twice.
        live = 0.0
        for process in processes:
            cpu = process_cpu_seconds(process.pid)
            self.live_observations[process.pid] = max(
                cpu, self.live_observations.get(process.pid, 0.0))
            live += cpu
        total = (time.process_time() - self.parent_started
                 + _children_cpu_seconds() - self.children_started + live)
        self.observed = max(self.observed, total)
        return self.observed

    def exhausted(self, processes=()):
        return self.spent(processes) >= self.limit - self.cleanup_margin


def _phase_worker(kind, key, output, config, records, events):
    """Only compact terminal metadata crosses the parent control channel."""
    try:
        result = (run_seed(key, output) if kind == "selection"
                  else reporting_audit(output, records, config))
        events.put({"key": key, "result": result})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        # Ensure the feeder has delivered the terminal event before child exit.
        events.close()
        events.join_thread()


def _run_phase(kind, keys, output, config, budget, workers, records=None,
               worker_target=_phase_worker):
    """Run interruptible processes; stopping decisions never read task scores."""
    context = multiprocessing.get_context("spawn")
    events = context.Queue()
    pending, active, all_processes = list(keys), {}, {}
    started_at, results = {}, {}
    outcome = {"results": results, "started": [], "reason": None,
               "observed_cpu": {}, "elapsed_wall": {}}

    def receive(event):
        key = event["key"]
        if key not in all_processes or key in results:
            raise RuntimeError("unexpected or duplicate worker result")
        results[key] = event
        if "error" in event:
            outcome["reason"] = f"{kind} worker {key} failed: {event['error']}"
        elif kind == "selection" and event["result"]["status"] != "selection_frozen":
            outcome["reason"] = f"selection worker {key} did not finish"

    def drain():
        while True:
            try:
                receive(events.get_nowait())
            except queue.Empty:
                return

    def interrupted(error):
        outcome["reason"] = f"parent interrupted: {type(error).__name__}: {error}"
        outcome.setdefault("exception", error)

    try:
        while pending or active:
            # All possible waitpid/reap calls precede the CPU snapshot below.
            for key, process in list(active.items()):
                cpu = process_cpu_seconds(process.pid)
                outcome["observed_cpu"][key] = max(
                    outcome["observed_cpu"].get(key, 0.0), cpu)
                outcome["elapsed_wall"][key] = time.perf_counter() - started_at[key]
                if not process.is_alive():
                    process.join()
                    del active[key]
            drain()
            for key, process in all_processes.items():
                if key not in active and key not in results:
                    outcome["reason"] = f"{kind} worker {key} exited without a result"
                elif key not in active and process.exitcode != 0 and outcome["reason"] is None:
                    outcome["reason"] = f"{kind} worker {key} exited with status {process.exitcode}"
            if outcome["reason"] is not None:
                break
            if budget.exhausted(active.values()):
                outcome["reason"] = "aggregate CPU ceiling reached"
                break
            while pending and len(active) < workers:
                if budget.exhausted(active.values()):
                    outcome["reason"] = "aggregate CPU ceiling reached"
                    break
                key = pending.pop(0)
                process = context.Process(target=worker_target,
                    args=(kind, key, str(output), config, records, events))
                process.start()
                active[key] = all_processes[key] = process
                started_at[key] = time.perf_counter()
                outcome["started"].append(key)
            if outcome["reason"] is not None or not active:
                continue
            try:
                receive(events.get(timeout=POLL_SECONDS))
            except queue.Empty:
                pass
    except BaseException as error:
        interrupted(error)
    finally:
        # Preserve a lower bound for each worker before discarding its /proc
        # entry. The final aggregate below includes all reaped termination CPU.
        try:
            budget.spent(active.values())
        except BaseException as error:
            interrupted(error)
        for key, process in active.items():
            outcome["observed_cpu"][key] = max(outcome["observed_cpu"].get(key, 0.0),
                budget.live_observations.get(process.pid, 0.0))
            outcome["elapsed_wall"][key] = time.perf_counter() - started_at[key]
            process.terminate()
        for process in active.values():
            process.join(timeout=1.0)
            if process.is_alive():
                process.kill()
                process.join()
        try:
            budget.spent()
        except BaseException as error:
            interrupted(error)
        # Workers flush before normal exit; all processes are now reaped.
        try:
            if outcome["reason"] is None:
                drain()
        except BaseException as error:
            interrupted(error)
        finally:
            events.close()
            events.join_thread()
    return outcome


def _selection_candidates(record):
    if "actual_candidate_evaluations" in record:
        return record["actual_candidate_evaluations"]
    initial = record.get("initial_learning", {})
    total = (initial.get("wake_candidate_evaluations", 0)
             + initial.get("dream_candidate_evaluations", 0)
             + record.get("baseline_training", {}).get("actual_candidate_evaluations", 0))
    for target in record.get("arms", {}).values():
        total += target.get("evaluation_memory", {}).get("actual_candidate_evaluations", 0)
        for row in target.get("cycles", []):
            total += (row["draw"]["new_raw_draws"] + row["draw"].get("replay_draws", 0)
                      + row["probe_program_evaluations"])
    return total


def _records_after_selection(output, config, phase):
    records = []
    for seed in config["seeds"]:
        path = output / f"seed{seed}.json"
        record = (json.loads(path.read_text()) if path.exists() else
                  {"seed": seed, "config": config, "status": "unrun", "arms": {}})
        if record["status"] not in ("selection_frozen", "complete"):
            if seed in phase["started"]:
                record["status"] = "partial"
            record["stop_reason"] = phase["reason"] or "selection incomplete"
            record["candidate_evaluations_scope"] = "completed_operations_lower_bound"
            record["cpu_seconds"] = max(record.get("cpu_seconds", 0.0),
                                          phase["observed_cpu"].get(seed, 0.0))
            record["wall_seconds"] = max(record.get("wall_seconds", 0.0),
                                           phase["elapsed_wall"].get(seed, 0.0))
            record["actual_candidate_evaluations"] = _selection_candidates(record)
            atomic_write(path, record)
        records.append(record)
    return records


def _audit_lower_bound(records):
    task_candidates = probes = examples = steps = 0
    for record in records:
        for target in record.get("arms", {}).values():
            for name in ("audit", "training"):
                task_candidates += target.get(name, {}).get("actual_candidate_evaluations", 0)
            for row in target.get("cycles", []):
                counts = row.get("audit_productivity", {})
                probes += counts.get("program_evaluations", 0)
                examples += counts.get("example_evaluations", 0)
                steps += counts.get("evaluator_steps", 0)
    return {"candidate_evaluations": task_candidates + probes,
            "candidate_evaluations_scope": "completed_operations_lower_bound",
            "probe_program_evaluations": probes, "probe_example_evaluations": examples,
            "probe_evaluator_steps": steps,
            "memory": {"actual_candidate_evaluations": task_candidates}}


def reporting_audit(output, records, config):
    """Reporting only: no proposer or learner is instantiated after this point."""
    if any(r["status"] != "selection_frozen" for r in records):
        return {"status": "unrun", "reason": "selection incomplete",
                "cpu_seconds": 0.0, "candidate_evaluations": 0}
    started = time.process_time()
    tasks, train = load_audit(), load_train()
    profile = profile_from_tasks(tasks)
    memory = EvaluationMemory()
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
                          "verified": sum(a["valid"] and a["informative"] for a in audits),
                          "program_evaluations": sum(a["program_evaluations"] for a in audits),
                          "example_evaluations": sum(a["example_evaluations"] for a in audits),
                          "evaluator_steps": sum(a["evaluator_steps"] for a in audits)}
                row["audit_productivity"] = counts
                probe_evaluations += counts["program_evaluations"]
                probe_examples += counts["example_evaluations"]
                probe_steps += counts["evaluator_steps"]
            print(json.dumps({"phase": "reporting-only audit", "seed": record["seed"],
                              "arm": arm, "audit_solved": target["audit"]["solved"],
                              "training_solved": target["training"]["solved"]}), flush=True)
            # Keep completed audit operations if the aggregate controller stops
            # the next operation. Selection remains frozen throughout auditing.
            atomic_write(Path(output) / f"seed{record['seed']}.json", record)
        record["status"] = "complete"
        atomic_write(Path(output) / f"seed{record['seed']}.json", record)
    return {"status": "complete", "cpu_seconds": time.process_time() - started,
            "candidate_evaluations": memory.actual_candidate_evaluations + probe_evaluations,
            "memory": memory.summary(), "probe_program_evaluations": probe_evaluations,
            "probe_example_evaluations": probe_examples, "probe_evaluator_steps": probe_steps}


def run(output, workers=3):
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
               "selection_frozen_before_audit": False, "seeds": []}
    atomic_write(output / "summary.json", summary)
    phase = _run_phase("selection", config["seeds"], output, config, budget, workers)
    records = _records_after_selection(output, config, phase)
    summary["seeds"] = [{"seed": r["seed"], "status": r["status"],
                         "cpu_seconds": r.get("cpu_seconds", 0.0)} for r in records]
    summary["selection_frozen_before_audit"] = all(r["status"] == "selection_frozen" for r in records)
    # Save a reviewable freeze before the isolated reporting loader is used.
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
        audit_phase = _run_phase("audit", ["audit"], output, config, budget, 1, records)
        records = [json.loads((output / f"seed{seed}.json").read_text())
                   for seed in config["seeds"]]
        event = audit_phase["results"].get("audit", {})
        if audit_phase["reason"] is None and "result" in event:
            audit = event["result"]
        else:
            audit = {"status": "partial", "reason": audit_phase["reason"] or "audit incomplete",
                     **_audit_lower_bound(records)}
        # This includes audit-process startup/teardown and parent control CPU.
        audit["worker_cpu_seconds"] = audit.get("cpu_seconds", 0.0)
        audit["cpu_seconds"] = budget.spent() - before_audit
    summary["audit"] = audit
    summary["audit_cpu_seconds"] = audit["cpu_seconds"]
    summary["cpu_seconds"] = budget.spent()
    summary["wall_seconds"] = time.perf_counter() - started
    summary["actual_candidate_evaluations"] = sum(_selection_candidates(r) for r in records) + audit["candidate_evaluations"]
    summary["seeds"] = [{"seed": r["seed"], "status": r["status"],
                         "cpu_seconds": r.get("cpu_seconds", 0.0)} for r in records]
    summary["status"] = ("complete" if audit["status"] == "complete"
                         and all(r["status"] == "complete" for r in records) else "partial")
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
