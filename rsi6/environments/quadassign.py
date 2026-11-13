"""Quadratic assignment instances of QAPLIB.

Published form: two n-by-n matrices A and B. An answer is a permutation p; its cost is the sum
over all i, j of A[i][j] * B[p(i)][p(j)]. Reference: the value printed in the first line of
each instance's solution file (optimal or best known), with a permutation that reaches it.

Score: the share of the way from the expected cost of a uniformly random permutation to the
published value that an answer covers, cut to [0, 1]. (The plain ratio of published value to
cost is above 0.9 for random permutations on several families, as an independent audit showed.)
Families share matrices (one distance matrix serves several instances), so families are kept
whole on one side of every split.

Answer form: variable i takes option p(i); every option is used once. One group: the cost of
the pairs already assigned (soft). The two matrices are exposed as they are published: A as a
relation between variables, B as a relation between options.

Instances larger than 64 are left out for run time; instances whose published value is not
positive are left out because the score is a ratio; an instance is used only if its published
permutation (as given, or read as the inverse) reproduces its published value.
"""
from __future__ import annotations

import json
import os

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

MAX_SIZE = 64


def parse(text: str):
    tokens = text.split()
    n = int(tokens[0])
    values = np.array([float(x) for x in tokens[1:1 + 2 * n * n]])
    return values[:n * n].reshape(n, n), values[n * n:].reshape(n, n)


def parse_solution(text: str):
    tokens = text.replace(",", " ").split()
    n, value = int(tokens[0]), float(tokens[1])
    return value, np.array([int(x) for x in tokens[2:2 + n]]) - 1


def random_cost(A: np.ndarray, B: np.ndarray) -> float:
    """The expected cost of a uniformly random permutation (exact)."""
    n = len(A)
    return float((A.sum() - np.trace(A)) * (B.sum() - np.trace(B)) / (n * (n - 1)) + np.trace(A) * np.trace(B) / n)


def cost(A: np.ndarray, B: np.ndarray, p) -> float:
    p = np.asarray(p)
    return float((A * B[np.ix_(p, p)]).sum())


class QuadAssignProblem(AssignProblem):
    def __init__(self, A: np.ndarray, B: np.ndarray, meter):
        n = len(A)
        self.A, self.B = A, B
        super().__init__(n_vars=n, n_opts=n, hard=[False], ordered=False, capacity=np.ones(n, dtype=np.int64),
                         var_var=(A,), opt_opt=(B,), meter=meter)

    def partial_totals(self, a):
        placed = np.flatnonzero(a >= 0)
        where = a[placed]
        return np.array([float((self.A[np.ix_(placed, placed)] * self.B[np.ix_(where, where)]).sum())])

    def _new(self):
        s = super()._new()
        s["G"] = np.outer(np.diag(self.A), np.diag(self.B))     # change of the cost if variable v took option l
        return s

    def _rows(self, s, variables):
        rows = s["G"][np.asarray(variables, dtype=np.int64)][:, :, None].copy()
        rows[:, s["used"] >= self.capacity] = 0.0             # an option that is already taken
        return rows

    def _push(self, s, v, o):
        s["tot"] = s["tot"] + s["G"][v, o]
        s["a"][v] = o
        s["G"] += np.outer(self.A[:, v], self.B[:, o]) + np.outer(self.A[v, :], self.B[o, :])


class QuadAssign(Environment):
    name = category = "quadassign"
    form = "assign"
    threshold = 0.90
    anchor = ("an operating point, not an external fact: on average nine tenths of the way from the expected cost of a "
              "random permutation to the published optimal or best known value")

    def __init__(self):
        manifest = fetch.fetch("quadassign", quiet=True)
        have = {e["path"] for e in manifest["files"] if not e.get("missing")}
        self.instances = {}
        for path in sorted(have):
            if not path.endswith(".dat") or path[:-4] + ".sln" not in have:
                continue
            name = path[:-4]
            A, B = parse(open(fetch.path("quadassign", path)).read())
            value, permutation = parse_solution(open(fetch.path("quadassign", name + ".sln")).read())
            if len(A) > MAX_SIZE or value <= 0 or sorted(permutation.tolist()) != list(range(len(A))):
                continue
            inverse = np.empty(len(A), dtype=np.int64)
            inverse[permutation] = np.arange(len(A))
            # an instance is used only if its published permutation reproduces its published value
            if min(abs(cost(A, B, permutation) - value), abs(cost(A, B, inverse) - value)) < 1e-6:
                self.instances[name] = {"A": A, "B": B, "value": value, "permutation": permutation}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["value"])

    def group(self, instance_id):
        return instance_id.rstrip("abcdefghijklmnopqrstuvwxyz").rstrip("0123456789")      # the family

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        n = len(inst["A"])
        var_perm, _ = relabel(rng, n)                    # new variable -> old variable
        opt_perm, _ = relabel(rng, n)                    # new option -> old option
        problem = QuadAssignProblem(inst["A"][np.ix_(var_perm, var_perm)], inst["B"][np.ix_(opt_perm, opt_perm)], meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[var_perm] = opt_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        n = len(inst["A"])
        a = np.asarray(answer)
        if a.shape != (n,) or sorted(a.tolist()) != list(range(n)):
            return 0.0
        value, chance = cost(inst["A"], inst["B"], a), random_cost(inst["A"], inst["B"])
        if chance <= inst["value"]:
            return 0.0
        return float(min(1.0, max(0.0, (chance - value) / (chance - inst["value"]))))
