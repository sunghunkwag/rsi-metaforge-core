"""Read the depth measurement by the rules of ``rsi6/results/dev_proof_depth_20261128/PLAN.md``.

    python -m rsi6.experiments.read_proof_depth A.json B.json C.json
"""
from __future__ import annotations

import collections
import json
import sys


def depths(rows) -> dict:
    """Depth of every proof of an arm: 0 without pool theorems, else 1 + the largest depth among those it uses."""
    d = {}
    for r in rows:
        if r.get("proved"):
            used = [d[x] for x in r["lemmas"] if x in d]
            missing = [x for x in r["lemmas"] if x not in d]
            if missing:
                raise ValueError(f"{r['label']} uses {missing}, which this arm did not prove before it")
            d[r["label"]] = 0 if not r["lemmas"] else 1 + max(used)
    return d


def read(a: dict, b: dict, c: dict) -> dict:
    rows = {arm["arm"]: arm["rows"] for arm in (a, b, c)}
    readable = [r["label"] for r in rows["A"] if r["readable"]]
    order = {lab: k for k, lab in enumerate(readable)}
    proved = {arm: {r["label"] for r in rs if r.get("proved")} for arm, rs in rows.items()}
    rejected = {arm: [r["label"] for r in rs if r.get("note")] for arm, rs in rows.items()}
    dB = depths(rows["B"])
    only_b = proved["B"] - proved["A"]
    out = {"readable": len(readable), "unreadable": sum(1 for r in rows["A"] if not r["readable"]),
           "proved": {arm: len(p) for arm, p in proved.items()}, "rejected": rejected,
           "B_not_A": len(only_b), "A_not_B": len(proved["A"] - proved["B"]),
           "depth_hist_B": dict(sorted(collections.Counter(dB.values()).items())),
           "depth_hist_B_not_A": dict(sorted(collections.Counter(dB[x] for x in only_b).items())),
           "max_depth_B": max(dB.values()) if dB else 0}
    late = {lab for lab in readable if order[lab] >= 200}
    out["after_first_200"] = {"readable": len(late), "proved": {arm: len(p & late) for arm, p in proved.items()},
                              "B_not_A": len(only_b & late),
                              "B_not_A_depth_2_or_more": sum(1 for x in only_b & late if dB[x] >= 2)}
    n_depth2 = sum(1 for x in only_b if dB[x] >= 2)
    out["R0_valid"] = not any(rejected.values())
    out["R1_first_step"] = (len(proved["B"]) - len(proved["A"]) >= 0.10 * len(readable)) and len(only_b) >= 100
    out["R2_second_step"] = n_depth2 >= 30
    out["B_not_A_depth_2_or_more"] = n_depth2
    # the longest chain of B's own theorems behind one proof
    by = {r["label"]: r for r in rows["B"] if r.get("proved")}
    deepest = max(dB, key=lambda x: (dB[x], -order.get(x, 0))) if dB else None
    chain, x = [], deepest
    while x is not None:
        chain.append(x)
        nxt = [y for y in by[x]["lemmas"] if dB.get(y) == dB[x] - 1]
        x = nxt[0] if nxt else None
    out["deepest_chain"] = chain
    out["seconds"] = {arm["arm"]: arm["seconds"] for arm in (a, b, c)}
    return out


def main() -> None:
    a, b, c = (json.load(open(p)) for p in sys.argv[1:4])
    print(json.dumps(read(a, b, c), indent=1))


if __name__ == "__main__":
    main()
