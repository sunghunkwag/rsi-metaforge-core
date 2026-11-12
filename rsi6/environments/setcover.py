"""Set covering problems of the OR-Library (J. E. Beasley): the test problem sets 4, 5, 6, A, B, E.

Published form (file format of the library's page scpinfo.html): m rows and n columns; a cost
c(j) for each column; for each row the list of the columns which cover it. An answer is a set
of columns such that every row is covered by at least one of them; its value is the sum of the
costs of its columns, to be made small.

Reference: the value recorded for each instance in the manifest (reference_values), read by
``score`` and ``reference`` only. Where the values come from, said plainly: the library's page
does not print them; it says that "the value of the optimal solution for each of these data
files is given in the paper" (J. E. Beasley, "An algorithm for set covering problems", European
Journal of Operational Research 31 (1987) 85-93). Neither that paper nor any other document
that states the values could be fetched. The 40 values were recorded from memory of the
literature (Beasley 1987, as tabulated e.g. by Beasley and Chu 1996); no table was consulted.
What is verified from the pinned files, by the adapter's checks and not by the adapter (the
checks are outside the package, and the covers they find are answers and are kept out of it):
  (a) every value is attained (40 of 40): for each instance a set of columns that covers every
      row and costs exactly the recorded value is exhibited and evaluated, so no value is a mere
      bound;
  (b) no cover is cheaper (40 of 40): for 12 instances a Lagrangian lower bound, rounded up,
      equals the value; for the other 28 a branch-and-bound search over all covers of cost at
      most value - 1 (depth first, Lagrangian bounds, reduced-cost fixing) ends without one.
The first audit of this adapter reported, by its own code, a cover at the value for 40 of 40 and
a proof by its own exhaustive search for 31. The second audit proved for all 40, with a branch
and bound of its own written without reading the builder's, that no cheaper cover exists. Every
value is therefore established from the pinned files by independent computations; that the
values were first written down from memory no longer carries weight. Should a reference
be beaten after all, the score is cut at 1. The instance files state no optimum and no bound,
and the source publishes no optimal covers.

Answer form: one variable per column; it takes option 0 (left out) or 1 (taken). Every set of
columns, covering or not, redundant or not, is exactly one answer, and every answer is one set
of columns. (The other natural form, a variable per row choosing the column that covers it,
is not used: a cover with more columns than rows, or with columns no row needs, cannot be
written in it, and it has 200 x 1,000 options and more.) Options are not limited in use.

Groups: [0] the sum of the costs of the taken columns (soft; the term of a column reads that
column only). [1] the number of rows that are not covered (hard; the term of a row reads the
columns which cover it: it is 1 when all of them are assigned and none is taken, 0 otherwise).
For a complete answer [0] is the published value and [1] is zero exactly when the answer is a
cover.

Exposed arrays, each for the columns in their relabelled order:
  var_attr[:, 0]  the cost c(j) of the column (the cost line of the file);
  var_attr[:, 1]  the number of rows the column covers (counted from the rows' lists);
  var_var[0][j, k]  the number of rows covered by both column j and column k (counted from
                  the rows' lists; the diagonal repeats var_attr[:, 1]).
The rows are not entities of the answer form and no array is indexed by them, so their order
and number appear nowhere; the columns are relabelled with the seed. The options 0 and 1 are
the two meanings "left out" and "taken" and are not relabelled (as for the knapsack problems).
All instances have the same layout without any padding.

Score: the plain ratio, optimal value / value of the answer, cut at 1; 0 for an answer that is
not a 0/1 integer vector over the columns or leaves a row uncovered. The plain ratio is kept
because a uniformly random valid answer scores far below 0.5 on it: nearly every subset of the
columns is a cover here (at least 96 per cent of the uniformly drawn subsets of every instance),
so a random cover holds about half the columns; its score, measured by the adapter's checks, is
0.001 to 0.02 on average per group and never above 0.03.

Threshold: 0.95, an operating point and not an external fact. On the groups with costs (4, 5,
6, A, B) it means covers that cost on average about 5 per cent more than the reference. It does
not mean that on group E: there every cost is 1 and the optimum is 5 columns, so a cover of k
columns scores 5/k, that is 1, 0.833, 0.714, ... and nothing in between. Group E is 5 of the 20
instances of the kernel's fresh side and half of its confirming half {6, E}; a mean of 0.95 on
that half needs at least three of the five E instances solved exactly unless group 6 is nearly
perfect. That the threshold was fixed before any algorithm was measured is the builder's
statement: the files do not record the order of the two decisions, and the number equals the
fresh-side mean of the second baseline below. It has not been moved since the baselines were
seen. For orientation only, the adapter's checks ran plain published algorithms on the files
(never the learner): the textbook greedy rule (Chvatal: repeatedly the column with the least
cost per newly covered row) has a mean score of 0.90 over the 40 instances, the same rule
followed by the removal of columns that are not needed 0.96 (0.95 on the instances of the
kernel's fresh side: 0.954 on the half {5} and 0.947 on the half {6, E}), and a Lagrangian
heuristic in the manner of Beasley (1990) 0.99.

Cost: an instance with n columns has n variables and 2 options; one construction costs 3n+1
units. var_var[0] is an n-by-n table: 8 MB for 1,000 columns, 32 MB for 2,000, 72 MB for 3,000.

Instances. Used: the 40 instances of the sets 4 (10 files, 200 rows x 1,000 columns), 5 (10,
200 x 2,000), 6 (5, 200 x 1,000), A (5, 300 x 3,000), B (5, 300 x 3,000) and E (5, 50 x 500,
all costs 1). The group of an instance is its published problem set.
Left out by the size rule, fixed before anything was scored: instances with more than 3,000
columns. 3,000 is the smallest limit that leaves 40 instances; instances of 2,000 and 3,000
columns are already two and three times the package's preferred number of variables, although
their construction costs (6,001 and 9,001 units) are far below the preferred 30,000. By this
rule: scpc1..5 and scpd1..5 (400 x 4,000; optimal values are given in the same paper),
scpnre1..5 and scpnrf1..5 (500 x 5,000), scpnrg1..5 and scpnrh1..5 (1,000 x 10,000),
scpcyc10 (5,120 columns), scpcyc11 (11,264), rail507, rail516, rail582, rail2536, rail2586,
rail4284 and rail4872 (47,311 columns and more).
Left out although within the size rule, and NOT by a size rule (a deviation from "by a size
rule only", said plainly, for the orchestrator to accept or to refuse): the unicost files of
Grossman and Wool scpclr10..13 (210 to 715 columns) and scpcyc06..09 (192 to 2,304 columns).
The reason is the precondition of a reference. The page prints no value for any file; but for
the sets 4 to 6 and A to E it names a source of optimal values (the paper above), and for these
eight files it names none: no optimal values, no best known values and no table of them. (The
same holds for scpnre..scpnrh, for which the page speaks of heuristic values only.) The
exclusion was made without any score: these files are never loaded. If they are wanted, their
values would have to be stated as best known and not proven.
"""
from __future__ import annotations

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

