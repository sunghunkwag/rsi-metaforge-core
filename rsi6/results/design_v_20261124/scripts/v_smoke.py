"""Scratch: design v against the first design through the kernel. python3 -I v_smoke.py TEST_E N_SEEDS kind..."""
# Development script, kept as it was run (2026-11-24) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import sys, time, warnings, json
warnings.filterwarnings("ignore")
import numpy as np
from rsi6.learner import design_v, version as version_a
from rsi6.environments import fresh
from rsi6.kernel.run import measure
design_v.install(); fresh.install()
budget = {"train": 40.0, "test_c": 2.0, "test_e": float(sys.argv[1]), "n_train": 16, "n_fresh": 24}
seeds = list(range(751001, 751001 + int(sys.argv[2])))
for kind in sys.argv[3:]:
    out = {}
    for name, v in (("first", version_a.default()), ("v", design_v.default())):
        rows = [measure({"env": kind, "version": v, "seed": s, "budget": dict(budget), "purpose": "dev-v"})["record"] for s in seeds]
        out[name] = (np.mean([r["untrained"] for r in rows]), np.mean([r["acquired"] for r in rows]), np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in rows]),
                     np.mean([r["report"].get("credit") for r in rows], axis=0) if name == "v" else None)
    c = out["v"][3]
    print(f"{kind:11s} test_e {budget['test_e']:g} | " + " | ".join(f"{n}: untrained {u:.4f} acquired {a:.4f} cpu {t:.0f}s" for n, (u, a, t, _) in out.items())
          + " | credit " + " ".join(f"{x:.2f}" for x in c), flush=True)
