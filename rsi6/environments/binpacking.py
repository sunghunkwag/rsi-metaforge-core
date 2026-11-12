"""One-dimensional bin packing instances of the OR-Library (files binpack1 to binpack3).

Published form: items with sizes and bins of one capacity. A packing is valid when no bin
holds more than its capacity; its cost is the number of bins used. Reference: the best known
number of bins, printed in the header line of each problem. That number is read by the scorer
only and is not part of the problem the learner receives.

Answer form: a bin index for every item. There are as many bins to choose from as items, which
is always enough.

Groups: [0] number of bins in use (soft); [1] total size above capacity (hard).
"""
from __future__ import annotations

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

FILES = ("binpack1.txt", "binpack2.txt", "binpack3.txt")


def parse(text: str) -> dict:
    tokens = text.split()
    count, pos, out = int(tokens[0]), 1, {}
    for _ in range(count):
        name = tokens[pos]
        capacity, n, best = float(tokens[pos + 1]), int(tokens[pos + 2]), int(tokens[pos + 3])
        sizes = np.array([float(x) for x in tokens[pos + 4:pos + 4 + n]])
        out[name] = {"capacity": capacity, "sizes": sizes, "best": best}
        pos += 4 + n
    return out


class BinPackingProblem(AssignProblem):
    def __init__(self, sizes: np.ndarray, capacity: float, meter):
        n = len(sizes)
        self.sizes, self.cap = sizes, float(capacity)
        super().__init__(n_vars=n, n_opts=n, hard=[False, True], ordered=False, capacity=None,
                         var_attr=sizes[:, None], opt_attr=np.full((n, 1), capacity), meter=meter)

    def partial_totals(self, a):
        placed = a >= 0
        load = np.bincount(a[placed], weights=self.sizes[placed], minlength=self.n_opts)
        return np.array([float(np.count_nonzero(np.bincount(a[placed], minlength=self.n_opts))),
                         float(np.maximum(load - self.cap, 0.0).sum())])

    def _new(self):
        s = super()._new()
        s["load"] = np.zeros(self.n_opts)
        s["count"] = np.zeros(self.n_opts, dtype=np.int64)
        return s

    def _rows(self, s, variables):
        size = self.sizes[variables][:, None]
        over = np.maximum(s["load"][None, :] + size - self.cap, 0.0) - np.maximum(s["load"][None, :] - self.cap, 0.0)
        out = np.empty((len(variables), self.n_opts, 2))
        out[:, :, 0] = (s["count"] == 0)[None, :]
        out[:, :, 1] = over
        return out

    def _push(self, s, v, o):
        before = max(s["load"][o] - self.cap, 0.0)
        opened = 1.0 if s["count"][o] == 0 else 0.0
        s["load"][o] += self.sizes[v]
        s["count"][o] += 1
        s["a"][v] = o
        s["tot"] = s["tot"] + np.array([opened, max(s["load"][o] - self.cap, 0.0) - before])


class BinPacking(Environment):
    name = category = "binpacking"
    form = "assign"
    threshold = 0.98
    anchor = "about one bin above the best known number of bins for the 120-item problems, on average"

    def __init__(self):
        fetch.fetch("binpacking", quiet=True)
        self.instances = {}
        for name in FILES:
            self.instances.update(parse(open(fetch.path("binpacking", name)).read()))

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return instance_id.split("_")[0]                   # the size class: u120, u250, u500

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        item_perm, _ = relabel(rng, len(inst["sizes"]))
        problem = BinPackingProblem(inst["sizes"][item_perm], inst["capacity"], meter)

        def decode(answer):
            out = np.empty(len(item_perm), dtype=np.int64)
            out[item_perm] = np.asarray(answer, dtype=np.int64)
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        a = np.asarray(answer)
        n = len(inst["sizes"])
        if a.shape != (n,) or a.min() < 0 or a.max() >= n:
            return 0.0
        load = np.bincount(a, weights=inst["sizes"], minlength=n)
        if np.any(load > inst["capacity"] + 1e-9):
            return 0.0
        return float(min(1.0, inst["best"] / np.count_nonzero(np.bincount(a, minlength=n))))
