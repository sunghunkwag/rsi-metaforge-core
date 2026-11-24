"""Kinds of prediction problem made from the Penn Machine Learning Benchmarks (PMLB).

Published form: one tab-separated table per data set with a column ``target`` (Olson et al.
2017; Romano et al. 2021; https://github.com/EpistasisLab/pmlb). The tables are fetched as
data, by hash; nothing in the repository is executed. A *kind* is a list of data sets fixed by a
written rule in its manifest (``rsi6/environments/manifests/<kind>.json``, field ``rule``); the
lists are made by ``rsi6/results/design_t_20261124/scripts/make_manifests.py`` from the
collection's own summary table and nothing else.

Problem form: prediction. An instance is a data set (or, for kinds with few data sets, one of
up to ``PER_SET`` disjoint draws of its rows). The rows are put in a fixed order (the SHA-256
of the data set's name and the row's position); the first rows in that order are the observed
entities with their targets, the next ones the queries. At most 256 observed and 128 queries;
a data set with fewer than 384 rows gives two thirds of its rows as observed and the rest as
queries. The attributes are the table's other columns as numbers, in an order relabelled per
seed, padded with zero columns to the widest table of the kind (every problem of an environment
has one layout; a column of zeros carries nothing).

Reference: the targets of the queries, which the scorer alone reads.

* ``regression``: the score is the coefficient of determination on the queries, cut to [0, 1].
* ``binary``: the target is 1 for the larger of the two class labels and 0 for the other; the
  score is the share of queries on the right side of 0.5.
* ``rest``: for tables with more than two classes the target is 1 for the most frequent class
  of the table and 0 for the rest; scored as ``binary``.

Refused at load, by rule: a table with a missing or non-numeric cell, and an instance whose
query targets do not vary under ``regression``.

Training and fresh instances never share a data set (``group`` is the data set).
The thresholds are operating points, not external facts.
"""
from __future__ import annotations

import gzip
import hashlib

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import PredictProblem

N_OBSERVED, N_QUERIES = 256, 128


class Tabular(Environment):
    form = "predict"
    task = "regression"          # "regression", "binary" or "rest"
    PER_SET = 1
    threshold = 0.9
    anchor = "an operating point: a mean score of 0.9 on the fresh data sets"

    def __init__(self):
        manifest = fetch.fetch(self.name, quiet=True)
        self.files = {entry["path"][:-7]: entry for entry in manifest["files"]}
        self.width = max(int(entry["features"]) for entry in manifest["files"])
        self._tables, self._instances, self.refused = {}, {}, []
        for name in sorted(self.files):
            table = self._table(name)
            if table is None:
                self.refused.append(name)
                continue
            n = len(table[1])
            draws = max(1, min(self.PER_SET, n // (N_OBSERVED + N_QUERIES)))
            order = np.argsort([hashlib.sha256(f"{name}|{i}".encode()).hexdigest() for i in range(n)])
            for k in range(draws):
                if draws == 1:
                    n_obs = min(N_OBSERVED, (2 * n) // 3)
                    rows_o, rows_q = order[:n_obs], order[n_obs:n_obs + min(N_QUERIES, n - n_obs)]
                else:
                    at = k * (N_OBSERVED + N_QUERIES)
                    rows_o, rows_q = order[at:at + N_OBSERVED], order[at + N_OBSERVED:at + N_OBSERVED + N_QUERIES]
                if self.task == "regression" and np.ptp(table[1][rows_q]) == 0.0:
                    self.refused.append(f"{name}/{k}")
                    continue
                self._instances[f"{name}/{k}"] = (name, rows_o, rows_q)

    def _table(self, name):
        if name not in self._tables:
            with gzip.open(fetch.path(self.name, name + ".tsv.gz"), "rt") as handle:
                header = handle.readline().rstrip("\n").split("\t")
                try:
                    cells = np.genfromtxt(handle, delimiter="\t", dtype=float)
                except ValueError:
                    cells = None
            if cells is None or cells.ndim != 2 or cells.shape[1] != len(header) or not np.all(np.isfinite(cells)):
                self._tables[name] = None
            else:
                at = header.index("target")
                y, x = cells[:, at], np.delete(cells, at, axis=1)
                if self.task == "binary":
                    y = (y == y.max()).astype(float)
                elif self.task == "rest":
                    values, counts = np.unique(y, return_counts=True)
                    y = (y == values[np.argmax(counts)]).astype(float)
                self._tables[name] = (x, y)
        return self._tables[name]

    def instance_ids(self):
        return sorted(self._instances)

    def _arrays(self, instance_id):
        name, rows_o, rows_q = self._instances[instance_id]
        x, y = self._table(name)
        return x[rows_o], y[rows_o], x[rows_q], y[rows_q]

    def reference(self, instance_id):
        return self._arrays(instance_id)[3].tolist()

    def group(self, instance_id):
        return self._instances[instance_id][0]

    def problem(self, instance_id, meter, seed, training):
        ctx_x, ctx_y, qry_x, qry_y = self._arrays(instance_id)
        rng = np.random.default_rng(seed)
        columns, _ = relabel(rng, ctx_x.shape[1])
        pad = lambda x: np.column_stack([x[:, columns], np.zeros((len(x), self.width - x.shape[1]))])
        problem = PredictProblem(pad(ctx_x), ctx_y, pad(qry_x), ordered=False,
                                 target=qry_y if training else None, meter=meter)
        return problem, (lambda answer: np.asarray(answer, dtype=float))

    def score(self, instance_id, answer):
        target = self._arrays(instance_id)[3]
        a = np.asarray(answer, dtype=float)
        if a.shape != target.shape or not np.all(np.isfinite(a)):
            return 0.0
        if self.task == "regression":
            spread = float(((target - target.mean()) ** 2).sum())
            return float(np.clip(1.0 - ((a - target) ** 2).sum() / spread, 0.0, 1.0)) if spread > 0.0 else 0.0
        return float(np.mean((a >= 0.5) == (target >= 0.5)))


class Friedman(Tabular):
    name = category = "friedman"


class Table(Tabular):
    name = category = "table"


class Binary(Tabular):
    name = category = "binary"
    task = "binary"
