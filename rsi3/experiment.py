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
from dataclasses import replace
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
    # Compounding study: concepts searched in their own pathway at full weight
    # with half of each task's budget; the prior pathway is left undiluted.
    "RSI3_UNIFORM_FM_INVP": ArmConfig("RSI3_UNIFORM_FM_INVP", allocation="uniform",
                                      genesis=False, designer_kinds=("prior",),
                                      failure_memory=True, invention=True,
                                      invention_split=0.5),
    # Self-directed arm: INVP plus near-miss parts (structure from programs
    # that almost solved an unsolved task) and a meta-learned inventor (the
    # share of proposal slots per kind follows that kind's adoption record).
    "RSI3_UNIFORM_FM_INVX": ArmConfig("RSI3_UNIFORM_FM_INVX", allocation="uniform",
                                      genesis=False, designer_kinds=("prior",),
                                      failure_memory=True, invention=True,
                                      invention_split=0.5, invention_near_misses=True,
                                      invention_meta=True),
    # Backward decomposition (decompose.py, ported from verified-code-rsi):
    # alone, and with every self-directed mechanism.
    "RSI3_UNIFORM_FM_DEC": ArmConfig("RSI3_UNIFORM_FM_DEC", allocation="uniform", genesis=False,
                                     designer_kinds=("prior",), failure_memory=True,
                                     decomposition_split=0.5),
    "RSI3_UNIFORM_FM_INVXD": ArmConfig("RSI3_UNIFORM_FM_INVXD", allocation="uniform",
                                       genesis=False, designer_kinds=("prior",),
                                       failure_memory=True, invention=True,
                                       invention_split=1 / 3, invention_near_misses=True,
                                       invention_meta=True, decomposition_split=1 / 3),
    # Meta-RL study (PREDICTIONS_METARL.md): every mechanism, with a meta-learned
    # policy choosing prior / invented / skeleton chunks inside each task's
    # share (metarl.py), and its wiped-memory control.
    "RSI3_META": ArmConfig("RSI3_META", allocation="meta", genesis=False,
                           designer_kinds=("prior",), failure_memory=True, invention=True,
                           invention_near_misses=True, invention_meta=True),
    "RSI3_META_WIPE": ArmConfig("RSI3_META_WIPE", allocation="meta", genesis=False,
                                designer_kinds=("prior",), failure_memory=True, invention=True,
                                invention_near_misses=True, invention_meta=True,
                                meta_wipe=True),
    # Fold-cascade study: RSI3_META plus fold (catamorphism) skeletons.
    "RSI3_META_FOLD": ArmConfig("RSI3_META_FOLD", allocation="meta", genesis=False,
                                designer_kinds=("prior",), failure_memory=True, invention=True,
                                invention_near_misses=True, invention_meta=True,
                                decomposition_fold=True),
    # Self-play meta-RL: RSI3_META_FOLD plus relation features and imagined
    # tasks that give the policy dense training signal.
    "RSI3_META_PLAY": ArmConfig("RSI3_META_PLAY", allocation="meta", genesis=False,
                                designer_kinds=("prior",), failure_memory=True, invention=True,
                                invention_near_misses=True, invention_meta=True,
                                decomposition_fold=True, meta_extended=True,
                                meta_selfplay=True),
    # Problem transformation: RSI3_META_PLAY plus conjugate skeletons.
    "RSI3_META_CONJ": ArmConfig("RSI3_META_CONJ", allocation="meta", genesis=False,
                                designer_kinds=("prior",), failure_memory=True, invention=True,
                                invention_near_misses=True, invention_meta=True,
                                decomposition_fold=True, meta_extended=True,
                                meta_selfplay=True, decomposition_conjugate=True),
    # Behavioural-search study (PREDICTIONS_BEHAVE.md): RSI3_META_CONJ plus
    # behavioural search (behave.py) as meta-RL actions, building from the
    # system's own library and ordered by its fitted grammar; and the same
    # search from RSI-2's primitives only (the designer-only control).
    "RSI3_META_BEH": ArmConfig("RSI3_META_BEH", allocation="meta", genesis=False,
                               designer_kinds=("prior",), failure_memory=True, invention=True,
                               invention_near_misses=True, invention_meta=True,
                               decomposition_fold=True, meta_extended=True,
                               meta_selfplay=True, decomposition_conjugate=True, behave=True),
    "RSI3_META_BEH_BASE": ArmConfig("RSI3_META_BEH_BASE", allocation="meta", genesis=False,
                                    designer_kinds=("prior",), failure_memory=True,
                                    invention=True, invention_near_misses=True,
                                    invention_meta=True, decomposition_fold=True,
                                    meta_extended=True, meta_selfplay=True,
                                    decomposition_conjugate=True, behave=True,
                                    behave_library=False),
    # Fold follow-up (PREDICTIONS_BEHAVE_FOLD.md): RSI3_META_BEH plus the
    # behavioural fold action (closed steps folded over pool lists).
    "RSI3_META_BEH_FOLD": ArmConfig("RSI3_META_BEH_FOLD", allocation="meta", genesis=False,
                                    designer_kinds=("prior",), failure_memory=True,
                                    invention=True, invention_near_misses=True,
                                    invention_meta=True, decomposition_fold=True,
                                    meta_extended=True, meta_selfplay=True,
                                    decomposition_conjugate=True, behave=True,
                                    behave_folds=True),
    # Honest self-play (PREDICTIONS_HONEST.md): RSI3_META_BEH_FOLD, with every
    # action credited by its actual one-chunk outcome on the imagined task.
    "RSI3_META_HONEST": ArmConfig("RSI3_META_HONEST", allocation="meta", genesis=False,
                                  designer_kinds=("prior",), failure_memory=True,
                                  invention=True, invention_near_misses=True,
                                  invention_meta=True, decomposition_fold=True,
                                  meta_extended=True, meta_selfplay=True,
                                  decomposition_conjugate=True, behave=True,
                                  behave_folds=True, selfplay_honest=True),
    # Portfolio (PREDICTIONS_PORTFOLIO.md): RSI3_META_HONEST, with every
    # behavioural problem also offered from RSI-2's primitives only, and a
    # fixed-output-length flag in the policy's task shape.
    "RSI3_META_PORTFOLIO": ArmConfig("RSI3_META_PORTFOLIO", allocation="meta", genesis=False,
                                     designer_kinds=("prior",), failure_memory=True,
                                     invention=True, invention_near_misses=True,
                                     invention_meta=True, decomposition_fold=True,
                                     meta_extended=True, meta_selfplay=True,
                                     decomposition_conjugate=True, behave=True,
                                     behave_folds=True, selfplay_honest=True,
                                     behave_dual=True, meta_fixed_length=True),
    # Dream practice (PREDICTIONS_DREAM.md): RSI3_META_HONEST, also
    # practising every action on dreams from the system's own grammar.
    "RSI3_META_DREAM": ArmConfig("RSI3_META_DREAM", allocation="meta", genesis=False,
                                 designer_kinds=("prior",), failure_memory=True,
                                 invention=True, invention_near_misses=True,
                                 invention_meta=True, decomposition_fold=True,
                                 meta_extended=True, meta_selfplay=True,
                                 decomposition_conjugate=True, behave=True,
                                 behave_folds=True, selfplay_honest=True,
                                 selfplay_dreams=True),
    # Hard-dream practice: dreams the prior finds in one chunk are skipped.
    "RSI3_META_DREAM_HARD": ArmConfig("RSI3_META_DREAM_HARD", allocation="meta", genesis=False,
                                      designer_kinds=("prior",), failure_memory=True,
                                      invention=True, invention_near_misses=True,
                                      invention_meta=True, decomposition_fold=True,
                                      meta_extended=True, meta_selfplay=True,
                                      decomposition_conjugate=True, behave=True,
                                      behave_folds=True, selfplay_honest=True,
                                      selfplay_dreams=True, selfplay_dreams_hard=True),
}
# Exact-control variants: replace only the action policy's update rule.
ARMS["RSI3_META_HONEST_DUST"] = replace(
    ARMS["RSI3_META_HONEST"], name="RSI3_META_HONEST_DUST", meta_dust=True)
