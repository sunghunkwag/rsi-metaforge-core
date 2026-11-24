"""Per category: the changes of the scan around the adopted version with the largest and smallest mean of min(d acquired, d gain)."""
import glob, json, os, sys
import numpy as np
root = sys.argv[1]
cats = {}
for path in sorted(glob.glob(os.path.join(root, "**", "landscape*.json"), recursive=True)):
    d = json.load(open(path))
    if d.get("smoke"): continue
    cats.setdefault(d["category"], []).extend(d["rows"])
table = {}
for cat, rows in sorted(cats.items()):
    by = {}
    for r in rows: by.setdefault((r["field"], json.dumps(r["value"])), {})[r["seed"]] = r
    base = by[("", "null")]
    out = []
    for (f, v), runs in by.items():
        if f == "": continue
        seeds = sorted(set(runs) & set(base))
        da = np.mean([runs[s]["acquired"] - base[s]["acquired"] for s in seeds]); dg = np.mean([runs[s]["gain"] - base[s]["gain"] for s in seeds])
        cpu = sum(runs[s]["cpu"] for s in seeds) / max(sum(base[s]["cpu"] for s in seeds), 1e-9)
        out.append((min(da, dg), f"{f}={json.loads(v)}", cpu, len(seeds)))
        table.setdefault(f"{f}={json.loads(v)}", {})[cat] = min(da, dg)
    out.sort(reverse=True)
    print(f"== {cat} (n seeds {out[0][3]}): top", "; ".join(f"{n} {m:+.3f} (x{c:.2f})" for m, n, c, _ in out[:7]))
    print(f"   bottom", "; ".join(f"{n} {m:+.3f}" for m, n, c, _ in out[-4:]))
print()
mech = [k for k in table if k.split("=")[0].split(".")[0] in ("model", "assess", "shortlist")]
cs = sorted(cats)
print("mechanism fields, per category:"); print(" " * 24 + " ".join(f"{c[:8]:>8s}" for c in cs) + "     mean")
for k in sorted(mech):
    print(f"{k:24s}" + " ".join(f"{table[k].get(c, float('nan')):+8.3f}" for c in cs) + f"  {np.mean([table[k].get(c, 0.0) for c in cs]):+.4f}")
best = {c: max(table[k].get(c, 0.0) for k in table) for c in cs}
bestm = {c: max([table[k].get(c, 0.0) for k in mech] + [0.0]) for c in cs}
print("oracle, best change per category (winner's curse included): all fields", round(float(np.mean(list(best.values()))), 4), "| mechanism fields", round(float(np.mean(list(bestm.values()))), 4))
