"""The open design of the learner (design "o"): its representation and its learning principle
are programs, not settings.

A version of this design is a *mechanism*: a handful of short programs in one small vector
machine, plus the starting values of the constants those programs read. Nothing in it is a
choice from a list written by the experimenter: a program is any sequence of the machine's
instructions, and the discovery process (``rsi6/open/discovery.py``) changes it by editing
instructions, not by picking values.

The machine has generic instructions only: arithmetic on vectors, order statistics, noise, and
reads of the generic arrays of the problem forms (``rsi6/kernel/problem.py``). It knows nothing
about any environment.

The programs of a mechanism, for the assignment form:

``score``    runs at every step of a construction, on vectors over the options of the variable
             being assigned. It reads *sensors* (the exact change of the soft and hard totals if
             the variable took each option, how used each option is, rows of the option-option,
             variable-option and variable-variable relations as they stand in the partial
             answer, attributes, progress, noise) and combines them; register 0 is the score of
             each option, and the best allowed option is taken. Which sensors are read, and how
             they are combined, is the program: the representation is not fixed.
``pick``     for problems that are free in order: runs on vectors over the unassigned variables
             and scores which one to assign next.
``init``,    the learning principle. Acquisition runs ``init`` once, then repeats: ``propose``
``propose``, fills a population of parameter vectors from eight state registers; the kernel's
``update``   problems evaluate each by constructions on a few training problems; ``update``
             turns the fitness of the population into new state. Elite averaging, a
             rank-weighted gradient step, greedy selection, step-size control and momentum are
             each a few instructions in this machine; none is built in, and others can be
             written.

The parameters being learned are the constants ``theta`` that ``score`` and ``pick`` read.
After the budget the learner compares, on held-back training problems, its starting constants,
its state register 0 and the best vector of its last population, and keeps the best; on a tie
it keeps the start.

Random streams are kept apart: the order and the batches of the training problems, the
learning principle and the constructions each draw from their own stream, and population noise
is drawn for every coordinate the machine allows and then cut to the constants in use, so that
an edit which adds a constant leaves the draws of the existing ones unchanged.

Contract and interface are those of the other designs. The prediction form is answered by the
first design's predictor, unchanged: this design opens the assignment form only, and says so.
The answer at test time is a construction followed by the first design's local improvement
with its default settings.

Generation 0 is not the first design in another machine. It is a reduced linear prior (ten
constants over the soft and hard changes, usage, the first option-option, variable-option and
variable-variable relations and the first variable attribute) with cross-entropy search, and it
differs from the first design's generation 0 in several ways that matter for any comparison of
the two: one variable is scored per step where the first design scores four (so a construction
costs about a quarter of the units and acquisition gets about four times the rounds from the
same budget); the step sizes have a floor of 0.1 (0.02 there); three vectors are compared on
held-back problems (two there); the hard change is scaled by its range (by its largest value
there); and it has none of the first design's per-group, remaining-relation, occupancy and
option-sum terms. A comparison with the first design is therefore made at matched CPU.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from rsi6.kernel.problem import BudgetExhausted
from rsi6.learner import version as design_a
from rsi6.learner.learner import Learner, _finish_arbitrarily, _key

TINY = 1e-9


class Infeasible(Exception):
    """A partial answer that no option can extend (possible only on problems with domains)."""
N_REG, N_PREG, N_AREG, N_WREG = 8, 4, 8, 4                  # score, pick, acquirer and fitness registers
LIMITS = {"score": 48, "pick": 24, "init": 8, "propose": 16, "update": 24, "theta": 32}
CONST = (-2.0, -1.0, -0.5, -0.1, 0.0, 0.1, 0.25, 0.5, 0.9, 1.0, 1.1, 1.5, 2.0, 4.0)

# ---- the score and pick machine ------------------------------------------------------------
UNARY = ("neg", "abs", "sq", "sqrt", "log", "tanh", "relu", "step", "exp", "rank", "z", "mm", "mean", "maxb",
         "minb", "sumb")
BINARY = ("add", "sub", "mul", "div", "max", "min", "gt")
PARAM = ("scale", "shift")                                     # with a constant theta[k]
SCORE_SENSORS = ("dsoft", "dhard", "dgroup", "used", "capleft", "prev", "vo", "oa", "neigh", "usedrel", "progress",
                 "ones", "occnext", "vattr", "optsum", "noise")
PICK_SENSORS = ("vattr", "vvdone", "vvopen", "deg", "domsize", "vosum", "vomin", "ones", "noise")
SENSOR_ARGS = 4                                                # sensors with an index read relation or column 0..3
SCORE_OPS = UNARY + BINARY + PARAM + ("const", "load", "rel", "relt")
PICK_OPS = UNARY + BINARY + PARAM + ("const", "load")

# ---- the acquirer machine -------------------------------------------------------------------
A_UNARY = ("copy", "abs", "sign", "neg", "sqrt", "sq", "mean", "norm")
A_BINARY = ("add", "sub", "mul", "max", "min")
A_CONST = ("scale", "clipc", "floor")                          # with CONST[c]
A_NULLARY = ("noise", "unif", "zero", "ones")
A_OPS = A_UNARY + A_BINARY + A_CONST + A_NULLARY
POP_OPS = ("rows", "anti", "row", "rowu")
W_OPS = ("wfit", "wrank", "wcenter", "wtop", "wexp", "wnorm", "wmul", "wadd", "wneg", "wbest", "comb", "combabs")
PARTS_OPS = {"score": SCORE_OPS, "pick": PICK_OPS, "init": A_OPS, "propose": A_OPS + POP_OPS, "update": A_OPS + W_OPS}
SELECT = ("best_of_3", "state", "last_best")


# =============================================================================================
# the version record
# =============================================================================================
def default() -> dict:
    """Generation 0 of the open design: a linear policy over a few sensors, starting from the
    first design's prior weights, and cross-entropy search as its learning principle (see the
    module text for how it differs from the first design). Every part is ordinary code of the
    machine and can be rewritten."""
    score = [
        ["load", 1, 0, 0], ["mm", 1, 1, 0], ["scale", 0, 1, 0],          # theta0 * dsoft (scaled to [0, 1])
        ["load", 2, 1, 0], ["step", 3, 2, 0], ["scale", 3, 3, 1],         # theta1 * (a new violation)
        ["mm", 2, 2, 0], ["scale", 2, 2, 2], ["add", 0, 0, 2], ["add", 0, 0, 3],   # theta2 * dhard (scaled)
        ["load", 4, 3, 0], ["mm", 4, 4, 0], ["scale", 4, 4, 3], ["add", 0, 0, 4],  # theta3 * usage
        ["load", 5, 5, 0], ["mm", 5, 5, 0], ["scale", 5, 5, 4], ["add", 0, 0, 5],  # theta4 * relation to the previous option
        ["load", 6, 6, 0], ["mm", 6, 6, 0], ["scale", 6, 6, 5], ["add", 0, 0, 6],  # theta5 * variable-option relation
        ["load", 7, 8, 0], ["mm", 7, 7, 0], ["scale", 7, 7, 6], ["add", 0, 0, 7],  # theta6 * assigned neighbours on the option
    ]
    pick = [
        ["load", 1, 1, 0], ["mm", 1, 1, 0], ["scale", 0, 1, 7],           # theta7 * relation to assigned variables
        ["load", 2, 2, 0], ["mm", 2, 2, 0], ["scale", 2, 2, 8], ["add", 0, 0, 2],   # theta8 * relation to open ones
        ["load", 3, 0, 0], ["mm", 3, 3, 0], ["scale", 3, 3, 9], ["add", 0, 0, 3],   # theta9 * first attribute
    ]
    init = [["ones", 1, 0, 0], ["scale", 1, 1, 9]]                       # step sizes 1
    propose = [["rows", 0, 0, 1], ["row", 0, 0, 0]]                      # population around the mean; the mean kept
    update = [["wfit", 0, 0, 0], ["wtop", 1, 0, 6], ["wnorm", 1, 1, 0],   # the best quarter, equal weights
              ["zero", 4, 0, 0], ["comb", 5, 1, 4], ["copy", 0, 5, 0],     # their mean is the new mean
              ["scale", 1, 1, 8], ["floor", 1, 1, 5]]                     # step sizes shrink, not below 0.1
    return {"design": "o", "score": score, "pick": pick, "theta": [-1.0, -6.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "init": init, "propose": propose, "update": update, "pop": 16, "batch": 4, "shortlist": 1,
            "holdback": 0.25, "select": "best_of_3"}


def _check_instr(part: str, ins, n_theta: int) -> list:
    if not isinstance(ins, (list, tuple)) or len(ins) != 4:
        raise ValueError(f"{part}: an instruction is [op, dst, a, b]")
    op, dst, a, b = ins[0], int(ins[1]), int(ins[2]), int(ins[3])
    if op not in PARTS_OPS[part]:
        raise ValueError(f"{part}: unknown op {op!r}")
    if part in ("score", "pick"):
        nreg = N_REG if part == "score" else N_PREG
        sensors = SCORE_SENSORS if part == "score" else PICK_SENSORS
        if not 0 <= dst < nreg:
            raise ValueError(f"{part}: register {dst} out of range")
        if op == "load":
            if not (0 <= a < len(sensors) and 0 <= b < SENSOR_ARGS):
                raise ValueError(f"{part}: sensor {a}/{b} out of range")
        elif op in PARAM:
            if not (0 <= a < nreg and 0 <= b < n_theta):
                raise ValueError(f"{part}: {op} reads register {a} and constant {b}")
        elif op == "const":
            if not 0 <= b < n_theta:
                raise ValueError(f"{part}: constant {b} out of range")
        elif op in ("rel", "relt"):
            if not (0 <= a < nreg and 0 <= b < SENSOR_ARGS):
                raise ValueError(f"{part}: {op} out of range")
        else:
            if not (0 <= a < nreg and 0 <= b < nreg):
                raise ValueError(f"{part}: register out of range")
    else:
        if op in W_OPS:
            if op in ("comb", "combabs"):
                if not (0 <= dst < N_AREG and 0 <= a < N_WREG and 0 <= b < N_AREG):
                    raise ValueError(f"{part}: {op} out of range")
            elif not (0 <= dst < N_WREG and 0 <= a < N_WREG and 0 <= b < max(N_WREG, len(CONST))):
                raise ValueError(f"{part}: {op} out of range")
        elif op in POP_OPS:
            if not (0 <= a < N_AREG and 0 <= b < N_AREG and 0 <= dst < 64):
                raise ValueError(f"{part}: {op} out of range")
        else:
            if not (0 <= dst < N_AREG and 0 <= a < N_AREG):
                raise ValueError(f"{part}: register out of range")
            if op in A_CONST and not 0 <= b < len(CONST):
                raise ValueError(f"{part}: constant {b} out of range")
            if op in A_BINARY and not 0 <= b < N_AREG:
                raise ValueError(f"{part}: register out of range")
    return [op, dst, a, b]


def validate(version: dict) -> dict:
    """The version, checked: known parts, valid instructions, size limits, finite constants."""
    keys = {"design", "score", "pick", "theta", "init", "propose", "update", "pop", "batch", "shortlist", "holdback", "select"}
    if set(version) != keys or version.get("design") != "o":
        raise ValueError(f"an open version has exactly the parts {sorted(keys)}")
    theta = [float(x) for x in version["theta"]]
    if not 1 <= len(theta) <= LIMITS["theta"] or not all(np.isfinite(theta)) or max(abs(x) for x in theta) > 100.0:
        raise ValueError("theta: 1 to 32 finite constants of size at most 100")
    out = {"design": "o", "theta": [round(x, 6) for x in theta]}
    for part in ("score", "pick", "init", "propose", "update"):
        program = version[part]
        if len(program) > LIMITS[part]:
            raise ValueError(f"{part}: longer than {LIMITS[part]} instructions")
        out[part] = [_check_instr(part, ins, len(theta)) for ins in program]
    pop, batch, shortlist = int(version["pop"]), int(version["batch"]), int(version["shortlist"])
    if not (2 <= pop <= 32 and 1 <= batch <= 8 and shortlist in (1, 2, 4)):
        raise ValueError("pop 2..32, batch 1..8, shortlist 1, 2 or 4")
    holdback = float(version["holdback"])
    if not 0.1 <= holdback <= 0.5:
        raise ValueError("holdback in [0.1, 0.5]")
    if version["select"] not in SELECT:
        raise ValueError(f"select one of {SELECT}")
    out.update({"pop": pop, "batch": batch, "shortlist": shortlist, "holdback": round(holdback, 6), "select": version["select"]})
    return out


def digest(version: dict) -> str:
    text = json.dumps(validate(version), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


FUNCTION_OF = {"score": "represent/decide", "pick": "decide", "theta": "model", "init": "model", "propose": "explore",
               "update": "model", "pop": "explore", "batch": "decide", "shortlist": "decide", "holdback": "self-assess",
               "select": "self-assess"}


def differences(a: dict, b: dict) -> dict:
    """Parts in which two versions differ. For a program: its length before and after and how
    many instructions differ in place."""
    out = {}
    for part, function in FUNCTION_OF.items():
        if a[part] == b[part]:
            continue
        if part in ("score", "pick", "init", "propose", "update"):
            moved = sum(1 for x, y in zip(a[part], b[part]) if list(x) != list(y)) + abs(len(a[part]) - len(b[part]))
            out[part] = {"from": f"{len(a[part])} instructions", "to": f"{len(b[part])} instructions, {moved} changed",
                         "function": function}
        elif part == "theta":
            out[part] = {"from": f"{len(a[part])} constants", "to": f"{len(b[part])} constants", "function": function}
        else:
            out[part] = {"from": a[part], "to": b[part], "function": function}
    return out


SCHEMA = {}                                                    # no fields: the open design has no grid of values


# =============================================================================================
# the score and pick machine
# =============================================================================================
def _norm_fn(kind):
    def f(x, mask, idx):
        sel = x[idx] if idx is not None else x
        if sel.size == 0:
            return np.zeros_like(x)
        if kind == "mm":
            lo, hi = sel.min(), sel.max()
            return (x - lo) / (hi - lo) if hi - lo > TINY else np.zeros_like(x)
        if kind == "z":
            m, s = sel.mean(), sel.std()
            return np.clip((x - m) / s, -3.0, 3.0) if s > TINY else np.zeros_like(x)
        if kind == "rank":
            out = np.zeros_like(x)
            ids = idx if idx is not None else np.arange(len(x))
            if len(ids) < 2:
                return out
            order = np.argsort(x[ids], kind="stable")
            ranks = np.empty(len(ids))
            ranks[order] = np.arange(len(ids))
            out[ids] = 2.0 * ranks / (len(ids) - 1) - 1.0
            return out
        value = {"mean": sel.mean, "maxb": sel.max, "minb": sel.min, "sumb": sel.sum}[kind]()
        return np.full_like(x, float(value))
    return f


_ELEMENTWISE = {
    "neg": np.negative, "abs": np.abs,
    "sq": lambda x: np.minimum(x * x, 1e12),
    "sqrt": lambda x: np.sign(x) * np.sqrt(np.abs(x)),
    "log": lambda x: np.sign(x) * np.log1p(np.abs(x)),
    "tanh": np.tanh, "relu": lambda x: np.maximum(x, 0.0),
    "step": lambda x: (x > TINY).astype(float),
    "exp": lambda x: np.exp(np.clip(x, -20.0, 5.0)),
}
_NORMALISING = {k: _norm_fn(k) for k in ("rank", "z", "mm", "mean", "maxb", "minb", "sumb")}
_PAIRWISE = {
    "add": np.add, "sub": np.subtract,
    "mul": lambda x, y: np.clip(x * y, -1e12, 1e12),
    "div": lambda x, y: x / (np.abs(y) + 1e-3),
    "max": np.maximum, "min": np.minimum,
    "gt": lambda x, y: (x > y).astype(float),
}


def live(program) -> list:
    """The instructions of a score or pick program whose result reaches register 0, in order.
    Only these are run: an instruction whose result is never read does nothing, not even draw
    noise, so two programs with the same live instructions behave identically."""
    need, keep = {0}, []
    for i in range(len(program) - 1, -1, -1):
        op, dst, a, b = program[i]
        if dst not in need:
            continue
        keep.append(i)
        need.discard(dst)
        if op in BINARY:
            need |= {a, b}
        elif op in UNARY or op in PARAM or op in ("rel", "relt"):
            need.add(a)
    return [program[i] for i in sorted(keep)]


def compile_vector_program(program, theta, nreg=N_REG):
    """A score or pick program, turned into one function ``f(sensor, length, mask, rel)``.
    ``sensor(id, arg)`` returns a vector of ``length``; ``rel(r, x, transposed)`` propagates a
    vector over an option-option relation; ``mask`` marks the entries that normalising
    instructions look at. Register 0 is the result; registers not written read as zeros. Only
    the live instructions are compiled."""
    steps = []
    for op, dst, a, b in live(program):
        if op == "load":
            steps.append((0, dst, a, b, None))
        elif op in PARAM:
            c = float(theta[b])
            steps.append((1, dst, a, c, op == "scale"))
        elif op == "const":
            steps.append((2, dst, float(theta[b]), None, None))
        elif op in ("rel", "relt"):
            steps.append((3, dst, a, b, op == "relt"))
        elif op in _PAIRWISE:
            steps.append((4, dst, a, b, _PAIRWISE[op]))
        elif op in _ELEMENTWISE:
            steps.append((5, dst, a, None, _ELEMENTWISE[op]))
        else:
            steps.append((6, dst, a, None, _NORMALISING[op]))

    def run(sensor, length, mask, rel=None):
        zero = np.zeros(length)
        R = [zero] * nreg
        idx = np.flatnonzero(mask) if mask is not None else None
        for kind, dst, a, b, f in steps:
            if kind == 0:
                R[dst] = sensor(a, b)
            elif kind == 1:
                R[dst] = R[a] * b if f else R[a] + b
            elif kind == 2:
                R[dst] = np.full(length, a)
            elif kind == 3:
                R[dst] = rel(b, R[a], f) if rel is not None else zero
            elif kind == 4:
                R[dst] = f(R[a], R[b])
            elif kind == 5:
                R[dst] = f(R[a])
            else:
                R[dst] = f(R[a], mask, idx)
        out = R[0]
        return out if np.all(np.isfinite(out)) else np.where(np.isfinite(out), out, 0.0)
    return run


def run_vector_program(program, theta, sensor, length, mask, rel=None, nreg=N_REG):
    """Run a score or pick program once (``compile_vector_program`` for repeated runs)."""
    return compile_vector_program(program, theta, nreg)(sensor, length, mask, rel)


class Sensors:
    """The generic sensors of one assignment problem during a construction. Aggregates over the
    partial answer (relations to assigned variables, options already used) are kept up to date
    step by step, and only those that the mechanism's programs read."""

    def __init__(self, P, genome: dict):
        self.P = P
        self.soft = ~P.hard & ~P.detail
        self.cap = P.capacity.astype(float) if P.capacity is not None else np.full(P.n_opts, float(P.n_vars))
        self.deg = [R.sum(axis=1) for R in P.var_var]
        loads = lambda part, names: {(names[ins[2]], ins[3]) for ins in live(genome[part]) if ins[0] == "load"}
        self.score_reads = loads("score", SCORE_SENSORS)
        self.pick_reads = loads("pick", PICK_SENSORS)
        self.need_neigh = sorted({arg for name, arg in self.score_reads if name == "neigh" and arg < len(P.var_var)})
        self.need_done = sorted({arg for name, arg in self.pick_reads if name in ("vvdone", "vvopen") and arg < len(P.var_var)})
        self.need_usedrel = sorted({arg for name, arg in self.score_reads if name == "usedrel" and arg < len(P.opt_opt)})
        self.need_optsum = sorted({arg for name, arg in self.score_reads if name == "optsum" and arg < P.var_attr.shape[1]})

    def begin(self):
        P = self.P
        self.neigh = {r: np.zeros((P.n_vars, P.n_opts)) for r in self.need_neigh}
        self.done = {r: np.zeros(P.n_vars) for r in self.need_done}
        self.usedrel = {r: np.zeros(P.n_opts) for r in self.need_usedrel}
        self.optsum = {c: np.zeros(P.n_opts) for c in self.need_optsum}

    def assigned(self, s, v: int, o: int) -> None:
        P = self.P
        for r, N in self.neigh.items():
            N[:, o] += P.var_var[r][:, v]
        for r, done in self.done.items():
            done += P.var_var[r][:, v]
        if self.usedrel and s["used"][o] == 1:                 # the option is used for the first time
            for r, u in self.usedrel.items():
                u += P.opt_opt[r][:, o]
        for c, acc in self.optsum.items():
            acc[o] += P.var_attr[v, c]

    def score_sensor(self, s, v, D, prev, step, rng):
        P = self.P
        n = P.n_opts

        def read(kind, arg):
            name = SCORE_SENSORS[kind]
            if name == "dsoft":
                return D[:, self.soft].sum(axis=1) if self.soft.any() else np.zeros(n)
            if name == "dhard":
                return D[:, P.hard].sum(axis=1) if P.hard.any() else np.zeros(n)
            if name == "dgroup":
                return D[:, arg].copy() if arg < P.n_groups else np.zeros(n)
            if name == "used":
                return s["used"].astype(float)
            if name == "capleft":
                return self.cap - s["used"]
            if name == "prev":
                return P.opt_opt[arg][prev].astype(float) if arg < len(P.opt_opt) and prev >= 0 else np.zeros(n)
            if name == "vo":
                return P.var_opt[arg][v].astype(float) if arg < len(P.var_opt) else np.zeros(n)
            if name == "oa":
                return P.opt_attr[:, arg].astype(float) if arg < P.opt_attr.shape[1] else np.zeros(n)
            if name == "neigh":
                return self.neigh[arg][v].copy() if arg in self.neigh else np.zeros(n)
            if name == "usedrel":
                return self.usedrel[arg].copy() if arg in self.usedrel else np.zeros(n)
            if name == "progress":
                return np.full(n, 2.0 * step / max(P.n_vars - 1, 1) - 1.0)
            if name == "ones":
                return np.ones(n)
            if name == "occnext":
                if arg >= len(P.occ_attr):
                    return np.zeros(n)
                A = P.occ_attr[arg]
                k = np.minimum(s["used"], A.shape[1] - 1)
                return np.where(s["used"] < A.shape[1], A[np.arange(n), k], 0.0)
            if name == "vattr":
                return np.full(n, float(P.var_attr[v, arg])) if arg < P.var_attr.shape[1] else np.zeros(n)
            if name == "optsum":
                return self.optsum[arg].copy() if arg in self.optsum else np.zeros(n)
            return rng.random(n)                                 # noise
        return read

    def pick_sensor(self, s, U, allowed, rng):
        P = self.P

        def read(kind, arg):
            name = PICK_SENSORS[kind]
            m = len(U)
            if name == "vattr":
                return P.var_attr[U, arg].astype(float) if arg < P.var_attr.shape[1] else np.zeros(m)
            if name in ("vvdone", "vvopen"):
                if arg not in self.done:
                    return np.zeros(m)
                done = self.done[arg][U]
                return done if name == "vvdone" else self.deg[arg][U] - done
            if name == "deg":
                return self.deg[arg][U] if arg < len(P.var_var) else np.zeros(m)
            if name == "domsize":
                if P.domain is None:
                    return np.full(m, float(allowed.sum()))
                return (P.domain[U] & allowed[None, :]).sum(axis=1).astype(float)
            if name in ("vosum", "vomin"):
                if arg >= len(P.var_opt):
                    return np.zeros(m)
                rows = P.var_opt[arg][U]
                if name == "vosum":
                    return rows.sum(axis=1)
                return np.where(allowed[None, :], rows, 1e12).min(axis=1) if allowed.any() else np.zeros(m)
            if name == "ones":
                return np.ones(m)
            return rng.random(m)
        return read

    def rel(self, r, x, transposed):
        P = self.P
        if r >= len(P.opt_opt):
            return np.zeros(P.n_opts)
        R = P.opt_opt[r]
        return (R.T @ x) if transposed else (R @ x)


