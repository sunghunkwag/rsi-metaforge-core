"""Job-shop scheduling instances of JSPLIB.

Published form: J jobs, M machines; each job is a fixed sequence of M operations, each on a
given machine for a given time. A schedule is valid when every operation starts after the
job's previous operation has finished and no machine runs two operations at once; its cost is
the makespan, the time the last operation finishes. Reference: the optimum, or the best known
upper bound, published with each instance. Only instances whose optimum is proven in the
published table are used: an independent check of that table found upper bounds that are out of
date and one that contradicts another source.

Answer form: a sequence of J*M job indices in which every job appears M times. The k-th
appearance of a job stands for its k-th operation, and every operation starts as early as the
sequence allows (after the job's previous operation and after the operations already placed
on its machine). Every such sequence is a valid schedule, and some sequence gives an optimal
one, so there is no hard group.

Groups: [0] the makespan of the operations placed so far (soft); [1] the sum of the finishing
times of the operations placed so far (detail: the terms whose largest is the makespan).
"""
from __future__ import annotations

import json

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

MAX_OPERATIONS = 400          # instances larger than this are left out for run time


def parse(text: str):
    rows = [line.split() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    jobs, machines = int(rows[0][0]), int(rows[0][1])
    table = np.array([[int(x) for x in row] for row in rows[1:1 + jobs]])
    return table[:, 0::2].copy(), table[:, 1::2].astype(float)       # machine and duration of each step


def makespan(machine: np.ndarray, duration: np.ndarray, sequence) -> float:
    """The schedule of a sequence, by the rule in the module text. Plain reference code."""
    jobs = len(duration)
    done = [0] * jobs
    job_ready = [0.0] * jobs
    machine_ready = {}
    end = 0.0
    for j in sequence:
        k = done[j]
        m = machine[j][k]
        finish = max(job_ready[j], machine_ready.get(m, 0.0)) + duration[j][k]
        job_ready[j] = finish
        machine_ready[m] = finish
        done[j] = k + 1
        end = max(end, finish)
    return end


class JobShopProblem(AssignProblem):
    def __init__(self, machine: np.ndarray, duration: np.ndarray, meter):
        jobs, steps = duration.shape
        self.machine, self.duration = machine, duration
        self.n_machines = int(machine.max()) + 1
        super().__init__(n_vars=jobs * steps, n_opts=jobs, hard=[False, False], detail=[False, True], ordered=True,
                         capacity=np.full(jobs, steps), occ_attr=(duration,), meter=meter)

    def partial_totals(self, a):
        done = np.zeros(self.n_opts, dtype=int)
        job_ready = np.zeros(self.n_opts)
        machine_ready = np.zeros(self.n_machines)
        end = total = 0.0
        for j in a:
            if j < 0:
                break
            k = done[j]
            m = self.machine[j, k]
            finish = max(job_ready[j], machine_ready[m]) + self.duration[j, k]
            job_ready[j] = machine_ready[m] = finish
            done[j] += 1
            end = max(end, finish)
            total += finish
        return np.array([end, total])

    def _new(self):
        s = super()._new()
        s["job_ready"] = np.zeros(self.n_opts)
        s["machine_ready"] = np.zeros(self.n_machines)
        return s

    def _rows(self, s, variables):
        k = np.minimum(s["used"], self.duration.shape[1] - 1)
        jobs = np.arange(self.n_opts)
        m = self.machine[jobs, k]
        finish = np.maximum(s["job_ready"], s["machine_ready"][m]) + self.duration[jobs, k]
        out = np.empty((1, self.n_opts, 2))
        out[0, :, 0] = np.maximum(finish - s["tot"][0], 0.0)
        out[0, :, 1] = finish
        return out

    def _push(self, s, v, o):
        k = s["used"][o]
        m = self.machine[o, k]
        finish = max(s["job_ready"][o], s["machine_ready"][m]) + self.duration[o, k]
        s["job_ready"][o] = s["machine_ready"][m] = finish
        s["a"][v] = o
        s["tot"] = np.array([max(s["tot"][0], finish), s["tot"][1] + finish])


class JobShop(Environment):
    name = category = "jobshop"
    form = "assign"
    threshold = 0.85
    anchor = "a makespan within 1/0.85 of the published proven optimum, on average"

    def __init__(self):
        fetch.fetch("jobshop", quiet=True)
        self.index = {row["name"]: row for row in json.load(open(fetch.path("jobshop", "instances.json")))
                      if row["jobs"] * row["machines"] <= MAX_OPERATIONS and row.get("optimum") is not None}
        self._parsed = {}

    def instance_ids(self):
        return sorted(self.index)

    def _instance(self, instance_id):
        if instance_id not in self._parsed:
            self._parsed[instance_id] = parse(open(fetch.path("jobshop", self.index[instance_id]["path"])).read())
        return self._parsed[instance_id]

    def reference(self, instance_id):
        return float(self.index[instance_id]["optimum"])

    def group(self, instance_id):
        return instance_id.rstrip("0123456789")            # the family: abz, ft, la, orb, swv, ta, yn, dmu

    def problem(self, instance_id, meter, seed, training):
        machine, duration = self._instance(instance_id)
        rng = np.random.default_rng(seed)
        job_perm, _ = relabel(rng, duration.shape[0])              # new job index -> old job index
        machine_perm, machine_inv = relabel(rng, int(machine.max()) + 1)
        problem = JobShopProblem(machine_inv[machine[job_perm]], duration[job_perm], meter)
        return problem, (lambda answer: job_perm[np.asarray(answer, dtype=np.int64)])

    def score(self, instance_id, answer):
        machine, duration = self._instance(instance_id)
        jobs, steps = duration.shape
        a = np.asarray(answer)
        if a.shape != (jobs * steps,) or a.min() < 0 or a.max() >= jobs or np.any(np.bincount(a, minlength=jobs) != steps):
            return 0.0
        return float(min(1.0, self.reference(instance_id) / makespan(machine.tolist(), duration.tolist(), a.tolist())))
