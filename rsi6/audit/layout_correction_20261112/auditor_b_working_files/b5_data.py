"""Auditor B, B5/B6: facts about the two corrected adapters, from the data files and from problem
objects.  No learner call: problems are constructed, answers are evaluated, files are read.
Reads REPO; writes nothing.
"""
import collections
import os
import sys

import numpy as np

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
sys.path.insert(0, REPO)

from rsi6 import environments                                   # noqa: E402
from rsi6.kernel import run                                     # noqa: E402
from rsi6.kernel.environment import split                       # noqa: E402
from rsi6.kernel.problem import AssignProblem, Meter, view      # noqa: E402

DATA = os.path.join(REPO, "rsi6", "data")

# ------------------------------------------------------------------------------------ knapsack
print("== KNAPSACK")
env = environments.load("knapsack")
FILES = {1: "5.100", 2: "5.250", 4: "10.100", 5: "10.250", 7: "30.100", 8: "30.250"}
mine = {}
third = collections.Counter()
for number, label in FILES.items():
    tokens = open(os.path.join(DATA, "knapsack", f"mknapcb{number}.txt")).read().split()
    count, pos = int(tokens[0]), 1
    for k in range(count):
        n, m, stated = int(tokens[pos]), int(tokens[pos + 1]), tokens[pos + 2]
        third[stated] += 1
        pos += 3
        profit = np.array(tokens[pos:pos + n], dtype=float); pos += n
        use = np.array(tokens[pos:pos + m * n], dtype=float).reshape(m, n); pos += m * n
        limit = np.array(tokens[pos:pos + m], dtype=float); pos += m
        mine[f"{label}-{k:02d}"] = (profit, use, limit)
    assert pos == len(tokens), (number, pos, len(tokens))
print("independent parse: instances", len(mine), "| every file consumed exactly | third header number values:", dict(third))
same = all(np.array_equal(env.instances[i]["profit"], mine[i][0]) and np.array_equal(env.instances[i]["use"], mine[i][1])
           and np.array_equal(env.instances[i]["limit"], mine[i][2]) for i in mine) and set(mine) == set(env.instances)
print("adapter's instances equal the independent parse:", same)
shape = collections.Counter((len(l), len(p)) for p, u, l in mine.values())
print("(constraints m, items n) -> instances:", dict(sorted(shape.items())))
print("largest m:", max(len(l) for _, _, l in mine.values()), "| env.width:", env.width)
zero_rows = sum(int(np.any(np.all(u == 0, axis=1))) for _, u, _ in mine.values())
zero_cells = sum(int((u == 0).sum()) for _, u, _ in mine.values())
neg_limits = sum(int(np.any(l < 0)) for _, _, l in mine.values())
print("instances with a published constraint whose coefficients are all zero:", zero_rows,
      "| zero coefficients anywhere in the published matrices:", zero_cells, "| instances with a negative limit:", neg_limits)

rng = np.random.default_rng(12345)
checked = bad_present = bad_eval = bad_score = bad_pre = bad_fast = answers = 0
for iid in env.instance_ids():
    profit, use, limit = mine[iid]
    n, m = len(profit), len(limit)
    for seed in (run._seed(101, "knapsack", iid, "relabel"), run._seed(206, "knapsack", iid, "relabel"), 3):
        P, decode = env.problem(iid, Meter(float("inf")), seed, True)
        r = np.random.default_rng(seed)                 # the adapter's own draws, repeated independently
        item_perm = r.permutation(n)
        row_perm = r.permutation(m)
        checked += 1
        pre = np.column_stack([profit[item_perm], use[np.ix_(row_perm, item_perm)].T])     # the presentation before the correction
        ok = (P.var_attr.shape == (n, 31) and np.array_equal(P.var_attr[:, :1 + m], pre)
              and not P.var_attr[:, 1 + m:].any() and np.array_equal(P.var_attr[:, 0], profit[item_perm]))
        bad_present += not ok
        bad_pre += not (np.array_equal(P.use, use[np.ix_(row_perm, item_perm)]) and np.array_equal(P.limit, limit[row_perm])
                        and np.array_equal(P.profit, profit[item_perm]) and P.n_vars == n and P.n_opts == 2
                        and P.capacity is None and P.opt_attr.shape == (2, 0) and P.construction_units() == n * 3 + 1)
        for density in (0.0, 0.2, 0.5, 0.8, 1.0):
            a = (rng.random(n) < density).astype(np.int64)
            answers += 1
            own = decode(a)                              # in the instance's own labels
            taken = own == 1
            load = use[:, taken].sum(axis=1)
            want = np.array([-profit[taken].sum(), np.maximum(load - limit, 0).sum()])
            got = P.evaluate(a)
            bad_eval += not np.allclose(got, want, rtol=1e-12, atol=1e-9)
            feasible = bool(np.all(load <= limit))
            want_score = float(min(1.0, profit[taken].sum() / env.instances[iid]["best"])) if feasible else 0.0
            bad_score += env.score(iid, own) != want_score
    # the fast incremental rows against the specification, a few steps
    P, _ = env.problem(iid, Meter(float("inf")), 7, True)
    s = P.start()
    for _ in range(6):
        U = P.unassigned(s)[:3]
        fast = P.candidates(s, U)
        slow = AssignProblem._rows(P, s, U)
        bad_fast += not np.allclose(fast, slow)
        P.assign(s, int(U[0]), int(rng.integers(2)))
        bad_fast += not np.allclose(P.totals(s), P.partial_totals(s["a"]))
