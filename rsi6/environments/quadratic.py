"""Unconstrained binary quadratic programming: the quadratic 0-1 part ("Biq") of the Biq Mac
Library of A. Wiegele (Alpen-Adria-Universitaet Klagenfurt), sets beasley, gka and be.

Published form (the page biqmaclib.html and the library's description biqmaclib.tex of September
2007, both pinned as data files; the page is pinned as the record of the file format and is not
parsed): "Biq: min x'Qx s.t. x in {0,1}^n", "where Q is a symmetric matrix of order n", "indexed by
the numbers from 1 up to n". A file in the sparse format reads "n m" and then m lines "i j q_ij",
"where n is the number of variables and m the number of entries of Q specified in the subsequent
list". Every x in {0,1}^n is feasible; its value x'Qx = sum_i q_ii x_i + 2 sum_{i<j} q_ij x_i x_j
(x_i^2 = x_i) is to be made SMALL. The beasley and gka sets are also in the OR-Library, which
states them as maximisation problems ("Note that in the OR-library the problems are given for
maximization!"); this adapter follows the Biq Mac library: its files, its values and its direction.
Every value used is the library's optimal value of min x'Qx for the matrix of its own file; all
are negative.

Reading of the files. Every pinned instance file lists each entry at most once, with i <= j (the
upper triangle with the diagonal) and integer values; the parser refuses a file that does not have
that form, a number of entries other than m, or an index outside 1..n. An entry (i, j) with i < j
stands for q_ij and q_ji (Q is symmetric); an entry that is not listed is 0. Three things show that
this is the reading under which the published values hold, and not "every listed entry counted
once": the page's notation (its .mat form prints q_{1,2} in row 1 and in row 2, its .sparse form
lists "i j q_{i,j}"); the .mat files of the gka and be sets (the same matrices printed in full; not
pinned and not read here), which equal the symmetric completion of the .sparse files for all 120
gka and be instances used (checked outside the adapter); and a plain one-flip descent from 300
random starts, run outside the adapter on ten small instances (bqp50-1, bqp50-2, gka1a, gka6a,
gka1b, gka3b, gka1c, gka1d, be100.1, be120.3.1): under this reading it reached the published value
exactly on all ten and never went below it; under the other reading it went below the published
value on gka1b (-154 against -133) and gka3b (-134 against -118), which a published minimum
excludes. That checks the reading, not the values: nothing here proves a published value optimal.

Reference: the optimal values in the tables of biqmaclib.tex ("For each class of instances a table
lists the problem names and the optimal solution values. For instances where the optimum is not
known, we give some lower/upper bounds"), parsed by ``parse_tables`` from the quadratic section of
the file (from "\\section{Quadratic 0-1 Programming problems}" to "\\section{Max-Cut instances}"): a
row reads "name & value \\\\" (tables tab:beasley, tab:be1, tab:be2) or "name & n & density &
value \\\\" (tab:gka1, tab:gka2); a row whose value cell reads "$\\le$ v", followed by a lower bound,
gives an upper bound and no optimum, and its instance is not used. The number of variables the
table states (its column n, or the line "$n=..., d=...$" above the rows of a class) must be the n
of the file. The values are in the library's convention (minimisation of x'Qx for the library's
matrices). The source publishes values only, no solution vectors, and does not say for each value
how it was established (the instances were "collected while developing Biq Mac", an SDP based
branch and bound code).

Answer form: variable i is x_i (i in the file's order, before relabelling), option 0 is x_i = 0
and option 1 is x_i = 1. Every x in {0,1}^n is an answer of this form and every answer of this form
is an x in {0,1}^n: the published problem has no constraint, and there is no hard group. One group:
  [0] the sum of the terms of x'Qx whose variables are all assigned (soft, to be made small):
      q_ii x_i as soon as i is assigned, q_ij x_i x_j and q_ji x_j x_i (i != j) as soon as i and j
      are both assigned. For a complete answer it is x'Qx exactly; the change when one more
      variable is assigned is exact.
Exposed arrays, each a field of the instance file: var_attr[i, 0] = q_ii (the entry (i, i), 0 if
the file lists none); var_var[0][i, j] = q_ij for i != j (the entry (min(i, j), max(i, j)), 0 if
the file lists none; symmetric, zero diagonal), so that x'Qx = sum_i var_attr[i, 0] x_i +
sum_{i != j} var_var[0][i, j] x_i x_j. Nothing else is exposed: no option attribute, no capacity,
no domain, no start answer. Variables are relabelled with the seed (one permutation of the rows
and the columns of Q); their order in the file carries nothing. The options are not relabelled:
they are the two values of a variable, and exchanging them is not a relabelling of this problem
(x -> 1 - x changes Q and adds a constant to the value), as for the taken and left items of the
knapsack adapter.

One layout: every problem has the one soft group, one variable attribute, one relation between
variables and two options without capacity. The numbers of variables differ (20 to 250), which the
layout allows; nothing is padded.

Score: (zero - value) / (zero - optimum), cut to [0, 1]: 1 at the published optimum (an answer
cannot go below a right minimum; the cut is a guard), 0 at the zero point and above it, monotone
in x'Qx. An answer that is not an integer array of shape (n,) with entries 0 and 1 scores 0; it is
never repaired (decode keeps the dtype and leaves an answer of another shape as it is).

The zero point is the smaller of two values that need no work: 0, the value of the answer x = 0,
and the chance value, the expected value of x'Qx for x uniformly random in {0,1}^n. Both are EXACT
and in closed form: by linearity each x_i is 1 with probability 1/2 and each product x_i x_j
(i != j) with probability 1/4, so the chance value is sum_i q_ii / 2 + sum_{i<j} q_ij / 2, half the
sum of the entries listed in the file, (sum of Q + trace of Q) / 4. Every answer is valid, so it is
also the mean over the valid answers. Neither value is below the optimum on any instance. The
chance value is below 0 on 84 instances (the zero point is the chance value there, at most 0.132 of
|optimum| below 0) and at or above 0 on 66 (the zero point is 0 there). The chance value alone, the
zero point suggested for this category, is not used because of the gka set b: its diagonal entries
are in [-63, 0], its off-diagonal ones in [1, 100] and its density is 1, so its chance value is
4,196.5 (gka1b) to 191,686 (gka10b) while its optima are -118 to -160; on the chance value alone the
answer x = 0 would score 0.969 to 0.999 there, and 9 of the 24 fresh instances of the kernel's split
belong to that set. With the smaller of the two values x = 0 scores 0 on every instance and a
uniformly random answer is on average at the zero point or above it (its mean score after the
cut, measured on 20 answers per instance, is 0.029 over the 150 instances). On this scale a score
s is a value of s to s + 0.132 (1 - s) of the optimum.

Threshold 0.97: an operating point, not an external fact, fixed before any answer of a learner on
this category was scored (the builder's statement; this copy holds no ledger to check it) and left
unchanged after the audit: on average a value within about three hundredths of the published
optimum (a score of 0.97 is 0.970 to 0.974 of it), the operating point of the knapsack adapter (a
mean ratio of 0.97 to its reference). On this category reaching the threshold is NOT evidence of a
learned capability, and neither is a gain within the metered budget: computation on var_attr and
var_var is not metered, so more search on them raises the score without anything learned; a gain
counts only when the acquired and the untrained answers, or two arms compared, were produced with
equal CPU time (wording of the second audit, applied at the merge). Plain procedures that learn nothing reach it without a
single metered call: they read the exposed arrays var_attr and var_var, which no meter counts (the
meter counts the calls start, candidates, assign and evaluate), and an answer is scored whatever
produced it. Measured outside the adapter (seeded; no learner was run) with the steepest one-flip
descent from a uniformly random answer (flip the variable whose flip lowers x'Qx most, until none
does), 30 descents per instance, on the kernel's split(env, 16, 24) and halves() (one descent: the
mean over the 30 runs, in brackets the lowest and the highest run; best of k: the mean over the
disjoint blocks of k runs):

    scored instances                    one descent           best of 3   best of 10   best of 30
    deciding half (be250, gka-b; 15)    0.841 (0.768-0.904)   0.929       0.978        0.993
    confirming half (be200.3; 9)        0.977 (0.961-0.989)   0.989       0.995        0.998
    all 24 fresh                        0.892 (0.849-0.933)   0.951       0.984        0.995
    gka-b (9 fresh)                     0.750 (0.629-0.855)   0.890       0.968        0.990
    be250 (6 fresh)                     0.977 (0.961-0.986)   0.986       0.992        0.997

An independent audit (audit/adapters_fresh_20261116/audit2_quadratic.json) reproduced the
confirming-half figures but, over 19 runs with other seeds and tie rules, lower ones elsewhere: on
the deciding half one descent 0.807 to 0.828, the best of 10 0.944 to 0.972, the best of 30 0.982
to 0.991; on gka-b one descent 0.692 to 0.727; on all 24 one descent 0.873 to 0.883, the best of 3
0.928 to 0.938. The table is one seed's. On the confirming half one descent from a random answer
reaches the threshold on average, and the best of 30 descents reaches it on both halves; the best of 30 reached the published value on 9 of
the 24 fresh instances (8 of the 9 of gka-b, 1 of the 9 of be200.3, none of the 6 of be250). The
confirmation therefore does not fail for a learner that runs a plain local search with a few
restarts on the exposed arrays (the best of 3 scored 0.984 to 0.993 on the confirming half in each
of its 10 blocks of 3 runs, the best of 10 0.975 to 0.982 on the deciding half in each of its 3
blocks), and on no half does the threshold separate learning from search. A threshold per
published set above what a pinned plain procedure reaches on that set was considered and not
used: as computation on the exposed arrays is not metered, a threshold set above one plain
procedure is passed by the same procedure with more restarts (on every fresh set the best of 30
scores 0.990 or more, against 0.890 to 0.989 for the best of 3). That reaching the threshold is no
evidence here and that a gain counts only at equal CPU belongs in the registration of any test that uses this
category; this module can only state it. For orientation, averages over all 150 instances (5
descents per instance): a uniformly random answer 0.030, one greedy pass in a random order (each
variable to the option with the smaller change) 0.56, the best-first greedy (always the variable
whose setting to 1 lowers the total most, until none does) 0.93, one descent 0.96, the best of 3
descents 0.98; over the 24 fresh ones the random answer scores 0.014, the greedy pass 0.58 and the
best-first greedy 0.90. The instances are not hard for search at these sizes: the 300-start descent
of the reading check reached the published value on all ten small instances it was run on.

Groups: the 16 published sets of the library: bqp50, bqp100, bqp250 (beasley; 10 each; n = 50, 100,
250), gka-a (8; n = 30 to 100), gka-b (10; n = 20 to 125), gka-c (7; n = 40 to 100), gka-d (10;
n = 100), gka-e (5; n = 200), and be100, be120.3, be120.8, be150.3, be150.8, be200.3, be200.8, be250
(10 each; n and density in the name). Whole sets go to one side of the kernel's split: with
split(env, 16, 24) the fresh side is drawn from be200.3, be250 and gka-b (9, 6 and 9 of their 30
instances), the training side is 16 instances of nine other sets; halves() gives be250 and gka-b
(15) to the deciding half and be200.3 (9) to the confirming one.

Shared generator streams. Whole sets are not independent draws: files made with one seed of the
library's generator share its stream of values across sets. biqmaclib.tex gives the seeds (the
third number of each line of its generator parameters): 1 to 10 for every be class, 10 for all of
the gka sets a and b and for gka1c, 31 for gka3c, gka1d and gka5d, 34 for gka4c and gka3e, 47 for
gka4d and gka6d, 8 for gka5c (every other gka file used has a seed of its own), and none for the
beasley sets. Measured outside the adapter on the listed values in file order (a common stretch: a
run of 6 consecutive listed values found in both files; where the value ranges differ, a common
run of 48 consecutive up/down steps): every be file shares stretches with the seven files of the
other be classes that carry its number (all 280 such pairs, and no pair of files with different
numbers); the first listed values of be100.1, be200.3.1, be200.8.1 and be250.1 are the same (-100,
-24, 1, 42, -44, -6); for equal n the nonzero pattern of the sparser file lies almost within the
denser one (over the 30 pairs of be120, be150 and be200 files of one number 0.987 to 0.994 of its
off-diagonal nonzero positions, against 0.784 to 0.795, the density of the denser file, for an
unrelated pattern; be200.3.6 in be200.8.6: 0.988 of its off-diagonal nonzero positions, against
0.788). Pairs of gka files of one seed share stretches where their off-diagonal ranges agree (all
78 such pairs) and up/down runs in 88 of the 98 other pairs (the ten others are gka1b, the
smallest file, with the eight gka-a files and with gka1c, and gka1a with gka3b); gka1c shares
stretches with the eight be files numbered 10 and gka5c with the eight numbered 8; the files of
the gka sets a and b share up/down runs with the be files numbered 10 (all 64 pairs of set a; 72
of the 80 of set b, all but those of gka1b). bqp50-1 to bqp50-10 share stretches with bqp100-1 to
bqp100-4 (13 pairs; bqp250 shares none). Across the present split and halves:
  - training and fresh: 10 of the 24 fresh instances (be200.3.1, be200.3.2, be200.3.4, be200.3.5,
    be200.3.6, be200.3.9, be250.1, be250.2, be250.4, be250.5) share a stream with one or two of 7
    training instances (be100.1, be100.9, be120.3.5, be120.8.2, be150.8.2, be150.8.4, be200.8.6):
    12 pairs, 1,174 to 4,781 common stretches each, the k-th listed values equal for 0.414 to
    0.974 of k < 2,000;
  - the two halves: be250.1, be250.2, be250.4, be250.5, be250.7 and be250.10 (deciding), each with
    the be200.3 file of its number (be200.3.1, be200.3.2, be200.3.4, be200.3.5, be200.3.7 and
    be200.3.10; confirming): 1,726 to 1,871 common stretches, the k-th listed values equal for
    0.898 to 0.939; and gka2b, gka3b, gka4b, gka6b, gka7b, gka8b, gka9b and gka10b (deciding) with
    be200.3.10: 8 to 1,074 common up/down runs and no common stretch of values;
  - no other pair crosses them: no beasley file and no gka file of the seeds 8, 31, 34 and 47 is
    fresh, no be file numbered 10 is a training instance, and gka-a and gka1c are on neither side.
The matrices of these pairs differ entry-wise: of the off-diagonal positions where both files have
a nonzero, 0.0 to 1.6 percent hold equal values outside the first row (about 1.0 percent by chance
between two be files, 0.5 percent between gka-b and be), so these instances are siblings, not
copies. The one exception is the first row of be120.3.5 and be200.3.5 (both of density 0.3): its 33
positions that are nonzero in both hold equal values (6.7 percent of all their common positions).
group() stays the published set: the kernel's split takes whole published groups, and a grouping by
seed would put files of one published class on both sides. Whether a test on this category must
keep the files of one stream on one side (the rule the bin-packing adapter was held to) is for its
registration to decide; it would take another grouping or another instance set.

Size rule (the rule of the other adapters, fixed before anything was scored): at most 1,000
variables, and variables times options, 2n, at most 30,000. All 150 instances with a published
optimum satisfy it (the largest has 250 variables; a construction costs 751 units on it), so it
leaves nothing out.

Left out: bqp500-1 to bqp500-10 and gka1f to gka5f, for which the tables give an upper and a lower
bound and no optimum (not fetched); the files bqp1000-* and bqp2500-* of the beasley folder, which
the tables do not list (not fetched); the .mat files (the same matrices in full) and the other
files of the gka folder (.mc, .mat.mlb); the Max-Cut part of the library (another problem). 150
instances are used. A note for the audit: the description's generator parameters for the gka sets
b and c, read in the order it states ("n density seed OffDiagonalLower OffDiagonalUpper
DiagonalLower DiagonalUpper"), give ranges that differ from its own table of the sets, from the page
and from the files (set b: "0 63 -100 0", while the files have diagonal entries in [-63, 0] and
off-diagonal ones in [1, 100], as the table says); the adapter reads the files and uses neither
statement.
"""
from __future__ import annotations

