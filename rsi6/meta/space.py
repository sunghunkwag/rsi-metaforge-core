"""The space of versions, presented to the learner in the assignment form.

A variable is one field of the version record; its options are the values the field can take
(the listed choices, or five evenly spaced values of a real range and its default). The current
version is the answer that is already known. The only term reads every variable: it is the
cost of the whole version, measured by the kernel on the source pool. So nothing can be said
about a partial version, and the learner has to work by changing the known answer.

One evaluation here is expensive: it is a set of complete acquisition runs. The meter of this
problem therefore counts measured CPU-seconds of those runs, not units.
"""
from __future__ import annotations

import numpy as np

from rsi6.kernel.problem import AssignProblem, Meter
from rsi6.learner import version as versions

FIELDS = versions.FIELDS


def grid(name: str) -> list:
    spec = versions.SCHEMA[name]
    if spec[0] == "choice":
        return list(spec[1])
    values = {round(float(x), 6) for x in np.linspace(spec[1], spec[2], 5)} | {round(float(spec[3]), 6)}
    return sorted(values)


GRIDS = [grid(name) for name in FIELDS]


def encode(version: dict) -> np.ndarray:
    out = np.zeros(len(FIELDS), dtype=np.int64)
    for k, name in enumerate(FIELDS):
        values = GRIDS[k]
        if versions.SCHEMA[name][0] == "choice":
            out[k] = values.index(version[name])
        else:
            out[k] = int(np.argmin([abs(v - float(version[name])) for v in values]))
    return out


def decode(answer) -> dict:
    return versions.validate({name: GRIDS[k][int(answer[k])] for k, name in enumerate(FIELDS)})


class VersionProblem(AssignProblem):
    """``cost(version) -> (cost, cpu_seconds)`` is supplied by the kernel; lower is better and
    the starting version costs 0 by definition."""

    def __init__(self, start: dict, cost, meter: Meter):
        domain = np.zeros((len(FIELDS), max(len(g) for g in GRIDS)), dtype=bool)
        for k, values in enumerate(GRIDS):
            domain[k, :len(values)] = True
        self._cost = cost
        self.seen = {}
        self.history = []
        first = encode(start)
        self.seen[tuple(first.tolist())] = 0.0
        super().__init__(n_vars=len(FIELDS), n_opts=domain.shape[1], hard=[False], ordered=False, domain=domain,
                         start_answer=first, start_totals=[0.0], meter=meter)

    def partial_totals(self, a):
        if np.any(a < 0):
            return np.array([0.0])
        return np.array([self.seen[tuple(np.asarray(a).tolist())]])

    def evaluate(self, answer):
        a = np.asarray(answer, dtype=np.int64)
        if not self.well_formed(a):
            raise ValueError("not a well-formed answer")
        key = tuple(a.tolist())
        if key in self.seen:
            self.meter.charge(1.0)                      # a repeated version costs next to nothing
        else:
            self.meter.charge(0.0)                      # raises if the budget is already spent
            value, cpu = self._cost(decode(a))
            self.seen[key] = float(value)
            self.history.append({"version": decode(a), "cost": float(value), "cpu": float(cpu)})
            self.meter.used += cpu                      # the evaluation that crosses the limit still counts
        return np.array([self.seen[key]])