def construct(P, sensors: Sensors, genome: dict, theta, rng, shortlist: int, hold=None, compiled=None):
    """One construction under the programs of ``genome`` with constants ``theta``. Returns
    ``(totals, answer)``; raises ``BudgetExhausted`` when the meter ends (``hold`` keeps the state)."""
    score, pick = compiled if compiled is not None else (compile_vector_program(genome["score"], theta),
                                                         compile_vector_program(genome["pick"], theta, N_PREG))
    s = P.start()
    if hold is not None:
        hold.append(s)
    sensors.begin()
    prev = -1
    for step in range(P.n_vars):
        U = P.unassigned(s)
        allowed = P.allowed(s)
        if len(U) > 1:
            q = pick(sensors.pick_sensor(s, U, allowed, rng), len(U), None)
            q = q + 1e-9 * rng.random(len(U))
            k = min(shortlist, len(U))
            short = U[np.argsort(-q, kind="stable")[:k]] if k > 1 else U[[int(np.argmax(q))]]
        else:
            short = U
        D = P.candidates(s, short)
        best = None
        for i, v in enumerate(short):
            ok = allowed if P.domain is None else allowed & P.domain[int(v)]
            if not ok.any():
                continue
            value = score(sensors.score_sensor(s, int(v), D[i], prev, step, rng), P.n_opts, ok, sensors.rel)
            value = np.where(ok, value + 1e-9 * rng.random(P.n_opts), -np.inf)
            o = int(np.argmax(value))
            if best is None or value[o] > best[0]:
                best = (value[o], int(v), o)
        if best is None:                                       # no option left for any shortlisted variable: take any feasible pair
            for v in U:
                ok = allowed if P.domain is None else allowed & P.domain[int(v)]
                if ok.any():
                    best = (0.0, int(v), int(np.flatnonzero(ok)[0]))
                    break
            if best is None:
                raise Infeasible("no unassigned variable has an option left")
        _, v, o = best
        P.assign(s, v, o)
        sensors.assigned(s, v, o)
        prev = o
    return P.totals(s), P.assignment(s)


