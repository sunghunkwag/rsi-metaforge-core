"""J's evaluation of a learned solver: every reported number comes from here.

Semantics are ``rsi3.longrun.agent_validation``'s: the arm's own trained
solver, applied and never trained, B_eval = 64 candidates per task, one
verification per task, every seed's recognition model (the run's own for its
primary seed, the others refitted exactly as ``rsi3.longrun`` refits them).
What J adds:

- **J runs it.** The agent sends a checkpoint path and a request; J copies
  the checkpoint, marks the copy read-only, hashes it, and unpickles a fresh
  object from those bytes for every seed.
- **The solver sees public views only.** J passes ``public_view`` tasks to
  the solver and keeps the hidden examples in its own verifier.
- **J decides "solved".** ``JudgeVerifier`` checks the returned program on
  every public and every hidden example (``rsi2.search.verify``, the frozen
  evaluator, the registered step budget) and allows one query per task. The
  solver's own record is kept for its spending, never for its verdict.
- **Solved means 2 of 3 seeds** (F7) in every pooled count.

Solvers (``SOLVERS``): ``rsi3`` is ``rsi3.longrun.agent_validation`` itself,
for arms without a held-out-time controller. ``rsi4`` is
``rsi4.heldout.agent_validation`` (the same function signature, plus
``rules``), for arms whose controller C acts at held-out time. Both receive
J's verifier.

Interface a checkpoint must offer: a pickled dict with key ``"runtime"``
holding an ``rsi3.loop.Runtime`` (or subclass). Optional keys: ``"rules"``
(the rule vector the runtime was trained with). An rsi4 runtime whose sleep
phase fits on more tasks than ``runtime.public`` (TRAIN plus the stages seen
so far) exposes that list as ``runtime.sleep_public``; the seed refit then
uses it, as the runtime's own sleep did.
"""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import pickle
import shutil
import stat
import tempfile

from rsi2.search import verify as frozen_verify
from rsi3.verifier import QueryLimitExceeded, Receipt, public_view, term_digest

from . import pools
from .registry import B_EVAL, EVAL_SEEDS, SOLVED_MIN_SEEDS

SOLVERS = {"rsi3": ("rsi3.longrun", "agent_validation"),
           "rsi4": ("rsi4.heldout", "agent_validation")}
REGISTERED_SEARCH = {"max_size": 12, "max_expansions": 20000, "step_budget": 2000}
EXPOSED = ("validation", "near", "far", "far2", "fresh1", "fresh2", "compose24")
# Report-only partitions that are training data: TRAIN retention and
# stage-train retention of a final solver (§6). They never enter a decision.
REPORT = ("train", "stage_train_S1", "stage_train_S2", "stage_train_S3")


class EvaluationError(RuntimeError):
    """The request cannot be evaluated as registered."""


class JudgeVerifier:
    """Every public and hidden example; one query per task; J's verdicts only."""

    def __init__(self, tasks, step_budget: int):
        self._tasks = {task.name: task for task in tasks}
        self._step_budget = int(step_budget)
        self.verdicts: dict[str, bool] = {}
        self.digests: dict[str, str] = {}

    def verify(self, task_name: str, term, library, generation: int) -> Receipt:
        if task_name not in self._tasks:
            raise KeyError(f"unknown task {task_name!r}")
        if task_name in self.verdicts:
            raise QueryLimitExceeded(f"{task_name!r} already verified in this evaluation")
        task = self._tasks[task_name]
        verdict = bool(frozen_verify(term, tuple(task.examples) + tuple(task.hidden),
                                     library=library, step_budget=self._step_budget))
        digest = term_digest(term)
        self.verdicts[task_name], self.digests[task_name] = verdict, digest
        return Receipt(len(self.verdicts), task_name, int(generation), digest, verdict)

    @property
    def queries(self) -> int:
        return len(self.verdicts)


# ---- inputs -------------------------------------------------------------------
def load_tasks(pool: str, judge_dir: Path) -> list:
    if pool.startswith("report:"):
        name = pool.split(":", 1)[1]
        if name not in REPORT:
            raise EvaluationError(f"unknown report partition {name!r}")
        if name == "train":
            from rsi2.corpus import load_train
            return load_train()
        import json
        from rsi3.fresh import to_task
        stages = json.loads((Path(judge_dir).parent / "data" / "stage_train.json")
                            .read_text(encoding="utf-8"))["stages"]
        return [to_task(record) for record in stages[name.rsplit("_", 1)[1]]]
    if pool.startswith("exposed:"):
        name = pool.split(":", 1)[1]
        if name not in EXPOSED:
            raise EvaluationError(f"unknown exposed partition {name!r}")
        if name == "validation":
            from rsi2.corpus import load_validation
            return load_validation()
        if name.startswith("fresh"):
            from rsi3.fresh import load_fresh
            return load_fresh(name)
        if name == "compose24":
            from rsi3.compose24 import load_frozen_tasks
            return load_frozen_tasks()
        from rsi3.reserve import load_reserve
        return load_reserve(name)
    return pools.load_pool(pool, judge_dir)


def check_config(config: dict) -> None:
    """The registered budgets and search limits are never in a request's control."""
    if int(config.get("B_eval", -1)) != B_EVAL:
        raise EvaluationError(f"B_eval must be {B_EVAL}")
    search = {k: config.get("search", {}).get(k) for k in REGISTERED_SEARCH}
    if search != REGISTERED_SEARCH:
        raise EvaluationError(f"search limits must be {REGISTERED_SEARCH}, got {search}")


