"""Around a version of the list: every change of one field, per category, as paired differences of the acquired score."""
import glob, json, os, sys
import numpy as np
root, centre = sys.argv[1], tuple(int(x) for x in sys.argv[2].split(","))
cats = {}
for path in sorted(glob.glob(os.path.join(root, "**", "grid_*.json"), recursive=True)):
    d = json.load(open(path))
    if not d.get("smoke"): cats.setdefault(d["category"], []).append(d)
d0 = next(iter(cats.values()))[0]
index, fields, levels = np.array(d0["index"]), d0["fields"], d0["levels"]
number = lambda idx: int(np.flatnonzero((index == np.array(idx)).all(axis=1))[0])
name = lambda idx: "/".join(str(levels[f][idx[i]]) for i, f in enumerate(fields))
acq = {c: np.concatenate([np.array(d["table"]["acquired"]) for d in sorted(files, key=lambda d: d["seeds"][0])]) for c, files in cats.items()}
cpu = {c: np.concatenate([np.array(d["table"]["cpu"]) for d in sorted(files, key=lambda d: d["seeds"][0])]) for c, files in cats.items()}
cs = sorted(cats)
k0 = number(centre)
print("centre", name(centre), "| seeds per category:", {c: len(acq[c]) for c in cs})
print(" " * 30 + " ".join(f"{c[:9]:>9s}" for c in cs) + "      mean   (se)   cpu")
rows = []
for f_i, f in enumerate(fields):
    for l_i in range(len(levels[f])):
        if l_i == centre[f_i]: continue
        idx = list(centre); idx[f_i] = l_i
        k = number(idx)
        diffs = [acq[c][:, k] - acq[c][:, k0] for c in cs]
        means = [x.mean() for x in diffs]
        se = float(np.sqrt(sum(x.var(ddof=1) / len(x) for x in diffs)) / len(cs))
        ratio = sum(cpu[c][:, k].sum() / cpu[c][:, k0].sum() for c in cs) / len(cs)
        rows.append((np.mean(means), f"{f}={levels[f][l_i]}", means, se, ratio))
for m, label, means, se, ratio in sorted(rows, reverse=True):
    print(f"{label:30s}" + " ".join(f"{x:+9.4f}" for x in means) + f"   {m:+.4f} ({se:.4f})  x{ratio:.2f}")