# =============================================================================================
# the acquirer machine
# =============================================================================================
def _draw(rng, kind, rows, d):
    """Noise for ``rows`` vectors of the ``d`` constants in use, drawn for every coordinate the
    machine allows and cut: adding a constant leaves the draws of the others as they were."""
    shape = (rows, max(LIMITS["theta"], d))        # the discoverer's weight vectors are longer than any theta
    block = rng.standard_normal(shape) if kind == "normal" else rng.uniform(-1.0, 1.0, shape)
    return block[:, :d]


def _avec(op, x, y, c, d, rng):
    if op == "copy":
        return x.copy()
    if op == "abs":
        return np.abs(x)
    if op == "sign":
        return np.sign(x)
    if op == "neg":
        return -x
    if op == "sqrt":
        return np.sqrt(np.abs(x))
    if op == "sq":
        return np.clip(x * x, 0.0, 1e6)
    if op == "mean":
        return np.full(d, float(x.mean()))
    if op == "norm":
        n = float(np.linalg.norm(x))
        return x / n * np.sqrt(d) if n > TINY else np.zeros(d)
    if op == "add":
        return x + y
    if op == "sub":
        return x - y
    if op == "mul":
        return np.clip(x * y, -1e6, 1e6)
    if op == "max":
        return np.maximum(x, y)
    if op == "min":
        return np.minimum(x, y)
    if op == "scale":
        return x * CONST[c]
    if op == "clipc":
        return np.clip(x, -abs(CONST[c]), abs(CONST[c]))
    if op == "floor":
        return np.maximum(x, abs(CONST[c]))
    if op == "noise":
        return _draw(rng, "normal", 1, d)[0]
    if op == "unif":
        return _draw(rng, "uniform", 1, d)[0]
    if op == "zero":
        return np.zeros(d)
    return np.ones(d)                                          # ones


