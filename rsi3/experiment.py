"""Registered RSI-3 arms, run at equal per-generation wake budgets.

Arms (see PREDICTIONS.md for what each one tests):

  RSI2             RSI-2's own ``wake_sleep``, unchanged: B_wake per TRAIN task,
                   every task retried from the start of its enumeration.
  RSI3             learned allocation, full replay, genesis, resumable search,
                   binding integrator.
  RSI3_NO_REPLAY   value model fit on the latest generation only.
  RSI3_NO_GENESIS  designer pathways only.
  RSI3_UNIFORM     resumable search on the prior pathway with an even budget
                   split over unsolved tasks; no value model, no genesis.
  RSI3_UNIFORM_FM  RSI3_UNIFORM plus failure memory (experiment_config_failure_memory.json).
  RSI3_FM          RSI3 plus failure memory.
  RSI3_UNIFORM_FM_SCM  RSI3_UNIFORM_FM, auditing each self-rewrite (passive, uncharged).
  RSI3_UNIFORM_FM_SC   RSI3_UNIFORM_FM, auditing and restoring lost abilities (charged)
                       (experiment_config_self_continuity.json).
  RSI3_UNIFORM_FM_INV  RSI3_UNIFORM_FM with self-model concept invention
                       (experiment_config_invention.json).

Every arm receives the same per-generation cap of B_wake x |TRAIN| logical
candidate evaluations, the same RSI-2 sleep phase, the same seeds, and the same
verification rate (one hidden-example query per task per generation).
VALIDATION is measured after every generation with RSI-2's own ``assess`` at
B_eval for reporting only; no arm reads it to decide anything. TEST is not
opened.

    export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
    python -m rsi3.experiment --config rsi3/experiment_config.json --output NEW_DIR
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time

from rsi2.corpus import load_train, load_validation
from rsi2.learning import State, wake_sleep
from rsi2.measurement import assess
from rsi2.terms import pretty

from .loop import ArmConfig, Runtime

ARMS = {
    "RSI3": ArmConfig("RSI3"),
    "RSI3_NO_REPLAY": ArmConfig("RSI3_NO_REPLAY", value_mode="latest"),
    "RSI3_NO_GENESIS": ArmConfig("RSI3_NO_GENESIS", genesis=False),
    "RSI3_UNIFORM": ArmConfig("RSI3_UNIFORM", allocation="uniform", genesis=False,
                              designer_kinds=("prior",)),
    # Failure-memory study (PREDICTIONS_FAILURE_MEMORY.md): the same two arms
    # with public failures carried across grammar changes and pathways.
    "RSI3_UNIFORM_FM": ArmConfig("RSI3_UNIFORM_FM", allocation="uniform", genesis=False,
                                 designer_kinds=("prior",), failure_memory=True),
    "RSI3_FM": ArmConfig("RSI3_FM", failure_memory=True),
    # Self-continuity study (PREDICTIONS_SELF_CONTINUITY.md): the best arm so
    # far, with the rewritten self audited (passive) or audited and restored.
    "RSI3_UNIFORM_FM_SCM": ArmConfig("RSI3_UNIFORM_FM_SCM", allocation="uniform", genesis=False,
                                     designer_kinds=("prior",), failure_memory=True,
                                     continuity="measure"),
    "RSI3_UNIFORM_FM_SC": ArmConfig("RSI3_UNIFORM_FM_SC", allocation="uniform", genesis=False,
                                    designer_kinds=("prior",), failure_memory=True,
                                    continuity="restore"),
    # Concept-invention study (PREDICTIONS_INVENTION.md): the same arm with a
    # self-model that invents library concepts from its own verified programs.
    "RSI3_UNIFORM_FM_INV": ArmConfig("RSI3_UNIFORM_FM_INV", allocation="uniform", genesis=False,
                                     designer_kinds=("prior",), failure_memory=True,
                                     invention=True),
}
BASELINE = "RSI2"


def _validation(state, validation, config) -> dict:
    result = assess(validation, state.grammar, None, config["B_eval"], config["search"],
                    conditioner=state.condition)
    return {"solved": result["solved"], "tasks": result["tasks"],
            "solved_names": [r["name"] for r in result["records"] if r["solved"]],
            "candidate_evaluations": result["candidate_evaluations"]}


def run_one(arm: str, seed: int, config: dict) -> dict:
    cpu_started, wall_started = time.process_time(), time.perf_counter()
    train, validation = load_train(), load_validation()
    rsi2_config = {"B_wake": config["B_wake"], "B_eval": config["B_eval"],
                   "dreams": config["dreams"], "search": dict(config["search"])}
    generations = []
    if arm == BASELINE:
        state = State(seed)
        for _ in range(config["generations"]):
            started = time.process_time()
            record = wake_sleep(state, train, rsi2_config)
            wake = record.pop("wake")
            generations.append({
                "generation": record["generation"], "train_solved": len(state.solutions),
                "wake": {"budget": config["B_wake"] * len(train),
                         "spent": record["wake_candidate_evaluations"],
                         "verified_this_generation": sum(w["hidden_verified"] for w in wake),
                         "spent_on_unsolved_after": sum(w["candidates"] for w in wake
                                                        if not w["has_solution"]),
                         "max_depth": max((w["candidates"] for w in wake), default=0)},
                "sleep": {"adopted_library": record["adopted_library"],
                          "library_entries": record["library_entries"],
                          "dream_candidate_evaluations": record["dream_candidate_evaluations"]},
                "validation": _validation(state, validation, rsi2_config),
                "cpu_seconds": time.process_time() - started})
        final = {"train_solved": len(state.solutions), "solutions": sorted(state.solutions)}
    else:
        runtime = Runtime(seed, train, ARMS[arm],
                          rsi2_config | {"controller": config["controller"],
                                         "continuity": config.get("continuity", {}),
                                         "invention": config.get("invention", {})})
        for _ in range(config["generations"]):
            record = runtime.generation()
            record["validation"] = _validation(runtime.state, validation, rsi2_config)
            generations.append(record)
        final = {"train_solved": len(runtime.state.solutions),
                 "solutions": sorted(runtime.state.solutions),
                 "provenance": runtime.integrator.provenance,
                 "pathways": {pid: p.to_record() for pid, p in runtime.registry.pathways.items()},
                 "memory": {"episodes": len(runtime.memory.episodes),
                            "verified": sum(e.outcome == "verified" for e in runtime.memory.episodes),
                            "rejected": sum(e.outcome == "rejected" for e in runtime.memory.episodes)},
                 "verifier_queries": runtime.verifier.queries,
                 "failure_memory": (None if runtime.failures is None
                                    else runtime.failures.sizes()),
                 "library": {name: pretty(term)
                             for name, term in sorted(runtime.state.grammar.library.items())},
                 "adopted_concepts": runtime.adopted_concepts}
    return {"arm": arm, "seed": seed, "config": config, "status": "complete",
            "generations": generations, "final": final,
            "cpu_seconds": time.process_time() - cpu_started,
            "wall_seconds": time.perf_counter() - wall_started}


def _job(arm, seed, config, output):
    record = run_one(arm, seed, config)
    path = Path(output) / f"{arm}_seed{seed}.json"
    path.write_text(json.dumps(record, indent=1, default=str) + "\n", encoding="utf-8")
    return arm, seed, record["final"]["train_solved"], record["cpu_seconds"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--arms", nargs="*", default=None)
    parser.add_argument("--seeds", nargs="*", type=int, default=None)
    parser.add_argument("--generations", type=int, default=None,
                        help="development smoke runs only; finals use the config value")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.generations is not None:
        config["generations"] = args.generations
    arms = args.arms or config["arms"]
    seeds = args.seeds or config["seeds"]
    unknown = [arm for arm in arms if arm != BASELINE and arm not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms: {unknown}")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(arm, seed) for seed in seeds for arm in arms]
    started = time.perf_counter()
    workers = args.workers or config.get("workers", 1)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_job, arm, seed, config, str(args.output)) for arm, seed in jobs]
        for future in futures:
            arm, seed, solved, cpu = future.result()
            print(f"{arm} seed {seed}: TRAIN solved {solved}/36, cpu {cpu:.1f}s", flush=True)
    summary = {"jobs": len(jobs), "workers": workers,
               "elapsed_wall_seconds": time.perf_counter() - started}
    (args.output / "execution_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
