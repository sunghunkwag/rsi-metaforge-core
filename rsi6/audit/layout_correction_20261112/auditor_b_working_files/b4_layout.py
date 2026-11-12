"""Auditor B, B4: could the kernel's new check refuse an environment that ran before?

No learner call is made here: problems are constructed, the kernel's layout() is read, and the
learner's Layout object (the descriptor names) is constructed.  Reads REPO; writes nothing.

(a) every instance of each of the seven adapters, as a training and as a fresh problem, three seeds;
(b) exactly what measure() checks, for every (environment, budget, seed) that has a run record:
    training problems (training=True), fresh problems and training problems again (training=False),
    with the kernel's own relabelling seeds;
(c) the same for knapsack and regression under the registered run budget (parts A and B) and the
    registered gate and confirm seeds (problem construction only);
(d) is the kernel's layout() a complete proxy of what the learner's parameter vector depends on?
    The learner's descriptor names (Layout.names) per instance, for every recovered version.
"""
import collections
import json
import os
import sys

import numpy as np

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
WORK = os.path.join(BASE, "work_b")
sys.path.insert(0, REPO)

from rsi6 import environments                                   # noqa: E402
from rsi6.kernel import ledger as ledgers                       # noqa: E402
from rsi6.kernel import run                                     # noqa: E402
from rsi6.kernel.environment import split                       # noqa: E402
from rsi6.kernel.problem import Meter, view                     # noqa: E402
from rsi6.learner import version as versions                    # noqa: E402
from rsi6.learner.learner import Layout                         # noqa: E402

book = ledgers.Ledger(os.path.join(REPO, "rsi6", "ledger", "main.jsonl"))
runs = [r for r in book.records if r["type"] == "run"]
reg = [r for r in book.records if r["type"] == "registration"][0]["registration"]
known = json.load(open(os.path.join(WORK, "versions.json")))
v0 = versions.default()
RECORDED = ["forecasting", "jobshop", "binpacking", "quadassign", "pmedian"]
NEW = ["knapsack", "regression"]

print("(a) every instance of every adapter, training and fresh form, seeds 3, 11, 101")
for name in RECORDED + NEW:
    env = environments.load(name)
    ids = env.instance_ids()
    seen = collections.Counter()
    for i in ids:
        for seed in (3, 11, 101):
            for training in (True, False):
                P = env.problem(i, Meter(float("inf")), run._seed(seed, env.name, i, "relabel"), training)[0]
                seen[run.layout(P)] += 1
    print(f"   {name}: instances {len(ids)}, problems built {sum(seen.values())}, distinct layouts {len(seen)}")
    for lay, n in seen.items():
        print("        ", n, lay)

print("(b) what measure() checks, for every (env, budget, seed) with a run record")
combos = sorted({(r["env"], ledgers.canon(r["budget"]), r["seed"]) for r in runs})
print("   combinations:", len(combos))
total = refused = 0
ids_ok = True
by_combo = {}
for r in runs:
    by_combo.setdefault((r["env"], ledgers.canon(r["budget"]), r["seed"]), r)
for env_name, budget_text, seed in combos:
    env = environments.load(env_name)
    budget = json.loads(budget_text)
    train_ids, fresh_ids = split(env, budget["n_train"], budget["n_fresh"])
    if budget.get("part") in ("A", "B"):
        fresh_ids = run.halves(env, fresh_ids)[0 if budget["part"] == "A" else 1]
    rec = by_combo[(env_name, budget_text, seed)]
    ids_ok &= list(fresh_ids) == rec["fresh_ids"] and len(train_ids) == rec["n_train"]
    relabel = lambda i: run._seed(seed, env.name, i, "relabel")
    problems = [env.problem(i, Meter(0.0), relabel(i), True)[0] for i in train_ids]
    shape = run.layout(problems[0])
    bad = sum(run.layout(P) != shape for P in problems)
    for i in list(fresh_ids) + list(train_ids):
        bad += run.layout(env.problem(i, Meter(0.0), relabel(i), False)[0]) != shape
    total += len(problems) + len(fresh_ids) + len(train_ids)
    refused += bad > 0
print(f"   problems built {total}; combinations the new check would refuse: {refused}; "
      f"fresh ids and n_train equal to the recorded ones in every combination: {ids_ok}")
