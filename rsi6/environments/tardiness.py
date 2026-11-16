"""Single-machine total weighted tardiness of the OR-Library (J. E. Beasley): files wt40, wt50, wt100.

Published form (the page wtinfo.html, pinned and parsed as a data file). Each of n jobs "is to be
processed without interruption on a single machine that can handle no more than one job at a
time"; job j "becomes available for processing at time zero, requires an uninterrupted positive
processing time p(j) on the machine, has a positive weight w(j), and has a due date d(j)". "For a
given processing order of the jobs, the earliest completion time C(j) and the tardiness
T(j)=max{C(j)-d(j),0} of job j ... can readily be computed. The problem is to find a processing
order of the jobs with minimum total weighted tardiness SUM{j=1,...,n}w(j)T(j)". The files wt40,
wt50 and wt100 hold the instances of n = 40, 50 and 100, 125 each (the number is parsed from the
page), "listed one after the other": the n processing times, then the n weights, then the n due
dates of an instance, as integers separated by white space. ``parse`` reads them so and refuses a
file that does not hold exactly 125 * 3n non-negative integers or holds a processing time or a
weight below 1. As pinned: p(j) in 1..100 and w(j) in 1..10 (the page's generator), d(j) in
0..7122; no due date is negative.

Reference: one integer per instance in the order of the data file (``parse_values``; a file with
another count is refused): wtopt40 for n = 40, wtopt50 for n = 50, wtbest100b for n = 100. The
page: "Optimal values of solutions are available for 124 and 115 of the 40 and 50 job problem
instances"; the unsolved ones (instance 19 of n = 40; 11, 12, 14, 19, 36, 44, 66, 87, 88 and 111
of n = 50, parsed from the page by ``parse_page`` and checked against those two counts) carry in
wtopt40 and wtopt50 "the best known to Crauwels, Potts & Van Wassenhove (1996)". For n = 100 the
page names wtbest100a, the values known to Crauwels, Potts & Van Wassenhove (1998), and
wtbest100b, "The best known solutions to date" (dynasearch found better ones for some); the
reference is wtbest100b, and wtbest100a is read only to check that no value of wtbest100b is above
it (as pinned, eight are below, instances 111 to 114, 116 and 118 to 120; the others are equal).
So 239 references are optimal and 136 are best known (``proven``). The source publishes values
only, no processing order; whether they are reached is not checked here. 53 instances have the
reference 0 (18, 17 and 18 of the three files). A check outside the adapter, written from the
page's text alone, found on all 375 instances that the reference is 0 exactly when the order by
non-decreasing due date (which has no tardy job whenever some order has none) has no tardiness,
as a consistent reading of the files and of the objective requires.

Answer form: the n positions of the processing order are the variables, assigned in index order
(``ordered``); the n jobs are the options, each with capacity one, so a complete answer is a
permutation: answer[k] is the job processed k-th (0-based). The job at position k finishes at the
sum of the processing times of the jobs at positions 0 to k: its earliest completion time for this
order (it cannot start before the job before it has finished, and nothing else delays it: every
job is available at time zero). Every processing order of the published problem is exactly one
answer of this form, and every answer of this form is a processing order. Idle time is not part
of an answer of the published problem: the page computes C(j) as the earliest completion time of
the given order, so an answer is the order alone. Were idle time admitted, leaving it out would
lose nothing: removing it moves no job later, and T(j) does not grow when C(j) falls, so the same
order without idle time is never worse, and the optimum over orders is the optimum over schedules.

Term group (one): [0] the total weighted tardiness of the jobs at the positions given so far
(soft). The term of position k is w(j) T(j) of the job j there; it reads positions 0 to k (their
processing times make C(j)) and counts as soon as all of them are assigned. For a complete answer
[0] is the published objective. No hard group: every answer of the form is a valid order. No
detail group: the objective is a sum, not a largest term.

Exposed arrays: ``opt_attr``, one row per job, the three numbers the file gives the job: [0] p(j),
[1] w(j), [2] d(j). Nothing else: the positions have no attributes (they are the order), no
relation between jobs is exposed, and nothing of the generation class (below) is. The jobs are
relabelled with the seed; the positions are not relabelled. In wt100 the jobs of every instance are
listed in non-increasing w(j)/p(j), the w/p order, which scores 0.81 on average; in wt40 and wt50
the position shows no relation to p, w or d (its rank correlation with each of p, w, d and w/p
averages between -0.024 and +0.004 over the 125 instances of a file). The relabelling removes the
file order, and the w/p order is a function of the exposed attributes in any case. ``decode`` maps
an answer to the file's job labels; anything but n integers in 0..n-1 decodes to n times -1, which
scores 0 (a negative label is not wrapped around to a job, a float is not truncated). One layout:
every instance has one soft group, three job attributes, no relation and capacity one; n differs
(40, 50, 100), which the layout allows; nothing is padded.

Score: (Z - V) / (Z - R) for a valid answer of value V, cut to [0, 1]; 0 for anything that is not
a processing order (wrong type, shape or range, a job twice); nothing is repaired. R is the
reference; a plain ratio V/R is not used, R being 0 on 53 instances. Z, the zero point, is the
expected total weighted tardiness of a processing order drawn uniformly from all n! orders. It is
EXACT: the finite formula of ``random_order_value``, computed in floating point; no sampler is
involved. Checked outside the adapter against exact rational arithmetic by direct counting (a
different algorithm: integers only, no recursion over k, no complement) on five whole instances
of n = 40 and 50, one whole instance and six single jobs of n = 100, and against all n! orders of
20 small made-up instances: the largest relative difference was 3.2e-16. So 0 is the value of a
random order on average (random orders score 0.05 to 0.08 on average after the cut at 0) and 1 is
the published value. On these instances Z - R lies between 0.36 Z and Z (its smallest value is
7,128): no scale is degenerate. Where R is only best known (136 instances), an answer can be
better than R; it scores 1.

Threshold 0.98: an operating point, not an external fact: on average 98 hundredths of the way from
the expected value of a random order to the published value. At a score of 0.98 the value may
exceed R by a fiftieth of Z - R, which on the 322 instances with R > 0 is a median of 4.7% of R
(quartiles 2.6% and 14%), and on the 15 fresh instances with R > 0 a median of 14% (1.8% to 330%:
where R is small, Z - R is many times R). Answers 10% above R, the operating point of the tour
and routing adapters, would score 0.978 on the fresh instances. The builder's first draft had 0.90
(fixed, it states, before any answer was scored); an audit found that the better of two sorting
rules meets 0.90 on the fresh instances, and the fixer raised the threshold to 0.98 knowing the
scores of the rules below and no learner result.

Rules with no learning, measured outside the adapter (this module contains none of them), as means
over the 24 fresh instances of split(env, 16, 24) / its deciding half (14) / its confirming half
(10) / all 375: the order by non-decreasing due date 0.733 / 0.967 / 0.405 / 0.510; by
non-increasing w(j)/p(j) 0.691 / 0.635 / 0.770 / 0.801; the better of the two on each instance
0.908 / 0.967 / 0.826 / 0.887 (it reaches 0.90 on 54% of all instances); an adjacent-swap descent
from the better one (a search) 0.969 / 0.994 / 0.933 / 0.946. Two one-pass dispatching rules of the
textbooks for this objective, which read p, w and d together and search nothing, reach the
threshold: ATC (apparent tardiness cost: next the job of largest (w/p) exp(-max(d - p - t, 0) /
(2 P/n)), t the time so far) 0.992 / 0.995 / 0.987 / 0.984, and WMDD (weighted modified due
date: next the job of smallest max(p, d - t) / w) 0.993 / 0.995 / 0.989 / 0.990; random tie-breaks
move none of these means in the third decimal. So 0.98 asks for more than either sorting rule
everywhere and, on the fresh instances as a whole and on the confirming half, for more than the
descent from the better one; it asks for about what a textbook dispatching rule for this problem
reaches, not more: a capability held here is that level. A threshold above every one of these
rules on every part would have to be 0.996 or more (ATC with 1 or 3 in place of 2 averages 0.9958
on the deciding half) and would ask for nearly the published value on every instance; whether
"held" should mean that is for the owner of the experiment to decide.

What the fresh instances can show. Of the 24, 9 have R = 0, all in the deciding half (the five of
wt100-tf0.2-rdd0.6 and four of wt50-tf0.2-rdd1.0), and the due-date order attains it there: the
deciding half is nearly saturated and its signal is carried by its five instances of
wt50-tf0.4-rdd0.8; the headroom is in the confirming half (the five of wt100-tf0.8-rdd0.2 and the
five of wt50-tf0.6-rdd1.0, R > 0 on all ten). The adapter did not choose this and does not select
instances by difficulty.

Groups (for the split): the generation classes, one per size and pair of TF and RDD, 75 groups of
five instances, named like "wt40-tf0.2-rdd0.2". The page: "Five instances were generated for each
of the 25 pairs of values of RDD and TF", each taking the values 0.2, 0.4, 0.6, 0.8 and 1.0
(parsed from the page), d(j) drawn "from the uniform distribution [P(1-TF-RDD/2),
P(1-TF+RDD/2)], where P = SUM p(j)". It does not say where in a file each pair's instances are.
The files list them in runs of five consecutive instances, one run per pair, TF changing fastest
(instances 1-5: TF 0.2, RDD 0.2; 6-10: TF 0.4, RDD 0.2; ...; 121-125: TF 1.0, RDD 1.0), and a
draw below zero appears as 0 (no due date is negative, and the share of zeros in every run is
about the share of its interval below zero). The adapter does not assume the pairs: it names each
run of five by the pair under which the due dates of its instances are jointly most likely under
that generator (``due_date_likelihood``, ``classes``), and refuses the files unless the 25 runs of
every file are the 25 pairs. As pinned, every run's pair wins by at least 22.6 nats over the next;
the pair most likely for an instance alone is its run's for 374 of the 375 (instance 123 of wt50,
run TF 1.0 and RDD 1.0, has 15 due dates of 0 where 25 are expected and is on its own 1.4 nats
more likely under TF 0.8 and RDD 0.6). Only d and the sum of p are read for this, and the groups
reach the kernel's split alone, not the problem. Instances of one pair at different sizes are in
different groups: they share no number, only the generator's parameters. split(env, 16, 24) puts
5 groups (24 instances) on the fresh side and 16 training instances from 15 other groups.

Size rule: as in the other adapters, instances with at most 1,000 positions and positions times
jobs at most 30,000 are used; all 375 pass (the largest, n = 100, has 10,000, and one construction
costs 10,101 units). Instances left out: none (none fails the size rule, and Z > R on all 375).
The directory of the files also serves wtpack1 to wtpack7, which this page does not name; they are
not used.
"""
from __future__ import annotations

