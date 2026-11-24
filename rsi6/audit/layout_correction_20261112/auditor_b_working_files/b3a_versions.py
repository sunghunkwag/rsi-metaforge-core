"""Auditor B, B3 (preparation): recover the version dictionary behind every version digest of the
ledger's run records, and account for every run record.

Sources of version dictionaries:
  * rsi6.learner.version.default()
  * the field nominee_version of the search records
  * a replay of each search: the improver's sequence of proposals is a function of its seed and of
    the costs it was given, and the search records carry those costs (rounded to 6 decimals).  The
    replay calls the learner only on the *version space* (rsi6.meta.space.VersionProblem), with a
    cost function that returns the recorded costs; no environment is touched.
The replay is checked against the ledger: every job it implies must have its key in the ledger, and
the keys it implies, with those of the gates and confirmations, must be exactly the ledger's keys.

Reads REPO; writes only WORK/versions.json.
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

from rsi6.kernel import ledger as ledgers                      # noqa: E402
from rsi6.kernel.problem import BudgetExhausted, Meter, view   # noqa: E402
from rsi6.kernel import run                                    # noqa: E402
from rsi6.learner import version as versions                   # noqa: E402
from rsi6.learner.learner import Learner                       # noqa: E402
from rsi6.meta import space                                    # noqa: E402

book = ledgers.Ledger(os.path.join(REPO, "rsi6", "ledger", "main.jsonl"))
records = book.records
runs = [r for r in records if r["type"] == "run"]
reg = [r for r in records if r["type"] == "registration"][0]["registration"]
by_key = {r["key"]: r for r in runs}
v0 = versions.default()
known = {versions.digest(v0): v0}
print("default version digest:", versions.digest(v0), "| equals freeze_L0 version_digest:",
      versions.digest(v0) == json.load(open(os.path.join(REPO, "rsi6/registry/freeze_L0.json")))["version_digest"])

searches = [r for r in records if r["type"] == "search"]
for s in searches:
    if s["nominee_version"] is not None:
        d = versions.digest(s["nominee_version"])
        assert d == s["nominee"], (s["tag"], "nominee digest differs from the digest of nominee_version")
        known[d] = versions.validate(s["nominee_version"])
print("digests known from default() and nominee_version:", len(known))


def key_for(env, version, seed, budget):
    return run.key_of({"env": env, "version": version, "seed": seed, "budget": budget})


def replay(s, edit_stats):
    """The versions a recorded search evaluated, in order, from its seed and its recorded costs."""
    g = s["round"]
    start = known[s["start"]]
    costs = list(s["costs"])
    position = [0]
    limit = 1.0e18

    def cost(version):
        if position[0] >= len(costs):
            raise BudgetExhausted()                 # the recorded search had stopped before this proposal
        value = costs[position[0]]
        position[0] += 1
        return value, 0.0

    meter = Meter(limit)
    problem = space.VersionProblem(start, cost, meter)
    seed = 1000 * g + (1 if s["improver"] == "learner" else 2)
    rng = np.random.default_rng(seed)
    if s["improver"] == "learner":
        improver = known[s["improver_version"]]
        learner = Learner(improver)
        capability = {"kind": "assign", "weights": {}, "edit_stats": edit_stats} if edit_stats else None
        learner.apply(capability, view(problem), rng)
    else:
        first = problem.start_answer
        try:
            while True:
                answer = first.copy()
                k = int(rng.integers(problem.n_vars))
                choices = np.flatnonzero(problem.domain[k])
                choices = choices[choices != first[k]]
                answer[k] = int(choices[int(rng.integers(len(choices)))])
                problem.evaluate(answer)
        except BudgetExhausted:
            pass
    return problem.history, position[0]


implied = set()
budget_search, budget_run = reg["budgets"]["search"], reg["budgets"]["run"]
seeds = reg["seeds"]
edit_stats_of = {}
for s in searches:
    tag = s["tag"]
    g, name = s["round"], s["name"]
    previous = edit_stats_of.get(f"search:{g - 1}:self")
    stats = previous if name == "self" else None
    history, consumed = replay(s, stats)
    edit_stats_of[tag] = s.get("edit_stats")
    ok_count = len(history) == s["evaluated"] and consumed == len(s["costs"])
    start = known[s["start"]]
    missing = 0
    for e in s["envs"]:
        for sd in s["seeds"]:
            k = key_for(e, start, sd, budget_search)
            implied.add(k)
            missing += k not in by_key
    new = 0
    order_ok = True
    last_idx = -1
    for h in history:
        d = versions.digest(h["version"])
        if d not in known:
            known[d] = h["version"]
            new += 1
        idxs = []
        for e in s["envs"]:
            for sd in s["seeds"]:
                k = key_for(e, h["version"], sd, budget_search)
                implied.add(k)
                if k not in by_key:
                    missing += 1
                else:
                    idxs.append(by_key[k]["idx"])
    best = min(history, key=lambda h: h["cost"]) if history else None
    nominee_ok = (best is not None and best["cost"] < 0 and versions.digest(best["version"]) == s["nominee"]) or \
                 (s["nominee"] is None and (best is None or best["cost"] >= 0))
    print(f"{tag}: improver {s['improver']}, recorded evaluated {s['evaluated']}, replayed {len(history)}, "
          f"costs consumed {consumed}/{len(s['costs'])}, count ok {ok_count}, jobs missing from ledger {missing}, "
          f"new digests {new}, replayed best is the recorded nominee: {nominee_ok}")

# gates and confirmations
for r in records:
    if r["type"] in ("gate", "confirm"):
        part = dict(budget_run, part="A" if r["type"] == "gate" else "B")
        missing = 0
        for d in (r["incumbent"], r["nominee"]):
            for e in r["envs"]:
                for sd in r["seeds"]:
                    k = key_for(e, known[d], sd, part)
                    implied.add(k)
                    missing += k not in by_key
        print(f"{r['tag']}: jobs missing from ledger {missing}")

print("keys implied by the replay:", len(implied), "| keys in the ledger:", len(by_key),
      "| implied == ledger:", implied == set(by_key), "| ledger keys not implied:", len(set(by_key) - implied),
      "| implied keys not in ledger:", len(implied - set(by_key)))
digests = {r["version"] for r in runs}
print("version digests in run records:", len(digests), "| recovered:", len(digests & set(known)),
      "| not recovered:", len(digests - set(known)))
# every run record's key recomputed from the recovered version
bad = [r["idx"] for r in runs if r["version"] in known and
       key_for(r["env"], known[r["version"]], r["seed"], r["budget"]) != r["key"]]
print("run records whose key differs from the key recomputed from the recovered version:", len(bad))
json.dump(known, open(os.path.join(WORK, "versions.json"), "w"), indent=0, sort_keys=True)

# near-ties of recorded costs (a replay from rounded costs could go wrong there)
for s in searches:
    c = sorted(s["costs"])
    gaps = [b - a for a, b in zip(c, c[1:]) if b - a < 2e-6 and b != a]
    print(f"{s['tag']}: recorded costs {len(c)}, distinct {len(set(c))}, pairs closer than 2e-6 but not equal: {len(gaps)}")

# measured CPU of the recorded runs, to plan the repetition
cpu = collections.defaultdict(list)
for r in runs:
    cpu[(r["env"], r["budget"]["n_train"], r["budget"].get("part"))].append(r["cpu"]["acquire"] + r["cpu"]["apply"])
print("recorded CPU-seconds (acquire + apply) per run:")
for k, v in sorted(cpu.items()):
    print("   ", k, "n", len(v), "mean %.1f  median %.1f  max %.1f" % (np.mean(v), np.median(v), np.max(v)))
print("versions by number of fields changed from the default:",
      dict(sorted(collections.Counter(len(versions.differences(v0, known[d])) for d in digests if d in known).items())))
