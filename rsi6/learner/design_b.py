"""The learner, second design.

The first design (``learner.py``, frozen as generation 0) fitted all weights of its policy at
once from a population of random policies. At the registered budget that gave it one to three
rounds of learning in six of seven categories, and it gained nothing on four of them. This
design changes how a capability is acquired, not what is measured:

* **One descriptor at a time.** The policy starts from the prior and is changed along one
  descriptor per test: a few values of that descriptor's weight are tried on a batch of training
  problems and compared, problem by problem, with the current policy. A change is kept only if
  it wins on more problems than it loses. Ten to twenty such tests fit where the first design
  had one population.
* **Descriptors that did not exist.** A test may be about a descriptor the learner builds
  itself, from descriptors it already has: the product of two, one multiplied by the progress of
  the construction, or a square. Built descriptors can be built upon. The ones that are kept
  are part of the capability, by their defining expression.
* **A proposal distribution.** With so few tests, the order in which descriptors are proposed
  decides what can be learned. The order is drawn from weights per family of descriptors and
  per kind of construction. These weights are fields of the version: they are what
  modifications of this design mostly act on.
* **Relative to the budget.** The number of variables shortlisted per step, the size of a test
  batch and the number of checks are derived from the budget and the sizes of the problems, so
  that a field means the same thing in every environment.
* **Self-assessment by prefix.** The states after each kept change are compared on the
  held-back problems, and the best one is returned: the start if nothing beats it.

The prediction form, the edits of a complete answer at test time, and the transfer of weights
by signature are those of the first design.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from rsi6.kernel.problem import BudgetExhausted
from rsi6.learner import version as versions_a
from rsi6.learner.learner import (Context, Layout, Learner, _finish_arbitrarily, _key, _opt_features, _var1_features,
                                  _var2_features)

FAMILIES = ("dsoft", "viol", "dhard", "group", "usage", "last", "rem", "var_opt", "opt_attr", "occ", "optsum",
            "ahead", "mem", "va", "vv", "var2", "built")
KINDS = ("mul", "prog", "sq")
WEIGHTS = (0.0, 0.5, 1.0, 2.0, 4.0)

# name: ("real", low, high, default) or ("choice", options, default)
SCHEMA = {
    "prior.dsoft": ("real", -4.0, 0.0, -1.0),
    "prior.dhard": ("real", -12.0, 0.0, -6.0),
    "feat.scale": ("choice", ("minmax", "z"), "minmax"),
    "shortlist": ("choice", (1, 2, 4), 4),
    "plan.min_tests": ("choice", (4, 8, 16, 32), 8),
    "plan.batch": ("real", 0.2, 1.0, 0.4),
    "plan.checks": ("choice", (2, 3, 5, 8), 5),
    "line.step": ("real", 0.25, 4.0, 1.0),
    "line.expand": ("choice", (0, 1), 1),
    "accept.margin": ("real", 0.0, 0.5, 0.0),
    "assess.holdback": ("real", 0.1, 0.5, 0.25),
    "assess.strict": ("choice", (0, 1), 1),
    **{f"pi.{family}": ("choice", WEIGHTS, 1.0) for family in FAMILIES},
    "new.share": ("real", 0.0, 0.6, 0.2),
    **{f"new.{kind}": ("choice", (0.0, 1.0, 2.0), 1.0) for kind in KINDS},
    "edit.reassign": ("choice", (0, 1), 1),
    "edit.swap": ("choice", (0, 1), 1),
    "edit.chain": ("choice", (1, 2, 3), 1),
    "edit.accept_equal": ("choice", (0, 1), 0),
    "edit.adaptive": ("choice", (0, 1), 0),
    "test.sampled": ("choice", (0, 1), 0),
    "test.temperature": ("real", 0.05, 1.0, 0.3),
    "transfer.on": ("choice", (0, 1), 1),
    "transfer.blend": ("real", 0.0, 1.0, 1.0),
    "predict.K": ("choice", (4, 8, 16, 32), 8),
    "predict.ridge": ("real", -3.0, 2.0, 0.0),
    "predict.selfsup": ("choice", (0, 1), 0),
    "predict.diff": ("choice", (0, 1), 0),
    "predict.attrs": ("choice", (0, 1), 1),
}
FIELDS = tuple(SCHEMA)
FUNCTION_OF = {"prior": "model", "line": "model", "accept": "model", "feat": "represent", "pi": "represent",
               "new": "represent", "shortlist": "decide", "plan": "decide", "test": "decide", "edit": "compose",
               "assess": "self-assess", "transfer": "consolidate", "predict": "represent/model"}


def default() -> dict:
    return dict({name: spec[-1] for name, spec in SCHEMA.items()}, design="b")


def validate(version: dict) -> dict:
    if version.get("design") != "b" or set(version) != set(SCHEMA) | {"design"}:
        raise ValueError(f"version fields differ from the schema: {sorted(set(version) ^ (set(SCHEMA) | {'design'}))}")
    out = {"design": "b"}
    for name, spec in SCHEMA.items():
        value = version[name]
        if spec[0] == "real":
            value = float(value)
            if not spec[1] <= value <= spec[2]:
                raise ValueError(f"{name}={value} outside [{spec[1]}, {spec[2]}]")
        elif value not in spec[1]:
            raise ValueError(f"{name}={value!r} not one of {spec[1]}")
        out[name] = value
    return out


def digest(version: dict) -> str:
    text = json.dumps(validate(version), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    return {name: {"from": a[name], "to": b[name], "function": FUNCTION_OF[name.split(".")[0]]}
            for name in FIELDS if a[name] != b[name]}


def family(name: str) -> str:
    """The family of a descriptor, from its name."""
    part, _, rest = name.partition(":")
    if part == "var2":
        return "var2"
    if part == "var1":
        return "va" if rest.startswith("va[") else "vv"
    head = rest.split("[")[0].split("(")[0]
    return {"dsoft": "dsoft", "viol": "viol", "dhard": "dhard", "d": "group", "usage": "usage", "last": "last",
            "rem": "rem", "vo": "var_opt", "oa": "opt_attr", "next": "occ", "left": "occ", "optsum": "optsum",
            "ahead": "ahead", "mem": "mem",
            "mul": "built", "prog": "built", "sq": "built"}[head]


def _split(expr: str) -> tuple:
    """``kind`` and operand names of a built descriptor's expression, e.g. ``mul(dsoft,usage)``."""
    kind, _, inner = expr.partition("(")
    inner, depth, parts, start = inner[:-1], 0, [], 0
    for k, ch in enumerate(inner):
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(inner[start:k])
            start = k + 1
    parts.append(inner[start:])
    return kind, parts