def read_only_copy(checkpoint: Path) -> tuple[bytes, str]:
    """The checkpoint's bytes, read from a read-only copy J made, and their sha256."""
    with tempfile.TemporaryDirectory(prefix="rsi4-judge-") as scratch:
        copy = Path(scratch) / "checkpoint.pkl"
        shutil.copyfile(checkpoint, copy)
        os.chmod(copy, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        blob = copy.read_bytes()
    return blob, hashlib.sha256(blob).hexdigest()


def solver_function(name: str, solvers: dict | None = None):
    registry = dict(SOLVERS)
    registry.update(solvers or {})
    if name not in registry:
        raise EvaluationError(f"unknown solver {name!r}")
    entry = registry[name]
    if callable(entry):
        return entry
    module, function = entry
    return getattr(importlib.import_module(module), function)


def solver_config(config: dict) -> dict:
    return {"B_wake": config["B_wake"], "B_eval": config["B_eval"],
            "dreams": config["dreams"], "search": dict(config["search"]),
            "meta": config.get("meta", {}), "behave": config.get("behave", {}),
            "analogy": config.get("analogy", {}), "chain": config.get("chain", {})}


# ---- the evaluation ---------------------------------------------------------------
def evaluate_blob(blob: bytes, digest: str, tasks: list, config: dict, *, solver: str = "rsi3",
                  rules: dict | None = None, seeds=EVAL_SEEDS, solvers: dict | None = None,
                  pool: str = "") -> dict:
    """Run the checkpoint's solver on ``tasks`` for every seed; J's verdicts decide."""
    from rsi3.longrun import curriculum_extra, seed_recognition
    check_config(config)
    if solver == "rsi3" and rules is not None:
        raise EvaluationError("the rsi3 solver takes no rules")
    function = solver_function(solver, solvers)
    names = [task.name for task in tasks]
    if len(set(names)) != len(names):
        raise EvaluationError("task names repeat")
    public = [public_view(task) for task in tasks]
    cfg = solver_config(config)
    rsi2_config = {k: cfg[k] for k in ("B_wake", "B_eval", "dreams", "search")}
    per_seed, generation, primary = {}, None, None
    for seed in seeds:
        runtime = pickle.loads(blob)["runtime"]
        generation, primary = runtime.state.generation, runtime.state.seed
        if seed == runtime.state.seed:
            model = runtime.state.recognition
        else:
            sleep_public = getattr(runtime, "sleep_public", None) or runtime.public
            model, _ = seed_recognition(runtime.state, sleep_public, rsi2_config, seed,
                                        generation, curriculum_extra(runtime))
        verifier = JudgeVerifier(tasks, config["search"]["step_budget"])
        extra = {} if solver == "rsi3" else {"rules": rules}
        record = function(runtime, model, public, cfg, verifier, generation, **extra)
        verdicts = {name: verifier.verdicts.get(name, False) for name in names}
        claimed = {r["name"]: bool(r.get("solved")) for r in record.get("tasks", [])}
        spent = {r["name"]: r.get("spent", {}) for r in record.get("tasks", [])}
        per_seed[str(seed)] = {
            "solved": sum(verdicts.values()), "verdicts": verdicts,
            "digests": dict(verifier.digests),
            "claims_differ": sorted(n for n in names if claimed.get(n, False) != verdicts[n]),
            "over_budget": sorted(n for n in names
                                  if sum(spent.get(n, {}).values()) > B_EVAL),
            "solver_record": record}
    pooled = {name: sum(per_seed[str(s)]["verdicts"][name] for s in seeds) >= SOLVED_MIN_SEEDS
              for name in names}
    return {"pool": pool, "tasks": len(names), "names": names, "checkpoint_sha256": digest,
            "generation": generation, "primary_seed": primary, "solver": solver,
            "rules": rules, "seeds": per_seed,
            "pooled": {"solved": sum(pooled.values()), "tasks": pooled},
            "complete": all(len(per_seed[str(s)]["verdicts"]) == len(names) for s in seeds)}


def evaluate_checkpoint(checkpoint: Path, pool: str, config: dict, *, judge_dir: Path,
                        solver: str = "rsi3", rules: dict | None = None,
                        solvers: dict | None = None, seeds=EVAL_SEEDS) -> dict:
    blob, digest = read_only_copy(Path(checkpoint))
    tasks = load_tasks(pool, judge_dir)
    return evaluate_blob(blob, digest, tasks, config, solver=solver, rules=rules,
                         seeds=seeds, solvers=solvers, pool=pool)


def summary(result: dict) -> dict:
    """What a ledger entry keeps of an evaluation: J's verdicts, not the solver's records."""
    return {"pool": result["pool"], "tasks": result["tasks"],
            "checkpoint_sha256": result["checkpoint_sha256"],
            "generation": result["generation"], "solver": result["solver"],
            "rules": result["rules"], "complete": result["complete"],
            "pooled": result["pooled"],
            "per_seed": {s: {"solved": r["solved"], "verdicts": r["verdicts"],
                             "claims_differ": r["claims_differ"],
                             "over_budget": r["over_budget"]}
                         for s, r in result["seeds"].items()}}
