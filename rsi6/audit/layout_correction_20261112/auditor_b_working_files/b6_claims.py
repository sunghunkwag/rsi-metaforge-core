"""Auditor B, B6: statements of corrections.json that can be tested on made-up fixtures.

Every problem here is made up in this file (random numbers); the environments knapsack and
regression are not loaded and the learner never sees a benchmark instance.  Section 5 repeats the
correction's own test on its own made-up numbers (the class KnapsackProblem with random integers,
not the environment).  Reads REPO; writes nothing.
"""
import json
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
from rsi6.learner import learner as learner_module                          # noqa: E402
from rsi6.learner import version as versions                                # noqa: E402
from rsi6.learner.learner import Layout, Learner                            # noqa: E402
from rsi6.meta import rounds                                                # noqa: E402

v0 = versions.default()
calls = {"acquire": 0, "apply": 0}
_acquire, _apply = Learner.acquire, Learner.apply


def counted_acquire(self, *args, **kwargs):
    calls["acquire"] += 1
    return _acquire(self, *args, **kwargs)


def counted_apply(self, *args, **kwargs):
    calls["apply"] += 1
    return _apply(self, *args, **kwargs)


Learner.acquire, Learner.apply = counted_acquire, counted_apply        # in this process only


def outcome(fn):
    before = dict(calls)
    try:
        fn()
        text = "no exception"
    except Exception as error:                                         # noqa: BLE001
        frame = traceback.extract_tb(error.__traceback__)[-1]
        text = f"{type(error).__name__}: {str(error)[:150]} (raised in {os.path.basename(frame.filename)}:{frame.lineno} {frame.name})"
    return text, {k: calls[k] - before[k] for k in calls}


# ------------------------------------------------------------------ 1. when does the kernel refuse?
class Columns(Environment):
    """Made-up prediction problems; the instances named in ``odd`` have one more column."""
    name = category = "audit-columns-fixture"
    form = "predict"

    def __init__(self, odd=()):
        self.odd = set(odd)

    def instance_ids(self):
        return [f"i{k:02d}" for k in range(12)]

    def problem(self, instance_id, meter, seed, training):
        k = int(instance_id[1:])
        x = np.random.default_rng(k).random((40, 3 if instance_id in self.odd else 2))
        return PredictProblem(x[:30], x[:30].sum(axis=1), x[30:], ordered=False,
                              target=x[30:].sum(axis=1) if training else None, meter=meter), (lambda a: a)

    def score(self, instance_id, answer):
        return 0.5


budget = dict(run.BUDGET, n_train=4, n_fresh=4)
train_ids, fresh_ids = split(Columns(), 4, 4)
print("1. the kernel's check: when is an uneven environment refused?  (made-up prediction fixture)")
print("   training ids", train_ids, "fresh ids", fresh_ids)
for label, odd in (("all instances alike", []), ("second TRAINING instance has another layout", [train_ids[1]]),
                   ("third FRESH instance has another layout", [fresh_ids[2]])):
    environments._CACHE["audit-columns-fixture"] = Columns(odd)
    text, used = outcome(lambda: run.measure({"env": "audit-columns-fixture", "version": v0, "seed": 1, "budget": budget}))
    print(f"   {label}: {text}; learner calls before the end: {used}")
del environments._CACHE["audit-columns-fixture"]


# ------------------------------------------------------- 2. the learner itself on uneven layouts
class Table(AssignProblem):
    """Made-up assignment problem: each variable pays a random cost per option, options hold
    ``hold`` variables, and every variable has ``columns`` random attributes."""

    def __init__(self, n, k, columns, hold, seed, meter, pad=0):
        rng = np.random.default_rng(seed)
        self.table = rng.random((n, k))
        attr = np.column_stack([rng.random((n, columns)), np.zeros((n, pad))])      # ``pad`` further columns of zeros
        super().__init__(n, k, hard=[False], ordered=False, capacity=np.full(k, hold), var_opt=(self.table,),
                         var_attr=attr, meter=meter)

    def partial_totals(self, a):
        placed = a >= 0
        return np.array([self.table[np.flatnonzero(placed), a[placed]].sum()])


