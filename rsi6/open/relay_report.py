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
import zlib

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.learner import design_r
from rsi6.open import evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def _betainc(a: float, b: float, x: float, y: float) -> float:
    """The regularised incomplete beta I_x(a, b), with y = 1 - x given exactly (no cancellation)."""
    if x <= 0.0:
        return 0.0
    if y <= 0.0:
        return 1.0
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _betainc(b, a, y, x)
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(y) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(400):
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
        if abs(c * d - 1.0) < 1e-14:
            break
    return front * (f - 1.0)


def t_sf(t: float, df: int) -> float:
    """The upper tail P(T >= t) of Student's t with df degrees of freedom."""
    if math.isnan(t):
        return 1.0
    if math.isinf(t):
        return 0.0 if t > 0 else 1.0
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t), t * t / (df + t * t))
    return tail if t >= 0 else 1.0 - tail


def t_quantile(p: float, df: int) -> float:
    """One-sided Student t quantile (upper tail p, 0 < p <= 0.5) by bisection on t_sf."""
    lo, hi = 0.0, 60.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_sf(mid, df) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def stats_of(record):
    """The r_stats entry an acquisition added (its report keeps it), or None."""
    for e in ((record.get("report") or {}).get("relay") or {}).get("new_entries") or []:
        if e.get("kind") == design_r.KIND_STATS:
            return e
    return None


def _seed(label: str) -> int:
    """Every resampling is seeded by the CRC-32 of its comparison's label."""
    return zlib.crc32(label.encode())


def paired(arm, base, chain_of, statistic="acquired", chains=None, seed_ok=None) -> dict:
    """arm minus base, paired by category and seed: per chain, the mean over categories of the mean
    over seeds; the CPU of the pairs that enter. ``statistic`` "acquired": the change of the acquired
    score; "both": that and the change of the gain, the series with the smaller mean deciding
    (comparisons with design a, whose untrained answers differ)."""
    b = {(r["env"], r["seed"]): r for r in base}
    by, cpu_a, cpu_b = {}, 0.0, 0.0
    for r in arm:
        o = b.get((r["env"], r["seed"]))
        j = chain_of(r["seed"])
        if o is None or (chains is not None and j not in chains) or (seed_ok is not None and not seed_ok(r["seed"])):
            continue
        by.setdefault(j, {}).setdefault(r["env"], []).append((r["acquired"] - o["acquired"], r["gain"] - o["gain"]))
        cpu_a += evaluate.cpu(r)
        cpu_b += evaluate.cpu(o)
    series = [{j: float(np.mean([np.mean([x[i] for x in v]) for v in ev.values()])) for j, ev in sorted(by.items())} for i in (0, 1)]
    means = [float(np.mean(list(m.values()))) if m else None for m in series]
    i = 1 if statistic == "both" and by and means[1] < means[0] else 0
    per_env = {}
    for ev in by.values():
        for e, v in ev.items():
            per_env.setdefault(e, []).extend(x[i] for x in v)
    return {"chains": series[i], "per_env": {e: float(np.mean(v)) for e, v in sorted(per_env.items())},
            "n_pairs": int(sum(len(v) for ev in by.values() for v in ev.values())),
            "cpu_ratio": cpu_a / cpu_b if cpu_b > 0 else None,
            "change": {"acquired": means[0], "gain": means[1], "used": ("acquired", "gain")[i]}}


FLIPS = 10000


def endpoint(label, arm, base, chain_of, alpha, test="t", statistic="acquired", chains=None, seed_ok=None, need=None) -> dict:
    """One-sided test over chain means of arm minus base: Student's t, or (``test`` "signflip", the
    alternative development check D6 prescribes) a sign-flip permutation test with 10,000 seeded
    flips. ``need``: the number of chains the registration requires; an endpoint measured on fewer
    is reported and its test does not count. ``single_test`` is this test alone; whether the
    registered endpoint is met is decided by the gate."""
    pr = paired(arm, base, chain_of, statistic, chains, seed_ok)
    x = np.array([pr["chains"][j] for j in sorted(pr["chains"])])
    if len(x) < 2:
        return {"n_pairs": pr["n_pairs"], "chains": int(len(x)), "single_test": False, "complete": False, "why": "not measured", "p": 1.0}
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    se = sd / math.sqrt(len(x))
    t = mean / se if se > 0 else (math.inf if mean > 0 else 0.0)
    crit = t_quantile(alpha, len(x) - 1)
    rng = np.random.default_rng(_seed(label))
    if test == "signflip":
        flips = rng.choice([-1.0, 1.0], size=(FLIPS, len(x)))
        pv = float((1 + np.sum((flips * x).mean(axis=1) >= mean - 1e-15)) / (1 + FLIPS))
        passed = pv <= alpha
    else:
        pv = t_sf(t, len(x) - 1)
        passed = t >= crit
    boot = [float(x[rng.integers(0, len(x), len(x))].mean()) for _ in range(5000)]
    complete = need is None or len(x) >= need
    out = {"mean": mean, "se": se, "t": t, "critical_t": crit, "alpha": alpha, "test": test, "p": pv,
           "single_test": bool(passed and complete), "complete": complete,
           "upper_95": float(mean + t_quantile(0.05, len(x) - 1) * se), "interval_95_chains": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
           "per_category": pr["per_env"], "categories_positive": int(sum(v > 0 for v in pr["per_env"].values())),
           "negative_transfer_categories": sorted(e for e, v in pr["per_env"].items() if v < -0.005), "chains": int(len(x)),
           "n_pairs": pr["n_pairs"], "cpu_ratio": pr["cpu_ratio"]}
    if statistic == "both":
        out["change"] = pr["change"]
    if not complete:
        out["why"] = f"measured on {len(x)} of the {need} registered chains"
    return out


