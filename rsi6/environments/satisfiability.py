"""Satisfiability: uniform random 3-SAT at the phase transition, the satisfiable sets of SATLIB.

Published form (SATLIB, H. Hoos and T. Stuetzle; DIMACS .cnf files): a formula in conjunctive
normal form. The line ``p cnf n m`` gives the numbers of variables and clauses; every following
line up to the line ``%`` is one clause, a list of non-zero integers closed by 0, where the
integer +v stands for variable v and -v for its negation. An answer gives every variable a
truth value. It is valid when every clause holds at least one true literal. There is no
objective: the published problem is to find a valid answer.

Reference: every instance of these sets is satisfiable. The source separated satisfiable from
unsatisfiable formulae with a complete algorithm ("unforced filtered"); its description page says
that the test sets uf* contain only satisfiable instances. The reference is therefore a status proved by the source, not a bound: some
assignment satisfies all m clauses. An answer of the form below attains it. The source
publishes no satisfying assignment. ``reference`` returns m, the number of clauses such an
assignment satisfies.

Answer form: variable v takes option 0 (false) or 1 (true); an option may be taken by any
number of variables; variables are free in order. Every truth assignment, and so every valid
published answer, is an answer of this form.

Term group, one only: [0] the number of falsified clauses (hard). A clause is a term that
reads the variables of its literals; it counts 1 when all of them are assigned and every one of
its literals is false, and 0 otherwise. On a complete answer the group is zero exactly when
the assignment satisfies the formula, which is the published validity. There is no soft group
because the published problem has no objective.

Exposed arrays, all computed from the clause lines of the instance file and from nothing else
(no attribute columns of variables or of options are exposed):
  var_opt[0][v, o]  the number of clauses that contain the literal of variable v which option o
                    makes true: column 1 counts the clauses with +v, column 0 those with -v.
  var_var[0][v, w]  the number of clauses that contain both +v and +w (v != w).
  var_var[1][v, w]  the number of clauses that contain both +v and -w.
  var_var[2][v, w]  the number of clauses that contain both -v and -w.
The diagonals of the three relations are zero. These arrays are the projections of the clause
list on single variables and on pairs of variables. The clause list itself relates three
variables at a time and has no generic field: it acts in full only through the hard group
(``candidates`` gives the exact number of clauses a step falsifies). The comment lines of a
file (generator settings) and the numbers of the ``p`` line are not exposed beyond the shape of
the arrays.

Relabelling: the variables are permuted, and each variable is negated or not at random (the
formula in which variable v is replaced by its negation is the same problem with the two
options of v exchanged). ``decode`` undoes both. The order of the clauses and of the literals
in a clause enters no exposed array.

Score: 1 if the answer is a truth assignment that satisfies every clause, otherwise 0. The
scale is all or nothing because an assignment that falsifies a clause is not a valid answer of
the published problem, and an invalid answer scores 0. The share of satisfied clauses is NOT
used: it would give credit to invalid answers, and a uniformly random assignment satisfies
seven eighths of the clauses of a 3-SAT formula, so that scale would sit near 0.875 for no
capability at all. Every valid answer reaches the reference, so there is no range of valid
values and the rule for random valid answers (the share of the way from a random valid answer
to the reference) has nothing to rescale. The mean score over instances is the share of
instances for which a satisfying assignment was produced.

Threshold 0.9; anchor: an operating point, not an external fact. A satisfying assignment for
nine in ten of the fresh instances. A mean of 1 is attainable by answers of the form, since every
instance is satisfiable; whether a satisfying assignment can be found within the budget of a test
is another matter (the audit found that a plain local search needs many times more evaluated
answers than the registered test budget pays for on the fresh sets, so every method may score 0).

Groups: the published set (uf50-218, ..., uf250-1065), which is also the size class: all
instances of a set have the same numbers of variables and clauses.

Instances used and left out, by a rule fixed before anything was scored: of each of the nine
sets, the twelve instances numbered 1 to 12 (the archive members uf<n>-01.cnf to
uf<n>-012.cnf), 108 instances in 9 groups. The instances numbered 13 and above are left out by
that rule alone (988 each of uf50-218 and uf100-430, 88 each of the seven other sets). No
instance is left out for its size: the largest has 250 variables and two options. The set
uf20-91 and the unsatisfiable sets (uuf...) of the same page are not part of this category's
benchmark; an unsatisfiable formula has no valid answer.
"""
from __future__ import annotations