class ExtLayout:
    """The descriptors of the first design, all present, and built option descriptors after them."""

    def __init__(self, problem, version: dict, built=()):
        base = dict(versions_a.default(), **{"feat.scale": version["feat.scale"]})
        self.base = Layout(problem, base)
        # aggregates over the problem's own relations, defined for any problem that has the relation:
        # ahead[r]: the mean of relation r between an option and the variables not yet assigned
        # mem[r]:   the sum of relation r between the variable and the variables already on an option
        self.n_ahead = len(problem.var_opt)
        self.n_mem = len(problem.var_var) if self.base.reusable else 0
        self.opt_names = list(self.base.opt_names) + [f"ahead[{r}]" for r in range(self.n_ahead)] + \
            [f"mem[{r}]" for r in range(self.n_mem)]
        self.n_fixed = len(self.opt_names)
        self.plan = []                                   # (kind, column, column) of every built descriptor, in order
        self.n_var1, self.n_var2 = self.base.n_var1, self.base.n_var2
        for expr in built:
            self.add(expr)

    def add(self, expr: str) -> bool:
        """Add a built descriptor. False if it exists already or an operand is unknown here."""
        if expr in self.opt_names:
            return False
        kind, parts = _split(expr)
        if kind not in KINDS or any(p not in self.opt_names for p in parts):
            return False
        cols = [self.opt_names.index(p) for p in parts]
        self.plan.append((kind, cols[0], cols[-1]))
        self.opt_names.append(expr)
        return True

    @property
    def names(self) -> list:
        return [f"opt:{n}" for n in self.opt_names] + [f"var1:{n}" for n in self.base.var1_names] + \
               [f"var2:{n}" for n in self.base.var2_names]

    @property
    def n_opt(self) -> int:
        return len(self.opt_names)

    @property
    def size(self) -> int:
        return self.n_opt + self.n_var1 + self.n_var2

    def vector(self, weights: dict) -> np.ndarray:
        return np.array([float(weights.get(name, 0.0)) for name in self.names])

    def weights(self, theta: np.ndarray) -> dict:
        return {name: float(t) for name, t in zip(self.names, theta) if t != 0.0}

    def prior(self, version: dict) -> np.ndarray:
        return self.vector({"opt:dsoft": version["prior.dsoft"], "opt:viol": version["prior.dhard"],
                            "opt:dhard": 0.5 * version["prior.dhard"]})

    def features(self, P, ctx, more, s, v, Dv, allowed, step) -> np.ndarray:
        F = _opt_features(P, self.base, ctx, s, v, Dv, allowed, step)
        if self.n_fixed == F.shape[1] and not self.plan:
            return F
        tf = self.base.transform
        progress = 2.0 * step / max(P.n_vars - 1, 1) - 1.0
        cols = [F[:, k] for k in range(F.shape[1])]
        for r in range(self.n_ahead):
            cols.append(tf(more.ahead[r] / max(more.open, 1.0), allowed))
        for r in range(self.n_mem):
            cols.append(tf(more.mem[r][v], allowed))
        for kind, a, b in self.plan:
            cols.append(cols[a] * cols[b] if kind == "mul" else cols[a] * progress if kind == "prog" else cols[a] * cols[a])
        return np.column_stack(cols)


