"""Evaluate an arm's final solver on a held-out partition, from its run checkpoint.

    python -m rsi3.reserve_eval --checkpoint RUN_DIR/ARM.checkpoint.pkl \
        --config rsi3/experiment_config_X.json --partition near --output OUT.json

This is the same measurement ``longrun`` makes on VALIDATION at every
generation (``longrun.agent_validation``). It uses the final generation's
state and every seed's recognition model: seed one's is the run's own, and
the others are refitted exactly as ``longrun`` refits them. The policy is
applied and never trained, and each task gets one verifier query.

``--partition validation`` reproduces the run's recorded final
VALIDATION numbers. That is the harness's own check, and it adds no new
information.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pickle
import time

from rsi2.corpus import load_validation

from .longrun import agent_validation, seed_recognition
from .reserve import load_reserve
from .verifier import FrozenVerifier


def evaluate(checkpoint: Path, config: dict, partition: str) -> dict:
    saved = pickle.loads(checkpoint.read_bytes())
    runtime = saved["runtime"]
    tasks = load_validation() if partition == "validation" else load_reserve(partition)
    seeds = list(config["seeds"])
    generation = runtime.state.generation
    rsi2_config = {"B_wake": config["B_wake"], "B_eval": config["B_eval"],
                   "dreams": config["dreams"], "search": dict(config["search"])}
    results = {}
    for seed in seeds:
        started = time.process_time()
        if seed == seeds[0]:
            model = runtime.state.recognition
        else:
            model, _ = seed_recognition(runtime.state, runtime.public, rsi2_config, seed,
                                        generation)
        verifier = FrozenVerifier(tasks, step_budget=config["search"]["step_budget"])
        record = agent_validation(runtime, model, tasks,
                                  rsi2_config | {"meta": config.get("meta", {}),
                                                 "behave": config.get("behave", {})},
                                  verifier, generation)
        record["cpu_seconds"] = time.process_time() - started
        results[seed] = record
    return {"arm": runtime.arm.name, "partition": partition, "generation": generation,
            "tasks": len(tasks), "seeds": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--partition", choices=("near", "far", "validation"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = evaluate(args.checkpoint, config, args.partition)
    args.output.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"arm": result["arm"], "partition": args.partition,
                      "solved": {s: r["solved"] for s, r in result["seeds"].items()}}))


if __name__ == "__main__":
    main()
