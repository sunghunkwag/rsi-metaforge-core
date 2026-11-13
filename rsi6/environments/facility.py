"""Uncapacitated warehouse location problems of the OR-Library (J. E. Beasley): the 15 files of the
library's page uncapinfo.html, cap71 to cap74, cap101 to cap104, cap131 to cap134 (problem sets
VII, X, XIII) and capa, capb, capc (problem sets A, B, C).

Published form (file format of uncapinfo.html): m potential warehouse locations and n customers;
for each warehouse a capacity and a fixed cost; for each customer a demand and, for each
warehouse i, "the cost of allocating all of the demand of j to warehouse i". An answer opens
some warehouses and supplies every customer from an open one; its value is the sum of the fixed
costs of the open warehouses and of the allocation costs, to be made small. The page says of
the capacity and demand figures that they "should (obviously) be ignored when solving these
problems as uncapacitated warehouse location problems": they are parsed and not used. (In capa,
capb and capc the capacity field is the word "capacity" and not a number; it is read as absent.)

Which problem is presented, and why. The same files also serve the library's capacitated problem
(page capinfo.html, values in capopt: the 37 files cap41 to cap134 and capa, capb, capc). That
problem is NOT presented, because it cannot be written exactly in the assignment form. Its
published answers divide the demand of a customer between warehouses, and the data show it: in
13 of its files (cap41 to cap44, cap51, cap81 to cap84, cap111 to cap114) one or two customers
have a demand above the capacity of every warehouse (12,912 against 5,000 in cap41), so no
answer that gives every customer one warehouse exists there, while capopt prints an optimal
value for each of them. (This is also the formulation of the paper the page cites, Beasley 1988;
said from knowledge of the literature, the paper was not fetched.) A value in capopt is therefore
only a lower bound for answers that give every customer one warehouse, and such answers are not
all of the published ones. Written exactly, the divided problem would need one variable per unit
of demand (58,268 variables for a 50-customer file), far beyond the size rule below. The
uncapacitated optimum is attained by an answer that gives every customer one warehouse, which is
the answer form here.

Reference: the optimal values of the uncapacitated problem in the library's file uncapopt, read
by ``score`` and ``reference`` only. They are values an answer of this form attains, not bounds:
the builder's checks (outside the package) exhibit for each of the 15 instances an answer with
the published value, and show for sets VII and X, by complete enumeration of the sets of open
warehouses, that none is cheaper (for sets XIII, A, B and C optimality rests on the source). The
file prints three decimals, and four of its values (cap101, cap103, cap131, cap133) are printed
0.0005 below the value an answer attains (796648.437 for 796648.4375, where capopt prints
796648.438 for the same optimum; the warning that "different machines may give slightly
different results ... due to rounding errors" stands in capopt, not in uncapopt), and one (capb)
0.0006 above it (12979071.582 for 12979071.5814): a value within 0.001 of the reference, one
unit of the last printed decimal, counts as reaching it. The source publishes no optimal
answers. The instance files state no optimum and no bound.

Answer form: variable j (a customer) takes option i (a warehouse): customer j is supplied from
warehouse i. An option may be taken by any number of variables; there is no order. A warehouse is
open exactly when at least one customer takes it. The published form also allows a warehouse to
be opened and left idle; such an answer is written here as the same supplies without the idle
warehouse. Fixed costs are not negative (checked when the files are read), so the value this
form gives is the published value of the answer with no idle warehouse, never above the value
of the answer with one, and the optimum is the same.

Term groups: one, soft. [0] the published objective on the customers assigned so far: the sum
of their allocation costs plus the fixed costs of the warehouses at least one of them takes.
For a complete answer it is exactly the published value. There is no hard group: every complete
assignment is a valid answer.

Exposed arrays (all relabelled; nothing else of the file is exposed):
  var_opt[0][j, i]  the cost of allocating all of the demand of customer j to warehouse i (the
                    m numbers after the demand in customer j's record);
  opt_attr[i, 0]    the fixed cost of warehouse i (the second number of warehouse i's line).
Not exposed: the capacities and the demands (to be ignored, as the page says), names, the
reference.

Score: the plain ratio reference / value of the answer, cut at 1; 1 when the value is within
0.001 of the reference or below it; 0 for an answer that is not n integers in 0..m-1. The plain
ratio is used because a uniformly random valid answer scores well below 0.5 on it (its expected
value gives ratios of 0.28 to 0.41 on the 12 instances with 50 customers and of 0.08 to 0.14 on
capa, capb, capc; the mean ratio over 2000 random answers is at most 0.42), so the rule that
calls for the scale "share of the way from a random answer" does not apply.

Threshold 0.95: an operating point, not an external fact. It is the mean ratio 0.95 (a value
about 5 per cent above the published optimum on average), the same operating point as the
package uses for the library's p-median problems; no published result fixes it.

Groups: the published size class, named by the number of customers: "50" (sets VII, X, XIII:
12 files with 16, 25 and 50 warehouses) and "1000" (sets A, B, C: 3 files with 100 warehouses).
The published problem set is NOT the group, because the sets with 50 customers are one body of
data: the four files of a set have one cost matrix and differ in the fixed cost only (7500,
12500, 17500, 25000; one warehouse has none), all three sets have the same 50 customers and the
same four levels of fixed cost, the 16 warehouses of set VII are the first 16 of the 25 of set X
with the same costs, and all 25 cost columns of set X occur among the 50 of set XIII. A split by
problem set would test on the training data with other warehouse columns. capa, capb and capc
share no data with them or with each other (three cost matrices without a common column,
three sets of demands and of fixed costs); they are kept in one group because they are one size
class of one source (the same dimensions and the same range of costs, at three levels of fixed
cost), as the kernel keeps instances of one generator together. The rule and the names were
fixed before the order of the kernel's split was computed. The grouping by common cost columns
alone (12, 1, 1, 1) was not adopted, because it would let capa, capb and capc fall on both
sides of the split; the order the kernel gives it was computed afterwards, for the record only
(the builder's checks print it). With these groups the kernel's split trains on the 12
instances of class "50" and tests on capa, capb, capc: fresh instances that share no data with
the training ones and are 20 times larger in customers. It is 12 training and 3 fresh instances against the 16
and 24 the kernel asks for, in 2 groups and not 3: the benchmark has no more (see below), and
a mean over 3 fresh instances is a coarse measure. The 12 training instances are not 12
independent ones either (3 cost matrices at 4 levels of fixed cost).

Instances left out: none. The size rule, restated after the first audit and before anything was
scored (no learner had met an instance of this category): an instance is used if it has at most
1,000 customers (variables) and at most 100,000 customer-warehouse pairs (n_vars * n_opts); all
15 files of the page pass it. The first version of the rule (at most 30,000 pairs) left out
capa, capb and capc (100,000 pairs each) and with them every instance that does not share its
data with the others, so that no fresh instance was independent of the training ones; that is
why the rule was changed. The price is compute on the fresh side only: one construction costs
101,001 units on capa, capb or capc against 851 to 2,551 on the others, and a fresh instance is
answered within the kernel's test budget (1,202,002 units for each answer), not with the 40
constructions per instance of training (752,480 units for the 12 training instances together).
The 25 files that are on the capacitated page only (cap41 to cap64, cap81 to cap94, cap111 to
cap124) add nothing: with the capacities ignored each of them is, number for number, one of the
12 with 50 customers (cap41 is cap71, cap51 is cap73, and so on), and uncapopt gives no value
under their names; they are not used and not fetched.
"""
from __future__ import annotations

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

