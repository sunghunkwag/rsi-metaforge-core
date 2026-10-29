"""Long-horizon runner: one TRAIN trajectory per arm, every seed's VALIDATION, checkpoints.

    python -m rsi3.longrun --config rsi3/experiment_config_long.json \\
        --arm RSI3_UNIFORM_FM_INVP --output DIR [--max-minutes 100]

Why a separate runner. In the uniform, prior-only arms (RSI3_UNIFORM_FM and
its invention variants) the wake phase never reads the recognition model:
every window searches the prior pathway (or the invented pathway), whose
grammar does not depend on recognition. The seed enters a run only through
the sleep phase's dreams and recognition model, which these arms use only to
measure VALIDATION. Their TRAIN trajectory is therefore identical for every
seed (observed in every committed run of these arms). This runner computes
that trajectory once with the first seed and, after each generation, refits
each other seed's dreams and recognition model exactly as RSI-2's sleep would
have, on the same solutions and grammar, then measures that seed's
VALIDATION. The per-seed records have the same schema as ``rsi3.experiment``'s
and are checked against committed 12-generation runs
(``tests/test_longrun.py`` and LONG_RESULTS.md).

Searches are always compact (released between windows and rebuilt by
fast-forwarding), so the runtime holds no generator and can be checkpointed
after every generation. A job stops cleanly after the generation in which
``--max-minutes`` is exceeded and resumes from its checkpoint when run again
with the same arguments.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import copy
import json
from pathlib import Path
import pickle
import random
import time

from rsi2.corpus import load_train, load_validation
from rsi2.learning import dream_pairs
from rsi2.measurement import assess
from rsi2.recognition import Recognition
from rsi2.terms import pretty

from .experiment import ARMS
from .loop import Runtime


def shared_trajectory_ok(arm) -> bool:
    return (arm.allocation in ("uniform", "meta") and tuple(arm.designer_kinds) == ("prior",)
            and not arm.genesis and arm.continuity == "off")


def seed_recognition(state, public, config: dict, seed: int, generation: int):
    """The dreams and recognition model RSI-2's sleep would fit for ``seed``."""
    search = config["search"]
    rng = random.Random(seed * 1000003 + generation)
    dreams, evaluations = dream_pairs(public, state.grammar, rng, count=config.get("dreams", 16),
                                      max_size=search["max_size"],
                                      step_budget=search["step_budget"])
    lookup = {task.name: task for task in public}
    pairs = [(lookup[name], term) for name, term in state.solutions.items()] + dreams
    model = Recognition(seed * 1000003 + generation)
    metrics = model.fit(pairs, state.grammar)
    return model, {"dreams": len(dreams), "dream_candidate_evaluations": evaluations,
                   "recognition_examples": metrics["examples"]}


def validation_record(state, model, validation, config: dict) -> dict:
    conditioner = None if model is None else (lambda task, grammar: model.grammar_for(task, grammar))
    result = assess(validation, state.grammar, None, config["B_eval"], config["search"],
                    conditioner=conditioner)
    return {"solved": result["solved"], "tasks": result["tasks"],
            "solved_names": [r["name"] for r in result["records"] if r["solved"]],
            "candidate_evaluations": result["candidate_evaluations"]}


