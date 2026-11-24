"""What the best possible use of the tables would find: choose the version of the list with the best mean on seven
categories (all seeds), score it on the eighth, against the adopted version and generation 0. Descriptive."""
import glob, json, os, sys
import numpy as np
root = sys.argv[1]
cats = {}
for path in sorted(glob.glob(os.path.join(root, "**", "grid_*.json"), recursive=True)):
    d = json.load(open(path))
    if not d.get("smoke"): cats.setdefault(d["category"], []).append(d)
d0 = next(iter(cats.values()))[0]
index, fields, levels = np.array(d0["index"]), d0["fields"], d0["levels"]
name = lambda k: "/".join(str(levels[f][index[k, i]]) for i, f in enumerate(fields))
number = lambda idx: int(np.flatnonzero((index == np.array(idx)).all(axis=1))[0])
acq = {c: np.concatenate([np.array(d["table"]["acquired"]) for d in sorted(files, key=lambda d: d["seeds"][0])]) for c, files in cats.items()}
cs = sorted(cats)
adopted, gen0 = number((0, 1, 1, 1, 0, 0)), number((1, 1, 1, 1, 0, 0))
mean = {c: acq[c].mean(axis=0) for c in cs}
rng = np.random.default_rng(3)
def loco(base):
    rows, diffs = [], {}
    for held in cs:
        rest = np.mean([mean[c] for c in cs if c != held], axis=0)
        k = int(np.argmax(rest))
        diffs[held] = acq[held][:, k] - acq[held][:, base]
        rows.append((held, name(k), rest[k] - rest[base], diffs[held].mean()))
    point = np.mean([diffs[c].mean() for c in cs])
    boot = [np.mean([diffs[c][rng.integers(0, len(diffs[c]), len(diffs[c]))].mean() for c in cs]) for _ in range(4000)]
    return rows, point, np.quantile(boot, 0.05), np.quantile(boot, 0.95)
for label, base in (("the adopted version", adopted), ("generation 0", gen0)):
    rows, point, lo, hi = loco(base)
    print(f"against {label} ({name(base)}):")
    for held, chosen, on_rest, on_held in rows:
        print(f"   held out {held:11s} chosen {chosen:28s} on the seven {on_rest:+.4f}  on the held-out {on_held:+.4f}")
    print(f"   mean on the held-out categories {point:+.4f}  (5 % point {lo:+.4f}, 95 % point {hi:+.4f}; the choice itself is not resampled)")
# split by seeds: choose on the first eight seeds of all categories, score on the other eight
first = np.mean([acq[c][:8].mean(axis=0) for c in cs], axis=0)
second = np.mean([acq[c][8:].mean(axis=0) for c in cs], axis=0)
k = int(np.argmax(first))
d = [acq[c][8:, k] - acq[c][8:, adopted] for c in cs]
boot = [np.mean([x[rng.integers(0, len(x), len(x))].mean() for x in d]) for _ in range(4000)]
print(f"split by seeds: best on seeds 1-8 is {name(k)} ({first[k] - first[adopted]:+.4f} over the adopted version there); on seeds 9-16 {second[k] - second[adopted]:+.4f} (5 % point {np.quantile(boot, 0.05):+.4f})")
allm = np.mean([mean[c] for c in cs], axis=0)
order = np.argsort(-allm)
print("mean over the eight categories, all seeds: adopted", round(float(allm[adopted]), 4), "rank", int((allm > allm[adopted]).sum()) + 1, "| generation 0", round(float(allm[gen0]), 4), "rank", int((allm > allm[gen0]).sum()) + 1, "| best", name(order[0]), round(float(allm[order[0]]), 4), "| list mean", round(float(allm.mean()), 4), "worst", round(float(allm.min()), 4))
print("top ten:", "; ".join(f"{name(k)} {allm[k]:.4f}" for k in order[:10]))