print("2. the frozen learner, called directly, on made-up problems whose layouts differ (no kernel check in between)")
meter = Meter(0.0)                                  # a finite budget, as the kernel gives: 40 constructions per problem
uneven = [Table(8, 5, c, 2, s, meter) for s, c in enumerate((2, 4, 2, 4, 3, 2, 4, 3))]
meter.limit = 40.0 * sum(P.construction_units() for P in uneven)
print("   sizes of the learner's parameter vector per problem:", [Layout(view(P), v0).size for P in uneven])
text, used = outcome(lambda: Learner(v0).acquire([view(P) for P in uneven], np.random.default_rng(0)))
print("   assignment form, attribute columns 2/4/2/4/3/2/4/3:", text)
meter = Meter(0.0)
even = [Table(8, 5, 3, 2, s, meter) for s in range(8)]
meter.limit = 40.0 * sum(P.construction_units() for P in even)
text, used = outcome(lambda: Learner(v0).acquire([view(P) for P in even], np.random.default_rng(0)))
print("   assignment form, 3 attribute columns everywhere:", text)


def predict_set(columns):
    out, shared = [], Meter(float("inf"))
    for k, c in enumerate(columns):
        x = np.random.default_rng(100 + k).random((40, c))
        out.append(PredictProblem(x[:30], x[:30].sum(axis=1), x[30:], ordered=False, target=x[30:].sum(axis=1), meter=shared))
    return out


text, used = outcome(lambda: Learner(v0).acquire([view(P) for P in predict_set((2, 3, 2, 3, 4, 2, 3, 4))], np.random.default_rng(0)))
print("   prediction form, columns 2/3/2/3/4/2/3/4:", text)
text, used = outcome(lambda: Learner(v0).acquire([view(P) for P in predict_set((3,) * 8)], np.random.default_rng(0)))
print("   prediction form, 3 columns everywhere:", text)


# ------------------------------------------- 3. is layout() all that the learner's vector depends on?
class Holds(Environment):
    """Made-up assignment problems that differ only in how many variables an option holds (1 or 2)."""
    name = category = "audit-holds-fixture"
    form = "assign"

    def instance_ids(self):
        return [f"i{k:02d}" for k in range(12)]

    def problem(self, instance_id, meter, seed, training):
        k = int(instance_id[1:])
        return Table(6, 6, 1, 1 + k % 2, k, meter), (lambda a: a)

    def score(self, instance_id, answer):
        return 0.5


print("3. problems that differ only in the largest capacity (1 or 2): same kernel layout, different learner descriptors?")
fx = Holds()
ps = [fx.problem(i, Meter(float("inf")), 0, True)[0] for i in fx.instance_ids()[:2]]
print("   kernel layout equal:", run.layout(ps[0]) == run.layout(ps[1]), "| learner descriptor lists:",
      [Layout(view(P), v0).names for P in ps])
environments._CACHE["audit-holds-fixture"] = fx
text, used = outcome(lambda: run.measure({"env": "audit-holds-fixture", "version": v0, "seed": 1, "budget": budget}))
print("   run.measure on such an environment:", text, "; learner calls:", used)
del environments._CACHE["audit-holds-fixture"]

# ----------------------------------------------------------- 4. registered numbers against the code
reg = json.load(open(os.path.join(REPO, "rsi6", "registry", "registration.json")))
print("4. registered numbers against the code")
print("   run.BUDGET == registration budgets.run:", run.BUDGET == reg["budgets"]["run"], run.BUDGET)
print("   rounds.RULES == registration rules:", rounds.RULES == reg["rules"], rounds.RULES)

# ------------------------------------- 5. the correction's third test, on its own made-up numbers
print("5. test_padded_columns_are_exact_and_learnable, repeated with its report printed (made-up numbers)")
from rsi6.environments.knapsack import KnapsackProblem                 # noqa: E402  (the class only; no benchmark data)

rng = np.random.default_rng(0)
meter = Meter(0.0)
problems = []
for m in (2, 5, 3, 2, 5, 3):
    use = rng.integers(1, 50, size=(m, 14)).astype(float)
    problems.append(KnapsackProblem(rng.integers(10, 99, size=14).astype(float), use, use.sum(axis=1) / 2, meter, 5))
