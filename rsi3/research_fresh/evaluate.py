"""Evaluate a frozen RSI-3 TRAIN checkpoint on FRESH-COMPOSE-V1.

Usage:
    python -m rsi3.research_fresh.evaluate --checkpoint TRAIN_DIR/ARM.checkpoint.pkl \
      --config rsi3/experiment_config_fresh_transfer.json --output OUT.json

This runner must be invoked *only after* all TRAIN generations complete.
It does not call policy.fit, expose hidden examples to the learner, or
modify the state. Existing agent_validation routes all hidden checks
through FrozenVerifier. The comparator evaluates exactly the same 24
fixed task records and per-task candidate budget.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pickle
import time

from rsi3.longrun import agent_validation
from rsi3.verifier import FrozenVerifier
from .suite import BENCHMARK_ID, load_frozen_tasks, suite_sha256


def evaluate(checkpoint: Path, config: dict) -> dict:
    with checkpoint.open("rb") as handle:
        saved = pickle.load(handle)
    runtime = saved["runtime"]
    expected_generations = int(config["generations"])
    if runtime.state.generation != expected_generations:
        raise ValueError("training checkpoint is not frozen at the registered horizon")
    if runtime.verifier.queries < 1:
        raise ValueError("empty training checkpoint")
    if list(config["seeds"]) != [runtime.seed] if hasattr(runtime, "seed") else False:
        raise ValueError("evaluation seed differs from training seed")
    tasks = load_frozen_tasks()
    if len(tasks) != 24 or len({t.name for t in tasks}) != 24:
        raise ValueError("benchmark task count/uniqueness gate")
    # An independent new namespace prevents accidental training-task identity.
    if any(not t.name.startswith("fresh20261031::") for t in tasks):
        raise ValueError("unexpected benchmark namespace")
    frozen_training_solutions = tuple(sorted(runtime.state.solutions))
    n_training_episodes = len(runtime.metapolicy.episodes)
    verification = FrozenVerifier(tasks, step_budget=config["search"]["step_budget"])
    settings = {
        "B_eval": config["B_eval"],
        "search": config["search"],
        "meta": config.get("meta", {}),
        "behave": config.get("behave", {}),
    }
    started = time.process_time()
    record = agent_validation(runtime, runtime.state.recognition, tasks,
                              settings, verification, expected_generations)
    cpu_seconds = time.process_time() - started
    if tuple(sorted(runtime.state.solutions)) != frozen_training_solutions:
        raise RuntimeError("holdout evaluation unexpectedly modified learned solutions")
    if len(runtime.metapolicy.episodes) != n_training_episodes:
        raise RuntimeError("holdout evaluation unexpectedly trained the policy")
    if verification.queries > len(tasks):
        raise RuntimeError("holdout verifier exceeded one query per task")
    return {
        "benchmark": BENCHMARK_ID,
        "suite_sha256": suite_sha256(),
        "arm": runtime.arm.name,
        "training_seed": int(config["seeds"][0]),
        "generations": expected_generations,
        "candidate_budget_per_task": config["B_eval"],
        "tasks": len(tasks),
        "solved": record["solved"],
        "solved_names": record["solved_names"],
        "details": record["tasks"],
        "verifier_queries": verification.queries,
        "cpu_seconds": cpu_seconds,
        "training_checkpoint_frozen": True,
        "TRAIN_state_unchanged": True,
        "policy_replay_unchanged": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = evaluate(args.checkpoint, json.loads(args.config.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("FRESH_TRANSFER_RESULT", result["arm"], result["training_seed"],
          result["solved"], "/", result["tasks"],
          "cpu", round(result["cpu_seconds"], 3),
          "suite_sha256", result["suite_sha256"], flush=True)


if __name__ == "__main__":
    main()