FILES = ("cap71", "cap72", "cap73", "cap74", "cap101", "cap102", "cap103", "cap104",
         "cap131", "cap132", "cap133", "cap134", "capa", "capb", "capc")       # the order of the library's page
MAX_VARS, MAX_PAIRS = 1000, 100000         # the size rule
PRINTED = 1.0e-3                           # one unit of the last decimal the reference file prints


def parse(text: str):
    """``(fixed, cost, capacity, demand)``: fixed (m,), cost (n, m) with cost[j, i] the cost of
    allocating all of the demand of customer j to warehouse i. A capacity given as the word
    "capacity" (capa, capb, capc) is read as absent (nan)."""
    tokens = text.split()
    m, n = int(tokens[0]), int(tokens[1])
    if len(tokens) != 2 + 2 * m + n * (m + 1):
        raise ValueError("not the published layout")
    warehouses = np.array([np.nan if x == "capacity" else float(x) for x in tokens[2:2 + 2 * m]]).reshape(m, 2)
    customers = np.array([float(x) for x in tokens[2 + 2 * m:]]).reshape(n, m + 1)
    return warehouses[:, 1].copy(), customers[:, 1:].copy(), warehouses[:, 0].copy(), customers[:, 0].copy()


def value_of(fixed: np.ndarray, cost: np.ndarray, a: np.ndarray) -> float:
    """The published objective of a complete answer: allocation costs plus the fixed costs of
    the warehouses in use."""
    return float(cost[np.arange(len(a)), a].sum() + fixed[np.unique(a)].sum())


