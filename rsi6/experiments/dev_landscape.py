"""Development: what every single-field change of generation 0 does on one category of the pool.

Development only: categories of the source pool, a scratch ledger, seeds no other run uses,
nothing here is evidence. The question it is for: every registered process of the first design
chose a version on some categories and lost on others, with gates of 18 paired runs. Whether a
change of one field carries from one category to another at all has never been measured with
every change on every category of the pool. This module measures it, one category per process:
generation 0 of the first design and each version that differs from it in exactly one field
(``experiments/alternating.neighbours``), at the run budget of the registrations, on all the
fresh instances, for the given seeds.

    python -m rsi6.experiments.dev_landscape <category> --seeds 730001 730002 --out DIR

For a category in the assignment form the eleven changes of the ``predict.*`` fields are left
out: they cannot change an assignment run. The five ``transfer.*`` changes are kept although no
run here hands a memory on: their runs must equal generation 0's, which checks the harness.

One more version is measured beside the single-field changes: the version process c adopted in
its generation 1 (seven fields; ledger record of type ``adopt``), listed as the field
``adopted:c1``. Its gate had 18 paired runs on three categories; here it meets generation 0 on
every category of the pool with seeds its search never used.

All runs of one process are measured on one machine, so the CPU of a change is compared with
generation 0's CPU of the same process and seed, never across processes. A stopped process
started again with the same ``--out`` repeats at most one chunk of runs.

``--out`` gets ``landscape_<category>_<first seed>.json`` (one row per version and seed: scores,
the score on the training problems, counted units, CPU) and the run records beside it.

``--only FIELD=VALUE ...`` measures generation 0 and the named changes only (the value as JSON;
``adopted:c1`` names the adopted version) and writes ``pair_<category>_<first seed>.json`` in the
same layout. It is for measuring again, with seeds the landscape did not use, the few changes a
reading of the landscape picked out: the mean of a change chosen for being the largest of many is
too large, and every change of a category shares generation 0's runs, so its luck.
``--also NAME=FIELD=VALUE+FIELD=VALUE`` adds a version that differs from generation 0 in the
named fields together, listed as the field ``combo:NAME``.
``--smoke`` checks the plumbing only (three changes, a quarter of the training budget, a seed
nothing else uses, files named ``smoke_*``); its numbers mean nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.experiments import alternating, guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache, key_of
from rsi6.learner import designs
from rsi6.meta import rounds

POOL = ("binpacking", "forecasting", "jobshop", "knapsack", "partitioning", "pmedian", "quadassign", "regression", "setcover")
BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}    # the run budget of the registrations
CHUNK = 16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("category", choices=POOL)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--only", nargs="+", default=None, metavar="FIELD=VALUE")
    parser.add_argument("--also", nargs="+", default=[], metavar="NAME=FIELD=VALUE+FIELD=VALUE")
    args = parser.parse_args()
    category = args.category
    base = designs.default("a")
    changes = alternating.neighbours(base)
    if environments.load(category).form == "assign":
        changes = [c for c in changes if not c[0].startswith("predict.")]
    budget, seeds = dict(BUDGET), list(args.seeds)
    if args.smoke:
        changes, budget, seeds = changes[:3], dict(BUDGET, train=10.0), [9730001]
    if any(not 730000 <= s < 740000 for s in seeds) and not args.smoke:
        raise SystemExit("the seeds of this development measurement are 730000 to 739999")
    stem = ("smoke_" if args.smoke else "") + ("pair" if (args.only or args.also) else "landscape") + f"_{category}_{seeds[0]}"
    os.makedirs(args.out, exist_ok=True)
    scratch = os.path.join(args.out, stem + ".scratch.jsonl")
    if guard.is_registered(scratch):
        raise SystemExit("development writes a scratch ledger, never a registered one")
    if not os.path.exists(scratch):
        shutil.copy(guard.MAIN, scratch)
    ledger = ledgers.Ledger(scratch)
    started = ledger.select(type="landscape_started")
    if not started:                                                # a process started again finds its own marker
        started = [ledger.append({"type": "landscape_started", "category": category, "seeds": seeds, "budget": budget})]
    before = started[0]["idx"]
    cache = Cache(ledger)
    adopted = ledger.select(type="adopt", process="c")
    if adopted and not args.smoke:
        changes = changes + [("adopted:c1", adopted[0]["digest"][:12], adopted[0]["version"])]
    if args.only:
        changes = _only(changes, args.only)
    for spec in args.also:
        name, _, parts = spec.partition("=")
        fields = {f: json.loads(t) for f, _, t in (part.partition("=") for part in parts.split("+"))}
        changes = changes + [("combo:" + name, parts, designs.validate(dict(base, **fields)))]
    versions = [("", None, base)] + changes
    jobs = [job for s in seeds for _, _, v in versions for job in rounds.jobs_for(v, [category], [s], budget, "dev-landscape")]
    records = []
    for k in range(0, len(jobs), CHUNK):
        records += cache.get(jobs[k:k + CHUNK])
        print(f"{min(k + CHUNK, len(jobs))} of {len(jobs)} runs", flush=True)
    rows, at = [], 0
    for s in seeds:
        for field, value, v in versions:
            r = records[at]
            at += 1
            assert r["key"] == key_of({"env": category, "version": v, "seed": s, "budget": budget})
            rows.append({"seed": s, "field": field, "value": value, "version": designs.digest(v),
                         "untrained": r["untrained"], "acquired": r["acquired"], "gain": r["gain"],
                         "train_untrained": r.get("train_untrained"), "train_acquired": r.get("train_acquired"),
                         "units": r.get("units"), "cpu": r["cpu"]["acquire"] + r["cpu"]["apply"]})
    out = {"what": ("development: generation 0 of the first design and the named changes on one category of the pool"
                    if args.only else
                    "development: every single-field change of generation 0 of the first design on one category of the pool"),
           "category": category, "form": environments.load(category).form, "seeds": seeds, "budget": budget,
           "generation_0": designs.digest(base), "changes": len(changes), "smoke": bool(args.smoke),
           "machine": {"python": sys.version.split()[0], "numpy": np.__version__, "cpus": os.cpu_count(),
                       "platform": platform.platform(), "processor": _processor()},
           "rows": rows}
    json.dump(out, open(os.path.join(args.out, stem + ".json"), "w"), indent=1)
    with open(os.path.join(args.out, stem + ".records.jsonl"), "w") as handle:
        for r in ledger.records[before:]:
            handle.write(json.dumps(r, sort_keys=True) + "\n")
    os.remove(scratch)                                             # the copy of the committed ledger is not part of what is kept
    by = {(r["seed"], r["field"], json.dumps(r["value"])): r for r in rows}
    summary = []
    for field, value, _ in changes:
        d = [by[(s, field, json.dumps(value))]["acquired"] - by[(s, "", "null")]["acquired"] for s in seeds]
        c = sum(by[(s, field, json.dumps(value))]["cpu"] for s in seeds) / max(sum(by[(s, "", "null")]["cpu"] for s in seeds), 1e-9)
        summary.append((float(np.mean(d)), f"{field}={value}", c))
    summary.sort(reverse=True)
    print("generation 0 acquired:", [round(by[(s, "", "null")]["acquired"], 4) for s in seeds])
    for mean, name, c in summary[:8] + summary[-3:]:
        print(f"  {mean:+.4f}  cpu x{c:.2f}  {name}")
    return 0


def _only(changes: list, names: list) -> list:
    """The changes named as FIELD=VALUE, in the order named. A name that fits no change of this category
    (a ``predict.*`` field on an assignment category) is an error, not a silent omission."""
    chosen = []
    for name in names:
        field, _, text = name.partition("=")
        if field == "adopted:c1":
            found = [c for c in changes if c[0] == field]
        else:
            wanted = json.dumps(json.loads(text))
            found = [c for c in changes if c[0] == field and json.dumps(c[1]) == wanted]
        if len(found) != 1:
            raise SystemExit(f"--only {name}: {len(found)} changes of this category fit")
        chosen.append(found[0])
    return chosen


def _processor() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


if __name__ == "__main__":
    sys.exit(main())
