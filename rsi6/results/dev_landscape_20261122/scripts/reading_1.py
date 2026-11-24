"""Reading 1 of PREDICTION.md: the change chosen on six categories, on the three it was chosen without.

    python3 -I reading_1.py DIR --out FILE.json

m3 = the mean over knapsack, partitioning and setcover of the mean over seeds of the smaller of the two changes
(acquired, gain) of ``assess.holdback`` 0.3; p3 = the share of the common changes whose own three-category mean
is at or above m3. Carries to the three if m3 > 0 and p3 <= 0.10.
"The smaller of the two changes" is taken per run, as the sentence in PREDICTION.md reads; the smaller of the
two means per category is printed beside it (it is what the table of the six categories used).
"""
import argparse, glob, json, os, statistics as st
from collections import defaultdict

THREE = ("knapsack", "partitioning", "setcover")
CHOICE = ("assess.holdback", "0.3")
BASE = ("", "null")

parser = argparse.ArgumentParser()
parser.add_argument("directory")
parser.add_argument("--out", required=True)
args = parser.parse_args()
data = defaultdict(lambda: defaultdict(dict))
for path in sorted(glob.glob(os.path.join(args.directory, "**", "landscape_*.json"), recursive=True)):
    doc = json.load(open(path))
    if doc.get("smoke") or doc["category"] not in THREE:
        continue
    for r in doc["rows"]:
        data[doc["category"]][r["seed"]][(r["field"], json.dumps(r["value"], sort_keys=True))] = r
missing = [c for c in THREE if c not in data]
if missing:
    raise SystemExit(f"not there yet: {missing}")
common = set.intersection(*(set(data[c][s]) for c in THREE for s in data[c])) - {BASE}
per_run, of_means, detail = {}, {}, {}
for k in common:
    a, b = [], []
    for c in THREE:
        seeds = sorted(data[c])
        da = [data[c][s][k]["acquired"] - data[c][s][BASE]["acquired"] for s in seeds]
        dg = [data[c][s][k]["gain"] - data[c][s][BASE]["gain"] for s in seeds]
        a.append(st.fmean(min(x, y) for x, y in zip(da, dg)))
        b.append(min(st.fmean(da), st.fmean(dg)))
        if k == CHOICE:
            cpu = sum(data[c][s][k]["cpu"] for s in seeds) / sum(data[c][s][BASE]["cpu"] for s in seeds)
            others = [1 for s in seeds]
            detail[c] = {"seeds": seeds, "acquired_change": st.fmean(da), "gain_change": st.fmean(dg),
                         "per_seed_acquired_change": da, "cpu_ratio": cpu,
                         "generation_0": {"untrained": st.fmean(data[c][s][BASE]["untrained"] for s in seeds),
                                          "acquired": st.fmean(data[c][s][BASE]["acquired"] for s in seeds)}}
    per_run[k], of_means[k] = st.fmean(a), st.fmean(b)
m3, m3_means = per_run[CHOICE], of_means[CHOICE]
p3 = sum(1 for v in per_run.values() if v >= m3) / len(per_run)
p3_means = sum(1 for v in of_means.values() if v >= m3_means) / len(of_means)
for c in THREE:
    ranked = sorted(common, key=lambda k: -min(
        st.fmean(data[c][s][k]["acquired"] - data[c][s][BASE]["acquired"] for s in data[c]),
        st.fmean(data[c][s][k]["gain"] - data[c][s][BASE]["gain"] for s in data[c])))
    detail[c]["rank_of_the_choice"] = ranked.index(CHOICE) + 1
    differ = [st.fmean(data[c][s][k]["acquired"] - data[c][s][BASE]["acquired"] for s in data[c]) for k in common
              if any(abs(data[c][s][k]["acquired"] - data[c][s][BASE]["acquired"]) > 1e-15 for s in data[c])
              and all(abs(data[c][s][k]["untrained"] - data[c][s][BASE]["untrained"]) < 1e-15 for s in data[c])]
    detail[c]["changes_that_differ"] = {"n": len(differ), "above_generation_0": sum(1 for x in differ if x > 0),
                                        "mean": st.fmean(differ) if differ else None}
verdict = bool(m3 > 0 and p3 <= 0.10)
out = {"what": "reading 1 of PREDICTION.md", "choice": list(CHOICE), "categories": list(THREE), "common_changes": len(common),
       "m3": m3, "p3": p3, "carries_to_the_three": verdict,
       "with_the_smaller_of_the_two_means": {"m3": m3_means, "p3": p3_means, "carries": bool(m3_means > 0 and p3_means <= 0.10)},
       "per_category": detail,
       "top_of_the_three": [[list(k), v] for k, v in sorted(per_run.items(), key=lambda kv: -kv[1])[:10]]}
json.dump(out, open(args.out, "w"), indent=1, sort_keys=True)
print(f"m3 {m3:+.4f}  p3 {p3:.3f}  carries to the three: {verdict}   (smaller of the means: m3 {m3_means:+.4f} p3 {p3_means:.3f})")
for c in THREE:
    d = detail[c]
    print(f"  {c:13s} seeds {len(d['seeds'])} acquired {d['acquired_change']:+.4f} gain {d['gain_change']:+.4f} cpu x{d['cpu_ratio']:.2f}"
          f" rank {d['rank_of_the_choice']}/{len(common)}; changes that differ: {d['changes_that_differ']}")
print("top of the three:", [(k[0], k[1], round(v, 4)) for k, v in sorted(per_run.items(), key=lambda kv: -kv[1])[:6]])