def bootstraps(label, arm, base, chain_of, n=5000):
    """95% intervals of the mean difference, resampling chains and seeds, and categories and seeds."""
    b = {(r["env"], r["seed"]): r["acquired"] for r in base}
    cell = {}
    for r in arm:
        if (r["env"], r["seed"]) in b:
            cell.setdefault((chain_of(r["seed"]), r["env"]), []).append(r["acquired"] - b[(r["env"], r["seed"])])
    if not cell:
        return None
    chains, cats = sorted({j for j, _ in cell}), sorted({c for _, c in cell})
    S = max(len(v) for v in cell.values())
    D = np.full((len(chains), len(cats), S), np.nan)
    for (j, c), v in cell.items():
        D[chains.index(j), cats.index(c), :len(v)] = v
    rng = np.random.default_rng(_seed(label + ": bootstraps"))
    counts = np.sum(~np.isnan(D), axis=2)                    # seeds measured per (chain, category)
    out = {}
    jj = rng.integers(0, len(chains), (n, len(chains)))
    pick = np.minimum((rng.random((n, len(chains), len(cats), S)) * counts[jj][..., None]).astype(int), S - 1)
    vals = np.take_along_axis(D[jj], pick, axis=3)
    out["chains and seeds"] = [float(x) for x in np.nanpercentile(np.nanmean(np.nanmean(np.nanmean(vals, axis=3), axis=2), axis=1), [2.5, 97.5])]
    cc = rng.integers(0, len(cats), (n, len(cats)))
    Dc = D[:, cc].transpose(1, 0, 2, 3)                      # (n, chains, categories drawn, seeds)
    cnt = np.sum(~np.isnan(Dc), axis=3)
    pick = np.minimum((rng.random(Dc.shape) * cnt[..., None]).astype(int), S - 1)
    vals = np.take_along_axis(Dc, pick, axis=3)
    out["categories and seeds"] = [float(x) for x in np.nanpercentile(np.nanmean(np.nanmean(np.nanmean(vals, axis=3), axis=2), axis=1), [2.5, 97.5])]
    return out


def productivity(rows):
    """Inner discovery per acquisition, from the run reports."""
    rounds = switches = variants = informative = 0
    U = n = 0.0
    kept = kept_splice = 0
    for r in rows:
        rep = r.get("report") or {}
        rounds += rep.get("program_rounds", 0)
        switches += rep.get("switches", 0)
        e = stats_of(r)
        if e is not None:
            variants += e["variants"]
            informative += e["informative"]
            U += sum(e["U"])
            n += sum(e["N"])
            kept += int(e["kept"])
            kept_splice += int(e["kept_splice"])
    return {"acquisitions": len(rows), "switches_per_round": switches / rounds if rounds else None,
            "informative_share": informative / variants if variants else None, "dplus_per_informative": U / n if n else None,
            "kept_switched_program": kept / len(rows) if rows else None, "kept_spliced_block": kept_splice / len(rows) if rows else None}


def _ranks(a):
    a = np.asarray(a, float)
    order = np.argsort(a, kind="mergesort")
    r = np.empty(len(a))
    i = 0
    while i < len(a):
        k = i
        while k + 1 < len(a) and a[order[k + 1]] == a[order[i]]:
            k += 1
        r[order[i:k + 1]] = (i + k) / 2.0
        i = k + 1
    return r


