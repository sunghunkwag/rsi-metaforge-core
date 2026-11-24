# Development script, kept as it was run (2026-11-24/25) apart from the two paths below.
# REPO: the root of the repository; DEV: a scratch directory for pools and outputs (RSI6_T_DEV).
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json, sys
import numpy as np
r = json.load(open(sys.argv[1]))
names = None
tot = {}
for t, d in r["targets"].items():
    a = {n: np.array(x) for n, x in d["acquired"].items()}
    names = list(a)
    print(f"{t:11s} untrained {d['untrained']:.4f} | " + " | ".join(f"{n} {a[n].mean():.4f}" for n in names))
    base = a["generation 0"]
    print("            vs generation 0: " + " ; ".join(f"{n} {(a[n]-base).mean():+.4f} ({(a[n]-base).std(ddof=1)/np.sqrt(len(base)):.4f})" for n in names[1:]))
    gens = sorted({int(n.split()[1]) for n in names if n.startswith("recursive")})
    print("            recursive - frozen: " + " ; ".join(f"g{g} {(a[f'recursive {g}']-a[f'frozen {g}']).mean():+.4f} ({(a[f'recursive {g}']-a[f'frozen {g}']).std(ddof=1)/np.sqrt(len(base)):.4f})" for g in gens)
          + " | recursive - shuffled: " + " ; ".join(f"g{g} {(a[f'recursive {g}']-a[f'shuffled {g}']).mean():+.4f}" for g in gens))
    if "foresight" in d:
        print("            foresight: " + " | ".join(f"{n} {v:+.3f}" for n, v in d["foresight"].items() if v is not None))
    if "cpu" in d:
        print("            cpu/run: " + " | ".join(f"{n} {v:.2f}" for n, v in d["cpu"].items()))
    for n in names:
        tot.setdefault(n, []).append(a[n].mean())
print("mean over kinds left out: " + " | ".join(f"{n} {np.mean(v):.4f}" for n, v in tot.items()))