ARMS["RSI3_META_PORTFOLIO_DUST"] = replace(
    ARMS["RSI3_META_PORTFOLIO"], name="RSI3_META_PORTFOLIO_DUST", meta_dust=True)

# Contrastive DUST receives exactly the same synthetic tasks and success labels,
# but downweights non-discriminative action outcomes within each task.
ARMS["RSI3_META_HONEST_DUST_CONTRAST"] = replace(
    ARMS["RSI3_META_HONEST_DUST"], name="RSI3_META_HONEST_DUST_CONTRAST",
    meta_dust_contrastive=True)
ARMS["RSI3_META_PORTFOLIO_DUST_CONTRAST"] = replace(
    ARMS["RSI3_META_PORTFOLIO_DUST"], name="RSI3_META_PORTFOLIO_DUST_CONTRAST",
    meta_dust_contrastive=True)

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
                                         "invention": config.get("invention", {}),
                                         "compact_searches": config.get("compact_searches",
                                                                        False)})
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
    parser.add_argument("--compact-searches", action="store_true",
                        help="release live searches between windows and rebuild them by "
                             "fast-forwarding; bounds memory, same logical behaviour "
                             "(recorded in each run's config)")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.generations is not None:
        config["generations"] = args.generations
    if args.compact_searches:
        config["compact_searches"] = True
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
