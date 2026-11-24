"""Generalised assignment problems of the OR-Library (J. E. Beasley), files gap1 to gap12.

Published form (the page gapinfo.html, which is pinned and parsed as a data file): m agents and
n jobs; c(i,j) the "cost of allocating job j to agent i", a(i,j) the "resource consumed in
allocating job j to agent i", b(i) the "resource capacity of agent i". An answer gives every
job exactly one agent. It is valid when, at every agent, the resource consumed by the jobs it
was given is at most the agent's capacity. Its value is the sum of c(i,j) over the jobs and
their agents, and for these 60 problems it is to be made LARGE: the page gives their optimal
values "when solved as maximisation problems".

Reference: those optimal values, read from the page (60 values, one per problem, matched to
the files by the page's own table: file, class notation c<m><n>, number in the class). They are
values of valid assignments, not bounds. The source publishes no assignment that reaches them.
An exact computation outside the adapter (branch and bound over the jobs with a Lagrangian bound
of its own, sharing no code with this module) found for each of the 60 problems a valid
assignment of the listed value and exhausted the tree of assignments of a larger value: all 60
listed values are attained in the answer form below and proven optimal for the files as pinned.

Answer form: the n jobs are the variables, the m agents are the options; job j takes the agent
it is given to. An agent may take any number of jobs (no count capacity: the resource a job
consumes depends on the agent, so the limit is not a number of jobs). Every assignment of the
published problem is an answer of this form and the other way round. Groups:
  [0] minus the sum of c over the jobs already assigned (soft, a cost to be made small: a soft
      group is minimised, so the maximisation is presented as the minimisation of the negated
      value; for a complete answer the published value is exactly minus this total);
  [1] the total amount, summed over the agents, by which the resource consumed exceeds the
      capacity (hard: it is zero exactly when the answer is valid).
Exposed arrays, each a field of the instance file: var_opt[0][j, i] = c(i,j) as published (the
value, not negated); var_opt[1][j, i] = a(i,j); opt_attr[i, 0] = b(i). Nothing else is exposed:
no attribute of a job alone, no relation between jobs or between agents. Jobs and agents are
relabelled with the seed; their order in the file carries nothing.

One layout: every problem has the same two groups, two job-agent relations, one agent
attribute and no count capacity. The numbers of jobs (15 to 60) and agents (5, 8, 10) differ,
which the layout allows; nothing is padded.

Score. The published values c lie between 10 and 25, and a valid assignment drawn at random is
worth 0.73 to 0.91 of the optimum (measured outside the adapter), so on the plain ratio of value
to optimum a random valid answer scores far above 0.5: the plain ratio is not used. The score is
the share of the way from a chance value to the optimum that a valid answer covers, cut to
[0, 1] (1 when the optimum is reached); an invalid answer scores 0.

The chance value. "A uniformly random valid answer" means here: an assignment drawn uniformly
from the set of assignments that respect every capacity. That is not a uniformly random
assignment (every job an agent, uniformly and independently): of 210 million of those drawn
outside the adapter 204 were valid, and their mean, which has a closed form (the sum over the
jobs of the mean of c(i,j) over the agents), is the mean of another population: it lies between
0.21 of the scale below and 0.16 of the scale above the mean over the valid set (the valid
assignments use the job-agent pairs that consume little, and the c of those pairs is not the
mean of c). The mean over the valid set has no closed form, so it is
ESTIMATED, by ``chance_value`` below: 512 random walks over the assignments whose steps are
decided by a and b alone (a step is kept exactly when the amount over capacity does not grow),
which keep the uniform distribution on the valid assignments, and whose valid states are
averaged. It reads c only to take that average, it never reads the reference, and its random
numbers are a fixed function of a counter written out in this module, so the chance value is a
function of the instance file and of this text alone. It is an estimate, not an exact value:
against the exact mean by complete enumeration of the valid set (possible for the five c515
problems, outside the adapter) it is off by at most 0.6 (0.016 of the scale); against
independent chains written in plain Python it is off by at most 0.014 of the scale on all 60
problems (the audit, with its own chains and an exact dynamic programme, measured at most 0.018,
on the smallest class, where the error is a bias of about 0.6 units and not sampling noise); another seed moved it by at most 0.003 of the scale on the 9 problems tried. An error of 0.016 of the scale in
the chance value moves a score of 0.90 by less than 0.002. The walk assumes that the valid set
is connected under its two kinds of step, which is not proven for the larger problems. This
sampler is the one thing in this module that is neither parsing nor evaluation. It belongs to
the score alone: it does not look at the objective to decide anything, it optimises nothing,
and neither it nor its result is in any field of the problem object.

Threshold 0.90: an operating point, not an external fact, fixed before any answer of the
learner on this category was scored: on average nine tenths of the way from the chance value to
the published optimum, an invalid assignment counting 0. On these problems a score of 0.90 is a
value of 0.973 to 0.991 of the optimum (0.984 on average).

Groups: the 12 published size classes (c515, c520, c525, c530, c824, c832, c840, c848, c1030,
c1040, c1050, c1060), 5 problems each. Size rule (fixed before anything was scored): problems
with at most 1,000 jobs and jobs times agents at most 30,000 are used; all 60 satisfy it (the
largest has 60 jobs and 10 agents), so no problem of gap1 to gap12 is left out. The files gapa,
gapb, gapc and gapd of the same page (minimisation problems) are left out entirely: the page
gives no reference value for them.
"""
from __future__ import annotations

