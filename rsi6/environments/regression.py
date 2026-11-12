"""Physical laws of the SRSD-Feynman data sets, as prediction from observations.

Published form: for each of 120 laws, samples of its input variables with the value the law
gives (the data set's authors generated them; the files have no header and the last column is
the value). Reference: the value column of the test sample, which the scorer alone reads.

Problem form: prediction. The observed entities are the first 256 rows of the law's validation
sample (attributes: the input variables, target: the value); the queries are the first 128 rows
of its test sample. The score is the coefficient of determination of the predictions on the
queries, cut to [0, 1]. Threshold anchor: the data set's own criterion for a recovered law,
a coefficient of determination above 0.999.

The benchmark was made for symbolic regression; here only its samples are used, and no
expression is searched for. Supplementary files that state the laws are not fetched.

Two rules applied at load, both from an independent audit. A law whose query targets have
fewer than 100 distinct values is refused: for one law (medium, iii.15.12) most published
targets are exactly 0, rounding residue of a difference below double precision. Queries whose
inputs equal an observed input are dropped: one law (easy, iii.12.43) has integer inputs and
repeats them. The 0.999 criterion of the data set is a criterion per law; here it is applied to
the mean over laws, which is stricter.
"""
from __future__ import annotations

import os

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import PredictProblem

TIERS = ("easy", "medium", "hard")
N_OBSERVED, N_QUERIES = 256, 128


class Regression(Environment):
    name = category = "regression"
    form = "predict"
    threshold = 0.999
    anchor = ("the data set's criterion for one recovered law (a coefficient of determination above 0.999), "
              "applied here to the mean over the fresh laws, which is stricter than the criterion")

    def __init__(self):
        manifest = fetch.fetch("regression", quiet=True)
        self.laws = {}
        for entry in manifest["files"]:
            tier, part, name = entry["path"].split("/")
            if part == "test":
                self.laws[f"{tier}/{name[:-4]}"] = (tier, name)
        self._loaded = {}
        self.refused = sorted(i for i in self.laws if len(np.unique(self._load(i)[3])) < 100)
        for i in self.refused:
            del self.laws[i]

    def instance_ids(self):
        return sorted(self.laws)

    def _load(self, instance_id):
        if instance_id not in self._loaded:
            tier, name = self.laws[instance_id]
            observed = np.loadtxt(fetch.path("regression", os.path.join(tier, "val", name)))[:N_OBSERVED]
            queries = np.loadtxt(fetch.path("regression", os.path.join(tier, "test", name)))
            seen = {tuple(row) for row in observed[:, :-1].tolist()}
            queries = queries[[tuple(row) not in seen for row in queries[:, :-1].tolist()]][:N_QUERIES]
            self._loaded[instance_id] = (observed[:, :-1], observed[:, -1], queries[:, :-1], queries[:, -1])
        return self._loaded[instance_id]

    def reference(self, instance_id):
        return self._load(instance_id)[3].tolist()

    def group(self, instance_id):
        return instance_id.split("/")[0]                      # the data set: easy, medium or hard

    def problem(self, instance_id, meter, seed, training):
        ctx_x, ctx_y, qry_x, qry_y = self._load(instance_id)
        rng = np.random.default_rng(seed)
        columns, _ = relabel(rng, ctx_x.shape[1])             # the order of the input variables carries nothing
        problem = PredictProblem(ctx_x[:, columns], ctx_y, qry_x[:, columns], ordered=False,
                                 target=qry_y if training else None, meter=meter)
        return problem, (lambda answer: np.asarray(answer, dtype=float))

    def score(self, instance_id, answer):
        target = self._load(instance_id)[3]
        a = np.asarray(answer, dtype=float)
        if a.shape != target.shape or not np.all(np.isfinite(a)):
            return 0.0
        spread = float(((target - target.mean()) ** 2).sum())
        if spread <= 0.0:
            return 0.0
        return float(np.clip(1.0 - ((a - target) ** 2).sum() / spread, 0.0, 1.0))