import math
import re

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

SIZES = (40, 50, 100)
VALUES = {40: "wtopt40.txt", 50: "wtopt50.txt", 100: "wtbest100b.txt"}     # the reference of each data file
EARLIER = {100: "wtbest100a.txt"}            # older best known values, read only to check wtbest100b against them
MAX_VARS, MAX_CELLS = 1000, 30000            # the size rule


def parse(text: str, n: int, count: int) -> list:
    """The instances of one data file: ``count`` blocks of 3n integers, the n processing times,
    the n weights and the n due dates of one instance after the other."""
    tokens = text.split()
    if len(tokens) != count * 3 * n or not all(re.fullmatch(r"\d+", t) for t in tokens):
        raise ValueError("data file does not have the published format")
    table = np.array([int(t) for t in tokens], dtype=np.int64).reshape(count, 3, n)
    if np.any(table[:, :2] < 1):
        raise ValueError("the page states positive processing times and weights")
    return [(row[0].copy(), row[1].copy(), row[2].copy()) for row in table]


def parse_values(text: str, count: int) -> np.ndarray:
    """A solution-value file: one integer per instance, in the order of the data file."""
    tokens = text.split()
    if len(tokens) != count or not all(re.fullmatch(r"\d+", t) for t in tokens):
        raise ValueError("solution-value file does not have one value per instance")
    return np.array([int(t) for t in tokens], dtype=np.int64)