import posixpath
import tarfile

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

SETS = {"uf50-218": (50, 218), "uf75-325": (75, 325), "uf100-430": (100, 430), "uf125-538": (125, 538),
        "uf150-645": (150, 645), "uf175-753": (175, 753), "uf200-860": (200, 860), "uf225-960": (225, 960),
        "uf250-1065": (250, 1065)}
PER_SET = 12


def parse(text: str):
    """``(n, clauses)`` of a DIMACS file as SATLIB writes it: comment lines ``c``, the line
    ``p cnf n m``, clauses closed by 0, and a closing line ``%`` after which nothing is read."""
    n = m = None
    clauses, current = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] == "c":
            continue
        if line[0] == "p":
            parts = line.split()
            if parts[1] != "cnf":
                raise ValueError("not a cnf file")
            n, m = int(parts[2]), int(parts[3])
            continue
        if line[0] == "%":
            break
        for token in line.split():
            x = int(token)
            if x == 0:
                clauses.append(current)
                current = []
            else:
                current.append(x)
    if n is None or current or len(clauses) != m or any(not c or max(abs(x) for x in c) > n for c in clauses):
        raise ValueError("the clauses do not match the header")
    return n, clauses


def table(clauses) -> np.ndarray:
    """The clauses as an (m, width) array of signed literals, 0 where a clause is shorter."""
    out = np.zeros((len(clauses), max(len(c) for c in clauses)), dtype=np.int64)
    for k, c in enumerate(clauses):
        out[k, :len(c)] = c
    return out


def falsified(literals: np.ndarray, truth: np.ndarray) -> int:
    """The number of clauses without a true literal under a complete truth assignment
    (``truth[v - 1]`` is the value of variable v)."""
    value = truth[np.abs(literals) - 1].astype(bool)             # the value of each literal's variable
    true = (literals != 0) & (value == (literals > 0))
    return int((~true.any(axis=1)).sum())


class SatProblem(AssignProblem):
    """``literals``: (m, width) signed literals over the variables 1..n, 0 for no literal."""

    def __init__(self, n: int, literals: np.ndarray, meter):
        self.present = literals != 0
        self.var = np.where(self.present, np.abs(literals) - 1, 0)
        self.pos = literals > 0
        rows = np.broadcast_to(np.arange(len(literals))[:, None], literals.shape)
        with_pos = np.zeros((len(literals), n), dtype=bool)       # clause c contains +v
        with_neg = np.zeros((len(literals), n), dtype=bool)       # clause c contains -v
        with_pos[rows[self.pos], self.var[self.pos]] = True
        neg = self.present & ~self.pos
        with_neg[rows[neg], self.var[neg]] = True
        # for each variable its clauses, and whether the variable satisfies the clause when true / when false
        inside = with_pos | with_neg
        self.width0 = inside.sum(axis=1).astype(np.int64)         # distinct variables of each clause
        self.of = [np.flatnonzero(inside[:, v]) for v in range(n)]
        depth = max(1, max(len(c) for c in self.of))
        self.occ = np.zeros((n, depth), dtype=np.int64)
        self.occ_real = np.zeros((n, depth), dtype=bool)
        self.occ_true = np.zeros((n, depth), dtype=bool)
        self.occ_false = np.zeros((n, depth), dtype=bool)
        for v, c in enumerate(self.of):
            self.occ[v, :len(c)], self.occ_real[v, :len(c)] = c, True
            self.occ_true[v, :len(c)], self.occ_false[v, :len(c)] = with_pos[c, v], with_neg[c, v]
        P, N = with_pos.astype(float), with_neg.astype(float)
        pairs = [P.T @ P, P.T @ N, N.T @ N]
        for matrix in pairs:
            np.fill_diagonal(matrix, 0.0)
        super().__init__(n_vars=n, n_opts=2, hard=[True], ordered=False, capacity=None,
                         var_opt=(np.column_stack([N.sum(axis=0), P.sum(axis=0)]),), var_var=pairs, meter=meter)

    def partial_totals(self, a):
        value = a[self.var]
        false = (value >= 0) & ((value == 1) != self.pos)        # an assigned literal that is false
        return np.array([float((false | ~self.present).all(axis=1).sum())])

    def _new(self):
        s = super()._new()
        s["open"] = self.width0.copy()                            # unassigned variables of each clause
        s["true"] = np.zeros(len(self.width0), dtype=np.int64)    # assigned variables that satisfy each clause
        return s

    def _rows(self, s, variables):
        variables = np.asarray(variables, dtype=np.int64)
        c, real = self.occ[variables], self.occ_real[variables]
        when_true, when_false = self.occ_true[variables], self.occ_false[variables]
        current = s["a"][variables]
        mine = np.where((current == 1)[:, None], when_true, False) | np.where((current == 0)[:, None], when_false, False)
        left = s["open"][c] - (current < 0)[:, None]              # after the variable is (re)assigned
        others = s["true"][c] - mine
        now = ((s["open"][c] == 0) & (s["true"][c] == 0) & real).sum(axis=1)
        out = np.zeros((len(variables), 2, 1))
        out[:, 0, 0] = ((left == 0) & (others == 0) & ~when_false & real).sum(axis=1) - now
        out[:, 1, 0] = ((left == 0) & (others == 0) & ~when_true & real).sum(axis=1) - now
        return out

    def _push(self, s, v, o):
        c = self.of[v]
        s["open"][c] -= 1
        s["true"][c] += (self.occ_true if o == 1 else self.occ_false)[v, :len(c)]
        s["tot"] = s["tot"] + float(((s["open"][c] == 0) & (s["true"][c] == 0)).sum())
        s["a"][v] = o


