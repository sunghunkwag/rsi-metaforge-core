"""D4 (development, source categories only): the CPU model of a run,
recorded CPU = a + b * train * U_train + d * U_test, fitted by least squares on the development runs
of D1 and D2, per design (o0 and r0), with its residual sd, and the r0/o0 CPU ratio of D1's pairs.
U_train and U_test are the construction units of a run's training and fresh problems, read from
problems built with a dummy meter (no learner, no score). The registered held-out stage applies
the model to the held-out categories' units, which it reads at its start.

    python3 dev_r_d4.py D1_SUMMARY.json D1_LEDGER D2_LEDGER [D2_LEDGER ...]

The runs of D1 are those its summary lists (by key); the runs of D2 are the chain acquisitions
(relay-meta:) and the arms on the left-out category (dev-d2:) of its ledgers. Only runs of the
registered version of design r and of design o's generation 0 enter.
"""
import json
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np

from rsi6 import environments
from rsi6.kernel import ledger as ledgers
from rsi6.learner import design_r, designs, dispatch_extra
from rsi6.open import evaluate, relay

dispatch_extra.install()
S = os.path.dirname(os.path.abspath(__file__))
o0d, r0d = designs.digest(designs.default("o")), designs.digest(design_r.default())
U = {}
rows = {"o0": [], "r0": []}
seen = set()
d1 = {}
summary = json.load(open(sys.argv[1]))
d1_keys = {x["key"]: arm for arm, xs in summary["runs"].items() for x in xs}
for n, path in enumerate(sys.argv[2:]):
    for r in ledgers.Ledger(path).records:
        if r.get("type") != "run" or r.get("budget", {}).get("n_train") != 16:
            continue
        if n == 0:
            if r.get("key") not in d1_keys:
                continue
        elif not str(r.get("purpose", "")).startswith(("relay-meta:", "dev-d2:")):
            continue
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        kind = "o0" if r["version"] == o0d else ("r0" if r["version"] == r0d else None)
        if kind is None:
            continue
        e = r["env"]
        if e not in U:
            U[e] = relay.units(environments.load(e))
        x = [1.0, r["units"]["train_limit"], U[e]["test"] * (0.5 if r["budget"].get("part") in ("A", "B") else 1.0)]
        rows[kind].append((x, evaluate.cpu(r), e, r["budget"]["train"], r["budget"].get("part")))
        if n == 0 and d1_keys[r["key"]] in ("r0", "o0"):
            d1.setdefault((e, r["seed"]), {})[kind] = evaluate.cpu(r)
out = {"fits": {}}
for kind, data in rows.items():
    if len(data) < 5:
        continue
    X = np.array([d[0] for d in data]); y = np.array([d[1] for d in data])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    out["fits"][kind] = {"a": float(coef[0]), "b": float(coef[1]), "d": float(coef[2]), "residual_sd": float(res.std(ddof=3)), "n": len(data),
                         # a chain acquisition of the registered meta stage: train 200, the deciding half of the fresh instances
                         "meta_run_cpu": {e: float(np.mean([d[1] for d in data if d[2] == e and d[3] == 200.0 and d[4] == "A"]))
                                          for e in sorted({d[2] for d in data if d[3] == 200.0 and d[4] == "A"})},
                         # a run at train 200 on all fresh instances (D1, and D2's arms on the left-out category)
                         "full_run_cpu": {e: float(np.mean([d[1] for d in data if d[2] == e and d[3] == 200.0 and d[4] is None]))
                                          for e in sorted({d[2] for d in data if d[3] == 200.0 and d[4] is None})}}
# the r0/o0 ratio from D1's pairs alone: the same category, seed and budget (train 200, all fresh instances)
both = [v for v in d1.values() if "r0" in v and "o0" in v]
out["r0_over_o0"] = float(sum(v["r0"] for v in both) / sum(v["o0"] for v in both)) if both else None
out["r0_over_o0_pairs"] = len(both)
out["r0_over_o0_by_category"] = {e: float(sum(v["r0"] for (c, s), v in d1.items() if c == e and "o0" in v and "r0" in v)
                                          / sum(v["o0"] for (c, s), v in d1.items() if c == e and "o0" in v and "r0" in v))
                                 for e in sorted({c for c, s in d1})}
# Nothing here reads a held-out (fresh) category: its instance sizes are read by the registered held-out
# stage alone, at its start. Planning uses the specification's planning cost for those categories.
json.dump(out, open(os.path.join(S, "dev_r_d4.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
