"""Development-only A/B runner for RSI-3 curriculum vs behavioral novelty.

No held-out evaluator is consulted. Runs are exploratory, not registered
RSI-4 evidence. Keep the base configuration identical across both arms.

Usage:
  python -m rsi4.novelty_pilot --smoke
  python -m rsi4.novelty_pilot --generations 4 --output /tmp/novelty.json
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from rsi2.corpus import load_train
from rsi3.experiment import ARMS
from rsi3.loop import Runtime
from .novelty import NoveltyCurriculumRuntime


def run(config, *, seed=11, generations=1, train_limit=None, arms=("baseline", "novelty")):
    if generations <= 0:
        raise ValueError("generations must be positive")
    train = sorted(load_train(), key=lambda task: task.name)
    if train_limit is not None:
        train = train[:train_limit]
    results = {}
    arm = ARMS["RSI3_META_CURRICULUM"]
    for label in arms:
        cls = Runtime if label == "baseline" else NoveltyCurriculumRuntime
        runtime = cls(seed, train, arm, copy.deepcopy(config))
        trajectory = []
        for _ in range(generations):
            record = runtime.generation()
            details = record["sleep"].get("curriculum", {})
            trajectory.append({
                "generation": record["generation"],
                "train_solved": record["train_solved"],
                "logical_evaluations": runtime.state.logical_evaluations,
                "curriculum_evaluations": details.get("curriculum_evaluations", 0),
                "imagined": details.get("imagined", 0),
                "hard": details.get("hard", 0),
                "self_generated_solved": details.get("solved", 0),
                "novelty_archive": details.get("novelty_archive"),
                "novelty_mean": details.get("novelty_mean"),
            })
        results[label] = trajectory
    return {"status": "exploratory_only", "seed": seed, "generations": generations,
            "train_tasks": len(train), "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="rsi3/experiment_config_curriculum.json")
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--train-limit", type=int, default=None)
    parser.add_argument("--mode", choices=("baseline", "novelty", "both"), default="both")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.smoke:
        config.update({"B_wake": 8, "B_eval": 8, "dreams": 2,
                       "workers": 1, "compact_searches": True})
        config["curriculum"] = {"count": 6, "hard_chunk": 4, "solve": 3, "pool": 6}
        config["meta"] = dict(config.get("meta", {}), chunk=4, selfplay=8)
        if args.train_limit is None:
            args.train_limit = 8
    config["novelty"] = {"k": 10, "archive": 256}
    labels = ("baseline", "novelty") if args.mode == "both" else (args.mode,)
    report = run(config, seed=args.seed, generations=args.generations,
                 train_limit=args.train_limit, arms=labels)
    output = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
