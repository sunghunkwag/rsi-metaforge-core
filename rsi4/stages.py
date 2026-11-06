"""The continual stream: TRAIN, then stages S1 -> S2 -> S3, with checkpoints and J's evaluations.

    python -m rsi4.stages --plan rsi4/runs/<name>.json --arm <ARM> --output DIR [--max-minutes M]

**The stream** (OWNER_DIRECTIVE.md §4). TRAIN (36 tasks) for 16 generations,
exactly as the base arm, then 8 generations on each stage's 36 stage-train
tasks (``rsi4/data/stage_train.json``), one verifier query per task per
generation. The logical budget is unchanged: B_wake = 64 per task of the
current task set.

**What "continued unchanged" means here.** ``StageRuntime`` is
``rsi3.loop.Runtime`` with three additions, none of which acts during TRAIN:

1. The frozen verifier is built over TRAIN and every stage-train task at
   construction (the stage-train tasks are fixed and committed before any
   run). During TRAIN it is only ever asked about TRAIN tasks, so receipts,
   query counts and the trajectory are those of rsi3's own runtime; a test
   checks the per-generation records against ``rsi3.longrun.run``.
2. ``begin_stage`` makes the stage's tasks the runtime's task set
   (``public``): the wake spends B_wake on each of them, and self-play
   imagines tasks on their public inputs. Everything the system holds is
   kept: solutions, library, concepts, grammar, recognition, the meta-policy
   and its full replay, episodic and failure memory. Per-task structures
   (skeletons, behavioural problems, probe inputs, shapes, the analogy index)
   are extended to the new tasks with the same functions rsi3 uses.
3. Sleep fits on every task the system has met (``sleep_public``: TRAIN and
   the stages so far), so abstraction, grammar fitting and recognition see
   every verified solution, as rsi3's sleep sees every TRAIN solution
   (replay, D1). During TRAIN ``sleep_public`` equals ``public``.

Earlier tasks are never searched again after their stage; forgetting is what
J measures on their stage-eval pools.

**Checkpoints.** After every generation (resumable), and a milestone after
TRAIN and after each stage (``<ARM>.after_<phase>.pkl``). After each
milestone J evaluates the learned solver on the three stage-eval pools:
R[i][j], i = 0 after TRAIN. After S3, J evaluates the final solver on the
plan's exposed partitions and on TRAIN and the stage-train sets (all
report-only).

**Isolation and cost.** Training runs in a spawned worker under the RSS
watchdog (3 GB); the worker installs ``guard`` before anything else. J runs
in its own process (``client``). CPU seconds and peak RSS are recorded per
run; J's own cost is logged separately by J.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import copy
import json
import multiprocessing
from pathlib import Path
import pickle
import resource
import subprocess
import sys
import time

from rsi3.loop import Runtime, sleep_phase, standardized_features
from rsi3.memory import EpisodicMemory
from rsi3.verifier import FrozenVerifier, public_view

PACKAGE = Path(__file__).resolve().parent
STAGE_FILE = PACKAGE / "data" / "stage_train.json"
STAGES = ("S1", "S2", "S3")
PHASES = ("TRAIN",) + STAGES
TIMING = ("cpu_seconds", "wall_seconds")


def load_stage_tasks(path: Path = STAGE_FILE) -> dict:
    """Stage-train tasks (hidden examples included, for the frozen verifier only)."""
    from rsi3.fresh import to_task
    stages = json.loads(Path(path).read_text(encoding="utf-8"))["stages"]
    return {name: [to_task(record) for record in stages[name]] for name in STAGES}


class StageRuntime(Runtime):
    """rsi3's Runtime, continued through stages (module docstring)."""

    def __init__(self, seed: int, train_tasks, arm, config: dict, stage_tasks: dict):
        super().__init__(seed, train_tasks, arm, config)
        everything = list(train_tasks) + [t for name in sorted(stage_tasks)
                                          for t in stage_tasks[name]]
        self.verifier = FrozenVerifier(everything, step_budget=config["search"]["step_budget"])
        self.memory = EpisodicMemory(self.verifier)
        self.sleep_public = list(self.public)
        self.stage = "TRAIN"
        self.stage_first_generation = {"TRAIN": 1}

    def begin_stage(self, name: str, tasks) -> dict:
        if self.arm.chain or self.arm.self_curriculum or self.arm.selfplay_dreams:
            raise NotImplementedError(f"{self.arm.name}: stage switching is not defined "
                                      "for chain, curriculum or dream-practice arms")
        from rsi3.integrator import probe_inputs
        from rsi3.metarl import shape_features
        new = [public_view(task) for task in tasks]
        known = {task.name for task in self.sleep_public}
        if known & {task.name for task in new}:
            raise ValueError(f"{name} repeats a task the system has met")
        self.public = new
        self.sleep_public = self.sleep_public + new
        self.features.update(standardized_features(new))
        registry = self.registry
        registry.tasks.update({task.name: task for task in new})
        for task in new:
            self.integrator.probes[task.name] = probe_inputs(task.examples)
            self.shapes[task.name] = shape_features(task.examples, self.arm.meta_extended,
                                                    self.arm.meta_fixed_length)
        if hasattr(registry, "skeletons"):
            from rsi3.decompose import skeletons_for
            from rsi3.pathways import Pathway
            for task in new:
                registry.skeletons[task.name] = {
                    sk.name: sk for sk in skeletons_for(task.examples, self.arm.decomposition_fold)}
                for sk in registry.skeletons[task.name]:
                    registry.pathways.setdefault(f"decompose:{sk}", Pathway(
                        f"decompose:{sk}", "decompose", "designer", 0, status="dormant"))
        if hasattr(registry, "behave_problems"):
            from rsi3.behave import problems_for
            from rsi3.decompose import skeletons_for
            from rsi3.pathways import Pathway
            settings = registry.behave_settings
            prefixes = ("behave", "behave0") if self.arm.behave_dual else ("behave",)
            for task in new:
                problems = problems_for(task.examples, task.request_type,
                                        skeletons_for(task.examples, False),
                                        int(settings.get("max_unroll", 6)), self.arm.behave_folds)
                registry.behave_problems[task.name] = problems
                for kind in problems:
                    for prefix in prefixes:
                        registry.pathways.setdefault(f"{prefix}:{kind}", Pathway(
                            f"{prefix}:{kind}", "behave", "designer", 0, status="dormant"))
        if hasattr(registry, "analogy_index"):
            index = registry.analogy_index      # TRAIN's standardization, kept
            for task in new:
                index.features[task.name] = index.vector(task.examples)
                index.request[task.name] = task.request_type
        self.stage = name
        self.stage_first_generation[name] = self.state.generation + 1
        return {"stage": name, "tasks": len(new), "known_tasks": len(self.sleep_public),
                "first_generation": self.state.generation + 1}

    def generation(self) -> dict:
        """rsi3's ``Runtime.generation``, with sleep over every task the system has met."""
        from rsi3.continuity import snapshot
        generation = self.state.generation + 1
        cpu_started, wall_started = time.process_time(), time.perf_counter()
        self.registry.begin_generation()
        wake = self.wake(generation)
        self.state.logical_evaluations += wake["spent"]
        replayed = self.memory.replay(self.arm.value_mode, generation)
        fit = self.value_model.fit([e.features for e in replayed],
                                   [self.memory.label(e) for e in replayed])
        before_rewrite = snapshot(self.state, "old")
        sink = {}
        sleep = sleep_phase(self.state, self.sleep_public, self.config, generation, sink=sink)
        continuity = self.continuity.after_sleep(
            self.state, before_rewrite, {t.name: t for t in self.public},
            sink.get("dreams", ()), generation)
        self.budget_debt = continuity["charged"]
        self.state.logical_evaluations += continuity["charged"]
        created = self.registry.genesis(self.state, generation)
        failed = self.failures.sizes() if self.failures is not None else {}
        return {"generation": generation, "wake": wake, "value_fit": fit, "sleep": sleep,
                "continuity": continuity,
                "failure_memory": {"tasks": len(failed), "programs": sum(failed.values()),
                                   "max_per_task": max(failed.values(), default=0)},
                "genesis_created": created, "pathways": self.registry.summary(),
                "train_solved": len(self.state.solutions),
                "verifier_queries": self.verifier.queries,
                "integrator": self.integrator.stats(),
                "cpu_seconds": time.process_time() - cpu_started,
                "wall_seconds": time.perf_counter() - wall_started}

    def stage_solved(self, name: str) -> list[str]:
        names = {t.name for t in self.sleep_public} if name == "all" else (
            {t.name for t in self.public} if name == self.stage else None)
        if names is None:
            raise KeyError(name)
        return sorted(n for n in self.state.solutions if n in names)