class More:
    """Running aggregates of one construction for the descriptors this design adds."""

    def __init__(self, P, lay: ExtLayout):
        self.open = float(P.n_vars)
        self.ahead = [R.sum(axis=0).astype(float) for R in P.var_opt[:lay.n_ahead]]
        self.mem = [np.zeros((P.n_vars, P.n_opts)) for _ in range(lay.n_mem)]

    def update(self, P, v: int, o: int) -> None:
        self.open -= 1.0
        for r in range(len(self.ahead)):
            self.ahead[r] -= P.var_opt[r][v]
        for r in range(len(self.mem)):
            self.mem[r][:, o] += P.var_var[r][:, v]


def construct(P, lay: ExtLayout, theta: np.ndarray, rng, shortlist: int, temperature: float = 0.0, hold=None):
    """One construction under the policy ``theta`` (the procedure of the first design, with the
    built descriptors added to the option descriptors)."""
    base = lay.base
    t_opt = theta[:lay.n_opt]
    t_v1 = theta[lay.n_opt:lay.n_opt + lay.n_var1]
    t_v2 = theta[lay.n_opt + lay.n_var1:]
    s = P.start()
    if hold is not None:
        hold.append(s)
    ctx = Context(P, base)
    more = More(P, lay)
    for step in range(P.n_vars):
        U = P.unassigned(s)
        allowed = P.allowed(s)
        if len(U) > 1:
            score = _var1_features(P, base, ctx, U) @ t_v1 if lay.n_var1 else np.zeros(len(U))
            score = score + 1e-9 * rng.random(len(U))
            if len(U) > shortlist:
                pick = np.argpartition(-score, shortlist - 1)[:shortlist]
                pick = pick[np.argsort(-score[pick], kind="stable")]
            else:
                pick = np.argsort(-score, kind="stable")
            short, score = U[pick], score[pick]
            D = P.candidates(s, short)
            if len(short) > 1 and lay.n_var2:
                score = score + _var2_features(base, D, allowed) @ t_v2
            i = int(np.argmax(score))
            v, Dv = int(short[i]), D[i]
        else:
            v = int(U[0])
            Dv = P.candidates(s, U)[0]
        if P.domain is not None:
            allowed = allowed & P.domain[v]
        value = lay.features(P, ctx, more, s, v, Dv, allowed, step) @ t_opt
        value = np.where(allowed, value + 1e-9 * rng.random(P.n_opts), -np.inf)
        if temperature > 0.0:
            logits = (value - value[allowed].max()) / temperature
            prob = np.where(allowed, np.exp(logits), 0.0)
            o = int(rng.choice(P.n_opts, p=prob / prob.sum()))
        else:
            o = int(np.argmax(value))
        P.assign(s, v, o)
        ctx.update(P, base, s, v, o)
        more.update(P, v, o)
    return P.totals(s), P.assignment(s)


