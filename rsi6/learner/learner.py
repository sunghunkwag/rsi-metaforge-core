"""The learner L: one program for every environment.

``acquire`` receives training problems in one of the kernel's two generic forms and returns a
capability (plain data), an updated memory and a self-report. ``apply`` answers one new problem
with a capability, or with none (the learner's uninformed behaviour). Nothing here knows what
an environment is about: the code reads only the generic arrays of the problem forms.

What is learned, for the assignment form: the weights of a constructive policy. The learner
builds an answer one variable at a time; for each option of the variable it computes generic
descriptors (the exact change of the soft and hard totals, how used the option is, how the
option relates to the previous one and to the remaining ones, attributes), and takes the
option with the highest weighted sum. For problems whose variables are free in order it also
weighs which variable to assign next. The weights are found by interaction with the training
problems and checked on held-back ones. For the prediction form: a linear fit with a ridge
penalty from generic descriptors of a query (targets of nearby observed entities, its own attributes) to
its target.

Every choice of method below is read from the version record (``version.py``), which is what
modifications change.
"""
from __future__ import annotations

import numpy as np

from rsi6.kernel.problem import BudgetExhausted
from rsi6.learner import version as versions

TINY = 1e-12


def _z(x: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Standardise over the masked entries; a constant column becomes zeros."""
    if mask is None:
        m, s = x.mean(), x.std()
    else:
        if not mask.any():
            return np.zeros_like(x, dtype=float)
        sel = x[mask]
        m, s = sel.mean(), sel.std()
    if not np.isfinite(s) or s < TINY:
        return np.zeros_like(x, dtype=float)
    return (x - m) / s


def _zc(x: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Standardised and clipped to three standard deviations, so that one rare value cannot
    outweigh every other descriptor."""
    return np.clip(_z(x, mask), -3.0, 3.0)


def _mm(x: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Scaled to [0, 1] over the masked entries; a constant column becomes zeros."""
    sel = x if mask is None else x[mask]
    if sel.size == 0:
        return np.zeros_like(x, dtype=float)
    lo, hi = sel.min(), sel.max()
    if not np.isfinite(hi - lo) or hi - lo < TINY:
        return np.zeros_like(x, dtype=float)
    return (x - lo) / (hi - lo)




def _rank(x: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Ranks scaled to [-1, 1] over the masked entries (zeros elsewhere)."""
    out = np.zeros_like(x, dtype=float)
    idx = np.arange(len(x)) if mask is None else np.flatnonzero(mask)
    if len(idx) < 2:
        return out
    order = np.argsort(x[idx], kind="stable")
    ranks = np.empty(len(idx))
    ranks[order] = np.arange(len(idx))
    out[idx] = 2.0 * ranks / (len(idx) - 1) - 1.0
    return out


def _key(totals: np.ndarray, P) -> tuple:
    """Lexicographic cost of group totals: hard violations first, then the soft total. Detail
    groups are not part of the cost."""
    return (float(totals[P.hard].sum()), float(totals[~P.hard & ~P.detail].sum()))


class Layout:
    """Names and builders of the descriptors of one assignment problem under one version."""

    def __init__(self, problem, version: dict):
        P, v = problem, version
        self.hard = P.hard
        self.soft = ~P.hard & ~P.detail
        self.any_soft, self.any_hard = bool(self.soft.any()), bool(P.hard.any())
        self.transform = {"minmax": _mm, "z": _zc, "rank": _rank}[v["feat.scale"]]
        self.limited = P.capacity is not None
        self.reusable = P.capacity is None or int(P.capacity.max()) > 1
        opt = []
        if self.any_soft:
            opt.append("dsoft")
        if self.any_hard:
            opt += ["viol", "dhard"]
        self.per_group = bool(v["feat.per_group"]) and P.n_groups > int(self.soft.sum() > 0) + int(self.any_hard)
        if self.per_group:
            opt += [f"d[{g}]" for g in range(P.n_groups)]
        self.usage = bool(v["feat.usage"]) and self.reusable
        if self.usage:
            opt.append("usage")
        self.last = bool(v["feat.last"]) and len(P.opt_opt) > 0
        if self.last:
            opt += [f"last[{r}]" for r in range(len(P.opt_opt))]
        self.rem = bool(v["feat.rem"]) and len(P.opt_opt) > 0 and self.limited
        if self.rem:
            opt += [f"rem[{r}]" for r in range(len(P.opt_opt))]
        self.var_opt = bool(v["feat.var_opt"]) and len(P.var_opt) > 0
        if self.var_opt:
            opt += [f"vo[{r}]" for r in range(len(P.var_opt))]
        self.opt_attr = bool(v["feat.opt_attr"]) and P.opt_attr.shape[1] > 0
        if self.opt_attr:
            opt += [f"oa[{c}]" for c in range(P.opt_attr.shape[1])]
        self.occ = bool(v["feat.occ"]) and len(P.occ_attr) > 0
        if self.occ:
            for r in range(len(P.occ_attr)):
                opt += [f"next[{r}]", f"left[{r}]"]
        self.optsum = bool(v["feat.optsum"]) and self.reusable and P.var_attr.shape[1] > 0
        if self.optsum:
            opt += [f"optsum[{c}]" for c in range(P.var_attr.shape[1])]
        self.templates = []
        for slot in ("feat.template1", "feat.template2"):
            name = v[slot]
            if name != "none" and name not in self.templates and self._template_ok(name, opt):
                self.templates.append(name)
        opt += self.templates
        self.opt_names = opt
        self.free = not P.ordered
        self.var1_names = []
        if self.free:
            self.var1_names += [f"va[{c}]" for c in range(P.var_attr.shape[1])]
            for r in range(len(P.var_var)):
                self.var1_names += [f"vv_done[{r}]", f"vv_open[{r}]"]
        self.var2_names = ["feasible", "best", "regret"] if self.free else []
        self.names = [f"opt:{n}" for n in self.opt_names] + [f"var1:{n}" for n in self.var1_names] + \
                     [f"var2:{n}" for n in self.var2_names]
        self.n_opt, self.n_var1, self.n_var2 = len(self.opt_names), len(self.var1_names), len(self.var2_names)
        self.size = len(self.names)
        self.static_oa = np.column_stack([self.transform(P.opt_attr[:, c]) for c in range(P.opt_attr.shape[1])]) \
            if self.opt_attr else None
        self.static_va = np.column_stack([self.transform(P.var_attr[:, c]) for c in range(P.var_attr.shape[1])]) \
            if self.free and P.var_attr.shape[1] > 0 else None

    @staticmethod
    def _template_ok(name: str, opt: list) -> bool:
        need = {"dsoft*progress": ["dsoft"], "dhard*progress": ["dhard"], "dsoft*usage": ["dsoft", "usage"],
                "last0*progress": ["last[0]"], "rem0*progress": ["rem[0]"], "dsoft*last0": ["dsoft", "last[0]"],
                "abs_dsoft": ["dsoft"]}[name]
        return all(n in opt for n in need)

    def vector(self, weights: dict) -> np.ndarray:
        """Weights by descriptor name, as a parameter vector (unknown names are ignored)."""
        theta = np.zeros(self.size)
        for i, name in enumerate(self.names):
            theta[i] = float(weights.get(name, 0.0))
        return theta

    def weights(self, theta: np.ndarray) -> dict:
        return {name: float(theta[i]) for i, name in enumerate(self.names)}

    def prior(self, version: dict) -> np.ndarray:
        return self.vector({"opt:dsoft": version["prior.dsoft"], "opt:viol": version["prior.dhard"],
                            "opt:dhard": 0.5 * version["prior.dhard"]})


class Context:
    """Running aggregates of one construction, kept by the learner."""

    def __init__(self, P, layout: Layout):
        self.prev = -1
        self.rem_sum = [R.sum(axis=1).astype(float) for R in P.opt_opt] if layout.rem else None
        self.rem_count = float(P.n_opts)
        self.done = [np.zeros(P.n_vars) for _ in P.var_var] if layout.free else None
        self.row = [R.sum(axis=1).astype(float) for R in P.var_var] if layout.free else None
        self.left = [A.sum(axis=1).astype(float) for A in P.occ_attr] if layout.occ else None
        self.optsum = np.zeros((P.n_opts, P.var_attr.shape[1])) if layout.optsum else None

    def update(self, P, layout: Layout, s: dict, v: int, o: int) -> None:
        self.prev = o
        if self.rem_sum is not None and s["used"][o] >= P.capacity[o]:
            for r, R in enumerate(P.opt_opt):
                self.rem_sum[r] -= R[:, o]
            self.rem_count -= 1.0
        if self.done is not None:
            for r, R in enumerate(P.var_var):
                self.done[r] += R[:, v]
        if self.left is not None:
            k = int(s["used"][o]) - 1
            for r, A in enumerate(P.occ_attr):
                if k < A.shape[1]:
                    self.left[r][o] -= A[o, k]
        if self.optsum is not None:
            self.optsum[o] += P.var_attr[v]


def _opt_features(P, layout: Layout, ctx: Context, s: dict, v: int, D: np.ndarray, allowed: np.ndarray,
                  step: int) -> np.ndarray:
    tf = layout.transform
    cols, by = [], {}

    def add(name, col):
        by[name] = col
        cols.append(col)

    if layout.any_soft:
        add("dsoft", tf(D[:, layout.soft].sum(axis=1), allowed))
    if layout.any_hard:
        # a hard total keeps its zero: "no new violation" must stay distinguishable from "a small one"
        amount = D[:, layout.hard].sum(axis=1)
        top = amount[allowed].max() if allowed.any() else 0.0
        add("viol", (amount > TINY).astype(float))
        add("dhard", amount / top if top > TINY else np.zeros(P.n_opts))
    if layout.per_group:
        for g in range(P.n_groups):
            cols.append(tf(D[:, g], allowed))
    if layout.usage:
        add("usage", tf(s["used"].astype(float), allowed))
    if layout.last:
        for r, R in enumerate(P.opt_opt):
            add(f"last[{r}]", tf(R[ctx.prev], allowed) if ctx.prev >= 0 else np.zeros(P.n_opts))
    if layout.rem:
        for r in range(len(P.opt_opt)):
            add(f"rem[{r}]", tf(ctx.rem_sum[r] / max(ctx.rem_count, 1.0), allowed))
    if layout.var_opt:
        for C in P.var_opt:
            cols.append(tf(C[v], allowed))
    if layout.opt_attr:
        cols.extend(layout.static_oa.T)
    if layout.occ:
        used = s["used"]
        for r, A in enumerate(P.occ_attr):
            k = np.minimum(used, A.shape[1] - 1)
            nxt = np.where(used < A.shape[1], A[np.arange(P.n_opts), k], 0.0)
            cols.append(tf(nxt, allowed))
            cols.append(tf(ctx.left[r], allowed))
    if layout.optsum:
        for c in range(ctx.optsum.shape[1]):
            cols.append(tf(ctx.optsum[:, c], allowed))
    if layout.templates:
        progress = 2.0 * step / max(P.n_vars - 1, 1) - 1.0
        for name in layout.templates:
            if name == "dsoft*progress":
                cols.append(by["dsoft"] * progress)
            elif name == "dhard*progress":
                cols.append(by["dhard"] * progress)
            elif name == "dsoft*usage":
                cols.append(by["dsoft"] * by["usage"])
            elif name == "last0*progress":
                cols.append(by["last[0]"] * progress)
            elif name == "rem0*progress":
                cols.append(by["rem[0]"] * progress)
            elif name == "dsoft*last0":
                cols.append(by["dsoft"] * by["last[0]"])
            elif name == "abs_dsoft":
                cols.append(np.abs(by["dsoft"]))
    return np.column_stack(cols) if cols else np.zeros((P.n_opts, 0))


def _var1_features(P, layout: Layout, ctx: Context, U: np.ndarray) -> np.ndarray:
    cols = []
    if layout.static_va is not None:
        cols.extend(layout.static_va[U].T)
    for r in range(len(P.var_var)):
        done = ctx.done[r][U]
        cols.append(layout.transform(done))
        cols.append(layout.transform(ctx.row[r][U] - done))
    return np.column_stack(cols) if cols else np.zeros((len(U), 0))


def _var2_features(layout: Layout, D: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """From the exact changes of the shortlisted variables: how many options stay free of a hard
    violation, the best combined change, and the gap to the second best."""
    hard = D[:, :, layout.hard].sum(axis=2) if layout.any_hard else np.zeros(D.shape[:2])
    soft = D[:, :, layout.soft].sum(axis=2) if layout.any_soft else np.zeros(D.shape[:2])
    feasible = ((hard <= TINY) & allowed[None, :]).sum(axis=1).astype(float)
    scale = np.abs(soft[:, allowed]).max() + 1.0 if allowed.any() else 1.0
    combined = np.where(allowed[None, :], hard * 4.0 * scale + soft, np.inf)
    part = np.sort(combined, axis=1)
    best = part[:, 0]
    second = part[:, 1] if part.shape[1] > 1 else part[:, 0]
    regret = np.where(np.isfinite(second), second - best, 0.0)
    return np.column_stack([layout.transform(feasible), layout.transform(best), layout.transform(regret)])


def construct(P, layout: Layout, theta: np.ndarray, rng, shortlist: int, temperature: float = 0.0, hold=None):
    """One construction under the policy ``theta``. Returns ``(totals, answer)``. Raises
    ``BudgetExhausted`` if the meter runs out; ``hold`` (a list) then holds the unfinished state."""
    t_opt = theta[:layout.n_opt]
    t_v1 = theta[layout.n_opt:layout.n_opt + layout.n_var1]
    t_v2 = theta[layout.n_opt + layout.n_var1:]
    s = P.start()
    if hold is not None:
        hold.append(s)
    ctx = Context(P, layout)
    for step in range(P.n_vars):
        U = P.unassigned(s)
        allowed = P.allowed(s)
        if len(U) > 1:
            score = _var1_features(P, layout, ctx, U) @ t_v1 if layout.n_var1 else np.zeros(len(U))
            score = score + 1e-9 * rng.random(len(U))
            if len(U) > shortlist:
                pick = np.argpartition(-score, shortlist - 1)[:shortlist]
                pick = pick[np.argsort(-score[pick], kind="stable")]
            else:
                pick = np.argsort(-score, kind="stable")
            short, score = U[pick], score[pick]
            D = P.candidates(s, short)
            if len(short) > 1 and layout.n_var2:
                score = score + _var2_features(layout, D, allowed) @ t_v2
            i = int(np.argmax(score))
            v, Dv = int(short[i]), D[i]
        else:
            v = int(U[0])
            Dv = P.candidates(s, U)[0]
        value = _opt_features(P, layout, ctx, s, v, Dv, allowed, step) @ t_opt
        value = np.where(allowed, value + 1e-9 * rng.random(P.n_opts), -np.inf)
        if temperature > 0.0:
            logits = (value - value[allowed].max()) / temperature
            prob = np.where(allowed, np.exp(logits), 0.0)
            o = int(rng.choice(P.n_opts, p=prob / prob.sum()))
        else:
            o = int(np.argmax(value))
        P.assign(s, v, o)
        ctx.update(P, layout, s, v, o)
    return P.totals(s), P.assignment(s)


def _finish_arbitrarily(P, s: dict | None) -> np.ndarray:
    """A well-formed answer from an unfinished state, without any evaluation."""
    a = np.full(P.n_vars, -1, dtype=np.int64) if s is None else s["a"].copy()
    used = np.bincount(a[a >= 0], minlength=P.n_opts)
    o = 0
    for v in np.flatnonzero(a < 0):
        if P.capacity is not None:
            while used[o] >= P.capacity[o]:
                o += 1
        a[v] = o
        used[o] += 1
        if P.capacity is None:
            o = (o + 1) % P.n_opts
    return a


def _edit(P, version: dict, a: np.ndarray, rng) -> np.ndarray | None:
    """One random composite change of a complete answer that keeps it well formed."""
    kinds = []
    reusable = P.capacity is None or int(P.capacity.max()) > 1
    if version["edit.reassign"] and reusable:
        kinds.append("reassign")
    if version["edit.swap"]:
        kinds.append("swap")
    if version["edit.reverse"]:
        kinds.append("reverse")
    if version["edit.move"]:
        kinds.append("move")
    if not kinds or P.n_vars < 2:
        return None
    kind = kinds[int(rng.integers(len(kinds)))]
    b = a.copy()
    i, j = (int(x) for x in rng.choice(P.n_vars, size=2, replace=False))
    if kind == "reassign":
        o = int(rng.integers(P.n_opts))
        if o == b[i]:
            return None
        if P.capacity is not None and np.count_nonzero(b == o) >= P.capacity[o]:
            return None
        b[i] = o
    elif kind == "swap":
        if b[i] == b[j]:
            return None
        b[i], b[j] = b[j], b[i]
    elif kind == "reverse":
        lo, hi = min(i, j), max(i, j)
        b[lo:hi + 1] = b[lo:hi + 1][::-1].copy()
    else:
        moved = b[i]
        b = np.delete(b, i)
        b = np.insert(b, j if j < len(b) else len(b), moved)
    return b


class Learner:
    def __init__(self, version: dict):
        self.v = versions.validate(version)

    # ---- the contract ---------------------------------------------------------------------
    def acquire(self, problems, rng, memory=None):
        """``(capability, memory, report)`` from the training problems (all of one form, sharing
        one meter)."""
        memory = {"entries": list((memory or {}).get("entries", []))}
        if problems[0].kind == "predict":
            capability, report = self._acquire_predict(problems, rng)
        else:
            capability, report = self._acquire_assign(problems, rng, memory)
        if capability is not None and self.v["transfer.on"]:
            memory["entries"].append({"signature": self._signature(problems[0]), "capability": capability})
        return capability, memory, report

    def apply(self, capability, problem, rng):
        """An answer to one problem: with a capability, or with none."""
        if problem.kind == "predict":
            return self._apply_predict(capability, problem)
        return self._apply_assign(capability, problem, rng)

    # ---- consolidation and transfer ---------------------------------------------------------
    @staticmethod
    def _signature(P) -> dict:
        if P.kind == "predict":
            return {"kind": "predict", "ordered": bool(P.ordered), "attrs": int(P.ctx_x.shape[1])}
        return {"kind": "assign", "ordered": bool(P.ordered), "limited": P.capacity is not None,
                "reusable": P.capacity is None or int(P.capacity.max()) > 1, "hard": int(P.hard.sum()),
                "soft": int((~P.hard).sum()), "opt_opt": len(P.opt_opt), "var_var": len(P.var_var),
                "var_opt": len(P.var_opt), "opt_attr": int(P.opt_attr.shape[1]), "var_attr": int(P.var_attr.shape[1]),
                "occ_attr": len(P.occ_attr), "detail": int(P.detail.sum())}

    def _recall(self, P, memory: dict):
        """Weights of the most similar earlier assignment capability, if any."""
        sig, best, score = self._signature(P), None, 0
        for entry in memory.get("entries", []):
            other = entry["signature"]
            if other.get("kind") != "assign" or entry["capability"].get("kind") != "assign":
                continue
            same = sum(1 for k, val in sig.items() if other.get(k) == val)
            if same >= score:
                best, score = entry["capability"]["weights"], same
        return best

    # ---- the assignment form -----------------------------------------------------------------
    def _cost(self, P, shortlist: int) -> float:
        factor = shortlist if not P.ordered else 1
        return float(factor * P.n_vars * P.n_opts + 1)

    def _rollouts(self, problems, layouts, thetas, rng, shortlist, meter):
        """Keys ``(hard, soft)`` of each policy on each problem; ``None`` if the budget ended."""
        keys = np.zeros((len(thetas), len(problems), 2))
        need = sum(self._cost(P, shortlist) for P in problems) * len(thetas)
        if meter.left() < need:
            return None
        for c, theta in enumerate(thetas):
            for i, (P, lay) in enumerate(zip(problems, layouts)):
                totals, _ = construct(P, lay, theta, rng, shortlist)
                keys[c, i] = _key(totals, P)
        return keys

    @staticmethod
    def _fitness(keys: np.ndarray) -> np.ndarray:
        """Mean rank of each policy over the problems (higher is better)."""
        n_c, n_p = keys.shape[:2]
        fit = np.zeros(n_c)
        for i in range(n_p):
            order = np.lexsort((keys[:, i, 1], keys[:, i, 0]))
            ranks = np.empty(n_c)
            ranks[order] = np.arange(n_c)
            # ties share the mean rank, so a policy gets no credit for an arbitrary order
            col = keys[:, i]
            for value in {tuple(row) for row in col.tolist()}:
                same = np.flatnonzero((col[:, 0] == value[0]) & (col[:, 1] == value[1]))
                if len(same) > 1:
                    ranks[same] = ranks[same].mean()
            fit += (n_c - 1 - ranks)
        return fit / n_p

    def _acquire_assign(self, problems, rng, memory):
        v = self.v
        meter = problems[0].meter
        layouts = [Layout(P, v) for P in problems]
        lay0 = layouts[0]
        shortlist = int(v["shortlist"])
        n = len(problems)
        order = rng.permutation(n)
        n_check = min(max(1, int(round(v["assess.holdback"] * n))), n - 1) if n > 1 else 0
        check, fit = order[:n_check], order[n_check:]
        start = lay0.prior(v)
        recalled = self._recall(problems[0], memory) if (v["transfer.on"] and memory.get("entries")) else None
        if recalled is not None:
            start = (1.0 - v["transfer.blend"]) * start + v["transfer.blend"] * lay0.vector(recalled)
        report = {"form": "assign", "descriptors": lay0.names, "fit": len(fit), "held_back": len(check),
                  "iterations": 0, "constructions": 0, "transferred": recalled is not None, "failed": None}
        check_cost = sum(self._cost(problems[i], shortlist) for i in check)
        reserve = 3.0 * check_cost
        d = lay0.size
        mu, sigma = start.copy(), np.full(d, float(v["model.sigma"]))
        pop, batch = int(v["model.pop"]), min(int(v["model.batch"]), len(fit))
        n_elite = max(2, int(round(v["model.elite"] * pop)))
        best_theta, momentum = start.copy(), np.zeros(d)
        fit_cost = np.array([self._cost(problems[i], shortlist) for i in fit])
        try:
            while d > 0 and len(fit) > 0:
                chosen = rng.choice(len(fit), size=batch, replace=False)
                if meter.left() - reserve < pop * fit_cost[chosen].sum():
                    break
                sub = [problems[fit[i]] for i in chosen]
                sub_lay = [layouts[fit[i]] for i in chosen]
                if v["model.variant"] == "cem":
                    cands = mu + sigma * rng.standard_normal((pop, d))
                    if v["model.keep_best"]:
                        cands[0] = mu
                    keys = self._rollouts(sub, sub_lay, cands, rng, shortlist, meter)
                    if keys is None:
                        break
                    elite = cands[np.argsort(-self._fitness(keys), kind="stable")[:n_elite]]
                    mu = elite.mean(axis=0)
                    sigma = np.maximum(sigma * v["model.decay"], 0.02)
                else:  # "es": antithetic pairs, a step along the rank-weighted direction
                    half = max(1, pop // 2)
                    eps = rng.standard_normal((half, d))
                    cands = np.concatenate([mu + sigma * eps, mu - sigma * eps])
                    keys = self._rollouts(sub, sub_lay, cands, rng, shortlist, meter)
                    if keys is None:
                        break
                    f = self._fitness(keys)
                    f = (f - f.mean()) / (f.std() + TINY)
                    grad = ((f[:half] - f[half:])[:, None] * eps).mean(axis=0)
                    momentum = 0.5 * momentum + grad
                    mu = mu + v["model.lr"] * sigma * momentum
                    sigma = np.maximum(sigma * v["model.decay"], 0.02)
                report["iterations"] += 1
                report["constructions"] += len(cands) * len(sub)
                best_theta = mu.copy()
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended inside a construction"
        # self-assessment on the held-back problems: the learned policy against where it started
        chosen_theta, learned = start, False
        if report["iterations"] == 0:
            report["failed"] = report["failed"] or "decide: the budget did not allow one round of learning"
        elif n_check == 0:
            chosen_theta, learned = best_theta, True
        else:
            try:
                held = [problems[i] for i in check]
                held_lay = [layouts[i] for i in check]
                keys = self._rollouts(held, held_lay, np.stack([start, best_theta]), rng, shortlist, meter)
                if keys is None:
                    report["failed"] = "decide: no budget left for the held-back check"
                else:
                    f = self._fitness(keys)
                    report["held_back_start"] = keys[0].mean(axis=0).tolist()
                    report["held_back_learned"] = keys[1].mean(axis=0).tolist()
                    if f[1] > f[0] or not v["assess.strict"]:
                        chosen_theta, learned = best_theta, True
                    else:
                        report["failed"] = ("model: the learned weights did not beat the starting weights on the "
                                            "held-back problems")
            except BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
        report["learned"] = learned
        capability = {"kind": "assign", "weights": lay0.weights(chosen_theta), "learned": learned}
        return capability, report

    def _apply_assign(self, capability, P, rng):
        v = self.v
        lay = Layout(P, v)
        theta = lay.vector(capability["weights"]) if capability else lay.prior(v)
        shortlist = int(v["shortlist"])
        if not P.ordered:
            while shortlist > 1 and self._cost(P, shortlist) > P.meter.left():
                shortlist //= 2
        best, best_key, hold = None, None, []
        try:
            totals, answer = construct(P, lay, theta, rng, shortlist, hold=hold)
            best, best_key = answer, _key(totals, P)
        except BudgetExhausted:
            return _finish_arbitrarily(P, hold[0] if hold else None)
        try:
            if v["test.sampled"]:
                while P.meter.left() > 2 * self._cost(P, shortlist):
                    totals, answer = construct(P, lay, theta, rng, shortlist, temperature=float(v["test.temperature"]))
                    key = _key(totals, P)
                    if key < best_key:
                        best, best_key = answer, key
            misses = 0
            while misses < 50 * P.n_vars:
                candidate = _edit(P, v, best, rng)
                if candidate is None:
                    misses += 1
                    continue
                key = _key(P.evaluate(candidate), P)
                if key < best_key or (v["edit.accept_equal"] and key == best_key):
                    best, best_key = candidate, key
        except BudgetExhausted:
            pass
        return best

    # ---- the prediction form --------------------------------------------------------------
    def _describe(self, P, ctx_x, ctx_y, qry_x):
        """Descriptors of each query: targets of nearby observed entities and its attributes.
        Returns ``(features, centre, scale, anchor)``; targets are in standardised units."""
        v = self.v
        K = int(v["predict.K"])
        centre, scale = float(ctx_y.mean()), float(ctx_y.std())
        scale = scale if scale > TINY else 1.0
        y = (ctx_y - centre) / scale
        h = len(qry_x)
        if P.ordered:
            pos = ctx_x[:, 0]
            order = np.argsort(pos, kind="stable")
            pos, ys = pos[order], y[order]
            gaps = np.diff(pos)
            gap = float(np.median(gaps)) if len(gaps) and np.median(gaps) > TINY else 1.0
            last = ys[-1]
            feats = np.empty((h, K))
            for d in range(1, K + 1):
                want = qry_x[:, 0] - d * gap
                j = np.clip(np.searchsorted(pos, want + 0.5 * gap) - 1, 0, len(pos) - 1)
                near = np.abs(pos[j] - want) <= 0.5 * gap
                feats[:, d - 1] = np.where(near, ys[j], last)
            horizon = (qry_x[:, 0] - pos[-1]) / (gap * K)
            anchor = np.full(h, last)
            extra = [horizon]
            rest = slice(1, None)
        else:
            sd = ctx_x.std(axis=0)
            sd = np.where(sd > TINY, sd, 1.0)
            a, b = (ctx_x - ctx_x.mean(axis=0)) / sd, (qry_x - ctx_x.mean(axis=0)) / sd
            dist = np.sqrt(((b[:, None, :] - a[None, :, :]) ** 2).sum(axis=2))
            ys = y
            k = min(K, len(ys))
            near = np.argsort(dist, axis=1, kind="stable")[:, :k]
            feats = np.zeros((h, 2 * K))
            feats[:, :k] = ys[near]
            feats[:, K:K + k] = np.take_along_axis(dist, near, axis=1)
            anchor = ys[near[:, 0]]
            extra = []
            rest = slice(0, None)
        if v["predict.diff"]:
            feats = feats.copy()
            feats[:, :K] -= anchor[:, None]
        cols = [feats] + [np.asarray(e)[:, None] for e in extra]
        if v["predict.attrs"] and ctx_x[:, rest].shape[1] > 0:
            sd = ctx_x[:, rest].std(axis=0)
            sd = np.where(sd > TINY, sd, 1.0)
            cols.append((qry_x[:, rest] - ctx_x[:, rest].mean(axis=0)) / sd)
        cols.append(np.ones((h, 1)))
        return np.column_stack(cols), centre, scale, anchor

    def _pairs(self, P, rng):
        """Training pairs of one problem: its own queries, and optionally queries it makes for
        itself by hiding part of what it observed."""
        out = []
        F, centre, scale, anchor = self._describe(P, P.ctx_x, P.ctx_y, P.qry_x)
        out.append((F, (P.qry_y - centre) / scale, anchor))
        if self.v["predict.selfsup"] and len(P.ctx_y) >= 4 * max(1, len(P.qry_x)):
            h = len(P.qry_x)
            if P.ordered:
                order = np.argsort(P.ctx_x[:, 0], kind="stable")
                keep, hide = order[:-h], order[-h:]
            else:
                order = rng.permutation(len(P.ctx_y))
                keep, hide = order[h:], order[:h]
            F2, c2, s2, a2 = self._describe(P, P.ctx_x[keep], P.ctx_y[keep], P.ctx_x[hide])
            out.append((F2, (P.ctx_y[hide] - c2) / s2, a2))
        return out

    def _acquire_predict(self, problems, rng):
        v = self.v
        n = len(problems)
        order = rng.permutation(n)
        n_check = min(max(1, int(round(v["assess.holdback"] * n))), n - 1) if n > 1 else 0
        check, fit = order[:n_check], order[n_check:]
        report = {"form": "predict", "fit": len(fit), "held_back": len(check), "failed": None, "iterations": 1}
        rows, targets = [], []
        try:
            for i in fit:
                P = problems[i]
                P.meter.charge(P.construction_units())
                for F, t, anchor in self._pairs(P, rng):
                    rows.append(F)
                    targets.append(t - anchor if v["predict.diff"] else t)
            X, t = np.vstack(rows), np.concatenate(targets)
            lam = 10.0 ** float(v["predict.ridge"])
            coef = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ t)
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended before the fit"
            return None, report
        capability = {"kind": "predict", "coef": coef.tolist(), "learned": True}
        if n_check:
            err_prior, err_learned = [], []
            for i in check:
                P = problems[i]
                err_prior.append(np.mean(np.abs(self._apply_predict(None, P) - P.qry_y)) / (P.ctx_y.std() + TINY))
                err_learned.append(np.mean(np.abs(self._apply_predict(capability, P) - P.qry_y))
                                   / (P.ctx_y.std() + TINY))
            report["held_back_start"], report["held_back_learned"] = float(np.mean(err_prior)), float(np.mean(err_learned))
            if v["assess.strict"] and not np.mean(err_learned) < np.mean(err_prior):
                report["failed"] = "model: the fitted predictor did not beat the nearest observed value on held-back problems"
                capability = {"kind": "predict", "coef": None, "learned": False}
        report["learned"] = capability["coef"] is not None
        return capability, report

    def _apply_predict(self, capability, P):
        F, centre, scale, anchor = self._describe(P, P.ctx_x, P.ctx_y, P.qry_x)
        if not capability or capability.get("coef") is None:
            return anchor * scale + centre                      # uninformed: the nearest observed target
        coef = np.asarray(capability["coef"])
        if len(coef) != F.shape[1]:
            return anchor * scale + centre
        out = F @ coef
        if self.v["predict.diff"]:
            out = out + anchor
        return out * scale + centre