import re

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

FILES = tuple(f"gap{k}" for k in range(1, 13))
MAX_VARS, MAX_CELLS = 1000, 30000
CHAINS, SWEEPS, SEED = 512, 60, np.uint64(20261113)      # the sampler of the chance value


def parse(text: str) -> list:
    """The problems of one data file, in the published format."""
    tokens = text.split()
    count, pos, out = int(tokens[0]), 1, []
    for _ in range(count):
        m, n = int(tokens[pos]), int(tokens[pos + 1])
        pos += 2
        value = np.array([float(x) for x in tokens[pos:pos + m * n]]).reshape(m, n)       # c(i,j)
        pos += m * n
        use = np.array([float(x) for x in tokens[pos:pos + m * n]]).reshape(m, n)         # a(i,j)
        pos += m * n
        limit = np.array([float(x) for x in tokens[pos:pos + m]])                         # b(i)
        pos += m
        out.append({"value": value, "use": use, "limit": limit})
    if pos != len(tokens):
        raise ValueError("data file does not have the published format")
    return out


def parse_page(text: str) -> dict:
    """``{file: [(notation, optimal value), ...]}`` from the table of the page: a line of file
    names, then lines of (notation, value) pairs in the same columns."""
    out, header = {}, []
    for line in text.split("<PRE>")[1].split("</PRE>")[0].splitlines():
        parts = line.split()
        if parts and all(re.fullmatch(r"gap\d+", p) for p in parts):
            header = parts
        elif header and len(parts) == 2 * len(header) and all(re.fullmatch(r"c\d+-\d+", p) for p in parts[0::2]) \
                and all(re.fullmatch(r"\d+", p) for p in parts[1::2]):
            for k, name in enumerate(header):
                out.setdefault(name, []).append((parts[2 * k], float(parts[2 * k + 1])))
        elif parts:
            header = []
    return out


def _draws(index: np.ndarray) -> np.ndarray:
    """Pseudo-random 64-bit numbers as a fixed function of a counter (SplitMix64), written out
    here so that the chance value is a function of the instance file and of this text alone."""
    z = SEED + (index + np.uint64(1)) * np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


def _below(index: np.ndarray, n: int) -> np.ndarray:
    """Integers in [0, n), uniform up to 2**-24."""
    return ((_draws(index) >> np.uint64(33)) % np.uint64(n)).astype(np.int64)


def chance_value(value: np.ndarray, use: np.ndarray, limit: np.ndarray, sweeps: int = SWEEPS, counts: bool = False):
    """An estimate of the expected value of an assignment drawn uniformly from the VALID ones.

    ``CHAINS`` assignments start uniformly at random and are changed ``sweeps * n`` times each,
    in turn by giving one random job to a random agent and by exchanging the agents of two random
    jobs; a change is kept exactly when the total amount over capacity does not grow. A valid
    assignment therefore stays valid, and among valid assignments every change that keeps
    validity is kept and is as likely as its reverse: the uniform distribution on the valid
    assignments is stationary. The value is averaged over the valid assignments in the second
    half of the changes. The values c are read only to take that average: they never decide a
    change, and the reference is not an argument."""
    m, n = value.shape
    C, A, b = value.astype(np.int64), use.astype(np.int64), limit.astype(np.int64)
    if not (np.array_equal(C, value) and np.array_equal(A, use) and np.array_equal(b, limit)):
        raise ValueError("the published numbers are integers")
    rows, cols = np.arange(CHAINS), np.arange(n)
    count = np.arange(CHAINS, dtype=np.uint64)
    x = _below(np.arange(CHAINS * n, dtype=np.uint64), m).reshape(CHAINS, n)
    load = np.zeros((CHAINS, m), dtype=np.int64)
    for i in range(m):
        load[:, i] = (A[i] * (x == i)).sum(axis=1)
    over = lambda amount, agent: np.maximum(amount - b[agent], 0)
    steps, total, seen, looked = sweeps * n, 0, 0, 0
    for t in range(steps):
        base = np.uint64(CHAINS * n + 3 * CHAINS * t)
        j = _below(base + count, n)
        p = x[rows, j]
        if t % 2 == 0:                                         # one job to another agent
            q = _below(base + np.uint64(CHAINS) + count, m)
            lp, lq, dp, dq = load[rows, p], load[rows, q], -A[p, j], A[q, j]
            keep = (p != q) & (over(lp + dp, p) + over(lq + dq, q) <= over(lp, p) + over(lq, q))
            k = rows[keep]
            x[k, j[keep]] = q[keep]
        else:                                                  # two jobs exchange their agents
            j2 = _below(base + np.uint64(2 * CHAINS) + count, n)
            q = x[rows, j2]
            lp, lq, dp, dq = load[rows, p], load[rows, q], A[p, j2] - A[p, j], A[q, j] - A[q, j2]
            keep = (p != q) & (over(lp + dp, p) + over(lq + dq, q) <= over(lp, p) + over(lq, q))
            k = rows[keep]
            x[k, j[keep]], x[k, j2[keep]] = q[keep], p[keep]
        load[k, p[keep]] += dp[keep]
        load[k, q[keep]] += dq[keep]
        if 2 * t >= steps and t % 4 == 3:
            valid = np.all(load <= b, axis=1)
            total += int(C[x[valid], cols].sum())
            seen += int(valid.sum())
            looked += CHAINS
    if 2 * seen < looked:
        raise ValueError("fewer than half of the sampled assignments were valid: no chance value")
    return (total / seen, seen, looked) if counts else total / seen