class FacilityProblem(AssignProblem):
    def __init__(self, cost: np.ndarray, fixed: np.ndarray, meter):
        n, m = cost.shape
        self.cost, self.fixed = cost, fixed
        super().__init__(n_vars=n, n_opts=m, hard=[False], ordered=False, capacity=None, opt_attr=fixed[:, None],
                         var_opt=(cost,), meter=meter)

    def partial_totals(self, a):
        placed = np.flatnonzero(a >= 0)
        return np.array([float(self.cost[placed, a[placed]].sum() + self.fixed[np.unique(a[placed])].sum())])

    def _new(self):
        s = super()._new()
        s["count"] = np.zeros(self.n_opts, dtype=np.int64)       # customers on each warehouse
        return s

    def _rows(self, s, variables):
        variables = np.asarray(variables, dtype=np.int64)
        opening = np.where(s["count"] == 0, self.fixed, 0.0)     # the fixed cost is paid by the first customer only
        return (self.cost[variables] + opening[None, :])[:, :, None]

    def _push(self, s, v, o):
        s["tot"] = s["tot"] + (self.cost[v, o] + (self.fixed[o] if s["count"][o] == 0 else 0.0))
        s["count"][o] += 1
        s["a"][v] = o


class Facility(Environment):
    name = category = "facility"
    form = "assign"
    threshold = 0.95
    anchor = ("an operating point, not an external fact: a mean ratio of the published optimal value of the "
              "uncapacitated problem (attainable, not a bound) to the cost of the answer of 0.95; the fresh side "
              "has three instances, so this is a mean over three")

    def __init__(self):
        fetch.fetch("facility", quiet=True)
        best = {}
        for line in open(fetch.path("facility", "uncapopt.txt")).read().splitlines()[1:]:
            parts = line.split()
            if len(parts) == 2:
                best[parts[0]] = float(parts[1])
        self.instances = {}
        for name in FILES:
            fixed, cost, _, _ = parse(open(fetch.path("facility", f"{name}.txt")).read())
            n, m = cost.shape
            if n > MAX_VARS or n * m > MAX_PAIRS:
                continue
            if not (fixed.min() >= 0 and cost.min() >= 0 and best[name] > 0):
                raise ValueError(f"{name}: the adapter's statements hold for non-negative costs only")
            self.instances[name] = {"fixed": fixed, "cost": cost, "best": best[name]}

    def instance_ids(self):
        return [name for name in FILES if name in self.instances]

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return str(len(self.instances[instance_id]["cost"]))     # the size class: 50 or 1000 customers

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        n, m = inst["cost"].shape
        var_perm, _ = relabel(rng, n)                    # new customer -> old customer
        opt_perm, _ = relabel(rng, m)                    # new warehouse -> old warehouse
        problem = FacilityProblem(inst["cost"][np.ix_(var_perm, opt_perm)], inst["fixed"][opt_perm], meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[var_perm] = opt_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        n, m = inst["cost"].shape
        a = np.asarray(answer)
        if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= m:
            return 0.0
        value = value_of(inst["fixed"], inst["cost"], a.astype(np.int64))
        if value <= inst["best"] + PRINTED * (1.0 + 1.0e-6):
            return 1.0
        return float(min(1.0, inst["best"] / value))