import json
import re

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

MAX_VARS, MAX_CELLS = 1000, 30000
TEX = "biqmaclib.tex"
NAME = re.compile(r"bqp\d+-\d+|gka\d+[a-f]|be\d+(?:\.\d)?\.\d+")
SIZE = re.compile(r"\$n=(\d+), *d=[0-9.]+\$")


def folder(name: str) -> str:
    """The library's folder of an instance: beasley (bqp...), gka or be."""
    return "beasley" if name.startswith("bqp") else ("gka" if name.startswith("gka") else "be")


def parse_tables(text: str) -> dict:
    """``{name: {"n": n, "value": optimal value or None}}`` from the tables of the quadratic
    section of biqmaclib.tex. ``value`` is None where the table gives bounds only."""
    section = text.split(r"\section{Quadratic 0-1 Programming problems}")[1].split(r"\section{Max-Cut instances}")[0]
    out, n = {}, None
    for line in section.splitlines():
        size = SIZE.search(line)
        if size and "multicolumn" in line:               # "$n=50, d=0.1$" above the rows of a class
            n = int(size.group(1))
            continue
        cells = [c.strip() for c in line.strip().removesuffix("\\\\").split("&")]
        if not NAME.fullmatch(cells[0]):
            continue
        name = cells[0]
        if name in out:
            raise ValueError(f"{name} stands twice in the tables")
        if name.startswith("gka"):                        # name & n & density & value
            stated, rest = int(cells[1]), cells[3:]
        else:                                             # name & value
            stated, rest = n, cells[1:]
        if len(rest) == 1 and re.fullmatch(r"-?\d+", rest[0]):
            out[name] = {"n": stated, "value": float(rest[0])}
        elif len(rest) == 2 and rest[0].startswith(r"$\le$"):
            out[name] = {"n": stated, "value": None}      # an upper and a lower bound: no optimum
        else:
            raise ValueError(f"{name}: a table row not in the expected form")
    return out


