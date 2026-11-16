"""Development profile (no ledger): where design r's generation 0 spends CPU against design o's."""
import cProfile, pstats, sys, os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
from rsi6.kernel import run as R
from rsi6.learner import design_r, designs, dispatch_extra
dispatch_extra.install()
env, kind = sys.argv[1], sys.argv[2]
v = design_r.default() if kind == "r0" else designs.default("o")
B = {"train": 200.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
job = {"env": env, "version": v, "seed": 9201, "budget": B, "purpose": "dev:profile"}
pr = cProfile.Profile(); pr.enable(); out = R.measure(job); pr.disable()
print(kind, env, out["record"]["cpu"], out["record"]["acquired"])
pstats.Stats(pr).sort_stats("cumulative").print_stats(28)
