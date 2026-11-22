"""Development check on the landscape files: is generation 0 unlucky on these seeds?
For every category: the distribution, over the changes whose runs differ from generation 0 at all, of the mean
change of the acquired score; and the changes of one field in order of value.
    python3 -I landscape_shift.py DIR [field ...]
"""
import glob, json, os, sys, statistics as st
from collections import defaultdict
d = sys.argv[1]; fields = sys.argv[2:]
data = defaultdict(lambda: defaultdict(dict))
for path in sorted(glob.glob(os.path.join(d, "**", "landscape_*.json"), recursive=True)):
    doc = json.load(open(path))
    for r in doc["rows"]:
        data[doc["category"]][r["seed"]][(r["field"], json.dumps(r["value"]))] = r
B = ("", "null")
for cat in sorted(data):
    seeds = sorted(data[cat]); keys = sorted(set.intersection(*(set(data[cat][s]) for s in seeds)) - {B})
    eff, same = [], 0
    for k in keys:
        da = [data[cat][s][k]["acquired"] - data[cat][s][B]["acquired"] for s in seeds]
        du = [data[cat][s][k]["untrained"] - data[cat][s][B]["untrained"] for s in seeds]
        if all(abs(x) < 1e-15 for x in da) and all(abs(x) < 1e-15 for x in du):
            same += 1
        elif all(abs(x) < 1e-15 for x in du):       # leave out the changes that move the untrained score
            eff.append(st.fmean(da))
    base = [data[cat][s][B]["acquired"] - data[cat][s][B]["untrained"] for s in seeds]
    if eff:
        print(f"{cat:13s} seeds {len(seeds)} gen0 gain {st.fmean(base):+.4f} | identical to gen0: {same:2d} | differ (untrained unchanged): {len(eff):2d}"
              f"  mean {st.fmean(eff):+.4f} median {st.median(eff):+.4f} positive {sum(1 for x in eff if x > 0)}/{len(eff)}")
    for f in fields:
        row = []
        for k in keys:
            if k[0] == f:
                row.append((json.loads(k[1]), st.fmean(data[cat][s][k]["acquired"] - data[cat][s][B]["acquired"] for s in seeds)))
        row.sort(key=lambda t: (isinstance(t[0], str), t[0]))
        print(f"    {f}: " + "  ".join(f"{v}:{x:+.4f}" for v, x in row))