MAX_COLUMNS = 3000
SETS = {"4": 10, "5": 10, "6": 5, "a": 5, "b": 5, "e": 5}        # published problem set: number of files


def parse(text: str):
    """``(cost, cover)``: the costs of the n columns and the m-by-n table of which column covers which row."""
    tokens = text.split()
    m, n = int(tokens[0]), int(tokens[1])
    cost = np.array([float(x) for x in tokens[2:2 + n]])
    cover = np.zeros((m, n), dtype=bool)
    pos = 2 + n
    for i in range(m):
        k = int(tokens[pos])
        columns = np.array([int(x) for x in tokens[pos + 1:pos + 1 + k]]) - 1      # the file counts columns from 1
        if k < 1 or columns.min() < 0 or columns.max() >= n or len(set(columns.tolist())) != k:
            raise ValueError("malformed row")
        cover[i, columns] = True
        pos += 1 + k
    if pos != len(tokens) or len(cost) != n:
        raise ValueError("malformed file")
    return cost, cover


class SetCoverProblem(AssignProblem):
    def __init__(self, cost, cover, meter):
        self.cost = np.asarray(cost, dtype=float)
        self.cover = np.asarray(cover, dtype=float)             # rows x columns, 1 where the column covers the row
        m, n = self.cover.shape
        columns, rows = np.nonzero(self.cover.T)
        self.rows_of = np.split(rows, np.cumsum(np.bincount(columns, minlength=n))[:-1])
        shared = self.cover.T @ self.cover
        super().__init__(n_vars=n, n_opts=2, hard=[False, True], ordered=False, capacity=None,
                         var_attr=np.column_stack([self.cost, np.diag(shared)]), var_var=(shared,), meter=meter)

    def partial_totals(self, a):
        a = np.asarray(a)
        taken, open_ = a == 1, a < 0
        covered = self.cover[:, taken].sum(axis=1) > 0
        undecided = self.cover[:, open_].sum(axis=1) > 0
        return np.array([float(self.cost[taken].sum()), float(np.count_nonzero(~covered & ~undecided))])

    def _new(self):
        s = super()._new()
        s["cov"] = np.zeros(self.cover.shape[0], dtype=np.int64)            # taken columns that cover the row
        s["rem"] = self.cover.sum(axis=1).astype(np.int64)                  # unassigned columns that cover the row
        return s

    def _rows(self, s, variables):
        out = np.zeros((len(variables), 2, 2))
        out[:, 1, 0] = self.cost[variables]
        last = np.flatnonzero((s["cov"] == 0) & (s["rem"] == 1))            # rows with one way left to be covered
        if len(last) and len(variables):
            out[:, 0, 1] = self.cover[np.ix_(last, variables)].sum(axis=0)
        out[s["a"][variables] >= 0] = 0.0                                   # a column that is already decided changes nothing
        return out

    def _push(self, s, v, o):
        s["a"][v] = o
        rows = self.rows_of[v]
        s["rem"][rows] -= 1
        if o == 1:
            s["cov"][rows] += 1
            s["tot"] = s["tot"] + np.array([self.cost[v], 0.0])
        else:
            lost = np.count_nonzero((s["cov"][rows] == 0) & (s["rem"][rows] == 0))
            s["tot"] = s["tot"] + np.array([0.0, float(lost)])


