"""The numbers of the relay experiment (design r), recomputed from the ledger.

    python -m rsi6.open.relay_report [--ledger PATH] [--registration PATH] [--json OUT]

Nothing is typed by hand. Reports, misses first: the registered predictions; the endpoints
E-R1 (relay minus frozen), E-R2 (relay minus shuffled), E-R3 (relay minus o0@relay: m_net, the
net change of held-out capability that the whole mechanism buys over the fixed design given the
same measured CPU) and E-R4 (relay minus offpolicy: the on-policy part, beyond the accumulation
of the same amount of record); the diagnostics; and, over the positions of the chains (the
generations of the discovery machinery), the discovery efficiency, the capability and the CPU
of the on-policy chains beside the off-policy ones, and retention.

Within the design-r arms the untrained answers are the same (same version, same apply stream),
so the change of the gain equals the change of the acquired score; comparisons with o0 use the
registered statistic, the smaller of the two.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.open import evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def t_quantile(p: float, df: int) -> float:
    """One-sided Student t quantile by bisection on the regularised incomplete beta (no scipy)."""
    def cdf(t):
        x = df / (df + t * t)
        # regularised incomplete beta I_x(df/2, 1/2) by continued fraction (Lentz)
        a, b = df / 2.0, 0.5
        lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
        f, c, d = 1.0, 1.0, 0.0
        for i in range(200):
            m = i // 2
            if i == 0:
                num = 1.0
            elif i % 2 == 0:
                num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
            d = 1.0 + num * d
            d = 1.0 / d if abs(d) > 1e-30 else 1e30
            c = 1.0 + num / c if abs(c) > 1e-30 else 1e30
            f *= c * d
            if abs(c * d - 1.0) < 1e-12:
                break
        ib = front * (f - 1.0)
        return 1.0 - 0.5 * ib if t > 0 else 0.5 * ib
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if cdf(mid) < 1 - p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def paired(arm_rows, base_rows, chain_of, statistic="acquired"):
    """Per chain: the mean over categories of the mean over seeds of arm minus base, paired by
    (category, seed). Returns per-chain means, per-category means, the cells used."""
    base = {(r["env"], r["seed"]): r for r in base_rows}
    by_chain_env = {}
    for r in arm_rows:
        b = base.get((r["env"], r["seed"]))
        if b is None:
            continue
        if statistic == "min":
            d = min(r["acquired"] - b["acquired"], r["gain"] - b["gain"])
        else:
            d = r["acquired"] - b["acquired"]
        by_chain_env.setdefault(chain_of(r["seed"]), {}).setdefault(r["env"], []).append(d)
    chains = {j: float(np.mean([np.mean(v) for v in envs.values()])) for j, envs in by_chain_env.items()}
    envs = {}
    for j, ev in by_chain_env.items():
        for e, v in ev.items():
            envs.setdefault(e, []).extend(v)
    return chains, {e: float(np.mean(v)) for e, v in envs.items()}, sum(len(v) for ev in by_chain_env.values() for v in ev.values())


def endpoint(arm, base, chain_of, alpha, statistic="acquired", min_effect=None):
    chains, per_env, n = paired(arm, base, chain_of, statistic)
    x = np.array([chains[j] for j in sorted(chains)])
    if len(x) < 2:
        return {"n_pairs": n, "chains": len(x)}
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    t = mean / (sd / math.sqrt(len(x))) if sd > 0 else (math.inf if mean > 0 else 0.0)
    crit = t_quantile(alpha, len(x) - 1)
    rng = np.random.default_rng(20261116)
    boot = [float(x[rng.integers(0, len(x), len(x))].mean()) for _ in range(5000)]
    return {"mean": mean, "t": t, "critical_t": crit, "met": bool(t >= crit and (min_effect is None or mean >= min_effect)),
            "interval_95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "upper_95": float(mean + t_quantile(0.05, len(x) - 1) * sd / math.sqrt(len(x))),
            "per_category": per_env, "categories_positive": int(sum(v > 0 for v in per_env.values())),
            "chains": len(x), "n_pairs": n, "cpu_ratio": float(sum(evaluate.cpu(r) for r in arm) / max(sum(evaluate.cpu(r) for r in base), 1e-9))}


def productivity(rows):
    """Inner discovery per acquisition, from the run reports: switches per program round, mean
    credited value per variant, share of acquisitions that keep a switched program."""
    rounds = sum((r.get("report") or {}).get("program_rounds", 0) for r in rows)
    switches = sum((r.get("report") or {}).get("switches", 0) for r in rows)
    kept = float(np.mean([bool((r.get("report") or {}).get("program_size")) for r in rows])) if rows else None
    n = s = 0.0
    for r in rows:
        rel = (r.get("report") or {}).get("relay")
        if rel:
            for cn, cs, _ in rel["cells"]:
                n += cn
                s += cs
    return {"switches_per_round": switches / rounds if rounds else None, "mean_d_per_variant": s / n if n else None,
            "kept_program": kept, "acquisitions": len(rows)}


def build(ledger, reg) -> dict:
    by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}
    out = {"registration": reg.get("what")}
    base_seed = reg["seeds"]["heldout_base"]
    chain_of = lambda seed: (seed - base_seed) // 10

    # the generations: positions of the chains
    curves = {}
    for kind in ("on", "off"):
        for s in ledger.select(type="r_chain", kind=kind):
            r = by_key[s["key"]]
            cell = curves.setdefault(kind, {}).setdefault(s["position"], [])
            cell.append(r)
    out["generations"] = {kind: {k: dict(productivity(rows), env=rows[0]["env"], acquired=float(np.mean([r["acquired"] for r in rows])),
                                         gain=float(np.mean([r["gain"] for r in rows])),
                                         cpu=float(np.mean([evaluate.cpu(r) for r in rows])))
                                 for k, rows in sorted(v.items())} for kind, v in curves.items()}
    ret = ledger.select(type="r_chain", kind="retention")
    if ret:
        d = [by_key[s["key"]]["acquired"] - by_key[s["key_empty"]]["acquired"] for s in ret]
        out["retention"] = {"final memory minus empty memory, first category": float(np.mean(d)), "chains": len(d),
                            "sd": float(np.std(d, ddof=1)) if len(d) > 1 else None}
    held = find(ledger, type="r_stage_done", stage="heldout")
    if held:
        arms = {name: [by_key[k] for k in keys] for name, keys in held["arms"].items()}
        matched = find(ledger, type="r_matched", arm="o0@relay")
        if matched:
            for row, reached in zip(arms["o0@relay"], matched["reached"]):
                row["reached"] = reached
        a = reg["heldout"]["alpha"]
        E = {}
        E["E-R1 relay minus frozen"] = endpoint(arms["relay"], arms["frozen"], chain_of, a["primary"], min_effect=None)
        E["E-R2 relay minus shuffled"] = endpoint(arms["relay"], arms["shuffled"], chain_of, a["secondary"])
        E["E-R3 relay minus o0@relay (m_net)"] = endpoint(arms["relay"], arms["o0@relay"], chain_of, a["secondary"], statistic="min")
        E["E-R4 relay minus offpolicy"] = endpoint(arms["relay"], arms["offpolicy"], chain_of, a["secondary"])
        unreached = int(sum(1 for r in arms["o0@relay"] if r.get("reached") is False))
        less = sum(1 for r in arms["o0@relay"] for s in arms["relay"] if (s["env"], s["seed"]) == (r["env"], r["seed"]) and evaluate.cpu(r) < evaluate.cpu(s))
        E["E-R3 relay minus o0@relay (m_net)"]["void"] = bool(unreached or less)
        out["endpoints"] = E
        D = {"L1 frozen minus o0@relay": endpoint(arms["frozen"], arms["o0@relay"], chain_of, a["secondary"], statistic="min"),
             "L2 ceiling minus frozen": endpoint(arms["frozen@ceiling"], arms["frozen"], chain_of, a["secondary"]),
             "L5 shuffled minus frozen": endpoint(arms["shuffled"], arms["frozen"], chain_of, a["secondary"]),
             "prior-only minus frozen": endpoint(arms["prior"], arms["frozen"], chain_of, a["secondary"]),
             "blocks-only minus frozen": endpoint(arms["blocks"], arms["frozen"], chain_of, a["secondary"]),
             "L3 inner productivity": {name: productivity(rows) for name, rows in arms.items() if name not in ("o0@relay",)}}
        out["diagnostics"] = D
        e1, e2, e4 = E["E-R1 relay minus frozen"], E["E-R2 relay minus shuffled"], E["E-R4 relay minus offpolicy"]
        out["success"] = {"improved its own discovery (E-R1 and E-R2)": bool(e1.get("met") and e2.get("met")),
                          "recursively (and E-R4)": bool(e1.get("met") and e2.get("met") and e4.get("met")),
                          "useful at matched compute (and E-R3, not void)": bool(e1.get("met") and e2.get("met")
                                                                                  and E["E-R3 relay minus o0@relay (m_net)"].get("met")
                                                                                  and not E["E-R3 relay minus o0@relay (m_net)"]["void"])}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=MAIN)
    parser.add_argument("--registration", default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    rec = find(ledger, type="registration_r")
    reg = rec["registration"] if rec else (json.load(open(args.registration)) if args.registration else None)
    if reg is None:
        print("the relay experiment is not registered in this ledger")
        return 0
    out = build(ledger, reg)
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
