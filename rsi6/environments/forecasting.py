"""Series of the M4 forecasting competition (hourly, weekly, yearly and quarterly files).

Published form: for every series, its history (the training file) and the real continuation
over the competition's horizon for its frequency (the test file). A forecast is scored against
the real continuation by the competition's symmetric mean absolute percentage error (sMAPE).
Reference: the real continuation, which the scorer alone reads. Threshold anchor: the sMAPE
the competition's organisers published for their Naive 2 benchmark.

Problem form: prediction. The observed entities are the points of the history (attribute: the
position in time, target: the value); the queries are the next positions. Histories longer
than 240 points are cut to their last 240. A fixed, seeded sample of 48 series per frequency
is used.
"""
from __future__ import annotations

import csv
import hashlib

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment
from rsi6.kernel.problem import PredictProblem

FREQUENCIES = ("Hourly", "Weekly", "Yearly", "Quarterly")
PER_FREQUENCY = 48
MAX_HISTORY = 240
# sMAPE of the organisers' Naive 2 benchmark per frequency, as published in the competition's
# "Evaluation and Ranks" table (read as data by an independent check on 2026-11-12).
NAIVE2 = {"Yearly": 16.34, "Quarterly": 11.01, "Weekly": 9.161, "Hourly": 18.38}


def smape(forecast: np.ndarray, actual: np.ndarray) -> float:
    return float(np.mean(200.0 * np.abs(forecast - actual) / (np.abs(forecast) + np.abs(actual) + 1e-12)))


def _rows(path: str) -> dict:
    out = {}
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row in reader:
            out[row[0]] = [float(x) for x in row[1:] if x not in ("", "NA")]
    return out


class Forecasting(Environment):
    name = category = "forecasting"
    form = "predict"
    anchor = "the published sMAPE of the competition's Naive 2 benchmark for the frequencies used"

    def __init__(self):
        fetch.fetch("forecasting", quiet=True)
        self.series, self.kind = {}, {}
        with open(fetch.path("forecasting", "M4-info.csv"), newline="") as handle:
            for row in csv.DictReader(handle):
                self.kind[row["M4id"]] = row["category"]
        for frequency in FREQUENCIES:
            history = _rows(fetch.path("forecasting", f"{frequency}-train.csv"))
            future = _rows(fetch.path("forecasting", f"{frequency}-test.csv"))
            chosen = sorted(history, key=lambda k: hashlib.sha256(f"m4|{k}".encode()).hexdigest())[:PER_FREQUENCY]
            for key in chosen:
                self.series[key] = (frequency, np.array(history[key][-MAX_HISTORY:]), np.array(future[key]))
        self.threshold = float(np.mean([1.0 - NAIVE2[f] / 200.0 for f, _, _ in self.series.values()]))

    def instance_ids(self):
        return sorted(self.series)

    def reference(self, instance_id):
        return self.series[instance_id][2].tolist()

    def group(self, instance_id):
        return self.kind[instance_id]                      # the competition's domain of the series

    def problem(self, instance_id, meter, seed, training):
        _, history, future = self.series[instance_id]
        t = len(history)
        problem = PredictProblem(np.arange(t, dtype=float)[:, None], history, np.arange(t, t + len(future), dtype=float)[:, None],
                                 ordered=True, target=future if training else None, meter=meter)
        return problem, (lambda answer: np.asarray(answer, dtype=float))

    def score(self, instance_id, answer):
        _, _, future = self.series[instance_id]
        a = np.asarray(answer, dtype=float)
        if a.shape != future.shape or not np.all(np.isfinite(a)):
            return 0.0
        return float(1.0 - min(smape(a, future), 200.0) / 200.0)