def _wvec(op, W, a, b, F):
    x = W[a]
    if op == "wfit":
        return F.copy()
    if op == "wrank":
        order = np.argsort(x, kind="stable")
        r = np.empty(len(x))
        r[order] = np.arange(len(x))
        return r / max(len(x) - 1, 1)
    if op == "wcenter":
        return x - x.mean()
    if op == "wtop":
        q = min(max(abs(CONST[b]), 1.0 / len(x)), 1.0)
        n = max(1, int(round(q * len(x))))
        out = np.zeros(len(x))
        out[np.argsort(-x, kind="stable")[:n]] = 1.0
        return out
    if op == "wexp":
        return np.exp(np.clip(CONST[b] * x, -20.0, 20.0))
    if op == "wnorm":
        t = float(np.abs(x).sum())
        return x / t if t > TINY else np.zeros(len(x))
    if op == "wmul":
        return x * W[b % N_WREG]
    if op == "wadd":
        return x + W[b % N_WREG]
    if op == "wneg":
        return -x
    out = np.zeros(len(x))                                     # wbest
    out[int(np.argmax(x))] = 1.0
    return out


class Acquirer:
    """State of the learning principle during one acquisition: eight registers over the
    parameter space, a population, four registers over the population."""

    def __init__(self, genome: dict, start: np.ndarray, rng, pop: int | None = None):
        self.g, self.rng = genome, rng
        self.d = len(start)
        self.K = int(pop or genome["pop"])
        self.A = [np.zeros(self.d) for _ in range(N_AREG)]
        self.A[0] = start.copy()
        self.A[3] = start.copy()
        self.C = np.tile(start, (self.K, 1))
        self.W = [np.zeros(self.K) for _ in range(N_WREG)]
        self._run(genome["init"], None)

    def _run(self, program, F):
        d, K, A, W = self.d, self.K, self.A, self.W
        for op, dst, a, b in program:
            if op in POP_OPS:
                if op == "rows":
                    self.C = A[a][None, :] + A[b][None, :] * _draw(self.rng, "normal", K, d)
                elif op == "rowu":
                    self.C = A[a][None, :] + A[b][None, :] * _draw(self.rng, "uniform", K, d)
                elif op == "anti":
                    half = (K + 1) // 2
                    eps = _draw(self.rng, "normal", half, d)
                    self.C = np.concatenate([A[a] + A[b] * eps, A[a] - A[b] * eps])[:K]
                else:                                           # row
                    self.C[dst % K] = A[a]
            elif op in W_OPS:
                if F is None:
                    continue                                     # before any evaluation there is no fitness
                if op in ("comb", "combabs"):
                    diff = self.C - A[b][None, :]
                    if op == "combabs":
                        diff = np.abs(diff)
                    A[dst] = W[a] @ diff
                else:
                    W[dst] = _wvec(op, W, a, b, F)
            else:
                A[dst] = _avec(op, A[a], A[b if op in A_BINARY else a], b, d, self.rng)
        for k in range(N_AREG):
            A[k] = np.clip(np.where(np.isfinite(A[k]), A[k], 0.0), -100.0, 100.0)
        self.C = np.clip(np.where(np.isfinite(self.C), self.C, 0.0), -100.0, 100.0)

    def propose(self) -> np.ndarray:
        self._run(self.g["propose"], None)
        return self.C.copy()

    def update(self, F: np.ndarray) -> None:
        self._run(self.g["update"], np.asarray(F, dtype=float))