class GenAssignProblem(AssignProblem):
    """``value[j, i]``, ``use[j, i]``: job j at agent i; ``limit[i]``: capacity of agent i."""

    def __init__(self, value, use, limit, meter):
        n, m = value.shape
        self.value, self.use, self.limit = value, use, limit
        super().__init__(n_vars=n, n_opts=m, hard=[False, True], ordered=False, capacity=None,
                         opt_attr=limit[:, None], var_opt=(value, use), meter=meter)

    def partial_totals(self, a):
        jobs = np.flatnonzero(a >= 0)
        load = np.bincount(a[jobs], weights=self.use[jobs, a[jobs]], minlength=self.n_opts)
        return np.array([-float(self.value[jobs, a[jobs]].sum()), float(np.maximum(load - self.limit, 0.0).sum())])

    def _new(self):
        s = super()._new()
        s["load"] = np.zeros(self.n_opts)
        return s

    def _rows(self, s, variables):
        variables = np.asarray(variables, dtype=np.int64)
        out = np.zeros((len(variables), self.n_opts, 2))
        over = np.maximum(s["load"] - self.limit, 0.0)
        out[:, :, 0] = -self.value[variables]
        out[:, :, 1] = np.maximum(s["load"] + self.use[variables] - self.limit, 0.0) - over
        for k in np.flatnonzero(s["a"][variables] >= 0):       # a job that already has an agent: the change if it moved
            v = variables[k]
            p = s["a"][v]
            left = max(s["load"][p] - self.use[v, p] - self.limit[p], 0.0) - over[p]
            out[k, :, 0] += self.value[v, p]
            out[k, :, 1] += left
            out[k, p] = 0.0
        return out

    def _push(self, s, v, o):
        before = max(s["load"][o] - self.limit[o], 0.0)
        s["a"][v] = o
        s["load"][o] += self.use[v, o]
        s["tot"] = s["tot"] + np.array([-self.value[v, o], max(s["load"][o] - self.limit[o], 0.0) - before])


class GenAssign(Environment):
    name = category = "genassign"
    form = "assign"
    threshold = 0.90
    anchor = ("an operating point, not an external fact: on average nine tenths of the way from the estimated expected value "
              "of a uniformly random valid assignment to the optimal value published by the OR-Library (a value a valid "
              "assignment attains, not a bound); an invalid assignment counts 0")

    def __init__(self):
        fetch.fetch("genassign", quiet=True)
        table = parse_page(open(fetch.path("genassign", "gapinfo.html"), encoding="latin-1").read())
        self.instances = {}
        for name in FILES:
            problems = parse(open(fetch.path("genassign", name + ".txt")).read())
            if len(problems) != len(table[name]):
                raise ValueError(f"{name}: the page and the file disagree on the number of problems")
            for k, (problem, (notation, best)) in enumerate(zip(problems, table[name])):
                m, n = problem["value"].shape
                if notation != f"c{m}{n}-{k + 1}":            # the page's notation must be the file's sizes and position
                    raise ValueError(f"{name}: problem {k + 1} is not {notation}")
                if n > MAX_VARS or n * m > MAX_CELLS:         # the size rule
                    continue
                self.instances[notation] = dict(problem, best=best, chance=chance_value(**problem))

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return instance_id.split("-")[0]                      # the size class: c<agents><jobs>

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        m, n = inst["value"].shape
        job_perm, _ = relabel(rng, n)                    # new job -> old job
        agent_perm, _ = relabel(rng, m)                  # new agent -> old agent
        cells = np.ix_(agent_perm, job_perm)
        problem = GenAssignProblem(inst["value"][cells].T.copy(), inst["use"][cells].T.copy(),
                                   inst["limit"][agent_perm].copy(), meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[job_perm] = agent_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        """``answer[j]``: the agent (0-based, in the file's order) of job j (in the file's order)."""
        inst = self.instances[instance_id]
        m, n = inst["value"].shape
        a = np.asarray(answer)
        if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= m:
            return 0.0
        jobs = np.arange(n)
        if np.any(np.bincount(a, weights=inst["use"][a, jobs], minlength=m) > inst["limit"]):
            return 0.0
        value, chance = float(inst["value"][a, jobs].sum()), inst["chance"]
        if chance >= inst["best"]:
            return 0.0
        return float(min(1.0, max(0.0, (value - chance) / (inst["best"] - chance))))