def agent_validation(runtime, model, validation, config: dict, verifier,
                     generation: int) -> dict:
    """Transfer test: the arm's own TRAIN-trained solver on unseen VALIDATION tasks.

    Same budget as VALIDATION (B_eval per task). Actions: the prior,
    recognition-conditioned exactly as in RSI-2's ``assess``, plus, for arms
    that decompose, every skeleton the task's public examples fit, searched
    with the adopted library, and for arms with behavioural search, its
    problems for the task (behave.py), built from the adopted library. The arm's own policy decides how the budget is
    spent: the meta-policy for meta arms (applied, never trained, on these
    tasks), a fixed split otherwise. One verifier query per task. For an arm
    that only searches the prior this equals VALIDATION exactly.
    """
    from .decompose import skeletons_for
    from .metarl import context, shape_features
    from .resumable import ResumableSearch
    search = config["search"]
    budget, chunk = config["B_eval"], int(config.get("meta", {}).get("chunk", 16))
    arm = runtime.arm
    decomposes = arm.decomposition_split > 0 or arm.allocation == "meta"
    solved, records = [], []
    library = runtime.state.grammar.library
    for task in validation:
        public = runtime_public(task)
        prior_grammar = (runtime.state.grammar if model is None
                         else model.grammar_for(public, runtime.state.grammar))
        searches = {"prior": ResumableSearch(public.examples, public.request_type,
                                             prior_grammar, **search)}
        if decomposes:
            for sk in skeletons_for(public.examples, arm.decomposition_fold):
                searches[f"decompose:{sk.name}"] = ResumableSearch(
                    public.examples, sk.hole_type, runtime.state.grammar, compose=sk.compose,
                    **search)
        if getattr(arm, "behave", False):
            from .behave import BehaviouralSearch, problems_for
            settings = config.get("behave", {})
            problems = problems_for(public.examples, public.request_type,
                                    skeletons_for(public.examples, False),
                                    int(settings.get("max_unroll", 6)))
            for kind, problem in problems.items():
                searches[f"behave:{kind}"] = BehaviouralSearch(
                    problem, library if arm.behave_library else {}, public.examples,
                    step_budget=search["step_budget"],
                    max_size=int(settings.get("max_size", 10)),
                    combo_limit=int(settings.get("combo_limit", 2_000_000)),
                    weights=runtime.state.grammar.weights if arm.behave_library else None)
        found, spent, used_by = None, 0, {}
        if runtime.metapolicy is not None:
            shape, history = shape_features(public.examples, arm.meta_extended), {}
            while spent < budget and found is None:
                live = [a for a, s in searches.items() if not s.exhausted]
                if not live:
                    break
                action = runtime.metapolicy.choose(live, shape, history, sum(history.values()))
                window = min(chunk, budget - spent)
                result = searches[action].run(window)
                spent += max(result.evaluated, 1)
                history[action] = history.get(action, 0) + 1
                used_by[action] = used_by.get(action, 0) + result.evaluated
                found = result.term
        else:
            skeleton_ids = [a for a in searches if a != "prior"]
            share = int(budget * arm.decomposition_split) if skeleton_ids else 0
            plan = [("prior", budget - share)] + [
                (a, share // len(skeleton_ids) + (1 if i < share % len(skeleton_ids) else 0))
                for i, a in enumerate(skeleton_ids)]
            for action, window in plan:
                if found is None and window:
                    result = searches[action].run(window)
                    used_by[action] = result.evaluated
                    found = result.term
        verdict = False
        if found is not None:
            verdict = verifier.verify(task.name, found, library, generation).verdict
        if verdict:
            solved.append(task.name)
        records.append({"name": task.name, "solved": verdict, "spent": used_by})
    return {"solved": len(solved), "solved_names": solved, "tasks": records}


def runtime_public(task):
    from .verifier import public_view
    return public_view(task)


def final_record(runtime) -> dict:
    return {"train_solved": len(runtime.state.solutions),
            "solutions": sorted(runtime.state.solutions),
            "provenance": runtime.integrator.provenance,
            "pathways": {pid: p.to_record() for pid, p in runtime.registry.pathways.items()},
            "memory": {"episodes": len(runtime.memory.episodes),
                       "verified": sum(e.outcome == "verified" for e in runtime.memory.episodes),
                       "rejected": sum(e.outcome == "rejected" for e in runtime.memory.episodes)},
            "verifier_queries": runtime.verifier.queries,
            "failure_memory": (None if runtime.failures is None else runtime.failures.sizes()),
            "library": {name: pretty(term)
                        for name, term in sorted(runtime.state.grammar.library.items())},
            "adopted_concepts": runtime.adopted_concepts}


def run(arm_name: str, config: dict, output: Path, max_minutes: float | None = None, *,
        train=None, validation=None, skip_validation: bool = False) -> bool:
    """Advance the job; return True when all generations are done.

    ``train`` and ``validation`` default to the corpus splits (tests pass subsets).
    ``skip_validation`` runs TRAIN only and never loads VALIDATION: for
    development runs, so that VALIDATION outcomes stay unseen until the
    registered runs.
    """
    arm = ARMS[arm_name]
    if not shared_trajectory_ok(arm):
        raise SystemExit(f"{arm_name} reads recognition during wake; use rsi3.experiment")
    seeds = list(config["seeds"])
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / f"{arm_name}.checkpoint.pkl"
    wall_started = time.perf_counter()
    train = load_train() if train is None else train
    if skip_validation:
        validation = []
    elif validation is None:
        validation = load_validation()
    rsi2_config = {"B_wake": config["B_wake"], "B_eval": config["B_eval"],
                   "dreams": config["dreams"], "search": dict(config["search"])}
    run_config = dict(config, compact_searches=True)
    if checkpoint.exists():
        with checkpoint.open("rb") as handle:
            saved = pickle.load(handle)
        runtime, records, cpu = saved["runtime"], saved["records"], saved["cpu"]
    else:
        runtime = Runtime(seeds[0], train, arm,
                          rsi2_config | {"controller": config["controller"],
                                         "continuity": config.get("continuity", {}),
                                         "invention": config.get("invention", {}),
                                         "compact_searches": True,
                                         "meta": config.get("meta", {}),
                                         "behave": config.get("behave", {})})
        records, cpu = {seed: [] for seed in seeds}, {seed: 0.0 for seed in seeds}
    from .verifier import FrozenVerifier
    agent_verifiers = {seed: FrozenVerifier(validation, step_budget=config["search"]["step_budget"])
                       for seed in seeds}
    while len(records[seeds[0]]) < config["generations"]:
        started = time.process_time()
        record = runtime.generation()
        generation = record["generation"]
        shared = time.process_time() - started
        for seed in seeds:
            seed_started = time.process_time()
            seed_record = copy.deepcopy(record)
            if skip_validation:
                seed_record["validation"] = seed_record["validation_agent"] = None
                records[seed].append(seed_record)
                cpu[seed] += shared
                continue
            if seed == seeds[0]:
                model = runtime.state.recognition
            else:
                model, sleep = seed_recognition(runtime.state, runtime.public, rsi2_config,
                                                seed, generation)
                seed_record["sleep"].update(sleep)
            seed_record["validation"] = validation_record(runtime.state, model, validation,
                                                          rsi2_config)
            seed_record["validation_agent"] = agent_validation(
                runtime, model, validation, rsi2_config | {"meta": config.get("meta", {}),
                                                           "behave": config.get("behave", {})},
                agent_verifiers[seed], generation)
            seed_record["cpu_seconds"] = record["cpu_seconds"] + (
                time.process_time() - seed_started)
            records[seed].append(seed_record)
            cpu[seed] += shared + (time.process_time() - seed_started)
        temporary = checkpoint.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump({"runtime": runtime, "records": records, "cpu": cpu}, handle)
        temporary.replace(checkpoint)
        print(f"{arm_name} generation {generation}: TRAIN {record['train_solved']}, "
              f"VALIDATION {[(records[s][-1]['validation'] or {}).get('solved') for s in seeds]}, "
              f"cpu {shared:.0f}s", flush=True)
        if max_minutes is not None and time.perf_counter() - wall_started > 60 * max_minutes:
            if len(records[seeds[0]]) < config["generations"]:
                return False
    final = final_record(runtime)
    for seed in seeds:
        path = output / f"{arm_name}_seed{seed}.json"
        payload = {"arm": arm_name, "seed": seed, "config": run_config, "status": "complete",
                   "generations": records[seed], "final": final, "cpu_seconds": cpu[seed],
                   "shared_trajectory": {"primary_seed": seeds[0], "seeds": seeds}}
        path.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-minutes", type=float, default=None)
    parser.add_argument("--generations", type=int, default=None,
                        help="checks against shorter committed runs only")
    parser.add_argument("--seeds", type=str, default=None,
                        help="comma-separated seeds overriding the config (development)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="TRAIN only; VALIDATION is never loaded (development)")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.generations is not None:
        config["generations"] = args.generations
    if args.seeds is not None:
        config["seeds"] = [int(x) for x in args.seeds.split(",")]
    done = run(args.arm, config, args.output, args.max_minutes,
               skip_validation=args.skip_validation)
    print(json.dumps({"arm": args.arm, "complete": done}))


if __name__ == "__main__":
    main()
