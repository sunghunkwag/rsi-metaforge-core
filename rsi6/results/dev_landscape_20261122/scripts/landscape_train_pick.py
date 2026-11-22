"""Development reading of the landscape files: inside one category and seed, does the score a version reaches
on the TRAINING problems say which version does better on the FRESH ones?

    python3 -I landscape_train_pick.py DIR [--out FILE.json]

For every category and seed: among generation 0 and the changes (those that leave the untrained score alone),
take the version with the highest score on the training problems after acquisition (ties: generation 0 first)
and read its score on the fresh instances against generation 0's. This costs nothing in the files (every
version had the full budget) and would cost one full run per version in a learner, so it is an upper reference
for what choosing by the training score could give, not an estimate of a mechanism.
Also: the rank correlation, over versions whose runs differ from generation 0's, between the training score
and the fresh score, per category and seed, averaged.
"""
import argparse, glob, json, os, statistics as st
from collections import defaultdict

def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r

def spearman(a, b):
    ra, rb = ranks(a), ranks(b); ma, mb = st.fmean(ra), st.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den > 0 else None

parser = argparse.ArgumentParser()
parser.add_argument("directory")
parser.add_argument("--out")
args = parser.parse_args()
data = defaultdict(lambda: defaultdict(dict))
for path in sorted(glob.glob(os.path.join(args.directory, "**", "landscape_*.json"), recursive=True)):
    doc = json.load(open(path))
    if doc.get("smoke"):
        continue
    for r in doc["rows"]:
        data[doc["category"]][r["seed"]][(r["field"], json.dumps(r["value"], sort_keys=True))] = r
BASE = ("", "null")
out = {}
for cat in sorted(data):
    picks, rhos, picked_names = [], [], defaultdict(int)
    for seed in sorted(data[cat]):
        rows = data[cat][seed]; base = rows[BASE]
        options = [(k, r) for k, r in rows.items() if abs(r["untrained"] - base["untrained"]) < 1e-15 and r.get("train_acquired") is not None]
        best = max(options, key=lambda kr: (kr[1]["train_acquired"], kr[0] == BASE))
        picks.append(best[1]["acquired"] - base["acquired"])
        picked_names[best[0][0] or "generation 0"] += 1
        differ = [r for k, r in options if k != BASE and (abs(r["acquired"] - base["acquired"]) > 1e-15 or abs(r["train_acquired"] - base["train_acquired"]) > 1e-15)]
        if len(differ) >= 5:
            rho = spearman([r["train_acquired"] for r in differ], [r["acquired"] for r in differ])
            if rho is not None:
                rhos.append(rho)
    n = len(picks)
    out[cat] = {"seeds": n, "fresh_change_of_the_pick": st.fmean(picks), "se": (st.stdev(picks) / n ** 0.5) if n > 1 else None,
                "seeds_above": sum(1 for x in picks if x > 0), "seeds_below": sum(1 for x in picks if x < 0),
                "rank_correlation_train_fresh": st.fmean(rhos) if rhos else None, "picked": dict(picked_names)}
    o = out[cat]
    print(f"{cat:13s} seeds {n} pick by training score: fresh {o['fresh_change_of_the_pick']:+.4f} (se {o['se'] if o['se'] is None else round(o['se'], 4)})"
          f" +{o['seeds_above']}/-{o['seeds_below']}  rank corr train~fresh {o['rank_correlation_train_fresh'] if o['rank_correlation_train_fresh'] is None else round(o['rank_correlation_train_fresh'], 3)}")
vals = [out[c]["fresh_change_of_the_pick"] for c in out]
print(f"mean over {len(vals)} categories: {st.fmean(vals):+.4f}")
if args.out:
    json.dump({"what": "development: the version with the best training score per category and seed, on the fresh instances",
               "per_category": out, "mean_over_categories": st.fmean(vals)}, open(args.out, "w"), indent=1, sort_keys=True)
