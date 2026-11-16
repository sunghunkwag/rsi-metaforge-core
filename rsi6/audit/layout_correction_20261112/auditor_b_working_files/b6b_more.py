"""Auditor B, B5/B6, two follow-ups on made-up generic fixtures (no benchmark data, neither
environment's problem class):

(a) an environment whose instances differ only in the largest capacity of an option (1 or 2): the
    kernel's layout() is the same for all, the learner's descriptor lists are not.  What happens
    in run.measure when the budget allows learning?
(b) the prediction form: does the number of zero columns change what the learner fits and predicts?

Reads REPO; writes nothing.
"""
import os
import sys
import traceback

import numpy as np

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
sys.path.insert(0, REPO)

from rsi6 import environments                                               # noqa: E402
from rsi6.kernel import run                                                 # noqa: E402
from rsi6.kernel.environment import Environment, split                      # noqa: E402
from rsi6.kernel.problem import AssignProblem, Meter, PredictProblem, view  # noqa: E402
from rsi6.learner import version as versions                                # noqa: E402
from rsi6.learner.learner import Layout, Learner                            # noqa: E402

v0 = versions.default()


class Table(AssignProblem):
    def __init__(self, n, k, hold, seed, meter):
        rng = np.random.default_rng(seed)
        self.table = rng.random((n, k))
        super().__init__(n, k, hard=[False], ordered=False, capacity=np.full(k, hold), var_opt=(self.table,),
                         var_attr=rng.random((n, 1)), meter=meter)

    def partial_totals(self, a):
        placed = a >= 0
        return np.array([self.table[np.flatnonzero(placed), a[placed]].sum()])


class Holds(Environment):
    name = category = "audit-holds-fixture"
    form = "assign"

    def __init__(self, mixed):
        self.mixed = mixed

    def instance_ids(self):
        return [f"i{k:02d}" for k in range(20)]

    def problem(self, instance_id, meter, seed, training):
        k = int(instance_id[1:])
        return Table(6, 6, (1 + k % 2) if self.mixed else 2, k, meter), (lambda a: a)

    def score(self, instance_id, answer):
        return 0.5


budget = dict(run.BUDGET, n_train=8, n_fresh=4)
print("(a) instances that differ only in the largest capacity of an option")
for mixed in (False, True):
    fx = Holds(mixed)
    environments._CACHE["audit-holds-fixture"] = fx
    train_ids, fresh_ids = split(fx, 8, 4)
    built = [fx.problem(i, Meter(float("inf")), 0, True)[0] for i in train_ids + fresh_ids]
    kernel = {run.layout(P) for P in built}
    learner = {tuple(Layout(view(P), v0).names) for P in built}
    try:
        record = run.measure({"env": "audit-holds-fixture", "version": v0, "seed": 1, "budget": budget})["record"]
        text = f"no exception; report: iterations {record['report']['iterations']}, learned {record['report']['learned']}, failed {record['report']['failed']}"
    except Exception as error:                                         # noqa: BLE001
        frame = traceback.extract_tb(error.__traceback__)[-1]
        text = f"{type(error).__name__}: {str(error)[:140]} (raised in {os.path.basename(frame.filename)}:{frame.lineno} {frame.name})"
    print(f"   capacities {'1 and 2 mixed' if mixed else 'all 2'}: distinct kernel layouts {len(kernel)}, distinct learner "
          f"descriptor lists {len(learner)} (sizes {sorted(len(n) for n in learner)}); run.measure: {text}")
del environments._CACHE["audit-holds-fixture"]


def laws(width, count=9):
    out, shared = [], Meter(float("inf"))
    for k in range(count):
        r = np.random.default_rng(700 + k)
        x = r.random((60, 3)) * (1.0 + 0.5 * k)
        y = 2.0 * x[:, 0] - x[:, 1] + 0.5 * x[:, 2]
        x = np.column_stack([x, np.zeros((60, width - 3))])
        out.append(PredictProblem(x[:40], y[:40], x[40:], ordered=False, target=y[40:], meter=shared))
    return out


print("(b) prediction form: 3 real columns shown in 3, 4, 5, 7, 8 and 9 columns")
answers, coefs = {}, {}
for width in (3, 4, 5, 7, 8, 9):
    made = laws(width)
    L = Learner(v0)
    capability, _, report = L.acquire([view(P) for P in made[:8]], np.random.default_rng(0))
    coef = capability.get("coef") if capability else None
    coefs[width] = None if coef is None else np.asarray(coef)
    answers[width] = L.apply(capability, view(made[8]), np.random.default_rng(1))
    K = int(v0["predict.K"])
    print(f"   width {width}: learned {report.get('learned')}, coefficients {None if coef is None else len(coef)}, "
          f"coefficients of the zero columns {None if coef is None else coefs[width][2 * K + 3:2 * K + width].tolist()}")
base = answers[3]
K = int(v0["predict.K"])
for width in (4, 5, 7, 8, 9):
    d = np.abs(answers[width] - base)
    same_coef = None
    if coefs[width] is not None and coefs[3] is not None:
        real = np.concatenate([coefs[width][:2 * K + 3], coefs[width][-1:]])
        same_coef = float(np.abs(real - coefs[3]).max())
    print(f"   width {width} against width 3: predictions identical bit for bit {np.array_equal(answers[width], base)}, "
          f"largest absolute difference {d.max():.3e}; largest difference of the fitted coefficients {same_coef}")
print("   (7 is the largest number of variables among the regression training and fresh laws of the registered split, "
      "8 the width the adapter uses, 9 the number the correction record states)")