def parse_page(text: str) -> dict:
    """From the page: the number of instances of each file, the values of TF and RDD of the
    generator, and the numbers of the instances of n = 40 and n = 50 that are not solved."""
    body = " ".join(text.split("<PRE>")[1].split("</PRE>")[0].split())
    count = int(re.search(r"(\d+) test instances are available for each problem size n=40, n=50 and n=100", body).group(1))
    grid = {key: [float(x) for x in re.search(rf"\({key}=([0-9.,\s]+)\)", body).group(1).replace(" ", "").split(",")]
            for key in ("TF", "RDD")}
    solved = re.search(r"available for (\d+) and (\d+) of the 40 and 50 job problem instances", body)
    unsolved = {40: re.search(r"The unsolved 40 job problem is number (\d+)", body).group(1),
                50: re.search(r"50 job problems ([\d,\s]+and \d+) remain unsolved", body).group(1)}
    unsolved = {n: {int(x) for x in re.findall(r"\d+", s)} for n, s in unsolved.items()}
    if count - int(solved.group(1)) != len(unsolved[40]) or count - int(solved.group(2)) != len(unsolved[50]):
        raise ValueError("the page's counts of solved instances and its lists of unsolved ones disagree")
    per_class = count // (len(grid["TF"]) * len(grid["RDD"]))
    if per_class * len(grid["TF"]) * len(grid["RDD"]) != count:
        raise ValueError("the page's classes do not divide its instances")
    return {"count": count, "tf": grid["TF"], "rdd": grid["RDD"], "per_class": per_class, "unsolved": unsolved}


