"""Main effects of the six fields in tables of the list (one line per category), and the best and worst mechanisms."""
import glob, json, os, sys
import numpy as np
root = sys.argv[1]
cats = {}
for path in sorted(glob.glob(os.path.join(root, "**", "grid_*.json"), recursive=True)):
    d = json.load(open(path))
    if d.get("smoke"): continue
    cats.setdefault(d["category"], []).append(d)
for cat, files in sorted(cats.items()):
    acq = np.concatenate([np.array(d["table"]["acquired"]) for d in files])          # [seed, version]
    unt = np.concatenate([np.array(d["table"]["untrained"]) for d in files])
    rounds = np.concatenate([np.array(d["table"]["rounds"]) for d in files]).mean(axis=0)
    learned = np.concatenate([np.array(d["table"]["learned"]) for d in files]).mean(axis=0)
    cpu = np.concatenate([np.array(d["table"]["cpu"]) for d in files])
    d0 = files[0]
    index, fields, levels = np.array(d0["index"]), d0["fields"], d0["levels"]
    mean = acq.mean(axis=0)
    se_pair = (acq - acq.mean(axis=1, keepdims=True)).std(axis=0).mean() / np.sqrt(len(acq))
    print(f"== {cat}: {len(acq)} seeds, untrained {unt.mean():.4f} (same for every version: {bool(np.allclose(unt, unt[:, :1]))}), acquired: best {mean.max():.4f} mean {mean.mean():.4f} worst {mean.min():.4f}; typical se of one version's mean (seed effect removed) {se_pair:.4f}; cpu/run {cpu.mean():.1f}s")
    for f_i, f in enumerate(fields):
        parts = []
        for l_i, level in enumerate(levels[f]):
            sel = index[:, f_i] == l_i
            parts.append(f"{level}: {mean[sel].mean():.4f} (rounds {rounds[sel].mean():.1f}, kept {learned[sel].mean():.2f})")
        print(f"   {f:13s} " + " | ".join(parts))
    order = np.argsort(-mean)
    name = lambda k: "/".join(str(levels[f][index[k, i]]) for i, f in enumerate(fields))
    print("   best: " + "; ".join(f"{name(k)} {mean[k]:.4f}" for k in order[:5]))
    print("   worst: " + "; ".join(f"{name(k)} {mean[k]:.4f}" for k in order[-3:]))
    for label, idx in (("generation 0", (1, 1, 1, 1, 0, 0)), ("adopted", (0, 1, 1, 1, 0, 0))):
        k = int(np.flatnonzero((index == np.array(idx)).all(axis=1))[0])
        print(f"   {label}: {mean[k]:.4f}, rank {int((mean > mean[k]).sum()) + 1} of {len(mean)}")