def parse_sparse(text: str) -> np.ndarray:
    """The symmetric matrix Q of a file in the sparse format: "n m", then m lines "i j q_ij"
    with 1 <= i <= j <= n, each pair once, integer values; q_ji = q_ij, unlisted entries 0."""
    tokens = text.split()
    n, m = int(tokens[0]), int(tokens[1])
    if len(tokens) != 2 + 3 * m:
        raise ValueError("sparse file: the number of entries is not the stated one")
    entries = np.array([int(t) for t in tokens[2:]], dtype=np.int64).reshape(m, 3)
    i, j, q = entries[:, 0] - 1, entries[:, 1] - 1, entries[:, 2]
    if m and (i.min() < 0 or j.max() >= n or np.any(i > j)):
        raise ValueError("sparse file: an entry outside the upper triangle of an n x n matrix")
    if len(np.unique(i * n + j)) != m:
        raise ValueError("sparse file: an entry listed twice")
    Q = np.zeros((n, n))
    Q[i, j] = q
    Q[j, i] = q
    return Q


def chance_value(Q: np.ndarray) -> float:
    """The expected value of x'Qx for x uniformly random in {0,1}^n (exact): every x_i is 1 with
    probability 1/2 and every product x_i x_j (i != j) with probability 1/4."""
    return float(Q.sum() + np.trace(Q)) / 4.0