# every run record: split fields recomputed with the corrected code
bad_fields = 0
for r in runs:
    env = environments.load(r["env"])
    b = r["budget"]
    train_ids, fresh_ids = split(env, b["n_train"], b["n_fresh"])
    if b.get("part") in ("A", "B"):
        fresh_ids = run.halves(env, fresh_ids)[0 if b["part"] == "A" else 1]
    same = (list(fresh_ids) == r["fresh_ids"] and len(train_ids) == r["n_train"] and len(fresh_ids) == r["n_fresh"]
            and sorted({env.group(i) for i in fresh_ids}) == r["fresh_groups"]
            and sorted({env.group(i) for i in train_ids}) == r["train_groups"]
            and float(env.threshold_for(fresh_ids)) == r["threshold"] and env.category == r["category"])
    bad_fields += not same
print(f"   run records whose fresh_ids, n_train, n_fresh, groups, threshold or category differ from the "
      f"corrected code's: {bad_fields} of {len(runs)}")

print("(c) knapsack and regression under the registered run budget (construction only)")
for name in NEW:
    env = environments.load(name)
    for part in ("A", "B"):
        budget = dict(reg["budgets"]["run"], part=part)
        train_ids, fresh_ids = split(env, budget["n_train"], budget["n_fresh"])
        all_fresh = fresh_ids
        fresh_ids = run.halves(env, fresh_ids)[0 if part == "A" else 1]
        seeds = reg["seeds"]["gate"] if part == "A" else reg["seeds"]["confirm"]
        bad = built = 0
        for seed in seeds:
            relabel = lambda i: run._seed(seed, env.name, i, "relabel")
            problems = [env.problem(i, Meter(0.0), relabel(i), True)[0] for i in train_ids]
            shape = run.layout(problems[0])
            bad += sum(run.layout(P) != shape for P in problems)
            for i in list(fresh_ids) + list(train_ids):
                bad += run.layout(env.problem(i, Meter(0.0), relabel(i), False)[0]) != shape
            built += len(problems) + len(fresh_ids) + len(train_ids)
        print(f"   {name} part {part}: train {len(train_ids)} from groups "
              f"{dict(collections.Counter(env.group(i) for i in train_ids))}; fresh (all 24) groups "
              f"{dict(collections.Counter(env.group(i) for i in all_fresh))}; this part {len(fresh_ids)} from "
              f"{dict(collections.Counter(env.group(i) for i in fresh_ids))}; problems built {built}; "
              f"layout mismatches {bad}; layout {shape}")
    # the search budget too (after round 2 the pair would join the source pool)
    budget = reg["budgets"]["search"]
    train_ids, fresh_ids = split(env, budget["n_train"], budget["n_fresh"])
    print(f"   {name} search budget: train {len(train_ids)} from groups "
          f"{dict(collections.Counter(env.group(i) for i in train_ids))}")

print("(d) the learner's own descriptor names against the kernel's layout()")
for name in RECORDED + NEW:
    env = environments.load(name)
    if env.form != "assign":
        widths = collections.Counter()
        for i in env.instance_ids():
            P = env.problem(i, Meter(float("inf")), 3, False)[0]
            widths[(bool(P.ordered), P.ctx_x.shape[1], P.qry_x.shape[1])] += 1
        print(f"   {name} (predict): (ordered, columns of observed, columns of queries) over instances: {dict(widths)}")
        continue
    ids = env.instance_ids()
    views = [view(env.problem(i, Meter(float("inf")), 3, False)[0]) for i in ids]
    reusable = collections.Counter((P.capacity is None, None if P.capacity is None else int(P.capacity.max()) > 1)
                                   for P in views)
    worst = 0
    sizes = set()
    for d, v in known.items():
        names = {tuple(Layout(P, versions.validate(v)).names) for P in views}
        worst = max(worst, len(names))
        if d == versions.digest(v0):
            sizes = {len(n) for n in names}
            names0 = sorted(names, key=len)[0]
    print(f"   {name}: instances {len(ids)}; (capacity is None, capacity.max() > 1): {dict(reusable)}; "
          f"distinct descriptor-name lists over instances, worst over {len(known)} versions: {worst}; "
          f"size of the parameter vector under the default version: {sorted(sizes)}")
    if name == "knapsack":
        print("        default-version descriptors of knapsack:", list(names0))
