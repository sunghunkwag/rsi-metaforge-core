"""What the learner sees of one instance.

Every environment is presented to the learner in one of two generic forms. Neither carries a
name, a reference value, or anything that is not in the published instance or defined by the
public specification.

``AssignProblem``: ``n_vars`` variables each take one of ``n_opts`` options. An option may be
limited in how many variables can take it (``capacity``); variables are either free in order or
must be assigned in index order (``ordered``). The published objective and constraints appear
as *term groups*: totals the evaluator computes, each flagged soft (a cost to be made small) or
hard (must be zero for a valid answer). A term contributes as soon as every variable it reads
is assigned, so a partial assignment has totals too, and the change of the totals when one
more variable is assigned is exact evaluation, not a heuristic. Where the published objective
is the largest of its terms rather than their sum, the sum of the same terms is exposed as a
further group flagged *detail*: it is not part of the cost, it only says what the newly
determined terms are worth. ``occ_attr`` carries attributes of the k-th use of an option, for
problems in which an option is used several times.

``PredictProblem``: observed entities with attributes and target values, and query entities
with attributes whose targets are to be predicted. Feedback exists on training instances only.

Compute is counted in *units* by a ``Meter`` the kernel owns: one unit per option examined in
``candidates``, ``n_vars`` units per full evaluation. When the meter runs out the call raises
``BudgetExhausted``; the learner has to plan for it.
"""
from __future__ import annotations

import numpy as np

EMPTY = np.zeros((0, 0))


class BudgetExhausted(Exception):
    """The compute budget of this call is spent."""


class Meter:
    """Counted work units with a hard limit. Owned by the kernel, shared by reference."""

    __slots__ = ("limit", "used", "calls")

    def __init__(self, limit: float):
        self.limit, self.used, self.calls = float(limit), 0.0, 0

    def charge(self, units: float) -> None:
        self.used += units
        self.calls += 1
        if self.used > self.limit:
            raise BudgetExhausted()

    def left(self) -> float:
        return self.limit - self.used


