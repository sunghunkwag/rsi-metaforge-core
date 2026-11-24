"""Uncapacitated p-median instances of the OR-Library (pmed1 to pmed20).

Published form: an undirected graph with edge costs and a number p. The allocation cost between
two vertices is their shortest-path distance, obtained exactly as the library prescribes: start
from infinity, set c(i,i) = 0, read the edge lines in turn setting c(i,j) = c(j,i) = k (so the
last of several lines for one edge counts), then apply Floyd's algorithm. An answer chooses at
most p vertices as medians and allocates every vertex to one of them; its cost is the sum of
the allocation costs. Reference: the optimal values in the library's file pmedopt.

Answer form: every vertex takes one vertex as its median. Groups: [0] the sum of allocation
costs (soft); [1] the number of distinct medians in use beyond p (hard).
"""
from __future__ import annotations

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

NUMBERS = range(1, 21)


def parse(text: str):
    tokens = text.split()
    n, m, p = int(tokens[0]), int(tokens[1]), int(tokens[2])
    c = np.full((n, n), np.inf)
    np.fill_diagonal(c, 0.0)
    for k in range(m):
        i, j, w = int(tokens[3 + 3 * k]) - 1, int(tokens[4 + 3 * k]) - 1, float(tokens[5 + 3 * k])
        c[i, j] = c[j, i] = w
    for k in range(n):                                   # Floyd's algorithm
        c = np.minimum(c, c[:, k:k + 1] + c[k:k + 1, :])
    return c, p


class PMedianProblem(AssignProblem):
    def __init__(self, c: np.ndarray, p: int, meter):
        n = len(c)
        self.c, self.p = c, int(p)
        super().__init__(n_vars=n, n_opts=n, hard=[False, True], ordered=False, capacity=None, var_opt=(c,),
                         meter=meter)

    def partial_totals(self, a):
        placed = np.flatnonzero(a >= 0)
        distinct = len(set(a[placed].tolist()))
        return np.array([float(self.c[placed, a[placed]].sum()), float(max(0, distinct - self.p))])

    def _new(self):
        s = super()._new()
        s["count"] = np.zeros(self.n_opts, dtype=np.int64)
        s["distinct"] = 0
        return s

    def _rows(self, s, variables):
        out = np.empty((len(variables), self.n_opts, 2))
        out[:, :, 0] = self.c[variables]
        out[:, :, 1] = ((s["count"] == 0) & (s["distinct"] >= self.p))[None, :]
        return out

    def _push(self, s, v, o):
        opened = s["count"][o] == 0
        excess = 1.0 if (opened and s["distinct"] >= self.p) else 0.0
        s["count"][o] += 1
        s["distinct"] += int(opened)
        s["a"][v] = o
        s["tot"] = s["tot"] + np.array([self.c[v, o], excess])


class PMedian(Environment):
    name = category = "pmedian"
    form = "assign"
    threshold = 0.95
    anchor = "an operating point, not an external fact: a mean ratio of the published optimal value to the cost of 0.95"

    def __init__(self):
        fetch.fetch("pmedian", quiet=True)
        best = {}
        for line in open(fetch.path("pmedian", "pmedopt.txt")).read().splitlines()[1:]:
            parts = line.split()
            if len(parts) == 2:
                best[parts[0]] = float(parts[1])
        self.instances = {}
        for k in NUMBERS:
            c, p = parse(open(fetch.path("pmedian", f"pmed{k}.txt")).read())
            self.instances[f"pmed{k}"] = {"c": c, "p": p, "best": best[f"pmed{k}"]}

    def instance_ids(self):
        return sorted(self.instances, key=lambda name: int(name[4:]))

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return str(len(self.instances[instance_id]["c"]))          # the size class: 100, 200, 300, 400 vertices

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        n = len(inst["c"])
        var_perm, _ = relabel(rng, n)
        opt_perm, _ = relabel(rng, n)
        problem = PMedianProblem(inst["c"][np.ix_(var_perm, opt_perm)], inst["p"], meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[var_perm] = opt_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        n = len(inst["c"])
        a = np.asarray(answer)
        if a.shape != (n,) or a.min() < 0 or a.max() >= n or len(set(a.tolist())) > inst["p"]:
            return 0.0
        value = float(inst["c"][np.arange(n), a].sum())
        return float(min(1.0, inst["best"] / value)) if value > 0 else 0.0
