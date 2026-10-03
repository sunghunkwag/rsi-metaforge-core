"""Run the preregistered experiment; TEST measurements never select an action.

Each arm/seed owns a fresh learner and an atomic checkpoint. Frozen controls
reuse measurements explicitly. Existing output directories cannot be rerun.
"""
from __future__ import annotations

import os

# Set these before importing the NumPy-backed learner, including spawned workers.
for _thread_variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                         "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_variable] = "1"

import argparse
import copy
import json
import multiprocessing
from pathlib import Path
import queue
import time

from . import heuristics, learning, sealed_evaluation
from .corpus import load_train, load_validation, split_ids
from .terms import pretty


FROZEN_CONFIG = {
    "schema_version": 1, "seeds": [11, 22, 33], "generations": 8,
    "arms": ["BASE", "BRUTE", "ONESHOT", "FULL", "NO_LIBRARY",
             "NO_RECOGNITION", "NO_HEURISTIC"],
    "B_wake": 64, "B_eval": 64, "M": 10, "dreams": 16,
    "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000},
    "heuristics": {"N_h": 4, "N_m": 2, "screen_tasks": 4,
                   "screen_budget_divisor": 4, "confirm_candidates": 2},
    "max_workers": 5, "numpy_threads": 1, "cpu_limit_seconds": 86400,
}


def validate_config(config):
    """Reject every parameter change, including changed numeric JSON types."""
    if json.dumps(config, sort_keys=True) != json.dumps(FROZEN_CONFIG, sort_keys=True):
        raise ValueError("experiment configuration differs from the preregistered protocol")
    return copy.deepcopy(config)


def load_config(path):
    return validate_config(json.loads(Path(path).read_text(encoding="utf-8")))


def load_partitions():
    """Validate the committed split, loading TEST through its separate capability."""
    manifest = json.loads((Path(__file__).parent / "data" / "split_manifest.json")
                          .read_text(encoding="utf-8"))
    expected = split_ids(manifest["eligible_names"], seed=20261002, selected_count=60)
    if (manifest["seed"] != 20261002 or manifest["population"] != 207
            or manifest["selected"] != 60
            or any(manifest[partition] != names for partition, names in expected.items())):
        raise ValueError("dataset split differs from the preregistered assignment")
    partitions = (load_train(), load_validation(), sealed_evaluation.load_test())
    for name, tasks, size in zip(("train", "validation", "test"), partitions, (36, 12, 12)):
        if len(tasks) != size or [task.name for task in tasks] != manifest[name]:
            raise ValueError(f"{name} tasks differ from the committed split")
    return partitions


def result_path(output, arm, seed):
    return Path(output) / f"{arm}_seed{seed}.json"


def atomic_write(path, record):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def initial_record(arm, seed, config, status="unrun"):
    return {"arm": arm, "seed": seed, "status": status,
            "config": copy.deepcopy(config), "generations": [], "final_state": None,
            "totals": {"candidate_evaluations": 0, "wall_seconds": 0.0,
                       "cpu_seconds": 0.0}}


def final_state(state):
    """Save reproducible state plus readable adopted terms; logs live in generations."""
    summary = learning.state_summary(state)
    summary["solutions"] = {
        name: {"term": term.to_dict(), "readable": pretty(term)}
        for name, term in state.solutions.items()}
    summary["library"] = {
        name: {"term": term.to_dict(), "readable": pretty(term)}
        for name, term in state.grammar.library.items()}
    summary["heuristic"] = (None if state.heuristic is None else
                            {"term": state.heuristic.to_dict(), "readable": pretty(state.heuristic)})
    summary["heuristic_history"] = [
        {"generation": report["generation"], "term": report["best_term"],
         "readable": _readable(report["best_term"]),
         "validation_solved_fraction": report["best_full_fraction"]}
        for report in state.heuristic_history if report["adopted"]]
    summary["recognition"] = (None if state.recognition is None else state.recognition.to_dict())
    return summary


def _readable(record):
    from .terms import Term
    return pretty(Term.from_dict(record))


