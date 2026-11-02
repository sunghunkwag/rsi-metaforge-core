"""The registered SWARM arms, run at identical per-generation logical budgets (OWNER_DIRECTIVE.md §7).

    export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
    python -m swarm.experiment --config swarm/experiment_config.json --output NEW_DIR
    python -m swarm.experiment --config swarm/pilot_config.json --output NEW_DIR --minutes 30   # pilot

One job per (arm, seed); each job writes ``<output>/<arm>_seed<seed>/``
with the ledger, the kernel-only vault dump, the archive, the snapshot
store and ``summary.json``. ``--minutes`` caps a job's wall clock (pilots);
registered runs use the config's ``generations``. The runner refuses to
overwrite a non-empty output directory.
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

from .loop import ARMS, Run


def run_one(arm: str, seed: int, config: dict, output: Path, minutes: float | None = None) -> dict:
    run = Run(ARMS[arm], seed, config, Path(output) / f"{arm}_seed{seed}")

    def log(summary):
        print(f"{arm} seed {seed} g{summary['generation']}: archive {summary['archive']['total']} "
              f"(open {summary['archive']['open']}, crossed {summary['archive']['crossed']}), "
              f"X={summary['crossings_cumulative']} (+{summary['crossings']}), "
              f"edits {summary['self_edits']['adopted']}/{summary['self_edits']['proposed']}, "
              f"forged {summary['primitives_forged']}, library {summary['library_entries']}, "
              f"builder {summary['budget']['builder']['evaluations']} cand, "
              f"{time.perf_counter() - run.wall_started:.0f}s", flush=True)

    return run.run(config["generations"], None if minutes is None else minutes * 60.0, log=log)


def _job(arm, seed, config, output, minutes):
    summary = run_one(arm, seed, config, output, minutes)
    return arm, seed, summary["final"]["crossings"], len(summary["generations"]), summary["wall_seconds"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--arms", nargs="*", default=None)
    parser.add_argument("--seeds", nargs="*", type=int, default=None)
    parser.add_argument("--generations", type=int, default=None, help="pilots only; finals use the config")
    parser.add_argument("--minutes", type=float, default=None, help="wall-clock cap per job (pilots)")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.generations is not None:
        config["generations"] = args.generations
    arms = args.arms or config["arms"]
    seeds = args.seeds or config["seeds"]
    unknown = [arm for arm in arms if arm not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms: {unknown}")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(arm, seed) for seed in seeds for arm in arms]
    workers = args.workers or config.get("resources", {}).get("workers", 1)
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_job, arm, seed, config, str(args.output), args.minutes) for arm, seed in jobs]
        for future in futures:
            arm, seed, crossings, generations, wall = future.result()
            print(f"{arm} seed {seed}: {crossings} crossings in {generations} generations, {wall:.0f}s", flush=True)
    summary = {"jobs": len(jobs), "workers": workers, "elapsed_wall_seconds": time.perf_counter() - started,
               "config": config}
    (args.output / "execution_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "config"}))


if __name__ == "__main__":
    main()
