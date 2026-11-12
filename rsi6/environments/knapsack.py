"""Multidimensional knapsack problems of the OR-Library (Chu and Beasley).

Published form: n items with profits p(j), m constraints with coefficients r(i,j) and limits
b(i). An answer takes a subset of the items; it is valid when, for every constraint, the
coefficients of the taken items sum to at most the limit; its value is the sum of their
profits, to be made large. Reference: the best feasible values of Chu and Beasley (the
library's file mkcbres), which are best known values, not proven optima.

Answer form: every item takes option 0 (left) or 1 (taken). Groups: [0] minus the profit of the
taken items (soft, a cost); [1] the total amount by which limits are exceeded (hard). The
profits and the constraint coefficients of an item are exposed as its attributes.
"""
from __future__ import annotations

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

FILES = {1: "5.100", 2: "5.250", 4: "10.100", 5: "10.250", 7: "30.100", 8: "30.250"}


def parse(text: str) -> list:
    tokens = text.split()
    count, pos, out = int(tokens[0]), 1, []
    for _ in range(count):
        n, m = int(tokens[pos]), int(tokens[pos + 1])        # the third number (a stated optimum, 0 here) is not kept
        pos += 3
        profit = np.array([float(x) for x in tokens[pos:pos + n]])
        pos += n
        use = np.array([float(x) for x in tokens[pos:pos + m * n]]).reshape(m, n)
        pos += m * n
        limit = np.array([float(x) for x in tokens[pos:pos + m]])
        pos += m
        out.append({"profit": profit, "use": use, "limit": limit})
    return out


def results(text: str) -> dict:
    out = {}
    for line in text.split("Problem Name")[1].splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2:
            out[parts[0]] = float(parts[1])
        elif out and not parts:
            continue
    return out


class KnapsackProblem(AssignProblem):
    def __init__(self, profit, use, limit, meter):
        n = len(profit)
        self.profit, self.use, self.limit = profit, use, limit
        super().__init__(n_vars=n, n_opts=2, hard=[False, True], ordered=False, capacity=None,
                         var_attr=np.column_stack([profit, use.T]), meter=meter)

    def partial_totals(self, a):
        taken = a == 1
        load = self.use[:, taken].sum(axis=1)
        return np.array([-float(self.profit[taken].sum()), float(np.maximum(load - self.limit, 0.0).sum())])

    def _new(self):
        s = super()._new()
        s["load"] = np.zeros(len(self.limit))
        return s

    def _rows(self, s, variables):
        out = np.zeros((len(variables), 2, 2))
        out[:, 1, 0] = -self.profit[variables]
        after = s["load"][:, None] + self.use[:, variables]
        out[:, 1, 1] = (np.maximum(after - self.limit[:, None], 0.0) - np.maximum(s["load"] - self.limit, 0.0)[:, None]).sum(axis=0)
        return out

    def _push(self, s, v, o):
        s["a"][v] = o
        if o == 1:
            before = np.maximum(s["load"] - self.limit, 0.0).sum()
            s["load"] = s["load"] + self.use[:, v]
            s["tot"] = s["tot"] + np.array([-self.profit[v], np.maximum(s["load"] - self.limit, 0.0).sum() - before])


class Knapsack(Environment):
    name = category = "knapsack"
    form = "assign"
    threshold = 0.97
    anchor = "a value of at least 0.97 of the best known value of Chu and Beasley, on average"

    def __init__(self):
        fetch.fetch("knapsack", quiet=True)
        best = results(open(fetch.path("knapsack", "mkcbres.txt")).read())
        self.instances = {}
        for number, label in FILES.items():
            for k, problem in enumerate(parse(open(fetch.path("knapsack", f"mknapcb{number}.txt")).read())):
                name = f"{label}-{k:02d}"
                self.instances[name] = dict(problem, best=best[name])

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return instance_id.split("-")[0]                      # the class: constraints.items

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        item_perm, _ = relabel(rng, len(inst["profit"]))
        row_perm, _ = relabel(rng, len(inst["limit"]))
        problem = KnapsackProblem(inst["profit"][item_perm], inst["use"][np.ix_(row_perm, item_perm)],
                                  inst["limit"][row_perm], meter)

        def decode(answer):
            out = np.empty(len(item_perm), dtype=np.int64)
            out[item_perm] = np.asarray(answer, dtype=np.int64)
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        a = np.asarray(answer)
        if a.shape != inst["profit"].shape or not np.all((a == 0) | (a == 1)):
            return 0.0
        if np.any(inst["use"][:, a == 1].sum(axis=1) > inst["limit"]):
            return 0.0
        return float(min(1.0, inst["profit"][a == 1].sum() / inst["best"]))