class LearnerB(Learner):
    def __init__(self, version: dict):
        self.v = validate(version)
        self.trace = {}

    # ---- the assignment form ------------------------------------------------------------------
    @staticmethod
    def _unit(P, shortlist: int) -> float:
        factor = shortlist if not P.ordered else 1
        return float(factor * P.n_vars * P.n_opts + P.n_vars + 1)

    def _keys(self, problems, layouts, idx, theta, shortlist, seeds, meter):
        """Keys of one policy on the problems ``idx`` (same random draws for every policy), or
        ``None`` if the budget does not allow them all."""
        if meter.left() < sum(self._unit(problems[i], shortlist) for i in idx):
            return None
        out = []
        for i in idx:
            totals, _ = construct(problems[i], layouts[i], theta, np.random.default_rng(seeds[i]), shortlist)
            out.append(_key(totals, problems[i]))
        return out

    def _acquire_assign(self, problems, rng, memory):
        v = self.v
        meter = problems[0].meter
        n = len(problems)
        order = rng.permutation(n)
        n_check = min(max(1, int(round(v["assess.holdback"] * n))), n - 1) if n > 1 else 0
        check, fit = [int(i) for i in order[:n_check]], [int(i) for i in order[n_check:]]
        recalled = self._recall(problems[0], memory) if (v["transfer.on"] and memory.get("entries")) else None
        built0 = list((recalled or {}).get("built", [])) if isinstance(recalled, dict) else []
        layouts = [ExtLayout(P, v, built0) for P in problems]
        lay0 = layouts[0]
        theta = lay0.prior(v)
        if recalled is not None:
            theta = (1.0 - v["transfer.blend"]) * theta + v["transfer.blend"] * lay0.vector(recalled.get("weights", recalled))
        seeds = [int(x) for x in rng.integers(2 ** 31, size=n)]
        report = {"form": "assign", "design": "b", "fit": len(fit), "held_back": len(check), "tests": 0, "kept": 0,
                  "iterations": 0, "constructions": 0, "transferred": recalled is not None, "failed": None, "kept_names": []}
        # the plan: the widest shortlist with which the wanted number of tests fits
        total = meter.left()
        batch = min(len(fit), max(2, int(round(v["plan.batch"] * len(fit))))) if fit else 0
        values = 2 + int(v["line.expand"])
        shortlist = int(v["shortlist"])
        while True:
            fit_mean = float(np.mean([self._unit(problems[i], shortlist) for i in fit])) if fit else 1.0
            reserve = v["plan.checks"] * sum(self._unit(problems[i], shortlist) for i in check)
            affordable = (total - reserve) / max((values + 0.5) * batch * fit_mean, 1.0)
            if affordable >= v["plan.min_tests"] or shortlist == 1 or problems[0].ordered:
                break
            shortlist //= 2
        report["shortlist"], report["batch"], report["affordable_tests"] = shortlist, batch, float(affordable)
        states = [theta.copy()]                    # the start and the state after every kept change
        tested = {}                                # descriptor name -> number of tests
        cache = {}                                 # keys of the current policy by problem
        step0 = float(v["line.step"])
        try:
            while fit and lay0.size > 0:
                names = lay0.names
                # ---- what to test: a descriptor that exists, or one built now
                j = None
                opt_names = lay0.opt_names
                if rng.random() < v["new.share"] and len(opt_names) >= 1:
                    kinds = [k for k in KINDS if v[f"new.{k}"] > 0]
                    if kinds:
                        w = np.array([v[f"new.{k}"] for k in kinds], dtype=float)
                        kind = kinds[int(rng.choice(len(kinds), p=w / w.sum()))]
                        act = np.abs(theta[:lay0.n_opt]) + 0.25
                        a = opt_names[int(rng.choice(lay0.n_opt, p=act / act.sum()))]
                        b = opt_names[int(rng.choice(lay0.n_opt, p=act / act.sum()))]
                        expr = f"mul({min(a, b)},{max(a, b)})" if kind == "mul" else f"{kind}({a})"
                        if (kind != "mul" or a != b) and expr not in opt_names and v["pi.built"] > 0:
                            for lay in layouts:
                                lay.add(expr)
                            at = lay0.n_opt - 1
                            theta = np.insert(theta, at, 0.0)
                            states = [np.insert(t, at, 0.0) for t in states]
                            j, names = at, lay0.names
                if j is None:
                    w = np.array([v[f"pi.{family(name)}"] / (1.0 + tested.get(name, 0)) for name in names], dtype=float)
                    if w.sum() <= 0.0:
                        break
                    j = int(rng.choice(len(names), p=w / w.sum()))
                name = names[j]
                # ---- one test: a few values of this weight, compared with the current policy problem by problem
                idx = [fit[i] for i in rng.choice(len(fit), size=batch, replace=False)]
                missing = [i for i in idx if i not in cache]
                need = (len(missing) + 2 * len(idx)) * max(self._unit(problems[i], shortlist) for i in idx)
                if meter.left() - reserve < need:
                    break
                if missing:
                    got = self._keys(problems, layouts, missing, theta, shortlist, seeds, meter)
                    cache.update(dict(zip(missing, got)))
                    report["constructions"] += len(missing)
                current = [cache[i] for i in idx]
                best_net, best_delta, best_keys = 0.0, None, None
                step = step0 * max(1.0, abs(theta[j]) * 0.5)
                tried = [+step, -step]
                k = 0
                while k < len(tried):
                    trial = theta.copy()
                    trial[j] += tried[k]
                    if meter.left() - reserve < len(idx) * max(self._unit(problems[i], shortlist) for i in idx):
                        break
                    keys = self._keys(problems, layouts, idx, trial, shortlist, seeds, meter)
                    report["constructions"] += len(idx)
                    net = (sum(a < b for a, b in zip(keys, current)) - sum(a > b for a, b in zip(keys, current))) / len(idx)
                    if net > best_net:
                        best_net, best_delta, best_keys = net, tried[k], keys
                        if v["line.expand"] and len(tried) == 2:
                            tried.append(2.0 * tried[k])       # the winning direction, once more and further
                    k += 1
                tested[name] = tested.get(name, 0) + 1
                report["tests"] += 1
                if best_delta is not None and best_net > v["accept.margin"]:
                    theta[j] += best_delta
                    cache = dict(zip(idx, best_keys))
                    states.append(theta.copy())
                    report["kept"] += 1
                    report["kept_names"].append(name)
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended inside a construction"
        report["iterations"] = report["tests"]
        # ---- self-assessment: the states after kept changes, on the held-back problems
        chosen, learned = 0, False
        if len(states) == 1:
            report["failed"] = report["failed"] or "model: no change of the policy won on its test batch"
        elif n_check == 0:
            chosen, learned = len(states) - 1, True
        else:
            picks = sorted({0, len(states) - 1} | {int(round(x)) for x in np.linspace(0, len(states) - 1, int(v["plan.checks"]))})
            try:
                rows = []
                for p in picks:
                    keys = self._keys(problems, layouts, check, states[p], shortlist, seeds, meter)
                    if keys is None:
                        break
                    rows.append(keys)
                    report["constructions"] += len(check)
                if len(rows) < 2:
                    report["failed"] = "decide: no budget left for the held-back check"
                else:
                    f = Learner._fitness(np.array(rows, dtype=float))
                    top = int(np.argmax(f))                                   # ties: the earlier state
                    report["held_back_states"] = {"states": picks[:len(rows)], "fitness": f.tolist()}
                    if top > 0 and (f[top] > f[0] or not v["assess.strict"]):
                        chosen, learned = picks[top], True
                    else:
                        report["failed"] = "model: no state beat the start on the held-back problems"
            except BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
        report["learned"] = learned
        final = states[chosen]
        weights = lay0.weights(final)
        kept_built = [n for n in lay0.opt_names[lay0.n_fixed:] if self._needed(n, weights, lay0)]
        report["built"] = kept_built
        return {"kind": "assign", "design": "b", "weights": weights, "built": kept_built, "learned": learned}, report

    @staticmethod
    def _needed(expr: str, weights: dict, lay: ExtLayout) -> bool:
        """A built descriptor is kept if it has a weight, or if a kept one is built from it."""
        if weights.get(f"opt:{expr}", 0.0) != 0.0:
            return True
        return any(expr in _split(other)[1] and LearnerB._needed(other, weights, lay)
                   for other in lay.opt_names[lay.n_fixed:] if other != expr)

    def _recall(self, P, memory: dict):
        """The most similar earlier assignment capability (weights and built descriptors), if any."""
        sig, best, score = self._signature(P), None, 0
        for entry in memory.get("entries", []):
            other, cap = entry["signature"], entry["capability"]
            if other.get("kind") != "assign" or cap.get("kind") != "assign":
                continue
            same = sum(1 for k, val in sig.items() if other.get(k) == val)
            if same >= score:
                best, score = {"weights": cap["weights"], "built": cap.get("built", [])}, same
        return best

    def _apply_assign(self, capability, P, rng):
        v = self.v
        best, best_key = None, None
        if P.start_answer is not None:
            best = P.start_answer.copy()
            try:
                totals = P.start_totals if P.start_totals is not None else P.evaluate(best)
            except BudgetExhausted:
                return best
            best_key = _key(totals, P)
        else:
            lay = ExtLayout(P, v, (capability or {}).get("built", []))
            theta = lay.vector(capability["weights"]) if capability else lay.prior(v)
            shortlist = int(v["shortlist"])
            if not P.ordered:
                while shortlist > 1 and self._unit(P, shortlist) > P.meter.left():
                    shortlist //= 2
            hold = []
            try:
                totals, answer = construct(P, lay, theta, rng, shortlist, hold=hold)
                best, best_key = answer, _key(totals, P)
            except BudgetExhausted:
                return _finish_arbitrarily(P, hold[0] if hold else None)
            try:
                if v["test.sampled"]:
                    while P.meter.left() > 2 * self._unit(P, shortlist):
                        totals, answer = construct(P, lay, theta, rng, shortlist, temperature=float(v["test.temperature"]))
                        key = _key(totals, P)
                        if key < best_key:
                            best, best_key = answer, key
            except BudgetExhausted:
                return best
        return self._improve(capability, P, rng, best, best_key)