def due_date_likelihood(p: np.ndarray, d: np.ndarray, tfs, rdds) -> dict:
    """The log-likelihood of an instance's due dates under each pair (TF, RDD). The page's
    generator draws d(j) uniformly from [P(1-TF-RDD/2), P(1-TF+RDD/2)], P the sum of the
    processing times; the files hold no negative due date, a draw below 1 appears as 0. So a due
    date above 0 has the density 1/(P RDD) inside the interval (with a tolerance of 1 for the
    rounding to an integer) and 0 outside, and a due date of 0 has the chance that a draw is
    below 1. Processing times and weights do not depend on the pair and are not read."""
    P = float(p.sum())
    positive, zeros = d[d > 0].astype(float), int(np.sum(d == 0))
    likelihood = {}
    for tf in tfs:
        for rdd in rdds:
            low, high = P * (1 - tf - rdd / 2), P * (1 - tf + rdd / 2)
            width = high - low
            zero_mass = min(max((1.0 - low) / width, 0.0), 1.0)
            inside = positive.size == 0 or (positive.min() >= low - 1 and positive.max() <= high + 1)
            if not inside or (zeros and zero_mass == 0.0):
                likelihood[(tf, rdd)] = -math.inf
            else:
                likelihood[(tf, rdd)] = -positive.size * math.log(width) + (zeros * math.log(zero_mass) if zeros else 0.0)
    return likelihood


def classes(rows: list, tfs, rdds, per_class: int) -> list:
    """The pair (TF, RDD) of every instance of a data file. The instances come in runs of
    ``per_class`` consecutive instances; a run's pair is the one under which the due dates of
    its instances are jointly most likely. Refused unless every pair is the pair of one run."""
    out = []
    for start in range(0, len(rows), per_class):
        joint = {}
        for p, _, d in rows[start:start + per_class]:
            for pair, value in due_date_likelihood(p, d, tfs, rdds).items():
                joint[pair] = joint.get(pair, 0.0) + value
        out += [max(joint, key=joint.get)] * per_class
    if len(set(out)) != len(tfs) * len(rdds) or len(out) != len(tfs) * len(rdds) * per_class:
        raise ValueError("the runs of the file are not the page's pairs of TF and RDD, one run each")
    return out


def weighted_tardiness(p, w, d, order) -> int:
    """SUM w(j) T(j) of a processing order (job labels of the file, 0-based), every job finishing
    at its earliest completion time. Plain reference code, in integers."""
    time = total = 0
    for j in order:
        time += int(p[j])
        total += int(w[j]) * max(time - int(d[j]), 0)
    return total