def spearman(a, b):
    """Spearman's correlation with average ranks for ties; None when either side is constant."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return None
    ra, rb = _ranks(a), _ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def relative_margin(m_entries, kappa):
    """Per cell, the shrunk mean positive margin over its mean (m_c / ubar) of pooled stats entries."""
    N = np.sum([np.asarray(e["N"], float) for e in m_entries], axis=0)
    U = np.sum([np.asarray(e["U"], float) for e in m_entries], axis=0)
    if N.sum() <= 0 or U.sum() <= 0:
        return None
    ubar = U.sum() / N.sum()
    return (U / ubar + kappa) / (N + kappa)


def l4(groups: dict, kappa: float) -> dict:
    """L4: the mean Spearman correlation, over pairs of categories, of the per-cell m_c/ubar of the
    stats entries pooled per category (``groups``: category -> entries); descriptive: the same over
    the cells in the lower and in the upper half of the pooled m_c/ubar."""
    vec = {c: v for c, v in ((c, relative_margin(e, kappa)) for c, e in groups.items() if e) if v is not None}
    cats = sorted(vec)
    pairs = {}
    for a in range(len(cats)):
        for b in range(a + 1, len(cats)):
            r = spearman(vec[cats[a]], vec[cats[b]])
            if r is not None:
                pairs[f"{cats[a]}/{cats[b]}"] = r
    out = {"categories": cats, "pairs": pairs, "mean_pairwise_spearman": float(np.mean(list(pairs.values()))) if pairs else None}
    if len(cats) >= 2:
        pooled = relative_margin([e for c in cats for e in groups[c]], kappa)
        low = pooled <= np.median(pooled)
        for label, sel in (("lower half (destructive cells)", low), ("upper half", ~low)):
            rs = [spearman(vec[cats[a]][sel], vec[cats[b]][sel]) for a in range(len(cats)) for b in range(a + 1, len(cats))]
            rs = [r for r in rs if r is not None]
            out[f"mean_pairwise_spearman, {label}"] = float(np.mean(rs)) if rs else None
    return out


def l6(final, frozen_rows, J2, relay_cfg, cats) -> dict:
    """L6: Spearman between the relayed prior w(M_j), fixed before any held-out run, and the frozen
    runs' realized U_c/N_c (pooled per category, cells with N_c >= 5), per category; the shuffled
    placebo w(shuffled(M_j)) for chains below J2; and the same among the 10 cells of highest w(M_j)."""
    out = {}
    for c in cats:
        entries = [e for e in (stats_of(r) for r in frozen_rows if r["env"] == c) if e is not None]
        if not entries:
            continue
        N = np.sum([np.asarray(e["N"], float) for e in entries], axis=0)
        U = np.sum([np.asarray(e["U"], float) for e in entries], axis=0)
        valid = np.flatnonzero(N >= 5)
        realized = np.where(N > 0, U / np.maximum(N, 1e-12), 0.0)
        rho, placebo, top = [], [], []
        for j in sorted(final):
            pr = design_r.prior_from((final[j] or {"entries": []})["entries"], relay_cfg)
            if pr is None or len(valid) < 3:
                continue
            w = np.asarray(pr["w"], float)
            r = spearman(w[valid], realized[valid])
            if r is not None:
                rho.append(r)
            best = valid[np.argsort(-w[valid], kind="mergesort")[:10]]
            r = spearman(w[best], realized[best])
            if r is not None:
                top.append(r)
            if j < J2:
                ps = design_r.prior_from((design_r.shuffled(final[j], j) or {"entries": []})["entries"], relay_cfg)
                r = spearman(np.asarray(ps["w"], float)[valid], realized[valid]) if ps else None
                if r is not None:
                    placebo.append(r)
        out[c] = {"cells": int(len(valid)), "relay": float(np.mean(rho)) if rho else None, "shuffled": float(np.mean(placebo)) if placebo else None,
                  "top10": float(np.mean(top)) if top else None, "chains": len(rho)}
    vals = [v["relay"] for v in out.values() if v["relay"] is not None]
    return {"by_category": out, "mean": float(np.mean(vals)) if vals else None, "categories_positive": int(sum(v > 0 for v in vals)),
            "shuffled_mean": float(np.mean([v["shuffled"] for v in out.values() if v["shuffled"] is not None])) if any(v["shuffled"] is not None for v in out.values()) else None,
            "top10_mean": float(np.mean([v["top10"] for v in out.values() if v["top10"] is not None])) if any(v["top10"] is not None for v in out.values()) else None}


def l7(gen_on, gen_off, order) -> dict:
    """L7: on- minus off-policy, chains that have both, positions 1 to K-1 and the category-switch
    positions: d+ per informative variant (relative, with a 95% chain bootstrap), switches per
    program round and CPU per switch."""
    switch = [k for k in range(1, len(order)) if order[k] != order[k - 1]]
    out = {"switch_positions": switch}
    chains = sorted({j for (j, k) in gen_off if (j, k) in gen_on})
    for label, positions in (("positions 1 to %d" % (len(order) - 1), list(range(1, len(order)))), ("category-switch positions", switch)):
        A, B = [], []
        sw_on = sw_off = rd_on = rd_off = cpu_on = cpu_off = 0.0
        for j in chains:
            a, b = [], []
            for k in positions:
                on, off = gen_on.get((j, k)), gen_off.get((j, k))
                if on is None or off is None:
                    continue
                pa, pb = productivity([on]), productivity([off])
                if pa["dplus_per_informative"] is not None and pb["dplus_per_informative"] is not None:
                    a.append(pa["dplus_per_informative"])
                    b.append(pb["dplus_per_informative"])
                ro, rf = on.get("report") or {}, off.get("report") or {}
                sw_on += ro.get("switches", 0); sw_off += rf.get("switches", 0)
                rd_on += ro.get("program_rounds", 0); rd_off += rf.get("program_rounds", 0)
                cpu_on += evaluate.cpu(on); cpu_off += evaluate.cpu(off)
            if a:
                A.append(np.mean(a)); B.append(np.mean(b))
        if not A:
            out[label] = None
            continue
        A, B = np.array(A), np.array(B)
        rng = np.random.default_rng(_seed("L7 " + label))
        idx = rng.integers(0, len(A), (5000, len(A)))
        boot = A[idx].mean(axis=1) / B[idx].mean(axis=1) - 1
        out[label] = {"dplus_relative": float(A.mean() / B.mean() - 1), "interval_95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                      "lower_95": float(np.percentile(boot, 2.5)), "upper_95": float(np.percentile(boot, 97.5)),
                      "chains": int(len(A)), "switches_per_round": {"on": sw_on / rd_on if rd_on else None, "off": sw_off / rd_off if rd_off else None},
                      "cpu_per_switch": {"on": cpu_on / sw_on if sw_on else None, "off": cpu_off / sw_off if sw_off else None}}
    return out


def l8(arms, depths, final_depth, chain_of, J2, base_seed) -> dict:
    """L8: the memories of depth d (chains below J2, seed s = 0) each minus frozen, and the slope
    over the registered depths (not given unless every one of them was measured)."""
    first = lambda rows: [r for r in rows if chain_of(r["seed"]) < J2 and (r["seed"] - base_seed) % 10 == 0]
    curve = {d: f"depth{d}" for d in depths}
    curve[final_depth] = "relay"
    per = {}
    for d, name in curve.items():
        if arms.get(name) and arms.get("frozen"):
            per[d] = paired(first(arms[name]), first(arms["frozen"]), chain_of)["chains"]
    ds = sorted(per)
    out = {"depths": ds, "mean_minus_frozen": {d: float(np.mean(list(per[d].values()))) for d in ds if per[d]}, "slope": None}
    if ds != sorted(curve) or any(not per[d] for d in ds):
        return out
    chains = sorted(set.intersection(*[set(per[d]) for d in ds]))
    slopes = np.array([float(np.polyfit(np.array(ds, float), np.array([per[d][j] for d in ds]), 1)[0]) for j in chains])
    if len(slopes):
        out.update({"mean_minus_frozen": {d: float(np.mean([per[d][j] for j in chains])) for d in ds}, "slope": float(slopes.mean()),
                    "slope_se": float(slopes.std(ddof=1) / math.sqrt(len(slopes))) if len(slopes) > 1 else None, "chains": len(chains)})
    return out


def two_by_two(arms, chain_of, J2) -> dict | None:
    """Prior x library: relay (both), prioronly, libonly, frozen (neither), chains below J2."""
    names = ("relay", "prioronly", "libonly", "frozen")
    if not all(arms.get(n) for n in names):
        return None
    sec = set(range(J2))
    key = lambda rows: {(r["env"], r["seed"]): r["acquired"] for r in rows if chain_of(r["seed"]) in sec}
    A = {n: key(arms[n]) for n in names}
    common = set.intersection(*[set(v) for v in A.values()])
    by = {}
    for pair in sorted(common):                                # a fixed order: the sums do not depend on the hash seed
        P, p, l, f = (A[n][pair] for n in names)
        by.setdefault(chain_of(pair[1]), {}).setdefault(pair[0], []).append(((P - l + p - f) / 2, (P - p + l - f) / 2, (P - p) - (l - f)))
    cm = np.array([[np.mean([np.mean([x[i] for x in v]) for v in ev.values()]) for i in range(3)] for j, ev in sorted(by.items())])
    if len(cm) < 2:
        return None
    se = cm.std(axis=0, ddof=1) / math.sqrt(len(cm))
    return {label: {"mean": float(cm[:, i].mean()), "se": float(se[i])} for i, label in
            enumerate(("prior main effect", "library main effect", "interaction (relay - prioronly) - (libonly - frozen)"))} | {"chains": int(len(cm))}


def per_arm(arms) -> dict:
    out = {}
    for name, rows in arms.items():
        if not rows:
            continue
        cats = sorted({r["env"] for r in rows})
        out[name] = {"runs": len(rows), "cpu_total": float(sum(evaluate.cpu(r) for r in rows)),
                     "cpu_per_run": float(np.mean([evaluate.cpu(r) for r in rows])),
                     "train_units_used": float(np.mean([r["units"]["train_used"] for r in rows])),
                     "constructions": float(np.mean([(r.get("report") or {}).get("constructions", 0) for r in rows])),
                     "at_or_above_threshold": {c: float(np.mean([r["acquired"] >= r["threshold"] for r in rows if r["env"] == c])) for c in cats},
                     "acquired": {c: float(np.mean([r["acquired"] for r in rows if r["env"] == c])) for c in cats}}
    return out


def compared(arms, rules, name):
    """An r0 arm as it is compared with relay: raised to relay's CPU on the categories where the
    registered CPU rule applied to it."""
    over = sorted({c for rule in rules if rule["arm"] == name for c in rule["matched_categories"]})
    rows = [r for r in arms.get(name, []) if r["env"] not in over] + [r for r in arms.get(f"{name}@relay", []) if r["env"] in over]
    return rows, over


def build(ledger, reg) -> dict:
    from rsi6.open import relay as relay_driver           # rebuild: the memories from the ledger alone, digests checked
    by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}
    H, M = reg["heldout"], reg["meta"]
    base_seed = H["seed_base"]
    chain_of = lambda seed: (seed - base_seed) // 10
    relay_cfg = design_r.validate(reg["version"])["relay"]
    order = M["order"]
    K = len(order)
    out = {"registration": reg.get("what")}

    # ---- meta: generations, P1, P2, L4, L7, library ---------------------------------------------
    gen = {}
    for s in ledger.select(type="r_memory"):
        gen.setdefault(s["policy"], {})[(s["chain"], s["position"])] = by_key[s["run_key"]]
    on, off = gen.get("on", {}), gen.get("off", {})
    out["generations"] = {}
    for policy, recs in (("on", on), ("off", off)):
        byk = {}
        for (j, k), r in recs.items():
            byk.setdefault(k, []).append(r)
        out["generations"][policy] = {k: dict(productivity(rows), env=rows[0]["env"], acquired=float(np.mean([r["acquired"] for r in rows])),
                                              cpu=float(np.mean([evaluate.cpu(r) for r in rows]))) for k, rows in sorted(byk.items())}
    if on:
        reps = [r.get("report") or {} for r in on.values()]
        st = [stats_of(r) for r in on.values()]
        out["meta per acquisition (on-policy)"] = {
            "median_program_rounds": float(np.median([x.get("program_rounds", 0) for x in reps])),
            "median_informative_share": float(np.median([e["informative"] / e["variants"] for e in st if e and e["variants"]])),
            "median_switches_per_round": float(np.median([x.get("switches", 0) / x["program_rounds"] for x in reps if x.get("program_rounds")]))}
        groups = {}
        for (j, k), r in on.items():
            e = stats_of(r)
            if e is not None:
                groups.setdefault(r["env"], []).append(e)
        out["L4 cross-category correlation of the learned per-cell statistics"] = l4(groups, relay_cfg["kappa"])
    if on and off:
        out["L7 discovery efficiency over generations (on- minus off-policy)"] = l7(on, off, order)
    mem = relay_driver.rebuild(ledger, reg) if on else {"on": {}, "off": {}}
    final = {j: d.get(K) for j, d in mem["on"].items() if K in d}
    if final:
        libs, low2 = [], []
        named = {("score", "replace"), ("score", "mutop"), ("score", "swap"), ("pick", "swap")}
        for j, m in sorted(final.items()):
            pr = design_r.prior_from((m or {"entries": []})["entries"], relay_cfg)
            libs.append(len(pr["library"]) if pr else 0)
            if pr:
                lowest = np.argsort(np.asarray(pr["w"], float), kind="mergesort")[:4]
                low2.append(sum(design_r.CELLS[int(c)] in named for c in lowest) >= 2)
        out["final memories"] = {"chains": len(final), "library_size_median": float(np.median(libs)),
                                 "share_with_two_named_destructive_cells_among_four_lowest": float(np.mean(low2)) if low2 else None}
    ret = find(ledger, type="r_retention")
    if ret:
        rows = {(x["chain"], x["env"], x["depth"]): by_key[x["key"]]["acquired"] for x in ret["rows"]}
        res = {}
        for env, depths in M["retention"]["plan"].items():
            d = sorted(depths)
            for label, a, b in ((f"R_{env}: depth {d[-1]} minus depth {d[1]}", d[-1], d[1]),
                                (f"within_{env}: depth {d[1]} minus no memory", d[1], d[0])):
                vals = [rows[(j, env, a)] - rows[(j, env, b)] for j in range(M["retention"]["chains"]) if (j, env, a) in rows and (j, env, b) in rows]
                if vals:
                    res[label] = {"mean": float(np.mean(vals)), "se": float(np.std(vals, ddof=1) / math.sqrt(len(vals))) if len(vals) > 1 else None,
                                  "chains": len(vals)}
        out["retention"] = res

    # ---- held-out --------------------------------------------------------------------------------
    held = find(ledger, type="r_stage_done", stage="heldout")
    if not held:
        out["predictions"] = score_predictions(reg, out)
        return out
    arms = {name: [dict(by_key[k]) for k in keys] for name, keys in held["arms"].items()}
    for m in ledger.select(type="r_matched"):
        if m["arm"] in arms:
            reached = dict(zip(m["keys"], zip(m["reached"], m["levels"])))
            for row in arms[m["arm"]]:
                if row["key"] in reached:
                    row["reached"], row["levels"] = reached[row["key"]]
    rules = ledger.select(type="r_cpu_rule")
    out["cpu rule"] = [{k: r[k] for k in ("arm", "part", "ratios", "matched_categories")} for r in rules]
    fut = find(ledger, type="r_futility")
    out["futility look"] = {k: fut[k] for k in ("chains", "mean", "t", "stop")} if fut else None
    out["items"] = [{k: r.get(k) for k in ("item", "name", "done", "why")} for r in ledger.select(type="r_item")]
    out["cap"] = [{k: r.get(k) for k in ("item", "name", "spent", "projection", "h_cap")} for r in ledger.select(type="r_cap")]
    out["dropped by the re-projection"] = [{k: r.get(k) for k in ("before_item", "dropped", "spent", "projection", "h_cap")}
                                           for r in ledger.select(type="r_drop")]
    a1 = H["alpha"]["primary"]
    test = H.get("test", "t")
    J, J2 = M["chains"], H["secondary_chains"]
    sec = set(range(J2))
    two = lambda seed: (seed - base_seed) % 10 < 2             # the secondaries, m_net and the diagnostics use seeds 0 and 1
    dropped = set(H.get("dropped_arms", []))

    def versus(label, name, alpha, chains=None, seed_ok=None, need=None):
        """relay minus the comparator ``name``, by the registered rule: against the comparator as the
        CPU rule leaves it (raised to relay's CPU where the rule applied; o0 raised everywhere) and,
        where that differs, also against the comparator at the registered budget. Both tests must
        hold: a comparator is not weakened by being given more CPU."""
        if name in ("o0", "a0"):
            designated, other = arms.get(f"{name}@relay", []), arms.get(name, [])
            over = sorted({r["env"] for r in designated})
        else:
            designated, over = compared(arms, rules, name)
            other = arms.get(name, []) if over else []
        stat = "both" if name == "a0" else "acquired"
        e = endpoint(label, arms["relay"], designated, chain_of, alpha, test, stat, chains, seed_ok, need)
        e["p_both"] = e["p"]
        if over:
            e["comparator raised to relay's CPU on"] = over
            e2 = endpoint(label + ", comparator at the registered budget", arms["relay"], other, chain_of, alpha, test, stat, chains, seed_ok, need)
            e["against the comparator at the registered budget"] = e2
            e["single_test"] = bool(e["single_test"] and e2["single_test"])
            e["p_both"] = max(e["p"], e2["p"])
        return e

    E1 = "E-R1 relay minus frozen"
    names = {"E-R2 relay minus shuffled": "shuffled", "E-R3 relay minus o0@relay (matched CPU)": "o0",
             "E-R4 relay minus offpolicy": "offpolicy", "E-R5 relay minus libonly": "libonly"}
    E = {E1: versus(E1, "frozen", a1, need=J)}
    E[E1]["bootstraps"] = bootstraps(E1, arms["relay"], compared(arms, rules, "frozen")[0], chain_of)
    if "upper_95" in E[E1]:
        E[E1]["decisive_negative"] = bool(E[E1]["upper_95"] < 0.007)
    for label, name in names.items():
        E[label] = versus(label, name, a1, chains=sec, seed_ok=two, need=J2)
    E3 = "E-R3 relay minus o0@relay (matched CPU)"
    o0m = arms.get("o0@relay", [])
    cpu_relay = {(r["env"], r["seed"]): evaluate.cpu(r) for r in arms["relay"]}
    less = sum(1 for r in o0m if evaluate.cpu(r) < cpu_relay.get((r["env"], r["seed"]), 0.0))
    E[E3]["void"] = bool(not o0m or any(r.get("reached") is False for r in o0m) or less)
    # the untrained answers must agree across every arm of design r and of design o (same programs and
    # constants before acquisition, same apply stream); the registered statistic rests on it
    un = {}
    for name, rows in arms.items():
        if not name.startswith("a0"):
            for r in rows:
                un.setdefault((r["env"], r["seed"]), set()).add(round(r["untrained"], 9))
    identical = all(len(v) == 1 for v in un.values())
    if not identical:
        for e in E.values():
            e["single_test"] = False
            e["why"] = "the untrained answers differ between arms: the registered statistic does not apply"
    # the gate: E-R1; then E-R2; then Holm over the remaining family
    gate = {"E-R1": bool(E[E1]["single_test"])}
    gate["E-R2"] = bool(gate["E-R1"] and E["E-R2 relay minus shuffled"]["single_test"])
    family = [label for label in (E3, "E-R4 relay minus offpolicy", "E-R5 relay minus libonly") if names[label] not in dropped]
    holm = []
    for label in family:                                       # development rule (b) removes E-R5 with the library arms
        e = E[label]
        ok = "t" in e and not e.get("void") and e.get("complete", False) and identical
        if ok and "against the comparator at the registered budget" in e:
            ok = e["against the comparator at the registered budget"].get("complete", False)
        holm.append((e["p_both"] if ok else 1.0, label))
    holm.sort()
    passed = set()
    for i, (pv, label) in enumerate(holm):
        if gate["E-R2"] and pv <= a1 / (len(holm) - i):
            passed.add(label)
        else:
            break
    for label in family:
        gate[label.split()[0]] = label in passed
    if "libonly" in dropped:
        E.pop("E-R5 relay minus libonly", None)
        gate["E-R5"] = None                                      # not an endpoint of this registration
    for label, e in E.items():
        e["met"] = gate[label.split()[0]]                        # the registered decision; single_test is the test alone
    out["endpoints"] = E
    out["gate"] = gate
    e5 = True if gate["E-R5"] is None else gate["E-R5"]
    out["tiers"] = {"T1": gate["E-R2"], "T2": bool(gate["E-R2"] and gate["E-R4"] and e5),
                    "T3": bool(gate["E-R2"] and gate["E-R4"] and e5 and gate["E-R3"]),
                    "meaning": {"T1": "the record carries information that helps on these unseen categories (E-R1, E-R2)",
                                "T2": "recursive, beyond accumulation and beyond retained blocks (and E-R4, E-R5)",
                                "T3": "useful at matched compute (and E-R3); 'recursive improvement observed' only here"}}
    # m_net: the smallest difference of relay over the registered comparators, chains below J2, seeds 0 and 1; each
    # comparator both as the CPU rule leaves it and at the registered budget
    comps = {}
    m_arms = [n for n in ("frozen", "shuffled", "offpolicy", "libonly", "o0") if n not in dropped]
    for name in m_arms:
        e = versus("m_net " + name, name, a1, chains=sec, seed_ok=two, need=J2)
        both = [x for x in (e, e.get("against the comparator at the registered budget")) if x and "mean" in x and x.get("complete")]
        if both and len(both) == (2 if "against the comparator at the registered budget" in e else 1):
            comps[name] = {"mean": min(x["mean"] for x in both), "lower": min(x["mean"] - t_quantile(0.01, x["chains"] - 1) * x["se"] for x in both),
                           "chains": e["chains"]}
    complete = len(comps) == len(m_arms)
    gain = float(np.mean([r["gain"] for r in arms["frozen"]]))
    worst = min(comps, key=lambda k: comps[k]["mean"]) if comps else None
    out["m_net"] = {"definition": reg.get("m_net"), "complete": complete, "per_comparator": comps,
                    "value": comps[worst]["mean"] if complete else None, "against": worst if complete else None,
                    "lower_bound": min(v["lower"] for v in comps.values()) if complete else None,
                    "relative_to_frozen_gain": comps[worst]["mean"] / gain if complete and gain else None}
    D = {}
    frozen_c = compared(arms, rules, "frozen")[0]
    pairs = (("L1 frozen minus o0@relay", frozen_c, arms.get("o0@relay"), "acquired"),
             ("L1 at the registered budget: frozen minus o0", arms.get("frozen"), arms.get("o0"), "acquired"),
             ("L2 frozen@ceiling minus frozen", arms.get("frozen@ceiling"), arms.get("frozen"), "acquired"),
             ("L5 shuffled minus frozen", arms.get("shuffled"), arms.get("frozen"), "acquired"),
             ("prioronly minus frozen", arms.get("prioronly"), arms.get("frozen"), "acquired"),
             ("libonly minus frozen", arms.get("libonly"), arms.get("frozen"), "acquired"),
             ("relay minus prioronly", arms.get("relay"), compared(arms, rules, "prioronly")[0], "acquired"),
             ("relay minus a0@relay", arms.get("relay"), arms.get("a0@relay"), "both"),
             ("relay minus a0 at the registered budget", arms.get("relay"), arms.get("a0"), "both"),
             ("o0@ref minus a0@ref", arms.get("o0@ref"), arms.get("a0@ref"), "both"))
    for label, a, b, stat in pairs:
        if a and b:
            D[label] = endpoint(label, a, b, chain_of, 0.05, "t", stat, chains=sec, seed_ok=two)
    D["L3 inner productivity"] = {name: {"all": productivity(rows), "by_category": {c: productivity([r for r in rows if r["env"] == c])
                                                                                     for c in sorted({r["env"] for r in rows})}}
                                  for name, rows in arms.items() if not name.startswith(("o0", "a0"))}
    D["L6 prospective transfer of discovery knowledge"] = l6(final, arms["frozen"], J2, relay_cfg, held["categories"]) if final else None
    D["L8 depth curve"] = l8(arms, H.get("depths", []), K, chain_of, J2, base_seed)
    D["2x2 prior x library"] = two_by_two(arms, chain_of, J2)
    D["per arm: CPU, units, constructions, share at or above the threshold, acquired"] = per_arm(arms)
    D["untrained answers identical across the arms of designs r and o"] = identical
    ratios = {}
    for c in held["categories"]:
        pr = paired([r for r in arms["relay"] if r["env"] == c], [r for r in arms["frozen"] if r["env"] == c], chain_of)
        ratios[c] = pr["cpu_ratio"]
    D["relay over frozen CPU per category (primary pairs)"] = ratios
    vals = [v for v in ratios.values() if v is not None]
    D["relay over frozen CPU, smallest"] = min(vals) if vals else None
    D["relay over frozen CPU, largest"] = max(vals) if vals else None
    l3 = D["L3 inner productivity"]
    if "relay" in l3 and "frozen" in l3:
        rc, fc = l3["relay"]["by_category"], l3["frozen"]["by_category"]
        both = [c for c in rc if c in fc]
        sw = [c for c in both if rc[c]["switches_per_round"] is not None and fc[c]["switches_per_round"]
              and rc[c]["switches_per_round"] >= 1.15 * fc[c]["switches_per_round"]]
        inf = [abs(rc[c]["informative_share"] - fc[c]["informative_share"]) for c in both
               if rc[c]["informative_share"] is not None and fc[c]["informative_share"] is not None]
        D["categories where relay's switches per round are at least 1.15 times frozen's"] = len(sw)
        D["largest informative-share difference, relay minus frozen"] = max(inf) if inf else None
    pa = D["per arm: CPU, units, constructions, share at or above the threshold, acquired"]
    if "relay" in pa and "frozen" in pa:
        th = [abs(pa["relay"]["at_or_above_threshold"][c] - pa["frozen"]["at_or_above_threshold"][c])
              for c in pa["relay"]["at_or_above_threshold"] if c in pa["frozen"]["at_or_above_threshold"]]
        D["largest threshold-share difference, relay minus frozen"] = max(th) if th else None
    D["o0@relay reached within 2 levels"] = float(np.mean([bool(r.get("reached")) and r.get("levels", 99) <= 2 for r in o0m])) if o0m else None
    D["o0@relay over relay CPU (matched pairs)"] = (1.0 / E[E3]["cpu_ratio"]) if E[E3].get("cpu_ratio") else None
    D["void comparisons"] = int(E[E3]["void"])
    out["diagnostics"] = D
    out["predictions"] = score_predictions(reg, out)
    return out


def quantity(out, path):
    """A scored quantity, by a registered path into the report (None when it was not measured)."""
    x = out
    for part in path.split(" / "):
        if not isinstance(x, dict) or part not in x or x[part] is None:
            return None
        x = x[part]
    if isinstance(x, bool):
        return float(x)
    return x


def score_predictions(reg, out) -> list:
    """Every registered prediction, scored by its registered checks: met when every checked
    quantity lies within its bounds, not scored when one was not measured; events are reported
    with the probability that was registered for them."""
    rows = []
    for p in reg.get("predictions") or []:
        if not isinstance(p, dict):
            rows.append({"text": p, "scored": False})
            continue
        row = {"id": p["id"], "text": p["text"]}
        checks = []
        for c in p.get("checks", []):
            v = quantity(out, c["quantity"])
            if isinstance(v, (list, dict)):
                v = None
            ok = None if v is None else bool((c.get("lo") is None or v >= c["lo"]) and (c.get("hi") is None or v <= c["hi"]))
            checks.append({"quantity": c["quantity"], "measured": v, "lo": c.get("lo"), "hi": c.get("hi"), "expected": c.get("expected"), "met": ok})
        if checks:
            row["checks"] = checks
            row["met"] = None if any(c["met"] is None for c in checks) else all(c["met"] for c in checks)
        for ev in p.get("events", []):
            v = quantity(out, ev["quantity"])
            row.setdefault("events", []).append({"quantity": ev["quantity"], "registered_probability": ev["probability"],
                                                 "occurred": None if v is None else bool(v == ev.get("equals", 1.0))})
        rows.append(row)
    rows.sort(key=lambda r: {False: 0, None: 1, True: 2}[r.get("met")] if "met" in r else 3)    # misses first
    return rows


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
