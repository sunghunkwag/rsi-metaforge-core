"""Phase 1: enumeration only, every exposed partition, original vs restored vocabulary.

    python -m rsi5.phase1 --plan rsi5/runs/p1.json --output rsi5/results_p1 [--partition P] [--vocabulary V]
    python -m rsi5.phase1 --throughput --output rsi5/results_p1

The registered experiment of OWNER_DIRECTIVE.md §3.3. For every task of every partition
in the plan, C1 (``rsi5.engine``) searches by bottom-up enumeration with observational
equivalence at the plan's budget, with each vocabulary. The engine sees public examples
only; the frozen verifier (``rsi5/verifier.py``) issues the verdict on public and hidden
examples. Because the enumeration is deterministic and budget-monotone (a task solved at
budget B is solved at every larger budget, by the same program), one run at the plan's
budget yields the solve count at every smaller budget in ``report_budgets``: a task
counts as solved at B when its verified program was found within the first B candidates.

Outputs, per (vocabulary, partition): ``<output>/<vocabulary>_<partition>.json`` with one
record per task and a digest over every deterministic field (wall-clock excluded), so
two runs of the same plan are checked byte for byte through their digests.

Process layout. ``main()`` installs the guard (``rsi5/guard.py``) first, then forks the
search workers, and only then loads a partition. A worker is forked before any loader
module is imported and before any task exists, so it inherits no hidden example; it calls
``guard.seal_task_data()``, which refuses the loaders' import and seals their sources and
data, and it is sent ``PublicTask`` values only. The driver process holds the tasks and
the frozen verifier and never searches: with ``--workers 1`` the search still runs in one
forked worker. A worker forked late (the pool replaces a worker that died) finds loader
modules in its ``sys.modules`` and refuses every task, which fails the run.

No learning anywhere. Nothing here reads J's pools, TEST, or any hidden example outside
the verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import sys
import time

from . import guard, partitions, probes
from .dsl.terms import term_from_dict, term_to_dict
from .dsl.types import Type, function_parts
from .dsl.vocabulary import VOCABULARIES
from .engine.bottomup import CHILD_POINT_CAP, Engine
from .verifier import FrozenVerifier, term_digest

SCHEMA = 1


def canonical(payload) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def load_plan(path: Path) -> dict:
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("budget", "report_budgets", "max_size", "step_budget", "partitions", "vocabularies"):
        if key not in plan:
            raise ValueError(f"plan lacks {key!r}")
    if plan.get("probe_set_sha256") != probes.sha256():
        raise ValueError("the probe set differs from the one the plan registered")
    if not probes.check():
        raise ValueError("the committed probe set is not the generator's output")
    if plan.get("child_point_cap", CHILD_POINT_CAP) != CHILD_POINT_CAP:
        raise ValueError(f"the engine's child-context point cap is {CHILD_POINT_CAP}, a constant; "
                         "the plan registers another value")
    if max(int(b) for b in plan["report_budgets"]) > int(plan["budget"]):
        raise ValueError("a report budget exceeds the run budget; its count would not be measured")
    return plan


# ---- the search workers -------------------------------------------------------------------
_WORKER = {}


def _init_worker(plan: dict) -> None:
    """Runs once in each search worker, right after its fork."""
    guard.install()                      # inherited from the driver; a no-op unless forked unguarded
    guard.seal_task_data()
    _WORKER["plan"] = plan
    _WORKER["probes"] = probes.load()
    _WORKER["late"] = guard.preloaded()


def worker_pool(plan: dict, workers: int):
    """Fork the search workers. Call it before the first ``partitions.load()``: a worker
    forked later inherits the loader modules and every task the driver then holds."""
    loaded = guard.loader_modules()
    if loaded:
        raise RuntimeError(f"search workers must be forked before any loader is imported; found {loaded}")
    context = multiprocessing.get_context("fork")
    return context.Pool(max(1, workers), initializer=_init_worker, initargs=(plan,))


def run_task(job) -> dict:
    """In a worker: search one public task with one vocabulary; a JSON-ready record, no verdict."""
    vocabulary_name, task = job
    if _WORKER["late"]:
        raise RuntimeError("this search worker was forked after these modules were imported and may "
                           f"hold hidden examples: {_WORKER['late']}")
    plan, vocabulary = _WORKER["plan"], VOCABULARIES[vocabulary_name]
    request = Type.from_dict(task.request)
    inputs = probes.inputs_for(function_parts(request)[0], _WORKER["probes"])
    engine = Engine(vocabulary, max_size=plan["max_size"], step_budget=plan["step_budget"],
                    max_lambda_depth=plan.get("max_lambda_depth", 2))
    result = engine.search(task.examples, request, inputs, plan["budget"],
                           wall_cap=plan.get("wall_cap_seconds"))
    term = result.term
    return {
        "name": task.name, "request_type": str(request),
        "public_match": term is not None,
        "program": str(term) if term is not None else None,
        "program_dict": term_to_dict(term) if term is not None else None,
        "program_digest": term_digest(term) if term is not None else None,
        "candidates": result.candidates,
        "candidates_to_solution": result.candidates_to_solution,
        "completed_size": result.completed_size, "pool_size": result.pool_size,
        "contexts": result.contexts, "pruned": result.pruned, "spurious": result.spurious,
        "exhausted": result.exhausted, "wall_seconds": round(result.wall_seconds, 3),
    }


# ---- the driver ---------------------------------------------------------------------------
def run_partition(plan: dict, vocabulary_name: str, partition: str, pool, workers: int,
                  limit: int | None = None) -> dict:
    """In the driver: load the partition, send its public views to ``pool``, verify the answers."""
    tasks = partitions.load(partition)
    if limit is not None:
        tasks = tasks[:limit]
    verifier = FrozenVerifier(tasks, step_budget=plan["step_budget"])
    jobs = [(vocabulary_name, partitions.public_view(task)) for task in tasks]
    started = time.perf_counter()
    records = pool.map(run_task, jobs, chunksize=1)
    for record in records:
        record["family"] = partitions.family(record["name"])
        term = term_from_dict(record["program_dict"]) if record["program_dict"] is not None else None
        receipt = verifier.verify(record["name"], term, generation=0)
        record["solved"] = receipt.verdict
        record["receipt"] = receipt.receipt_id
        record.pop("program_dict")
    budgets = sorted(int(b) for b in plan["report_budgets"] if int(b) <= int(plan["budget"]))
    solved_at = {str(b): sum(1 for r in records if r["solved"] and r["candidates_to_solution"] <= b)
                 for b in budgets}
    deterministic = [{k: v for k, v in r.items() if k != "wall_seconds"} for r in records]
    digest = hashlib.sha256(canonical(deterministic)).hexdigest()
    return {
        "schema": SCHEMA, "phase": 1, "plan": plan, "vocabulary": vocabulary_name,
        "partition": partition, "partition_label": partitions.PARTITIONS[partition][0],
        "tasks": len(records), "solved": sum(1 for r in records if r["solved"]),
        "public_matches_rejected": sum(1 for r in records if r["public_match"] and not r["solved"]),
        "solved_at": solved_at, "verifier_queries": verifier.queries,
        "wall_seconds": round(time.perf_counter() - started, 1), "workers": workers,
        "python": platform.python_version(), "digest": digest, "records": records,
    }


def write(result: dict, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{result['vocabulary']}_{result['partition']}.json"
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    guard.install()
    early = guard.preloaded()
    if early:
        raise SystemExit(f"imported before the guard was installed, so outside its import rule: {early}")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plan", type=Path, default=Path(__file__).resolve().parent / "runs" / "p1.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--partition", action="append")
    parser.add_argument("--vocabulary", action="append")
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int, help="first N tasks only (development)")
    parser.add_argument("--budget", type=int, help="override the plan's budget (development only)")
    parser.add_argument("--throughput", action="store_true", help="measure and record throughput")
    args = parser.parse_args(argv)
    if args.throughput:
        from .engine.throughput import measure
        figures = measure()
        figures["python"] = platform.python_version()
        figures["machine"] = platform.machine()
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "throughput.json").write_text(json.dumps(figures, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(figures, indent=1))
        return
    plan = load_plan(args.plan)
    if args.budget is not None:
        plan = dict(plan, budget=args.budget, development_override=True)
    workers = max(1, args.workers)
    with worker_pool(plan, workers) as pool:            # forked here, before any partition is loaded
        for vocabulary in args.vocabulary or plan["vocabularies"]:
            for partition in args.partition or plan["partitions"]:
                result = run_partition(plan, vocabulary, partition, pool, workers, args.limit)
                path = write(result, args.output)
                print(json.dumps({"vocabulary": vocabulary, "partition": partition, "tasks": result["tasks"],
                                  "solved": result["solved"], "solved_at": result["solved_at"],
                                  "wall_seconds": result["wall_seconds"], "digest": result["digest"][:16],
                                  "file": str(path)}), flush=True)


if __name__ == "__main__":
    main()