meter.limit = 20.0 * sum(P.construction_units() for P in problems)
probe = Learner(v0)
cost = [probe._cost(P, int(v0["shortlist"])) for P in problems]
n_check = min(max(1, int(round(v0["assess.holdback"] * len(problems)))), len(problems) - 1)
batch = min(int(v0["model.batch"]), len(problems) - n_check)
print(f"   budget of the test: {meter.limit} units; the learner's cost of one construction per problem: {cost}; "
      f"held back {n_check}; reserve {3.0 * n_check * cost[0]}; one round of learning needs pop*batch*cost = "
      f"{int(v0['model.pop']) * batch * cost[0]} units; available {meter.limit - 3.0 * n_check * cost[0]}")
learner = Learner(v0)
capability, _, report = learner.acquire([view(p) for p in problems], np.random.default_rng(1))
print("   report of acquire:", {k: report[k] for k in ("iterations", "constructions", "learned", "failed", "fit", "held_back")})
print("   units used by acquire:", meter.used, "| capability learned:", capability["learned"],
      "| non-zero weights:", {k: w for k, w in capability["weights"].items() if w != 0.0})
meter.limit = float("inf")
answer = learner.apply(capability, view(problems[4]), np.random.default_rng(2))
print("   answer well formed:", problems[4].well_formed(answer))
# (No other budget is tried here on purpose: how the frozen learner fares on problems of this form is
#  for the registered experiment to find out, not for an audit.)

# ------------------------- 7. does the NUMBER of zero columns matter to the learner? (made-up, generic)
print("7. width as a free choice, on made-up generic fixtures (not the form of either environment's data)")


def made_up_laws(width, count=9):
    out, shared = [], Meter(float("inf"))
    for k in range(count):
        r = np.random.default_rng(500 + k)
        x = r.random((60, 3)) * (1 + k)
        y = x[:, 0] * x[:, 1] + np.sin(x[:, 2]) + 0.1 * k
        x = np.column_stack([x, np.zeros((60, width - 3))])
        out.append(PredictProblem(x[:40], y[:40], x[40:], ordered=False, target=y[40:], meter=shared))
    return out


answers, coefs = {}, {}
for width in (3, 4, 5, 8):
    laws = made_up_laws(width)
    L = Learner(v0)
    capability, _, report = L.acquire([view(P) for P in laws[:8]], np.random.default_rng(0))
    coefs[width] = np.asarray(capability["coef"]) if capability and capability.get("coef") is not None else None
    answers[width] = L.apply(capability, view(laws[8]), np.random.default_rng(1))
    print(f"   prediction form, 3 real columns shown in {width}: learned {report.get('learned')}, coefficients "
          f"{None if coefs[width] is None else len(coefs[width])}, coefficients of the zero columns "
          f"{None if coefs[width] is None else coefs[width][16 + 3:16 + width].tolist()}")
for width in (4, 5, 8):
    d = np.abs(answers[width] - answers[3])
    print(f"   predictions with width {width} against width 3: identical bit for bit {np.array_equal(answers[width], answers[3])}, "
          f"largest absolute difference {d.max():.3e} (targets are of order {np.abs(answers[3]).mean():.2f})")

weights = {}
for pad in (0, 1, 2):
    shared = Meter(0.0)
    tables = [Table(8, 5, 2, 2, 900 + s, shared, pad=pad) for s in range(8)]
    shared.limit = 40.0 * sum(P.construction_units() for P in tables)
    capability, _, report = Learner(v0).acquire([view(P) for P in tables], np.random.default_rng(0))
    weights[pad] = capability["weights"]
    print(f"   assignment form, 2 real attribute columns + {pad} zero columns: parameters {len(capability['weights'])}, "
          f"iterations {report['iterations']}, learned {report['learned']}")
common = sorted(weights[0])
for pad in (1, 2):
    same = all(weights[pad][k] == weights[0][k] for k in common)
    print(f"   learned weights of the common descriptors with {pad} zero column(s) against none: identical {same}; "
          f"largest difference {max(abs(weights[pad][k] - weights[0][k]) for k in common):.3f}")

# ----------------------------------------------------------------- 6. the three new tests as written
print("6. the three new tests, called one by one (not the suite)")
import rsi6.tests.test_kernel as T                                       # noqa: E402
for name in ("test_layout_is_the_same_for_every_instance", "test_kernel_refuses_instances_with_different_layouts",
             "test_padded_columns_are_exact_and_learnable"):
    text, used = outcome(getattr(T, name))
    print(f"   {name}: {'PASS' if text == 'no exception' else 'FAIL ' + text}; learner calls: {used}")
