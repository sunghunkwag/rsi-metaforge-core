"""Step 1 of PREDICTION_3.md: the short list of a scan.

    python3 -I shortlist.py DIR [--top 5]

Among the versions one field away from the centre that were measured on every category: those whose CPU
over the categories is at most 1.15 times the centre's (per-run means summed over categories), ordered by
the value of amendment 2 (each category's mean change cut to [-0.03, +0.01], for the acquired score and for
the gain, the smaller of the two means), then by the plain mean (the smaller of the two uncut means), then
by name. The version process c adopted is in the files as one more row; it is not one field away from the
centre and is not on the list. Prints the list as arguments for ``dev_landscape --only``.
"""
import argparse, glob, json, os, statistics as st
from collections import defaultdict

FLOOR, CAP, CPU_LIMIT = -0.03, 0.01, 1.15
parser = argparse.ArgumentParser()
parser.add_argument("directory"); parser.add_argument("--top", type=int, default=5); parser.add_argument("--out")
args = parser.parse_args()
data = defaultdict(lambda: defaultdict(dict))
for path in sorted(glob.glob(os.path.join(args.directory, "**", "landscape_*.json"), recursive=True)):
    doc = json.load(open(path))
    if doc.get("smoke"):
        continue
    for r in doc["rows"]:
        data[doc["category"]][r["seed"]][(r["field"], json.dumps(r["value"], sort_keys=True))] = r
BASE = ("", "null")
cats = sorted(data)
common = set.intersection(*(set(data[c][s]) for c in cats for s in data[c])) - {BASE}
common = {k for k in common if not k[0].startswith("adopted:")}
rows = []
for k in common:
    a, g, ck, cb = [], [], 0.0, 0.0
    for c in cats:
        seeds = sorted(data[c])
        a.append(st.fmean(data[c][s][k]["acquired"] - data[c][s][BASE]["acquired"] for s in seeds))
        g.append(st.fmean(data[c][s][k]["gain"] - data[c][s][BASE]["gain"] for s in seeds))
        ck += st.fmean(data[c][s][k]["cpu"] for s in seeds); cb += st.fmean(data[c][s][BASE]["cpu"] for s in seeds)
    clip = lambda xs: st.fmean(max(FLOOR, min(CAP, x)) for x in xs)
    rows.append({"field": k[0], "value_json": k[1], "amendment_2": min(clip(a), clip(g)), "plain": min(st.fmean(a), st.fmean(g)),
                 "cpu_ratio": ck / cb, "per_category": {c: min(x, y) for c, x, y in zip(cats, a, g)}})
eligible = sorted((r for r in rows if r["cpu_ratio"] <= CPU_LIMIT), key=lambda r: (-r["amendment_2"], -r["plain"], r["field"], r["value_json"]))
print(f"categories {len(cats)}: " + ", ".join(f"{c}({len(data[c])})" for c in cats) + f"; changes on all of them {len(rows)}, eligible {len(eligible)}")
for r in eligible[:max(args.top, 10)]:
    print(f"  {r['field']:22s} {r['value_json']:>18s} amendment 2 {r['amendment_2']:+.4f} plain {r['plain']:+.4f} cpu x{r['cpu_ratio']:.2f}")
top = eligible[:args.top]
print("--only " + " ".join(f"'{r['field']}={r['value_json']}'" for r in top))
if args.out:
    json.dump({"categories": {c: sorted(data[c]) for c in cats}, "eligible": len(eligible), "short_list": top, "next": eligible[args.top:args.top + 10]},
              open(args.out, "w"), indent=1, sort_keys=True)