def random_order_value(p, w, d) -> float:
    """The expected total weighted tardiness of a processing order drawn uniformly from all n!
    orders. Exact formula, floating-point arithmetic.

    Job j has k jobs before it with probability 1/n for each k = 0..n-1, and given k the set of
    those jobs is a uniformly random k-subset of the other n-1 jobs, so
        E[T(j)] = (1/n) sum_k sum_s N_j(k, s) / C(n-1, k) * max(p(j) + s - d(j), 0),
    N_j(k, s) the number of k-subsets of the other jobs whose processing times sum to s. N_j
    is obtained from the counts N of the subsets of all jobs by N_j(k, s) = N(k, s) -
    N_j(k-1, s - p(j)), for k up to (n-1)/2 only (there the recursion keeps its rounding error
    small); a job with more than (n-1)/2 jobs before it has k' = n-1-k jobs after it, a
    uniformly random k'-subset of the others with sum s', and finishes at P - s'. N_j depends on
    j only through p(j), so it is computed once for every distinct processing time. Row k of
    the counts is zero outside the sums of the k smallest and of the k largest processing
    times, and is computed there only."""
    p, w, d = (np.asarray(x, dtype=np.int64) for x in (p, w, d))
    n, P = len(p), int(p.sum())
    K = (n - 1) // 2
    ascending = np.sort(p)
    low = np.concatenate([[0], np.cumsum(ascending)])[:K + 1]             # the smallest sum of k times
    high = np.concatenate([[0], np.cumsum(ascending[::-1])])[:K + 1]      # the largest
    count = np.zeros((K + 1, P + 1))                          # count[k, s]: k-subsets of all jobs of sum s
    count[0, 0] = 1.0
    done = 0                                                  # the sum of the times counted so far
    for m, t in enumerate(p.tolist()):
        top = min(m + 1, K)
        count[1:top + 1, t:done + t + 1] += count[:top, :done + 1].copy()
        done += t
    inverse = np.array([1.0 / math.comb(n - 1, k) for k in range(K + 1)])
    s = np.arange(P + 1, dtype=float)
    rest = np.zeros((K + 1, P + 1))                           # rest[k, s]: N_j(k, s) for a job j of time t
    rest[0, 0] = 1.0
    total = 0.0
    for t in sorted(set(p.tolist())):
        for k in range(1, K + 1):
            a, b = int(low[k]), int(high[k]) + 1
            rest[k, a:b] = count[k, a:b]
            c = max(a, t)
            rest[k, c:b] -= rest[k - 1, c - t:b - t]
        before = inverse @ rest                               # sum over k <= K of N_j(k, .) / C(n-1, k)
        after = before if n - 2 - K == K else before - inverse[K] * rest[K]       # the same over k' <= n-2-K
        for j in np.flatnonzero(p == t):
            late = before @ np.maximum(t + s - d[j], 0.0) + after @ np.maximum(P - s - d[j], 0.0)
            total += float(w[j]) * late / n
    return total


class TardinessProblem(AssignProblem):
    """``p``, ``w``, ``d``: processing time, weight and due date of each job (option)."""

    def __init__(self, p, w, d, meter):
        n = len(p)
        self.p, self.w, self.d = (np.asarray(x, dtype=float) for x in (p, w, d))
        super().__init__(n_vars=n, n_opts=n, hard=[False], ordered=True, capacity=np.ones(n, dtype=np.int64),
                         opt_attr=np.column_stack([self.p, self.w, self.d]), meter=meter)

    def partial_totals(self, a):
        a = np.asarray(a, dtype=np.int64)
        free = np.flatnonzero(a < 0)
        jobs = a[:free[0] if len(free) else len(a)]         # the positions before the first one not given
        finish = np.cumsum(self.p[jobs])
        return np.array([float(np.sum(self.w[jobs] * np.maximum(finish - self.d[jobs], 0.0)))])

    def _new(self):
        s = super()._new()
        s["time"] = 0.0                                        # when the jobs placed so far are finished
        return s

    def _rows(self, s, variables):
        variables = np.asarray(variables)
        if len(variables) == 0:
            return np.zeros((0, self.n_opts, 1))
        if len(variables) != 1 or variables[0] != s["n"] or s["n"] >= self.n_vars:
            raise ValueError("variables of this problem are assigned in index order")
        out = (self.w * np.maximum(s["time"] + self.p - self.d, 0.0))[None, :, None]
        out[0, s["used"] >= self.capacity] = 0.0               # a job that is already placed
        return out

    def _push(self, s, v, o):
        s["time"] += self.p[o]
        s["tot"] = s["tot"] + np.array([self.w[o] * max(s["time"] - self.d[o], 0.0)])
        s["a"][v] = o


