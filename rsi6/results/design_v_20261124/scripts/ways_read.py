"""Scratch: read the tables of ways (design v). For each kind: what the best way is worth over the version's own; main
effects of each setting; and, leaving the kind out, what the way that is best on the OTHER kinds is worth there."""
# Development script, kept as it was run (2026-11-24) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import json, sys, glob, os
import numpy as np
from rsi6.learner import design_v as V
ways = V.ways()
own = ways.index(V.MECH)
T = {}
for path in sorted(glob.glob(os.path.join(sys.argv[1], "ways_*.json"))):
    d = json.load(open(path))
    if len(d["ways"]) != len(ways):
        continue
    T[d["kind"]] = np.array([[[t[3] for t in p] for p in w] for w in d["results"]])       # way x problem x trial -> score
kinds = sorted(T)
M = {k: T[k].mean(axis=(1, 2)) for k in kinds}
print("kinds:", kinds)
for k in kinds:
    a, b = T[k][:, :, 0].mean(axis=1), T[k][:, :, 1].mean(axis=1)
    half = np.argmax(a)
    print(f"{k:11s} own {M[k][own]:.4f} | best {M[k].max():.4f} ({ {n: V.LEVELS[n][ways[int(np.argmax(M[k]))][n]] for n in V.LEVELS} }) | "
          f"best on trial 1 scored on trial 2: {b[half]:.4f} (own {b[own]:.4f}) | sd over ways {M[k].std():.4f} | trial-to-trial r {np.corrcoef(a, b)[0, 1]:+.2f}")
print("main effects (mean score at each level minus the kind's mean over all ways):")
for name in V.LEVELS:
    line = []
    for k in kinds:
        eff = [M[k][[i for i, w in enumerate(ways) if w[name] == lv]].mean() - M[k].mean() for lv in range(3)]
        line.append(k[:6] + " " + "/".join(f"{e:+.3f}" for e in eff))
    print(f"  {name:6s} {V.LEVELS[name]} | " + " | ".join(line))
if len(kinds) > 2:
    Z = {k: (M[k] - M[k].mean()) / (M[k].std() + 1e-12) for k in kinds}
    print("rank correlation of ways between kinds:")
    for i, a in enumerate(kinds):
        print("  " + a[:8].ljust(9) + " ".join(f"{np.corrcoef(np.argsort(np.argsort(M[a])), np.argsort(np.argsort(M[b])))[0, 1]:+.2f}" for b in kinds))
    print("leave one kind out: the way best on the others (mean of standardised scores), scored on the kind left out:")
    tot = []
    for k in kinds:
        others = [o for o in kinds if o != k]
        pick = int(np.argmax(np.mean([Z[o] for o in others], axis=0)))
        tot.append((M[k][pick] - M[k][own], M[k].max() - M[k][own]))
        print(f"  {k:11s} own {M[k][own]:.4f} | picked on the others {M[k][pick]:.4f} ({M[k][pick] - M[k][own]:+.4f}) | best of this kind {M[k].max():.4f} ({M[k].max() - M[k][own]:+.4f}) | "
              f"picked: { {n: V.LEVELS[n][ways[pick][n]] for n in V.LEVELS} }")
    print(f"  mean gain of the way picked on the others: {np.mean([t[0] for t in tot]):+.4f} ; mean gain of each kind's own best: {np.mean([t[1] for t in tot]):+.4f}")