class SetCover(Environment):
    name = category = "setcover"
    form = "assign"
    threshold = 0.95
    anchor = ("an operating point, not an external fact: a mean of 0.95 of the ratio reference value / cost of the cover "
              "(an answer that leaves a row uncovered counts 0), where the reference values were recorded from memory of "
              "the literature (Beasley 1987; no document stating them could be fetched) and are verified from the pinned "
              "files to be attained by a cover and to be optimal (40 of 40, by the builder's branch and bound and by "
              "the second audit's own), where on the unit-cost group E the "
              "score takes only the values 5/k, and where the fixing of the threshold before any baseline was measured is "
              "the builder's statement")

    def __init__(self):
        manifest = fetch.fetch("setcover", quiet=True)
        self.instances = {}
        for label, count in SETS.items():
            for k in range(1, count + 1):
                name = f"scp{label}{k}"
                cost, cover = parse(open(fetch.path("setcover", f"{name}.txt")).read())
                if len(cost) > MAX_COLUMNS:
                    continue
                self.instances[name] = {"cost": cost, "cover": cover, "set": label.upper(),
                                        "best": float(manifest["reference_values"][name])}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return self.instances[instance_id]["set"]                # the published problem set: 4, 5, 6, A, B, E

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        perm, _ = relabel(rng, len(inst["cost"]))
        problem = SetCoverProblem(inst["cost"][perm], inst["cover"][:, perm], meter)

        def decode(answer):
            out = np.empty(len(perm), dtype=np.int64)
            out[perm] = np.asarray(answer, dtype=np.int64)
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        a = np.asarray(answer)
        if a.shape != inst["cost"].shape or a.dtype.kind not in "iu" or not np.all((a == 0) | (a == 1)):
            return 0.0
        taken = a == 1
        if not np.all(inst["cover"][:, taken].any(axis=1)):
            return 0.0
        return float(min(1.0, inst["best"] / inst["cost"][taken].sum()))