class QuadraticProblem(AssignProblem):
    """``diag[i] = q_ii``; ``var_var[0][i, j] = q_ij`` for i != j (symmetric, zero diagonal)."""

    def __init__(self, Q, meter):
        n = len(Q)
        self.diag = np.diag(Q).copy()
        super().__init__(n_vars=n, n_opts=2, hard=[False], ordered=False, capacity=None,
                         var_attr=self.diag[:, None], var_var=(Q - np.diag(self.diag),), meter=meter)

    def partial_totals(self, a):
        on = np.flatnonzero(a == 1)                      # the variables assigned 1
        return np.array([float(self.diag[on].sum() + self.var_var[0][np.ix_(on, on)].sum())])

    def _new(self):
        s = super()._new()
        s["field"] = np.zeros(self.n_vars)               # sum of q_vj over the variables j assigned 1
        return s

    def _rows(self, s, variables):
        v = np.asarray(variables, dtype=np.int64)
        gain = self.diag[v] + 2.0 * s["field"][v]        # the change when v becomes 1 (q_vj and q_jv)
        out = np.zeros((len(v), 2, 1))
        one = s["a"][v] == 1                              # a variable already at 1: the change if it went to 0
        out[:, 1, 0] = np.where(one, 0.0, gain)
        out[:, 0, 0] = np.where(one, -gain, 0.0)
        return out

    def _push(self, s, v, o):
        s["a"][v] = o
        if o == 1:
            s["tot"] = s["tot"] + (self.diag[v] + 2.0 * s["field"][v])
            s["field"] = s["field"] + self.var_var[0][:, v]


