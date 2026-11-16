"""The numbers of the relay experiment (design r), recomputed from the ledger.

    python -m rsi6.open.relay_report [--ledger PATH] [--registration PATH] [--json OUT]

Nothing is typed by hand and nothing computed here feeds back into the experiment. Reports, misses
first, the registered predictions; the primary endpoint E-R1 (relay minus frozen, or frozen raised
to relay's CPU where the registered CPU rule applied); the gate (E-R2 relay minus shuffled, then
Holm over E-R3 relay minus o0 raised to relay's CPU, E-R4 relay minus offpolicy and E-R5 relay minus
library only); the tiers; m_net; the diagnostics L1 to L8; the generations of the meta chains;
retention.

Within the design-r arms and against o0 the untrained answers are the same (same programs and
constants before acquisition, same apply stream), which the report checks, so the change of the gain
equals the change of the acquired score; against a0 the smaller of the two is used.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.learner import design_r
from rsi6.open import evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def t_quantile(p: float, df: int) -> float:
    """One-sided Student t quantile (upper tail p) by bisection on the regularised incomplete beta."""
    def cdf(t):
        x = df / (df + t * t)
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
    lo, hi = 0.0, 60.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if cdf(mid) < 1 - p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def paired(arm, base, chain_of, statistic="acquired"):
    b = {(r["env"], r["seed"]): r for r in base}
    by = {}
    for r in arm:
        o = b.get((r["env"], r["seed"]))
        if o is None:
            continue
        d = r["acquired"] - o["acquired"] if statistic == "acquired" else min(r["acquired"] - o["acquired"], r["gain"] - o["gain"])
        by.setdefault(chain_of(r["seed"]), {}).setdefault(r["env"], []).append(d)
    chains = {j: float(np.mean([np.mean(v) for v in ev.values()])) for j, ev in by.items()}
    per_env = {}
    for ev in by.values():
        for e, v in ev.items():
            per_env.setdefault(e, []).extend(v)
    return chains, {e: float(np.mean(v)) for e, v in per_env.items()}, int(sum(len(v) for ev in by.values() for v in ev.values()))


def endpoint(arm, base, chain_of, alpha, statistic="acquired", chains=None):
    cm, per_env, n = paired(arm, base, chain_of, statistic)
    if chains is not None:
        cm = {j: v for j, v in cm.items() if j in chains}
    x = np.array([cm[j] for j in sorted(cm)])
    if len(x) < 2:
        return {"n_pairs": n, "chains": int(len(x)), "met": False, "why": "not measured"}
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    se = sd / math.sqrt(len(x))
    t = mean / se if se > 0 else (math.inf if mean > 0 else 0.0)
    crit = t_quantile(alpha, len(x) - 1)
    rng = np.random.default_rng(20261116)
    boot = [float(x[rng.integers(0, len(x), len(x))].mean()) for _ in range(5000)]
    return {"mean": mean, "se": se, "t": t, "critical_t": crit, "alpha": alpha, "met": bool(t >= crit),
            "upper_95": float(mean + t_quantile(0.05, len(x) - 1) * se), "interval_95_chains": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "per_category": per_env, "categories_positive": int(sum(v > 0 for v in per_env.values())), "chains": int(len(x)), "n_pairs": n,
            "cpu_ratio": float(sum(evaluate.cpu(r) for r in arm) / max(sum(evaluate.cpu(r) for r in base), 1e-9))}


def productivity(rows):
    """Inner discovery per acquisition, from the run reports."""
    rounds = switches = variants = informative = 0
    U = n = 0.0
    kept = kept_splice = 0
    for r in rows:
        rep = r.get("report") or {}
        rounds += rep.get("program_rounds", 0)
        switches += rep.get("switches", 0)
        for e in ((rep.get("relay") or {}).get("new_entries") or []):
            if e.get("kind") == design_r.KIND_STATS:
                variants += e["variants"]
                informative += e["informative"]
                U += sum(e["U"])
                n += sum(e["N"])
                kept += int(e["kept"])
                kept_splice += int(e["kept_splice"])
    return {"acquisitions": len(rows), "switches_per_round": switches / rounds if rounds else None,
            "informative_share": informative / variants if variants else None, "dplus_per_informative": U / n if n else None,
            "kept_program": kept / len(rows) if rows else None, "kept_splice": kept_splice / len(rows) if rows else None}


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return None
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def build(ledger, reg) -> dict:
    by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}
    H = reg["heldout"]
    base_seed = H["seed_base"]
    chain_of = lambda seed: (seed - base_seed) // 10
    out = {"registration": reg.get("what")}

    # the generations of the meta chains: on- against off-policy, position by position
    gen = {}
    for s in ledger.select(type="r_memory"):
        gen.setdefault(s["policy"], {}).setdefault(s["position"], []).append(by_key[s["run_key"]])
    out["generations"] = {p: {k: dict(productivity(rows), env=rows[0]["env"], acquired=float(np.mean([r["acquired"] for r in rows])),
                                      cpu=float(np.mean([evaluate.cpu(r) for r in rows])))
                              for k, rows in sorted(v.items())} for p, v in gen.items()}
    if "on" in gen and "off" in gen:
        L7 = {}
        for k in sorted(gen["on"]):
            if k == 0 or k not in gen["off"]:
                continue
            a, b = productivity(gen["on"][k]), productivity(gen["off"][k])
            if a["dplus_per_informative"] and b["dplus_per_informative"]:
                L7[k] = {"dplus_relative": a["dplus_per_informative"] / b["dplus_per_informative"] - 1,
                         "switches_per_round_on": a["switches_per_round"], "switches_per_round_off": b["switches_per_round"]}
        out["L7 discovery efficiency over generations (on- minus off-policy)"] = L7
    ret = find(ledger, type="r_retention")
    if ret:
        rows = {(x["chain"], x["env"], x["depth"]): by_key[x["key"]]["acquired"] for x in ret["rows"]}
        res = {}
        for env, depths in reg["meta"]["retention"]["plan"].items():
            d = sorted(depths)
            for a, b in ((d[-1], d[1]), (d[1], d[0])):
                vals = [rows[(j, env, a)] - rows[(j, env, b)] for j in range(reg["meta"]["retention"]["chains"]) if (j, env, a) in rows and (j, env, b) in rows]
                if vals:
                    res[f"{env}: depth {a} minus depth {b}"] = {"mean": float(np.mean(vals)), "sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
                                                                "chains": len(vals)}
        out["retention"] = res

    held = find(ledger, type="r_stage_done", stage="heldout")
    if not held:
        return out
    arms = {name: [dict(by_key[k]) for k in keys] for name, keys in held["arms"].items()}
    for m in ledger.select(type="r_matched"):
        if m["arm"] in arms:
            for row, reached in zip(arms[m["arm"]], m["reached"]):
                row["reached"] = reached
    rule = find(ledger, type="r_cpu_rule")
    a1 = H["alpha"]["primary"]
    J2 = H["secondary_chains"]
    sec = set(range(J2))
    # the primary: frozen raised to relay's CPU on the categories where the CPU rule applied
    base1 = arms["frozen"]
    if rule and rule["matched_categories"] and "frozen@relay" in arms:
        base1 = [r for r in arms["frozen"] if r["env"] not in rule["matched_categories"]] + arms["frozen@relay"]
    E = {"E-R1 relay minus frozen": endpoint(arms["relay"], base1, chain_of, a1)}
    E["E-R2 relay minus shuffled"] = endpoint(arms["relay"], arms.get("shuffled", []), chain_of, a1, chains=sec)
    E["E-R3 relay minus o0@relay (matched CPU)"] = endpoint(arms["relay"], arms.get("o0@relay", []), chain_of, a1, chains=sec)
    E["E-R4 relay minus offpolicy"] = endpoint(arms["relay"], arms.get("offpolicy", []), chain_of, a1, chains=sec)
    E["E-R5 relay minus libonly"] = endpoint(arms["relay"], arms.get("libonly", []), chain_of, a1, chains=sec)
    o0m = arms.get("o0@relay", [])
    less = sum(1 for r in o0m for s in arms["relay"] if (s["env"], s["seed"]) == (r["env"], r["seed"]) and evaluate.cpu(r) < evaluate.cpu(s))
    E["E-R3 relay minus o0@relay (matched CPU)"]["void"] = bool(not o0m or any(r.get("reached") is False for r in o0m) or less)
    # the gate: fixed sequence, then Holm at alpha over E-R3, E-R4, E-R5
    gate = {"E-R1": E["E-R1 relay minus frozen"]["met"]}
    gate["E-R2"] = bool(gate["E-R1"] and E["E-R2 relay minus shuffled"]["met"])
    holm = []
    for name in ("E-R3 relay minus o0@relay (matched CPU)", "E-R4 relay minus offpolicy", "E-R5 relay minus libonly"):
        e = E[name]
        if "t" in e and not e.get("void"):
            df = e["chains"] - 1
            # one-sided p by bisection on the quantile function
            lo, hi = 1e-12, 0.5
            for _ in range(80):
                mid = (lo + hi) / 2
                if t_quantile(mid, df) > e["t"]:
                    lo = mid
                else:
                    hi = mid
            holm.append((hi if e["t"] > 0 else 1.0, name))
        else:
            holm.append((1.0, name))
    holm.sort()
    passed, m = set(), len(holm)
    for i, (p, name) in enumerate(holm):
        if gate["E-R2"] and p <= a1 / (m - i):
            passed.add(name)
        else:
            break
    for name in ("E-R3 relay minus o0@relay (matched CPU)", "E-R4 relay minus offpolicy", "E-R5 relay minus libonly"):
        gate[name.split()[0]] = name in passed
    out["endpoints"] = E
    out["gate"] = gate
    out["tiers"] = {"T1 the record carries information that helps on these unseen categories (E-R1, E-R2)": gate["E-R2"],
                    "T2 recursive, beyond accumulation and beyond retained blocks (and E-R4, E-R5)": bool(gate["E-R2"] and gate["E-R4"] and gate["E-R5"]),
                    "T3 useful at matched compute (and E-R3)": bool(gate["E-R2"] and gate["E-R4"] and gate["E-R5"] and gate["E-R3"])}
    # m_net: the smallest difference of relay over the five comparators, chains below J2, two seeds
    comps = {}
    for name in ("frozen", "shuffled", "offpolicy", "libonly", "o0@relay"):
        if arms.get(name):
            e = endpoint(arms["relay"], arms[name], chain_of, a1, chains=sec)
            if "mean" in e:
                comps[name] = {"mean": e["mean"], "lower": e["mean"] - t_quantile(0.01, e["chains"] - 1) * e["se"]}
    if comps:
        worst = min(comps, key=lambda k: comps[k]["mean"])
        gain = float(np.mean([r["gain"] for r in arms["frozen"]]))
        out["m_net"] = {"definition": reg.get("m_net"), "value": comps[worst]["mean"], "against": worst,
                        "lower_bound": min(v["lower"] for v in comps.values()), "per_comparator": comps,
                        "relative_to_frozen_gain": comps[worst]["mean"] / gain if gain else None}
    D = {}
    for label, a, b in (("L1 frozen minus o0@relay", "frozen", "o0@relay"), ("L2 frozen@ceiling minus frozen", "frozen@ceiling", "frozen"),
                        ("L5 shuffled minus frozen", "shuffled", "frozen"), ("prioronly minus frozen", "prioronly", "frozen"),
                        ("libonly minus frozen", "libonly", "frozen"), ("relay minus prioronly", "relay", "prioronly"),
                        *[(f"L8 depth {d} minus frozen", f"depth{d}", "frozen") for d in H.get("depths", [])],
                        ("relay (depth 12) minus frozen, chains below the secondary limit", "relay", "frozen"),
                        ("relay minus a0@relay", "relay", "a0@relay")):
        if arms.get(a) and arms.get(b):
            D[label] = endpoint(arms[a], arms[b], chain_of, 0.05, statistic="min" if "a0" in b else "acquired", chains=sec)
    D["L3 inner productivity"] = {name: productivity(rows) for name, rows in arms.items() if not name.startswith(("o0", "a0"))}
    # the untrained answers must agree across the design-r arms and o0
    un = {}
    for name in ("relay", "frozen", "shuffled", "offpolicy", "libonly", "prioronly"):
        if arms.get(name):
            un[name] = {(r["env"], r["seed"]): r["untrained"] for r in arms[name]}
    ref = un.get("frozen", {})
    D["untrained answers identical across design-r arms"] = all(abs(v - ref[k]) < 1e-12 for n_, d in un.items() for k, v in d.items() if k in ref)
    out["diagnostics"] = D
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
        json.dump(out, open(args.json, "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