class Tardiness(Environment):
    name = category = "tardiness"
    form = "assign"
    threshold = 0.98
    anchor = ("an operating point, not an external fact, set knowing the scores of rules with no learning and no learner "
              "result: on average 98 hundredths of the way from the exact expected value of a uniformly random processing "
              "order to the value published by the OR-Library (optimal for 239 instances, best known for 136); an invalid "
              "answer counts 0. At 0.98 a value may exceed a reference above 0 by a median 4.7% of it. On the 24 fresh "
              "instances of split(env, 16, 24) the better of the due-date order and the w/p order averages 0.908 (0.967 on "
              "the deciding half, 0.826 on the confirming half) and an adjacent-swap descent from it 0.969 (0.994, 0.933); "
              "9 fresh instances (9 of the 14 of the deciding half) have reference 0, which the due-date order attains. "
              "One-pass textbook dispatching rules for this objective reach 0.98: ATC (k = 2) averages 0.992 and WMDD 0.993 "
              "on the fresh instances (0.987 and 0.989 on the confirming half), so a capability held here is the level of "
              "such a rule, not more")

    def __init__(self):
        fetch.fetch("tardiness", quiet=True)
        page = parse_page(open(fetch.path("tardiness", "wtinfo.html"), encoding="latin-1").read())
        count = page["count"]
        self.instances, self.left_out = {}, {}
        for n in SIZES:
            rows = parse(open(fetch.path("tardiness", f"wt{n}.txt")).read(), n, count)
            values = parse_values(open(fetch.path("tardiness", VALUES[n])).read(), count)
            if n in EARLIER and np.any(values > parse_values(open(fetch.path("tardiness", EARLIER[n])).read(), count)):
                raise ValueError(f"{VALUES[n]}: a best known value above the older one")
            pairs = classes(rows, page["tf"], page["rdd"], page["per_class"])
            for k, ((p, w, d), value, (tf, rdd)) in enumerate(zip(rows, values, pairs)):
                name = f"wt{n}-{k + 1:03d}"
                if n > MAX_VARS or n * n > MAX_CELLS:          # the size rule
                    self.left_out[name] = "the size rule"
                    continue
                zero = random_order_value(p, w, d)
                if not zero > value:                            # the scale has no length
                    self.left_out[name] = "a random order is on average no worse than the reference"
                    continue
                self.instances[name] = {"p": p, "w": w, "d": d, "reference": int(value), "zero": zero,
                                        "proven": n in page["unsolved"] and k + 1 not in page["unsolved"][n],
                                        "group": f"wt{n}-tf{tf:.1f}-rdd{rdd:.1f}"}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["reference"])

    def proven(self, instance_id) -> bool:
        """Whether the page calls the reference value optimal (else it is the best known one)."""
        return bool(self.instances[instance_id]["proven"])

    def group(self, instance_id):
        return self.instances[instance_id]["group"]           # the generation class: n, TF and RDD

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        n = len(inst["p"])
        rng = np.random.default_rng(seed)
        perm, _ = relabel(rng, n)                              # new job -> old job
        problem = TardinessProblem(inst["p"][perm], inst["w"][perm], inst["d"][perm], meter)

        def decode(answer):
            a = np.asarray(answer)
            if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= n:
                return np.full(n, -1, dtype=np.int64)          # not n labels of jobs: decoded to no order (scores 0)
            return perm[a.astype(np.int64)]

        return problem, decode

    def score(self, instance_id, answer):
        """``answer[k]``: the job (0-based, in the file's order) processed k-th."""
        inst = self.instances[instance_id]
        n = len(inst["p"])
        a = np.asarray(answer)
        if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= n:
            return 0.0
        if np.any(np.bincount(a.astype(np.int64), minlength=n) != 1):
            return 0.0
        value = weighted_tardiness(inst["p"], inst["w"], inst["d"], a.tolist())
        zero, best = inst["zero"], inst["reference"]
        return float(min(1.0, max(0.0, (zero - value) / (zero - best))))