# =============================================================================================
# the learner
# =============================================================================================
def _fitness(keys: np.ndarray) -> np.ndarray:
    """Mean rank of each candidate over the problems, ties sharing their mean rank (higher is better)."""
    n_c, n_p = keys.shape[:2]
    fit = np.zeros(n_c)
    for i in range(n_p):
        col = keys[:, i]
        order = np.lexsort((col[:, 1], col[:, 0]))
        ranks = np.empty(n_c)
        ranks[order] = np.arange(n_c)
        for value in {tuple(row) for row in col.tolist()}:
            same = np.flatnonzero((col[:, 0] == value[0]) & (col[:, 1] == value[1]))
            if len(same) > 1:
                ranks[same] = ranks[same].mean()
        fit += n_c - 1 - ranks
    return fit / n_p


class OpenLearner(Learner):
    """The learner of the open design. ``self.g`` is the mechanism; ``self.v`` is the first
    design's default version, used for the prediction form and for the local improvement at
    test time only."""

    def __init__(self, version: dict):
        self.g = validate(version)
        self.v = design_a.default()
        self.trace = {}

    def _cost(self, P, shortlist: int) -> float:
        factor = shortlist if not P.ordered else 1
        return float(factor * P.n_vars * P.n_opts + P.n_vars + 1)

    def acquire(self, problems, rng, memory=None):
        memory = {"entries": list((memory or {}).get("entries", []))}
        if problems[0].kind == "predict":
            capability, report = self._acquire_predict(problems, rng)
            return capability, memory, report
        capability, report = self._acquire_open(problems, rng)
        return capability, memory, report

    def _rollouts(self, problems, sensors, thetas, rng, meter):
        need = sum(self._cost(P, self.g["shortlist"]) for P in problems) * len(thetas)
        if meter.left() < need:
            return None
        keys = np.zeros((len(thetas), len(problems), 2))
        for c, theta in enumerate(thetas):
            compiled = (compile_vector_program(self.g["score"], theta), compile_vector_program(self.g["pick"], theta, N_PREG))
            for i, (P, sen) in enumerate(zip(problems, sensors)):
                try:
                    totals, _ = construct(P, sen, self.g, theta, rng, self.g["shortlist"], compiled=compiled)
                    keys[c, i] = _key(totals, P)
                except Infeasible:
                    keys[c, i] = (np.inf, np.inf)
        return keys

    def _acquire_open(self, problems, rng):
        g = self.g
        meter = problems[0].meter
        sensors = [Sensors(P, g) for P in problems]
        n = len(problems)
        rng_order, rng_acq, rng_con = (np.random.default_rng(int(x)) for x in rng.integers(0, 2 ** 63, size=3))
        order = rng_order.permutation(n)
        n_check = (min(max(1, int(round(g["holdback"] * n))), n - 1) if n > 1 else 0) if g["select"] == "best_of_3" else 0
        check, fit = order[:n_check], order[n_check:]
        start = np.array(g["theta"], dtype=float)
        report = {"form": "assign", "design": "o", "fit": len(fit), "held_back": len(check), "iterations": 0,
                  "constructions": 0, "failed": None}
        reserve = 3.0 * sum(self._cost(problems[i], g["shortlist"]) for i in check)
        fit_cost = np.array([self._cost(problems[i], g["shortlist"]) for i in fit])
        acq = Acquirer(g, start, rng_acq)
        last_best = start.copy()
        try:
            while len(fit) > 0:
                batch = min(g["batch"], len(fit))
                chosen = rng_order.choice(len(fit), size=batch, replace=False)
                if meter.left() - reserve < acq.K * fit_cost[chosen].sum():
                    break
                cands = acq.propose()
                keys = self._rollouts([problems[fit[i]] for i in chosen], [sensors[fit[i]] for i in chosen], cands, rng_con, meter)
                if keys is None:
                    break
                F = _fitness(keys)
                last_best = cands[int(np.argmax(F))].copy()
                acq.update(F)
                report["iterations"] += 1
                report["constructions"] += len(cands) * batch
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended inside a construction"
        chosen_theta, learned = start, False
        options = {"start": start, "state": acq.A[0].copy(), "last_best": last_best}
        if report["iterations"] == 0:
            report["failed"] = report["failed"] or "decide: the budget did not allow one round of learning"
        elif n_check == 0:                                     # no check: the selection rule names the vector
            chosen_theta, learned = options[g["select"] if g["select"] != "best_of_3" else "state"], True
            report["held_back"] = 0
        else:
            names = ["start", "state", "last_best"]
            try:
                keys = self._rollouts([problems[i] for i in check], [sensors[i] for i in check],
                                      np.stack([options[k] for k in names]), rng_con, meter)
                if keys is None:
                    report["failed"] = "decide: no budget left for the held-back check"
                else:
                    f = _fitness(keys)
                    report["held_back"] = {k: float(f[j]) for j, k in enumerate(names)}
                    best = int(np.argmax(f))
                    if f[best] > f[0]:                          # a learned vector must beat the start strictly
                        chosen_theta, learned = options[names[best]], True
                    else:
                        report["failed"] = "self-assess: nothing learned beat the starting constants on held-back problems"
            except BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
        report["learned"] = learned
        return {"kind": "open", "theta": [float(x) for x in chosen_theta], "learned": learned}, report

    def apply(self, capability, problem, rng):
        if problem.kind == "predict":
            return self._apply_predict(capability, problem)
        return self._apply_open(capability, problem, rng)

    def _apply_open(self, capability, P, rng):
        if P.start_answer is not None:
            best = P.start_answer.copy()
            try:
                totals = P.start_totals if P.start_totals is not None else P.evaluate(best)
            except BudgetExhausted:
                return best
            return self._improve(None, P, rng, best, _key(totals, P))
        theta = np.array(capability["theta"] if capability and capability.get("kind") == "open" else self.g["theta"], dtype=float)
        shortlist = self.g["shortlist"]
        if not P.ordered:
            while shortlist > 1 and self._cost(P, shortlist) > P.meter.left():
                shortlist //= 2
        hold = []
        try:
            totals, answer = construct(P, Sensors(P, self.g), self.g, theta, rng, shortlist, hold=hold)
        except (BudgetExhausted, Infeasible):
            return _finish_arbitrarily(P, hold[0] if hold else None)
        return self._improve(None, P, rng, answer, _key(totals, P))