class Quadratic(Environment):
    name = category = "quadratic"
    form = "assign"
    threshold = 0.97
    anchor = ("an operating point, not an external fact, and on this category NOT evidence of a learned capability: "
              "on average a value within about three hundredths of the optimal value printed in the tables of the "
              "Biq Mac Library's description biqmaclib.tex (the operating point of the knapsack adapter), on the "
              "scale from the smaller of 0 (the value of x = 0) and the exact expected value of x'Qx under a uniformly "
              "random x, to that optimum; every answer is valid. Plain search that learns nothing reaches it without a "
              "metered call: the steepest one-flip descent from a random answer, run on the exposed arrays (measured "
              "outside the adapter), scores 0.977 on the confirming half (be200.3; 0.961 to 0.989 over 30 runs) and "
              "0.81 to 0.84 on the deciding half (be250 and gka-b; over seeds); the best of 3 descents about 0.989 "
              "and 0.93, of 10 0.994 to 0.995 and 0.944 to 0.978, of 30 0.997 to 0.999 and 0.982 to 0.993. Neither "
              "reaching the threshold nor a gain within the metered budget is evidence here: computation on var_attr "
              "and var_var is not metered, so more search on them raises the score without anything learned; a gain "
              "counts only when the answers compared were produced with equal CPU time")

    def __init__(self):
        fetch.fetch("quadratic", quiet=True)
        listed = {entry["path"] for entry in json.load(open(fetch.manifest_path("quadratic")))["files"]}
        table = parse_tables(open(fetch.path("quadratic", TEX), encoding="latin-1").read())
        self.instances = {}
        for name, row in table.items():
            if row["value"] is None:                      # bounds only: not used
                continue
            path = f"{folder(name)}/{name}.sparse"
            if path not in listed:
                raise ValueError(f"{name}: the table gives an optimum but the manifest has no file for it")
            Q = parse_sparse(open(fetch.path("quadratic", path), encoding="latin-1").read())
            if len(Q) != row["n"]:
                raise ValueError(f"{name}: the file has {len(Q)} variables, the table says {row['n']}")
            if len(Q) > MAX_VARS or 2 * len(Q) > MAX_CELLS:   # the size rule
                continue
            chance = chance_value(Q)
            self.instances[name] = {"Q": Q, "best": row["value"], "chance": chance, "zero": min(chance, 0.0)}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        """The published set: bqp50, bqp100, bqp250; gka-a to gka-e; be100, be120.3, ..., be250."""
        if instance_id.startswith("bqp"):
            return instance_id.split("-")[0]
        if instance_id.startswith("gka"):
            return "gka-" + instance_id[-1]
        return instance_id.rsplit(".", 1)[0]

    def problem(self, instance_id, meter, seed, training):
        Q = self.instances[instance_id]["Q"]
        n = len(Q)
        perm, _ = relabel(np.random.default_rng(seed), n)      # new variable -> old variable
        problem = QuadraticProblem(Q[np.ix_(perm, perm)], meter)

        def decode(answer):
            a = np.asarray(answer)
            if a.shape != (n,):                           # not an answer of this problem: left as it is
                return a.copy()
            out = np.empty_like(a)                        # the same dtype: nothing is cast or repaired
            out[perm] = a
            return out

        return problem, decode

    def score(self, instance_id, answer):
        """``answer[i]``: the value (0 or 1) of variable i, in the file's order."""
        inst = self.instances[instance_id]
        Q = inst["Q"]
        a = np.asarray(answer)
        if a.shape != (len(Q),) or a.dtype.kind not in "iu" or not np.all((a == 0) | (a == 1)):
            return 0.0
        x = a.astype(float)
        value, zero, best = float(x @ Q @ x), inst["zero"], inst["best"]
        if zero <= best:
            return 0.0
        return float(min(1.0, max(0.0, (zero - value) / (zero - best))))