def strip_timing(value):
    """The record without wall-clock and CPU fields: what reproduces byte for byte."""
    if isinstance(value, dict):
        return {k: strip_timing(v) for k, v in value.items() if k not in TIMING}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value


# ---- the driver ---------------------------------------------------------------------
def _runtime_config(config: dict) -> dict:
    """Exactly the keys ``rsi3.longrun.run`` hands its Runtime."""
    return {"B_wake": config["B_wake"], "B_eval": config["B_eval"], "dreams": config["dreams"],
            "search": dict(config["search"]), "controller": config["controller"],
            "continuity": config.get("continuity", {}), "invention": config.get("invention", {}),
            "compact_searches": True, "meta": config.get("meta", {}),
            "behave": config.get("behave", {}), "analogy": config.get("analogy", {}),
            "chain": config.get("chain", {}), "curriculum": config.get("curriculum", {})}


def _held_out_config(config: dict) -> dict:
    return {"B_wake": config["B_wake"], "B_eval": config["B_eval"], "dreams": config["dreams"],
            "search": dict(config["search"]), "meta": config.get("meta", {}),
            "behave": config.get("behave", {}), "analogy": config.get("analogy", {}),
            "chain": config.get("chain", {})}


class Driver:
    def __init__(self, plan: dict, arm_name: str, output: Path, *, train=None, stage_tasks=None,
                 validation=None):
        from rsi2.corpus import load_train, load_validation
        from rsi3.experiment import ARMS
        self.plan, self.arm_name, self.output = plan, arm_name, Path(output)
        self.arm = ARMS[arm_name]
        self.config_path = Path(plan["arms"][arm_name])
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.config["seeds"] = list(plan["seeds"])
        self.seeds = list(plan["seeds"])
        self.generations = {"TRAIN": int(plan.get("train_generations", 16)),
                            **{s: int(plan.get("stage_generations", 8)) for s in STAGES}}
        self.train = load_train() if train is None else train
        self.stage_tasks = load_stage_tasks() if stage_tasks is None else stage_tasks
        self.validation = (load_validation() if validation is None else validation) \
            if plan.get("train_validation", True) else []
        self.output.mkdir(parents=True, exist_ok=True)
        self.judge_dir = self.output / "J"
        self.checkpoint = self.output / f"{arm_name}.checkpoint.pkl"
        self.status_path = self.output / "STATUS.json"
        self.status = (json.loads(self.status_path.read_text(encoding="utf-8"))
                       if self.status_path.exists() else
                       {"arm": arm_name, "config": str(self.config_path), "complete": False,
                        "phase": "TRAIN", "phase_done": 0, "milestones": {},
                        "evaluations": {}, "segments": []})

    # -- state --------------------------------------------------------------------------
    def save_status(self) -> None:
        tmp = self.status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.status, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.status_path)

    def load(self):
        if self.checkpoint.exists():
            saved = pickle.loads(self.checkpoint.read_bytes())
            return saved["runtime"], saved["records"], saved["cpu"], saved["stream"]
        runtime = StageRuntime(self.seeds[0], self.train, self.arm,
                               _runtime_config(self.config), self.stage_tasks)
        return runtime, {seed: [] for seed in self.seeds}, {seed: 0.0 for seed in self.seeds}, []

    def save(self, runtime, records, cpu, stream, path: Path | None = None) -> None:
        path = path or self.checkpoint
        tmp = path.with_suffix(".tmp")
        with tmp.open("wb") as handle:
            pickle.dump({"runtime": runtime, "records": records, "cpu": cpu, "stream": stream,
                         "phase": self.status["phase"], "rules": None,
                         "arm": self.arm_name}, handle)
        tmp.replace(path)

    # -- J ------------------------------------------------------------------------------
    def ask(self, request: dict) -> dict:
        from .client import ask
        request = dict(request, run_dir=str(self.judge_dir), config=str(self.config_path))
        response = ask(request, self.judge_dir)
        if not response.get("ok"):
            raise RuntimeError(f"J did not serve {request.get('op')}: "
                               f"{response.get('refused') or response.get('error')}")
        return response

    def evaluate(self, key: str, checkpoint: Path, pool: str, label: str) -> bool:
        """Ask J for one evaluation unless it is already recorded; True if J ran it now."""
        if key in self.status["evaluations"]:
            return False
        response = self.ask({"op": "evaluate", "checkpoint": str(checkpoint), "pool": pool,
                             "solver": "rsi3", "label": label})
        index = sum(1 for _ in (self.judge_dir / "judge_log.jsonl").open()) - 1
        self.status["evaluations"][key] = {
            "pool": pool, "label": label, "checkpoint": checkpoint.name,
            "ledger_index": index, "solved": response["result"]["pooled"]["solved"],
            "per_seed": {s: r["solved"] for s, r in response["result"]["seeds"].items()},
            "process": response.get("_process")}
        (self.output / "evaluations").mkdir(exist_ok=True)
        (self.output / "evaluations" / f"{key}.json").write_text(
            json.dumps(response, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        self.save_status()
        return True

    # -- the loop -----------------------------------------------------------------------
    def run(self, max_minutes: float | None = None) -> bool:
        from rsi3.longrun import agent_validation, final_record, seed_recognition, validation_record
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        segment = {"started": time.time(), "cpu_seconds": 0.0}
        self.status["segments"].append(segment)
        if not self.status.get("run_start"):
            response = self.ask({"op": "run_start", "run_id": self.run_id()})
            self.status["run_start"] = response["result"]
            self.save_status()
        runtime, records, cpu, stream = self.load()
        rsi2_config = {k: self.config[k] for k in ("B_wake", "B_eval", "dreams")}
        rsi2_config["search"] = dict(self.config["search"])
        agent_verifiers = {seed: FrozenVerifier(self.validation,
                                                step_budget=self.config["search"]["step_budget"])
                           for seed in self.seeds} if self.validation else {}

        def out_of_time():
            return max_minutes is not None and time.perf_counter() - started_wall > 60 * max_minutes

        for phase_index, phase in enumerate(PHASES):
            if PHASES.index(self.status["phase"]) > phase_index:
                continue
            if phase != "TRAIN" and runtime.stage != phase:
                begun = runtime.begin_stage(phase, self.stage_tasks[phase])
                self.status["phase_done"] = 0
                stream.append({"event": "begin_stage", **begun})
            while self.status["phase_done"] < self.generations[phase]:
                cpu_before = time.process_time()
                record = runtime.generation()
                generation = record["generation"]
                shared = time.process_time() - cpu_before
                if phase == "TRAIN":
                    for seed in self.seeds:
                        seed_started = time.process_time()
                        seed_record = copy.deepcopy(record)
                        if not self.validation:
                            seed_record["validation"] = seed_record["validation_agent"] = None
                            records[seed].append(seed_record)
                            cpu[seed] += shared
                            continue
                        if seed == self.seeds[0]:
                            model = runtime.state.recognition
                        else:
                            model, sleep = seed_recognition(runtime.state, runtime.public,
                                                            rsi2_config, seed, generation)
                            seed_record["sleep"].update(sleep)
                        seed_record["validation"] = validation_record(
                            runtime.state, model, self.validation, rsi2_config)
                        seed_record["validation_agent"] = agent_validation(
                            runtime, model, self.validation, _held_out_config(self.config),
                            agent_verifiers[seed], generation)
                        seed_record["cpu_seconds"] = record["cpu_seconds"] + (
                            time.process_time() - seed_started)
                        records[seed].append(seed_record)
                        cpu[seed] += shared + (time.process_time() - seed_started)
                else:
                    record["phase"] = phase
                    stage_names = {t.name for t in runtime.public}
                    record["stage_solved"] = sum(1 for n in runtime.state.solutions
                                                 if n in stage_names)
                    stream.append(record)
                    for seed in self.seeds:
                        cpu[seed] += shared
                self.status["phase"] = phase
                self.status["phase_done"] += 1
                self.save(runtime, records, cpu, stream)
                self.save_status()
                print(f"{self.arm_name} {phase} generation {generation}: solved "
                      f"{len(runtime.state.solutions)}, cpu {shared:.0f}s", flush=True)
                if out_of_time() and self.status["phase_done"] < self.generations[phase]:
                    return self._stop(segment, started_cpu)
            # Phase complete: milestone checkpoint, then J's stage-eval evaluations.
            milestone = self.output / f"{self.arm_name}.after_{phase}.pkl"
            if phase not in self.status["milestones"]:
                if phase == "TRAIN":
                    self.write_train_files(runtime, records, cpu, final_record(runtime))
                self.save(runtime, records, cpu, stream, milestone)
                self.status["milestones"][phase] = {
                    "generation": runtime.state.generation,
                    "solved": len(runtime.state.solutions),
                    "stage_solved": (len(runtime.stage_solved(phase)) if phase != "TRAIN"
                                     else None)}
                self.save_status()
            for j, stage in enumerate(STAGES, start=1):
                if self.plan.get("evaluate_stage_eval", True) and self.evaluate(
                        f"R{phase_index}{j}", milestone, f"stage_eval_{stage}",
                        f"R[{phase_index}][{j}]") and out_of_time():
                    return self._stop(segment, started_cpu)
            if phase != PHASES[-1]:
                self.status["phase"] = PHASES[phase_index + 1]
                self.status["phase_done"] = 0
                self.save_status()
        self.finish(runtime, stream, final_record(runtime))
        # Report-only evaluations (exposed partitions, TRAIN and stage-train
        # retention): "final_reports" on the after-S3 solver, "train_reports"
        # on the after-TRAIN solver. Each entry is a J pool name such as
        # "exposed:fresh1" or "report:train".
        report = []
        for when, phase in (("final", "S3"), ("train", "TRAIN")):
            checkpoint = self.output / f"{self.arm_name}.after_{phase}.pkl"
            for pool in self.plan.get(f"{when}_reports", []):
                if not pool.startswith(("exposed:", "report:")):
                    raise ValueError(f"{pool!r} is not a report-only partition")
                report.append((f"{when}_{pool.split(':', 1)[1]}", checkpoint, pool,
                               f"after {phase}: {pool} (report-only)"))
        for key, checkpoint, pool, label in report:
            if self.evaluate(key, checkpoint, pool, label) and out_of_time():
                return self._stop(segment, started_cpu)
        self.rsi3_reserve_eval()
        if not self.status.get("run_end"):
            self.status["run_end"] = self.ask({"op": "run_end", "run_id": self.run_id()})["result"]
        self.status["complete"] = True
        self._stop(segment, started_cpu)
        return True

    def run_id(self) -> str:
        return f"{self.plan.get('name', 'run')}:{self.arm_name}"

    def _stop(self, segment: dict, started_cpu: float) -> bool:
        segment["cpu_seconds"] = round(time.process_time() - started_cpu, 1)
        segment["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        segment["ended"] = time.time()
        self.save_status()
        return bool(self.status.get("complete"))

    def write_train_files(self, runtime, records, cpu, final) -> None:
        """The TRAIN phase in ``rsi3.longrun``'s per-seed format, for the base check."""
        run_config = dict(self.config, compact_searches=True)
        for seed in self.seeds:
            payload = {"arm": self.arm_name, "seed": seed, "config": run_config,
                       "status": "complete", "generations": records[seed], "final": final,
                       "cpu_seconds": cpu[seed],
                       "shared_trajectory": {"primary_seed": self.seeds[0], "seeds": self.seeds}}
            (self.output / f"{self.arm_name}_seed{seed}.json").write_text(
                json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")

    def finish(self, runtime, stream, final) -> None:
        path = self.output / f"{self.arm_name}_stream.json"
        if path.exists():
            return
        plasticity = {}
        for event in stream:
            if event.get("phase") in STAGES:
                plasticity[event["phase"]] = event["stage_solved"]
        payload = {"arm": self.arm_name, "config": str(self.config_path), "seeds": self.seeds,
                   "generations": self.generations, "stream": stream, "final": final,
                   "stage_train_receipts": plasticity,
                   "milestones": self.status["milestones"]}
        path.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")

    def rsi3_reserve_eval(self) -> None:
        """rsi3's own held-out runner on the TRAIN checkpoint, as rsi3's runs did (report-only)."""
        parts = self.plan.get("rsi3_reserve_eval_after_train", [])
        if not parts:
            return
        config = dict(self.config, seeds=self.seeds)
        config_path = self.output / "eval_config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        for part in parts:
            target = self.output / f"{self.arm_name}_seed{'-'.join(map(str, self.seeds))}_{part}.json"
            if target.exists():
                continue
            subprocess.run([sys.executable, "-m", "rsi3.reserve_eval", "--checkpoint",
                            str(self.output / f"{self.arm_name}.after_TRAIN.pkl"), "--config",
                            str(config_path), "--partition", part, "--output", str(target)],
                           check=True)


# ---- process structure -----------------------------------------------------------------
def _worker(plan_path: str, arm: str, output: str, max_minutes) -> None:
    from . import guard
    guard.install()
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    plan.setdefault("name", Path(plan_path).stem)
    Driver(plan, arm, Path(output)).run(max_minutes)


def main(argv=None):
    from .watchdog import RSS_CAP_BYTES, run_watched
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-minutes", type=float, default=None)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_worker, args=(str(args.plan), args.arm, str(args.output),
                                                    args.max_minutes))
    record = run_watched(process, cap_bytes=RSS_CAP_BYTES,
                         log_path=args.output / "watchdog.jsonl", label=f"train {args.arm}")
    status_path = args.output / "STATUS.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {"complete": False}
    status.setdefault("workers", []).append(record)
    status_path.write_text(json.dumps(status, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"arm": args.arm, "complete": status.get("complete"), "worker": record}))
    if record["breach"] or record["exitcode"] != 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


__all__ = ["StageRuntime", "Driver", "load_stage_tasks", "strip_timing"]
