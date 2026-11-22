"""Reading 2 of PREDICTION.md: generation 0 and the named changes on new seeds, all nine categories.

    python3 -I reading_2.py DIR --out FILE.json [--boot 5000]

Input: the ``pair_<category>_<seed>.json`` files of plan ``dev-pair``. For every change:
M9 = the mean over the categories of the mean over seeds of the smaller of the two changes (acquired, gain),
per run as the sentence in PREDICTION.md reads; its 5 % point from resampling seeds within categories; the CPU
over the categories against generation 0's (per-run means summed over categories, so that every category
weighs as one whatever its number of seeds). Confirmed on the pool: 5 % point above 0 and CPU at most 1.15.
Beside it: the value of amendment 2 (each category cut to [-0.03, +0.01], the smaller of the two means) against
the margin 0.005.
"""
import argparse, glob, json, os, random, statistics as st
from collections import defaultdict

BASE = ("", "null")
FLOOR, CAP, MARGIN, CPU_LIMIT = -0.03, 0.01, 0.005, 1.15

def quantile(xs, q):
    xs = sorted(xs); pos = q * (len(xs) - 1); lo = int(pos); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)

parser = argparse.ArgumentParser()
parser.add_argument("directory")
parser.add_argument("--out", required=True)
parser.add_argument("--boot", type=int, default=5000)
parser.add_argument("--seed", type=int, default=20261123)
args = parser.parse_args()
data = defaultdict(lambda: defaultdict(dict))
machines = {}
for path in sorted(glob.glob(os.path.join(args.directory, "**", "pair_*.json"), recursive=True)):
    doc = json.load(open(path))
    machines[os.path.basename(path)] = doc.get("machine")
    for r in doc["rows"]:
        data[doc["category"]][r["seed"]][(r["field"], json.dumps(r["value"], sort_keys=True))] = r
cats = sorted(data)
keys = sorted(set.intersection(*(set(data[c][s]) for c in cats for s in data[c])) - {BASE})
rng = random.Random(args.seed)
out = {"what": "reading 2 of PREDICTION.md", "categories": {c: sorted(data[c]) for c in cats}, "changes": {}, "machines": machines,
       "rules": {"floor": FLOOR, "cap": CAP, "margin": MARGIN, "cpu_limit": CPU_LIMIT, "bootstrap": args.boot}}
print(f"categories {len(cats)}: " + ", ".join(f"{c}({len(data[c])})" for c in cats))
for k in keys:
    d = {c: [(data[c][s][k]["acquired"] - data[c][s][BASE]["acquired"], data[c][s][k]["gain"] - data[c][s][BASE]["gain"])
             for s in sorted(data[c])] for c in cats}
    def m9(sample):
        return st.fmean(st.fmean(min(a, g) for a, g in sample[c]) for c in cats)
    def clipped(sample):
        a = st.fmean(max(FLOOR, min(CAP, st.fmean(x[0] for x in sample[c]))) for c in cats)
        g = st.fmean(max(FLOOR, min(CAP, st.fmean(x[1] for x in sample[c]))) for c in cats)
        return min(a, g)
    boots, boots_clipped = [], []
    for _ in range(args.boot):
        sample = {c: [rng.choice(d[c]) for _ in d[c]] for c in cats}
        boots.append(m9(sample)); boots_clipped.append(clipped(sample))
    cpu = (sum(st.fmean(data[c][s][k]["cpu"] for s in data[c]) for c in cats)
           / sum(st.fmean(data[c][s][BASE]["cpu"] for s in data[c]) for c in cats))
    per = {}
    for c in cats:
        x = [min(a, g) for a, g in d[c]]
        per[c] = {"n": len(x), "mean": st.fmean(x), "se": (st.stdev(x) / len(x) ** 0.5) if len(x) > 1 else None,
                  "acquired_change": st.fmean(a for a, _ in d[c]), "gain_change": st.fmean(g for _, g in d[c]),
                  "runs_above": sum(1 for v in x if v > 0), "runs_below": sum(1 for v in x if v < 0),
                  "cpu_ratio": sum(data[c][s][k]["cpu"] for s in data[c]) / sum(data[c][s][BASE]["cpu"] for s in data[c])}
    res = {"M9": m9(d), "q05": quantile(boots, 0.05), "q50": quantile(boots, 0.5), "q95": quantile(boots, 0.95),
           "share_at_or_below_zero": sum(1 for b in boots if b <= 0) / len(boots), "cpu_ratio": cpu,
           "amendment_2_value": clipped(d), "amendment_2_q05": quantile(boots_clipped, 0.05),
           "categories_above": sum(1 for c in cats if per[c]["mean"] > 0), "categories_below": sum(1 for c in cats if per[c]["mean"] < 0),
           "per_category": per}
    res["confirmed_on_the_pool"] = bool(res["q05"] > 0 and cpu <= CPU_LIMIT)
    res["amendment_2_at_or_above_margin"] = bool(res["amendment_2_value"] >= MARGIN)
    out["changes"]["=".join(k)] = res
    print(f"{k[0]}={k[1]}: M9 {res['M9']:+.4f} q05 {res['q05']:+.4f} q95 {res['q95']:+.4f} share<=0 {res['share_at_or_below_zero']:.3f}"
          f" cpu x{cpu:.2f} | amendment 2: {res['amendment_2_value']:+.4f} (q05 {res['amendment_2_q05']:+.4f})"
          f" | categories +{res['categories_above']}/-{res['categories_below']} | confirmed: {res['confirmed_on_the_pool']}")
    for c in cats:
        p = per[c]
        print(f"      {c:13s} n {p['n']:2d} mean {p['mean']:+.4f} se {p['se'] if p['se'] is None else round(p['se'], 4)} runs +{p['runs_above']}/-{p['runs_below']} cpu x{p['cpu_ratio']:.2f}")
out["generation_0"] = {c: {"untrained": st.fmean(data[c][s][BASE]["untrained"] for s in data[c]),
                           "acquired": st.fmean(data[c][s][BASE]["acquired"] for s in data[c]),
                           "gain": st.fmean(data[c][s][BASE]["gain"] for s in data[c]),
                           "gain_sd_over_seeds": st.pstdev([data[c][s][BASE]["gain"] for s in data[c]])} for c in cats}
json.dump(out, open(args.out, "w"), indent=1, sort_keys=True)