class AssignProblem:
    """The assignment form. An adapter subclasses it and implements ``partial_totals`` (the
    specification's meaning of the term groups) and, for speed, the three state methods
    ``_new``, ``_rows`` and ``_push``; the defaults here derive them from ``partial_totals`` and
    are the reference the fast ones are tested against."""

    kind = "assign"

    def __init__(self, n_vars: int, n_opts: int, hard, ordered: bool = False, capacity=None, var_attr=None,
                 opt_attr=None, var_var=(), opt_opt=(), var_opt=(), occ_attr=(), detail=None, domain=None,
                 start_answer=None, start_totals=None, meter: Meter | None = None):
        self.n_vars, self.n_opts = int(n_vars), int(n_opts)
        self.hard = np.asarray(hard, dtype=bool)
        self.n_groups = len(self.hard)
        self.detail = np.zeros(self.n_groups, dtype=bool) if detail is None else np.asarray(detail, dtype=bool)
        self.occ_attr = tuple(np.asarray(m, dtype=float) for m in occ_attr)
        # which options each variable may take at all (None: every option), and an answer that is
        # already known for this instance together with its totals (None: none is known)
        self.domain = None if domain is None else np.asarray(domain, dtype=bool)
        self.start_answer = None if start_answer is None else np.asarray(start_answer, dtype=np.int64)
        self.start_totals = None if start_totals is None else np.asarray(start_totals, dtype=float)
        self.ordered = bool(ordered)
        self.capacity = None if capacity is None else np.asarray(capacity, dtype=np.int64)
        self.var_attr = np.zeros((self.n_vars, 0)) if var_attr is None else np.asarray(var_attr, dtype=float)
        self.opt_attr = np.zeros((self.n_opts, 0)) if opt_attr is None else np.asarray(opt_attr, dtype=float)
        self.var_var = tuple(np.asarray(m, dtype=float) for m in var_var)
        self.opt_opt = tuple(np.asarray(m, dtype=float) for m in opt_opt)
        self.var_opt = tuple(np.asarray(m, dtype=float) for m in var_opt)
        self.meter = meter if meter is not None else Meter(float("inf"))

    # ---- the specification, implemented by the adapter ------------------------------------
    def partial_totals(self, a: np.ndarray) -> np.ndarray:
        """Totals of every term group for the assignment ``a`` (``-1`` where unassigned): the
        sum of the terms whose variables are all assigned."""
        raise NotImplementedError

    # ---- incremental state: slow exact defaults -------------------------------------------
    def _new(self) -> dict:
        a = np.full(self.n_vars, -1, dtype=np.int64)
        return {"a": a, "used": np.zeros(self.n_opts, dtype=np.int64), "tot": np.asarray(self.partial_totals(a), float),
                "n": 0}

    def _rows(self, s: dict, variables: np.ndarray) -> np.ndarray:
        out = np.zeros((len(variables), self.n_opts, self.n_groups))
        allowed = self.allowed(s)
        for i, v in enumerate(variables):
            for o in np.flatnonzero(allowed):
                a = s["a"].copy()
                a[v] = o
                out[i, o] = np.asarray(self.partial_totals(a), float) - s["tot"]
        return out

    def _push(self, s: dict, v: int, o: int) -> None:
        s["a"][v] = o
        s["tot"] = np.asarray(self.partial_totals(s["a"]), float)

    # ---- what the learner calls (metered) -------------------------------------------------
    def start(self) -> dict:
        self.meter.charge(1)
        return self._new()

    def unassigned(self, s: dict) -> np.ndarray:
        """The variables that may be assigned next."""
        if self.ordered:
            return np.array([s["n"]], dtype=np.int64) if s["n"] < self.n_vars else np.zeros(0, dtype=np.int64)
        return np.flatnonzero(s["a"] < 0)

    def allowed(self, s: dict) -> np.ndarray:
        """Which options can still take a variable."""
        if self.capacity is None:
            return np.ones(self.n_opts, dtype=bool)
        return s["used"] < self.capacity

    def candidates(self, s: dict, variables) -> np.ndarray:
        """For each given variable and each option: the exact change of every group total if
        that variable took that option. Shape ``(len(variables), n_opts, n_groups)``."""
        variables = np.asarray(variables, dtype=np.int64)
        self.meter.charge(len(variables) * self.n_opts)
        return self._rows(s, variables)

    def assign(self, s: dict, v: int, o: int) -> None:
        v, o = int(v), int(o)
        if s["a"][v] >= 0:
            raise ValueError("variable already assigned")
        if self.ordered and v != s["n"]:
            raise ValueError("variables of this problem are assigned in index order")
        if not 0 <= o < self.n_opts or (self.capacity is not None and s["used"][o] >= self.capacity[o]) \
                or (self.domain is not None and not self.domain[v, o]):
            raise ValueError("option not available")
        self._push(s, v, o)
        s["used"][o] += 1
        s["n"] += 1

    def totals(self, s: dict) -> np.ndarray:
        return np.array(s["tot"], dtype=float)

    def assignment(self, s: dict) -> np.ndarray:
        return s["a"].copy()

    def complete(self, s: dict) -> bool:
        return s["n"] == self.n_vars

    def well_formed(self, answer) -> bool:
        """A complete assignment that respects ranges and capacities."""
        a = np.asarray(answer)
        if a.shape != (self.n_vars,) or a.dtype.kind not in "iu" or a.min(initial=0) < 0 or a.max(initial=0) >= self.n_opts:
            return False
        if self.domain is not None and not bool(np.all(self.domain[np.arange(self.n_vars), a])):
            return False
        return self.capacity is None or bool(np.all(np.bincount(a, minlength=self.n_opts) <= self.capacity))

    def evaluate(self, answer) -> np.ndarray:
        """Totals of a complete answer."""
        self.meter.charge(self.n_vars)
        a = np.asarray(answer, dtype=np.int64)
        if not self.well_formed(a):
            raise ValueError("not a well-formed answer")
        return np.asarray(self.partial_totals(a), float)

    def construction_units(self) -> float:
        """Units of one construction that looks at every option of one variable per step."""
        return float(self.n_vars * self.n_opts + 1)


class PredictProblem:
    """The prediction form. ``ctx_x`` (m, a) and ``ctx_y`` (m,) are the observed entities and
    their targets; ``qry_x`` (h, a) are the entities to predict. ``ordered`` says that the first
    attribute is a position along which the entities are ordered. ``feedback`` exists only when
    the kernel built the problem from a training instance."""

    kind = "predict"

    def __init__(self, ctx_x, ctx_y, qry_x, ordered: bool, target=None, meter: Meter | None = None):
        self.ctx_x = np.asarray(ctx_x, dtype=float).reshape(len(ctx_y), -1)
        self.ctx_y = np.asarray(ctx_y, dtype=float)
        self.qry_x = np.asarray(qry_x, dtype=float).reshape(-1, self.ctx_x.shape[1])
        self.ordered = bool(ordered)
        self._target = None if target is None else np.asarray(target, dtype=float)
        self.meter = meter if meter is not None else Meter(float("inf"))

    @property
    def n_queries(self) -> int:
        return len(self.qry_x)

    @property
    def qry_y(self):
        """Targets of the queries: present on training instances, ``None`` otherwise."""
        return None if self._target is None else self._target.copy()

    def has_feedback(self) -> bool:
        return self._target is not None

    def feedback(self, prediction) -> np.ndarray:
        """Absolute error of each predicted value (training instances only)."""
        if self._target is None:
            raise PermissionError("no feedback on this instance")
        p = np.asarray(prediction, dtype=float)
        if p.shape != self._target.shape:
            raise ValueError("wrong number of predictions")
        self.meter.charge(len(p))
        return np.abs(p - self._target)

    def construction_units(self) -> float:
        return float(len(self.ctx_y) + len(self.qry_x))