def measured(call, *args, **kwargs):
    started, cpu_started = time.perf_counter(), time.process_time()
    report = call(*args, **kwargs)
    return {**report, "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started}


def vocabulary_comparison(primitive, current):
    if (primitive["synthesis_candidate_evaluations"] != 6
            or current["synthesis_candidate_evaluations"] != 6
            or primitive["incumbent"] != current["incumbent"]):
        raise RuntimeError("final vocabulary comparison did not share incumbent and six-slot quotas")
    return {"generation": current["generation"], "primary": "validation_solved_fraction",
            "library_best": current["best_full_fraction"],
            "primitives_best": primitive["best_full_fraction"], "quota": 6,
            "primitive_only": primitive}


def run_arm(arm, seed, config, output, *, progress=None, reserved=False):
    """One independent run; only public TRAIN/VALIDATION enter learning APIs."""
    config = validate_config(config)
    if arm not in config["arms"] or seed not in config["seeds"]:
        raise ValueError("arm or seed is outside the preregistered experiment")
    path = result_path(output, arm, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if (not reserved or previous != initial_record(arm, seed, config)):
            raise FileExistsError(f"refusing to rerun an existing experiment: {path}")
    record = initial_record(arm, seed, config, "running")
    started, cpu_started = time.perf_counter(), time.process_time()
    state = None

    def checkpoint(status):
        record["status"] = status
        record["final_state"] = final_state(state) if state is not None else None
        record["totals"] = {
            "candidate_evaluations": state.logical_evaluations if state is not None else 0,
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started}
        atomic_write(path, record)

    checkpoint("running")
    try:
        train, validation, testtasks = load_partitions()
        state = learning.State(seed, heuristic=heuristics.zero_heuristic())
        budget = config["B_eval"] * (config["M"] if arm == "BRUTE" else 1)
        for generation in range(config["generations"] + 1):
            frozen = generation > 0 and (arm in ("BASE", "BRUTE")
                                         or (arm == "ONESHOT" and generation > 1))
            if frozen:
                source = 1 if arm == "ONESHOT" else 0
                prior = record["generations"][source]
                row = {"generation": generation,
                       "validation": copy.deepcopy(prior["validation"]),
                       "test": copy.deepcopy(prior["test"]),
                       "reused_measurement": True, "reuse_source_generation": source,
                       "learning": None, "heuristic": None}
            else:
                learned = improved = None
                comparison = None
                record["in_progress"] = {"generation": generation, "learning": None,
                                         "heuristic": None, "validation": None}
                if generation > 0:
                    learned = learning.wake_sleep(
                        state, train, config, library_learning=arm != "NO_LIBRARY",
                        recognition_learning=arm != "NO_RECOGNITION")
                    if state.generation != generation:
                        raise RuntimeError("learner advanced to an unexpected generation")
                    record["in_progress"]["learning"] = learned
                    checkpoint("running")
                    if arm != "NO_HEURISTIC":
                        primitive = None
                        if arm == "FULL" and generation == config["generations"]:
                            primitive = heuristics.improve_heuristic(
                                state, validation, config, primitive_only=True, update_state=False)
                            # This measurement deliberately cannot update the learner.
                            # Its actual proposals and inner searches still cost FULL work.
                            state.logical_evaluations += primitive["candidate_evaluations"]
                            record["in_progress"]["primitive_only"] = primitive
                            checkpoint("running")
                        improved = heuristics.improve_heuristic(
                            state, validation, config, primitive_only=False, update_state=True)
                        record["in_progress"]["heuristic"] = improved
                        if primitive is not None:
                            comparison = vocabulary_comparison(primitive, improved)
                            record["in_progress"]["comparison"] = comparison
                        checkpoint("running")
                validation_report = measured(learning.assess_development, state, validation,
                                             budget, config["search"])
                state.logical_evaluations += validation_report["candidate_evaluations"]
                record["in_progress"]["validation"] = validation_report
                checkpoint("running")
                # TEST is reporting only. No learning call receives this partition
                # or this report, and no control flow inspects its solved fraction.
                test_report = measured(sealed_evaluation.report, testtasks, state.grammar,
                                       state.heuristic, budget, config["search"],
                                       conditioner=state.condition)
                state.logical_evaluations += test_report["candidate_evaluations"]
                row = {"generation": generation, "validation": validation_report,
                       "test": test_report, "reused_measurement": False,
                       "learning": learned, "heuristic": improved}
                if comparison is not None:
                    record["comparison"] = comparison
            record["generations"].append(row)
            row["state"] = final_state(state)
            record.pop("in_progress", None)
            checkpoint("running")
            if progress is not None:
                progress(arm, seed, generation)
        checkpoint("complete")
        return record
    except BaseException as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["accounting"] = {"candidate_evaluations_scope": "completed_operations_lower_bound"}
        checkpoint("failed")
        raise


def _worker(arm, seed, config, output, events):
    try:
        run_arm(arm, seed, config, output, reserved=True,
                progress=lambda a, s, g: events.put(("generation", a, s, g)))
        events.put(("complete", arm, seed, time.process_time()))
    except BaseException as exc:
        events.put(("failed", arm, seed, time.process_time(), f"{type(exc).__name__}: {exc}"))
        raise


def process_cpu_seconds(pid):
    """Linux process CPU; tolerate workers that exit between observation and read."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        fields = stat[stat.rfind(")") + 2:].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (FileNotFoundError, ProcessLookupError):
        return 0.0


def stop_unfinished(output, jobs, reason, observed_cpu=None, observed_wall=None):
    """Keep completed runs, label active runs partial, leave queued runs unrun."""
    for arm, seed in jobs:
        path = result_path(output, arm, seed)
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["status"] == "running":
            record["status"] = "partial"
            record["stop_reason"] = reason
            record["totals"]["cpu_seconds"] = max(
                record["totals"]["cpu_seconds"], (observed_cpu or {}).get((arm, seed), 0.0))
            record["totals"]["wall_seconds"] = max(
                record["totals"]["wall_seconds"], (observed_wall or {}).get((arm, seed), 0.0))
            record["accounting"] = {
                "candidate_evaluations_scope": "completed_operations_lower_bound",
                "cpu_seconds_scope": "observed_process_cpu_before_termination"}
            atomic_write(path, record)


def schedule(config, output, workers):
    """At most five processes, with an aggregate CPU guard independent of scores."""
    config = validate_config(config)
    if type(workers) is not int or not 1 <= workers <= config["max_workers"]:
        raise ValueError("workers must be between one and five")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError("experiment output must be empty; existing TEST runs cannot be rerun")
    jobs = [(arm, seed) for arm in config["arms"] for seed in config["seeds"]]
    for arm, seed in jobs:
        atomic_write(result_path(output, arm, seed), initial_record(arm, seed, config))
    context = multiprocessing.get_context("spawn")
    events = context.Queue()
    pending, active, active_started, finished_cpu = list(jobs), {}, {}, {}
    started, cpu_started = time.perf_counter(), time.process_time()
    reason = None
    peak_cpu = 0.0
    try:
        while pending or active:
            while pending and len(active) < workers:
                arm, seed = pending.pop(0)
                process = context.Process(target=_worker, args=(arm, seed, config, output, events))
                process.start()
                active[(arm, seed)] = process
                active_started[(arm, seed)] = time.perf_counter()
            try:
                event = events.get(timeout=1.0)
                kind, arm, seed = event[:3]
                if kind == "generation":
                    print(f"{arm} seed={seed} generation={event[3]} checkpoint saved", flush=True)
                else:
                    finished_cpu[(arm, seed)] = event[3]
                    if kind == "failed":
                        reason = f"core experiment failure in {arm} seed={seed}: {event[4]}"
            except queue.Empty:
                pass
            current_cpu = (time.process_time() - cpu_started + sum(finished_cpu.values())
                           + sum(process_cpu_seconds(process.pid)
                                 for key, process in active.items() if key not in finished_cpu))
            peak_cpu = max(peak_cpu, current_cpu)
            if current_cpu >= config["cpu_limit_seconds"]:
                reason = "aggregate CPU limit reached"
            for key, process in list(active.items()):
                if process.is_alive():
                    continue
                process.join()
                record = json.loads(result_path(output, *key).read_text(encoding="utf-8"))
                finished_cpu.setdefault(key, record["totals"]["cpu_seconds"])
                if process.exitcode != 0 or record["status"] != "complete":
                    reason = reason or f"core experiment failure in {key[0]} seed={key[1]}"
                del active[key]
            if reason:
                break
    except BaseException as exc:
        reason = f"controller stopped: {type(exc).__name__}: {exc}"
        raise
    finally:
        observed_cpu = {key: process_cpu_seconds(process.pid) for key, process in active.items()}
        observed_wall = {key: time.perf_counter() - active_started[key] for key in active}
        peak_cpu = max(peak_cpu, time.process_time() - cpu_started
                       + sum(finished_cpu.values())
                       + sum(value for key, value in observed_cpu.items() if key not in finished_cpu))
        for process in active.values():
            if process.is_alive():
                process.terminate()
        for process in active.values():
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
        if reason:
            stop_unfinished(output, jobs, reason, observed_cpu, observed_wall)
        records = [json.loads(result_path(output, *job).read_text(encoding="utf-8")) for job in jobs]
        summary = {"status": "partial" if reason else "complete", "stop_reason": reason,
                   "config": config, "workers": workers,
                   "runs": [{"arm": r["arm"], "seed": r["seed"], "status": r["status"]}
                            for r in records],
                   "totals": {"candidate_evaluations": sum(r["totals"]["candidate_evaluations"]
                                                           for r in records),
                              "wall_seconds": time.perf_counter() - started,
                              "cpu_seconds": max(peak_cpu, sum(r["totals"]["cpu_seconds"]
                                                                for r in records))}}
        if reason:
            summary["accounting"] = {
                "candidate_evaluations_scope": "completed_operations_lower_bound",
                "cpu_seconds_scope": "observed_process_cpu"}
        atomic_write(output / "execution_summary.json", summary)
        events.close()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("rsi2/results"))
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("experiment_config.json"))
    args = parser.parse_args()
    summary = schedule(load_config(args.config), args.output, args.workers)
    print(json.dumps({"status": summary["status"], "totals": summary["totals"],
                      "stop_reason": summary["stop_reason"]}), flush=True)
    if summary["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
