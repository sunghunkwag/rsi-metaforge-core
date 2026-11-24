"""Development diagnostic (no ledger): why a design-r run at a large budget collapses on some fresh
instances. Re-runs one D1 job with design o's ``construct`` wrapped to record, by phase, how each
construction ended, and prints what the apply phase did on every fresh and training instance."""
import json, os, sys
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
from rsi6.kernel import run as R
from rsi6.learner import design_o as O, design_q as Q, design_r, dispatch_extra
dispatch_extra.install()
env, seed, train = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
log = {"phase": "acquire", "acquire": {"ok": 0, "Infeasible": 0, "BudgetExhausted": 0}, "apply": []}
real = O.construct

def construct(P, *a, **k):
    try:
        out = real(P, *a, **k)
        hard = float(np.asarray(out[0])[P.hard].sum()) if P.hard.any() else 0.0
        name = "hard violation" if hard > 0 else "ok"
        if log["phase"] == "acquire":
            log["acquire"][name] = log["acquire"].get(name, 0) + 1
        else:
            log["apply"].append(name)
        return out
    except Exception as error:                               # noqa: BLE001
        name = type(error).__name__
        if log["phase"] == "acquire":
            log["acquire"][name] = log["acquire"].get(name, 0) + 1
        else:
            log["apply"].append(name)
        raise

O.construct = construct
acquire = design_r.LearnerR.acquire

def acquire_then_flag(self, problems, rng, memory=None):
    out = acquire(self, problems, rng, memory)
    log["phase"] = "apply"
    return out

design_r.LearnerR.acquire = acquire_then_flag
B = {"train": train, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
rec = R.measure({"env": env, "version": design_r.default(), "seed": seed, "budget": B, "purpose": "dev:diag"})["record"]
n_f = len(rec["fresh_acquired"])
ap = log["apply"]
# measure(): fresh untrained, fresh acquired, train untrained, train acquired; untrained applications make no program construction through design q's path unless a program is kept
print(json.dumps({"env": env, "seed": seed, "train": train, "gain": rec["gain"], "report": {k: rec["report"].get(k) for k in ("program_rounds", "switches", "program_size", "learned", "held_back", "failed")},
                  "acquire_constructions": log["acquire"], "apply_calls": len(ap), "apply_outcomes": {k: ap.count(k) for k in sorted(set(ap))},
                  "fresh_untrained": rec["fresh_untrained"], "fresh_acquired": rec["fresh_acquired"],
                  "apply_sequence": ap}, indent=1))