class Satisfiability(Environment):
    name = category = "satisfiability"
    form = "assign"
    threshold = 0.90
    anchor = ("an operating point, not an external fact: a satisfying assignment for nine in ten of the fresh "
              "instances (an instance scores 1 when every clause is satisfied and 0 otherwise; every instance is "
              "satisfiable, so a mean of 1 is attainable by answers of the form; the budget of a test may not allow it)")

    def __init__(self):
        fetch.fetch("satisfiability", quiet=True)
        self.instances = {}
        for group, (n, m) in SETS.items():
            wanted = {f"uf{n}-0{k}.cnf": k for k in range(1, PER_SET + 1)}       # the instances numbered 1 to 12
            with tarfile.open(fetch.path("satisfiability", group + ".tar.gz"), "r:gz") as archive:
                for member in archive:                                           # read in memory, never unpacked
                    k = wanted.get(posixpath.basename(member.name))
                    if k is None or not member.isfile():
                        continue
                    name = f"{group}/{k:02d}"
                    if name in self.instances:
                        raise ValueError(f"{name}: two members of the archive have this number")
                    size, clauses = parse(archive.extractfile(member).read().decode("ascii"))
                    if (size, len(clauses)) != (n, m):
                        raise ValueError(f"{name}: not the size of its set")
                    self.instances[name] = {"n": size, "literals": table(clauses), "group": group}
        if len(self.instances) != PER_SET * len(SETS):
            raise ValueError("an instance of the fixed selection is missing")

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(len(self.instances[instance_id]["literals"]))               # all clauses can be satisfied

    def group(self, instance_id):
        return self.instances[instance_id]["group"]                              # the published set, a size class

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        n, literals = inst["n"], inst["literals"]
        var_perm, var_new = relabel(rng, n)                    # new variable -> old variable, and old -> new
        flip = rng.integers(0, 2, size=n).astype(bool)         # new variable v stands for the negation of the old one
        new = var_new[np.abs(literals) - 1]
        sign = np.where((literals > 0) != flip[new], 1, -1)
        problem = SatProblem(n, np.where(literals != 0, sign * (new + 1), 0), meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[var_perm] = np.asarray(answer, dtype=np.int64) ^ flip
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        a = np.asarray(answer)
        if a.shape != (inst["n"],) or a.dtype.kind not in "iu" or not np.all((a == 0) | (a == 1)):
            return 0.0
        return 1.0 if falsified(inst["literals"], a) == 0 else 0.0
