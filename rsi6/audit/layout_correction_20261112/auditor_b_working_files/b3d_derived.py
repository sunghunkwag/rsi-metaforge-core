"""Auditor B, B3 (derived records): do the recorded search, gate and confirm records still follow
from the recorded runs under the code now in REPO?

The driver's own functions (rsi6.meta.rounds.search / gate / confirm) are called with a cache that
serves runs from the ledger and can run nothing (a job that is not in the ledger raises KeyError).
No environment is run; in a search the learner works on the space of versions only, as it did in
the registered run.  Reads REPO; writes nothing.
"""
import json
import os
import sys

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
sys.path.insert(0, REPO)

from rsi6 import environments                       # noqa: E402
from rsi6.kernel import ledger as ledgers           # noqa: E402
from rsi6.kernel import roles, run                  # noqa: E402
from rsi6.learner import version as versions        # noqa: E402
from rsi6.meta import rounds                        # noqa: E402

PATH = os.path.join(REPO, "rsi6", "ledger", "main.jsonl")
book = ledgers.Ledger(PATH)
records = book.records
reg = json.load(open(os.path.join(REPO, "rsi6", "registry", "registration.json")))
rounds.RULES.update(reg["rules"])


class LedgerCache:
    """Serves recorded runs; never runs anything."""

    def __init__(self, by_key):
        self.by_key = by_key
        self.asked = 0

    def get(self, jobs, workers=4):
        self.asked += len(jobs)
        return [self.by_key[run.key_of(job)] for job in jobs]


class Prefix:
    def __init__(self, upto):
        self.records = records[:upto]


def differences(old, new, skip=("idx", "prev", "h", "round", "name")):
    out = {}
    for k in sorted((set(old) | set(new)) - set(skip)):
        if k not in old or k not in new or ledgers.canon(old[k]) != ledgers.canon(new[k]):
            out[k] = (old.get(k, "absent"), new.get(k, "absent"))
    return out


v0 = versions.default()
lineage = {"self": v0, "fixed": v0, "random": v0}
cpu_limit = reg["search_cpu_limit"]
all_same = True
for position, record in enumerate(records):
    kind = record.get("type")
    if kind == "adopt":
        lineage[record["lineage"]] = record["version"]
    if kind not in ("search", "gate", "confirm"):
        continue
    # the cache as the driver had it at that moment: the runs recorded before this record
    cache = LedgerCache({r["key"]: r for r in records[:position] if r.get("type") == "run"})
    g, name = record["round"], record["name"]
    try:
        if kind == "search":
            source = sorted(n for n in environments.REGISTRY
                            if roles.effective_role(environments.load(n).category, Prefix(position)) == "source")
            improver_kind = record["improver"]
            improver = v0 if name in ("fixed", "fixed@self") else (lineage["self"] if name == "self" else None)
            start = lineage["self"] if name.endswith("@self") else lineage[name]
            previous = [r for r in records[:position] if r.get("type") == "search" and r.get("tag") == f"search:{g - 1}:self"]
            stats = previous[-1].get("edit_stats") if (name == "self" and previous) else None
            new = rounds.search(improver_kind, improver, start, source, reg["seeds"]["search"], reg["budgets"]["search"],
                                cpu_limit, cache, record["tag"], seed=1000 * g + (1 if improver_kind == "learner" else 2),
                                edit_stats=stats)
        else:
            adoption = sorted(n for n in environments.REGISTRY if roles.role_of(environments.load(n).category) == f"adoption:{g}")
            search = [r for r in records[:position] if r.get("type") == "search" and r.get("tag") == f"search:{g}:{name}"][-1]
            start = lineage["self"] if name.endswith("@self") else lineage[name]
            if kind == "gate":
                new = rounds.gate(start, search["nominee_version"], adoption, reg["seeds"]["gate"], reg["budgets"]["run"],
                                  cache, record["tag"], seed=g)
            else:
                new = rounds.confirm(start, search["nominee_version"], adoption, reg["seeds"]["confirm"],
                                     reg["budgets"]["run"], cache, record["tag"])
        diff = differences(record, new)
        text = "IDENTICAL" if not diff else f"DIFFERENT in {sorted(diff)}: {json.dumps(diff, sort_keys=True)[:600]}"
        all_same &= not diff
    except KeyError as error:
        text = f"NOT REPRODUCED: the recomputation asked for a run that the ledger did not hold at that point ({error})"
        all_same = False
    print(f"idx {record['idx']:5d} {record['tag']:22s} fields compared {len(set(record) - {'idx', 'prev', 'h', 'round', 'name'})}, "
          f"runs asked of the ledger {cache.asked}: {text}")
print("every search, gate and confirm record follows from the recorded runs under the present code:", all_same)
full = Prefix(len(records))
print("source pool now:", rounds.pool(full), "| role check now: knapsack ->", roles.check("knapsack", full),
      "| regression ->", roles.check("regression", full))
print("adoption decisions recorded:", [(r["tag"], r["adopted"], r["conditions"]) for r in records if r.get("type") == "gate"])
print("adopt records:", sum(1 for r in records if r.get("type") == "adopt"))
