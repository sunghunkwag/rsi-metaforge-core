"""D3 (development, no CPU): L4 on the D2 chains, the cross-category Spearman correlation of the
per-cell learned statistics (m_c / ubar), computed by the report's own function on the stats
entries of the on-policy development chains, pooled per category over the three D2 ledgers.

    python3 dev_r_d3.py
"""
import json
import os
import sys

sys.path.insert(0, "<repo>")
from rsi6.kernel import ledger as ledgers
from rsi6.learner import design_r
from rsi6.open.relay_report import l4, stats_of

S = os.path.dirname(os.path.abspath(__file__))
kappa = design_r.RELAY0["kappa"]
groups, per_ledger = {}, {}
for f in ("quadassign", "jobshop", "pmedian"):
    path = os.path.join(S, f"dev_r_d2n_{f}.jsonl")
    if not os.path.exists(path):
        continue
    L = ledgers.Ledger(path)
    by_key = {r["key"]: r for r in L.records if r.get("type") == "run" and "key" in r}
    mine = {}
    for s in L.select(type="r_memory"):
        if s["policy"] != "on":
            continue
        e = stats_of(by_key[s["run_key"]])
        if e is not None:
            groups.setdefault(s["env"], []).append(e)
            mine.setdefault(s["env"], []).append(e)
    per_ledger[f"left out {f}"] = l4(mine, kappa)
out = {"pooled over the D2 ledgers": l4(groups, kappa), "per D2 ledger": per_ledger,
       "acquisitions per category": {c: len(v) for c, v in groups.items()}}
v = out["pooled over the D2 ledgers"]["mean_pairwise_spearman"]
out["rule"] = ("L4 sets the expected value registered for P3; at most 0.1 means the registration states that transfer of discovery "
               "knowledge is predicted to fail and lowers P7 and P10")
out["transfer_predicted_to_fail"] = bool(v is not None and v <= 0.1)
json.dump(out, open(os.path.join(S, "dev_r_d3.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