print(f"problems built {checked}: presentation not [profit | published coefficients | zeros]: {bad_present}; "
      f"evaluator's arrays differ from the pre-correction ones: {bad_pre}")
print(f"answers evaluated {answers}: totals differ from an independent evaluation: {bad_eval}; "
      f"scores differ from an independent score: {bad_score}; fast rows differ from the specification: {bad_fast}")
V = view(env.problem("5.100-00", Meter(float("inf")), 3, False)[0])
print("what the learner is handed (public fields of the view):", sorted(k for k in vars(V) if not k.startswith("_")))
train_ids, fresh_ids = split(env, 16, 24)
print("registered split: training m:", dict(collections.Counter(len(mine[i][2]) for i in train_ids)),
      "| fresh m:", dict(collections.Counter(len(mine[i][2]) for i in fresh_ids)),
      "| largest m among training and fresh:", max(len(mine[i][2]) for i in train_ids + fresh_ids))
by_m = collections.Counter(len(l) for _, _, l in mine.values())
print("instances by m:", dict(by_m), "| share discarded if one m were kept:",
      {m: round(1 - c / len(mine), 3) for m, c in by_m.items()})

# ---------------------------------------------------------------------------------- regression
print("== REGRESSION")
env = environments.load("regression")
import json                                                      # noqa: E402
manifest = json.load(open(os.path.join(REPO, "rsi6", "environments", "manifests", "regression.json")))
cols = {}
for entry in manifest["files"]:
    tier, part, name = entry["path"].split("/")
    with open(os.path.join(DATA, "regression", tier, part, name)) as handle:
        first = handle.readline().split()
    cols.setdefault(f"{tier}/{name[:-4]}", {})[part] = len(first) - 1
print("laws in the manifest:", len(cols), "| val and test files agree on the number of input columns:",
      all(v["val"] == v["test"] for v in cols.values()))
dist_all = collections.Counter(v["test"] for v in cols.values())
print("number of input variables -> laws (all 120):", dict(sorted(dist_all.items())))
print("refused at load:", env.refused, "with input variables", [cols[i]["test"] for i in env.refused])
usable = env.instance_ids()
dist = collections.Counter(cols[i]["test"] for i in usable)
print("usable laws:", len(usable), "| number of input variables -> laws:", dict(sorted(dist.items())),
      "| smallest", min(dist), "largest", max(dist), "| env.width", env.width)
print("by tier:", {t: dict(sorted(collections.Counter(cols[i]["test"] for i in usable if i.startswith(t)).items()))
                   for t in ("easy", "medium", "hard")})
print("laws with the largest number of variables:", [i for i in cols if cols[i]["test"] == max(dist_all)])
train_ids, fresh_ids = split(env, 16, 24)
print("registered split: training laws' variables:", dict(sorted(collections.Counter(cols[i]["test"] for i in train_ids).items())),
      "| fresh laws' variables:", dict(sorted(collections.Counter(cols[i]["test"] for i in fresh_ids).items())),
      "| largest among training and fresh:", max(cols[i]["test"] for i in train_ids + fresh_ids))
print("share of usable laws discarded if only laws with k variables were kept:",
      {k: round(1 - c / len(usable), 3) for k, c in sorted(dist.items())})
bad = built = const_cols = zero_cols = 0
for iid in usable:
    ctx_x, ctx_y, qry_x, qry_y = env._load(iid)
    a = ctx_x.shape[1]
    const_cols += int(np.any(ctx_x.std(axis=0) == 0))
    zero_cols += int(np.any(~ctx_x.any(axis=0)))
    for seed in (run._seed(101, "regression", iid, "relabel"), 3):
        for training in (True, False):
            P, decode = env.problem(iid, Meter(float("inf")), seed, training)
            columns = np.random.default_rng(seed).permutation(a)
            built += 1
            ok = (P.ctx_x.shape == (len(ctx_y), 8) and P.qry_x.shape == (len(qry_y), 8)
                  and np.array_equal(P.ctx_x[:, :a], ctx_x[:, columns]) and not P.ctx_x[:, a:].any()
                  and np.array_equal(P.qry_x[:, :a], qry_x[:, columns]) and not P.qry_x[:, a:].any()
                  and np.array_equal(P.ctx_y, ctx_y) and P.ordered is False
                  and ((P.qry_y is not None and np.array_equal(P.qry_y, qry_y)) if training else P.qry_y is None))
            bad += not ok
print(f"problems built {built}: presentation not [published columns (relabelled) | zeros], or targets changed: {bad}")
print("usable laws with a constant published input column in the observed sample:", const_cols,
      "| with an all-zero published input column:", zero_cols)
rng = np.random.default_rng(5)
bad_score = 0
for iid in usable[:40]:
    target = env._load(iid)[3]
    guess = target + rng.normal(scale=target.std() * 0.1 + 1e-12, size=target.shape)
    want = float(np.clip(1.0 - ((guess - target) ** 2).sum() / ((target - target.mean()) ** 2).sum(), 0.0, 1.0))
    bad_score += abs(env.score(iid, guess) - want) > 1e-12
print("scores of 40 made-up answers that differ from an independent computation:", bad_score)
V = view(env.problem(usable[0], Meter(float("inf")), 3, False)[0])
print("what the learner is handed (public fields of the view):", sorted(k for k in vars(V) if not k.startswith("_")))
