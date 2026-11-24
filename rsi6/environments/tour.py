"""Symmetric travelling salesman instances of TSPLIB95 (G. Reinelt).

Published form: n cities and a distance d(i, j) = d(j, i) for every pair, given either as coordinates
(NODE_COORD_SECTION) with a distance function named in EDGE_WEIGHT_TYPE, or as an explicit matrix
(EDGE_WEIGHT_SECTION, laid out as EDGE_WEIGHT_FORMAT says). An answer is a tour that visits every city
once and returns to its start; its value is its length, the sum of the n distances between cities that
follow each other, to be made small. The distance functions are those of the TSPLIB95 documentation
(tsp95.pdf, section 2): EUC_2D nint(sqrt(dx^2 + dy^2)) with nint(x) = (int)(x + 0.5); CEIL_2D the same
rounded up; ATT the pseudo-Euclidean function (r = sqrt((dx^2 + dy^2) / 10), t = nint(r), t + 1 if t < r);
GEO the geographical function with PI = 3.141592 and RRR = 6378.388 on coordinates read as DDD.MM,
d = (int)(RRR * acos(0.5 * ((1 + q1) * q2 - (1 - q1) * q3)) + 1). One departure from the text of the
documentation, stated plainly: for GEO the degrees are the integer part of the coordinate (truncation),
not nint as the pdf prints (deg = nint(x[i])). Only truncation reproduces the lengths the source lists
for its own published optimal tours of the GEO instances (ulysses16 6859, ulysses22 7013, gr96 55209; with
nint the same tours measure 7030, 7230 and 56120), and with truncation the exact optimum of burma14 and of
ulysses16, computed by the builder's check over all subsets, is the listed one. Of the 43 instances used
25 are EUC_2D, 5 GEO, 1 ATT and 12 EXPLICIT (FULL_MATRIX, UPPER_ROW, LOWER_DIAG_ROW); none is CEIL_2D.

Reference: the optimal tour length the source lists for the instance in its page of optimal solutions
(TSP-BEST.html, formerly STSP.html; "all problems are now solved to optimality"). It is a value an
answer attains, not a bound: for 23 of the 43 instances used the source also publishes an optimal tour
(<name>.opt.tour.gz), and each of them reproduces the listed length exactly under the functions above
(checked when the adapter loads: an instance whose published tour did not reproduce its listed length
would be left out; none is). For the other 20 the source publishes the length only; it is attainable on
the source's statement that it is the length of an optimal tour (for two of them, burma14 and gr17, the
builder's check found it by exact dynamic programming). The reference and the published tours
are read by the kernel only (``reference``, ``score``); nothing of them is in a problem object. The
COMMENT, NAME and DISPLAY_DATA fields of a file are not exposed either.

Answer form (the generic assignment form, exact): variable i is city i, option k is the k-th position of
a cycle of n positions; every position takes one city (capacity 1), so the complete answers are exactly
the permutations, and every tour is one (in 2n ways: any start, either direction, all of the same
length). One term group, soft: the length. Its terms are the ordered pairs (i, j) of cities, worth
d(i, j) * c(p(i), p(j)), where c(k, l) = 1 if position l follows position k on the cycle and 0
otherwise; a term counts once both its cities are placed. For a complete answer the total is the sum of
d over the n pairs of cities in consecutive positions, the last and the first included: the published
tour length. There is no hard group: capacity alone makes an answer a tour.

Exposed arrays: ``var_var[0]`` is the n-by-n distance matrix d, computed from NODE_COORD_SECTION by the
function EDGE_WEIGHT_TYPE names, or read from EDGE_WEIGHT_SECTION; its diagonal, which no tour reads (and
which the GEO function would make 1), is presented as 0. ``opt_opt[0]`` is c, the successor relation of
the cycle of positions: it is the definition of a tour, the same for every instance of a size, and holds
nothing of the instance but n. ``capacity`` is 1 for every position. Coordinates are not exposed: they
exist only for a part of the instances and mean different things under different distance functions, and
the length reads d alone. Cities and positions are relabelled independently with the seed, so that
neither the order of the cities in the file nor where a tour starts or which way it runs carries
anything; ``decode`` maps an answer back to the file's cities and the cycle's own positions.

Score: the share of the way from the expected length of a uniformly random tour (n times the mean
distance of a pair of different cities, exact) to the listed optimal length that the tour covers, cut to
[0, 1]; 1 when the optimal length is reached, 0 for an answer that is not a permutation. The plain ratio
of optimal length to tour length is not used because the expected length of a uniformly random tour
would score above 0.5 on it on one instance (ulysses16 0.526; burma14 0.498, gr17 0.447 come next) and
between 0.07 and 0.15 on the instances of 96 cities and more: one scale is used for all instances, and
on the ratio "no better than chance" would be worth half the credit on the smallest ones.

Threshold: an operating point, not an external fact. It is the mean score that tours one tenth longer
than the listed optimal length would have on the same instances (``threshold_for``; ``threshold`` is its
value on the fresh instances of the kernel's split: 22 of them, because the split stops at half of the
43 instances; 0.9742). It is stated as an excess over the optimum because a fixed share of the way would
not mean one thing: a random tour is about twice the optimum at 16 cities and fourteen times the optimum
at 152, so the score of a tour 10 % too long runs from 0.889 to 0.992. The number 10 % is the builder's
choice, fixed before any algorithm was run on these instances; nothing was measured to set it. The
threshold is computed from the distances and the listed lengths alone. A consequence the audit
measured: on this scale the fresh mean is most sensitive to the smallest instances (ulysses16,
ulysses22, bayg29 and bays29, two sets of cities, carry about half of it), so the threshold can
also be met with tours about 20 % too long on the other fresh instances if those four are solved.

Groups: the family, which is the leading lower-case letters of the instance name (the contributor or
origin in TSPLIB's naming: gr, pr, kro, eil, ...). bayg29 and bays29 are the same 29 cities with two
distance tables and are one family, "bay". Whole families go to one side of every split.

Instances: the 43 instances on the source's list of optimal lengths with n * n <= 30,000 (n <= 173), a
rule on size alone that was fixed before anything was scored: att48 bayg29 bays29 berlin52 bier127
brazil58 burma14 ch130 ch150 dantzig42 eil51 eil76 eil101 fri26 gr17 gr21 gr24 gr48 gr96 gr120 gr137 hk48
kroA100 kroB100 kroC100 kroD100 kroE100 kroA150 kroB150 lin105 pr76 pr107 pr124 pr136 pr144 pr152 rat99
rd100 st70 swiss42 u159 ulysses16 ulysses22. Left out by that rule (more than 173 cities; their files are
not fetched): a280 ali535 att532 brd14051 brg180 d198 d493 d657 d1291 d1655 d2103 d15112 d18512 dsj1000
fl417 fl1400 fl1577 fl3795 fnl4461 gil262 gr202 gr229 gr431 gr666 kroA200 kroB200 lin318 linhp318 nrw1379
p654 pa561 pcb442 pcb1173 pcb3038 pla7397 pla33810 pla85900 pr226 pr264 pr299 pr439 pr1002 pr2392 rat195
rat575 rat783 rd400 rl1304 rl1323 rl1889 rl5915 rl5934 rl11849 si175 si535 si1032 ts225 tsp225 u574 u724
u1060 u1432 u1817 u2152 u2319 usa13509 vm1084 vm1748. No instance is left out for any other reason.
"""
from __future__ import annotations

import gzip
import re

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel, split
from rsi6.kernel.problem import AssignProblem

MAX_CELLS = 30000                      # n_vars * n_opts = n * n; the size rule
N_INSTANCES = 43                       # the instances the size rule admits (named in the module text)
EXCESS = 0.10                          # the threshold is the mean score of tours this much longer than the optimum
SECTIONS = ("NODE_COORD_SECTION", "EDGE_WEIGHT_SECTION", "DISPLAY_DATA_SECTION", "TOUR_SECTION", "FIXED_EDGES_SECTION",
            "DEPOT_SECTION", "DEMAND_SECTION", "EDGE_DATA_SECTION")


def read(path: str) -> str:
    """The text of a published file, unpacked in memory if it is gzip."""
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("latin-1")


def parse(text: str):
    """``(fields, sections)`` of a TSPLIB file: 'KEY : value' lines, and the numbers under each section keyword."""
    fields, sections, current = {}, {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        head = line.split(":")[0].split()[0] if line.split(":")[0].split() else ""
        if line == "EOF":
            break
        if head in SECTIONS:
            current = sections.setdefault(head, [])
        elif current is None or (":" in line and re.fullmatch(r"[A-Z_]+", head)):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
            current = None
        else:
            current.extend(line.split())
    return fields, sections


def nint(x):
    return np.floor(x + 0.5)           # (int)(x + 0.5) for the non-negative numbers it is applied to


def geo_radians(v, whole=np.trunc):
    degrees = whole(v)
    return 3.141592 * (degrees + 5.0 * (v - degrees) / 3.0) / 180.0


def coordinate_distances(kind: str, x: np.ndarray, y: np.ndarray, whole=np.trunc) -> np.ndarray:
    """The published distance function ``kind`` on every pair of cities."""
    dx, dy = x[:, None] - x[None, :], y[:, None] - y[None, :]
    if kind == "EUC_2D":
        return nint(np.sqrt(dx * dx + dy * dy))
    if kind == "CEIL_2D":
        return np.ceil(np.sqrt(dx * dx + dy * dy))
    if kind == "ATT":
        r = np.sqrt((dx * dx + dy * dy) / 10.0)
        t = nint(r)
        return np.where(t < r, t + 1.0, t)
    if kind == "GEO":
        lat, lon = geo_radians(x, whole), geo_radians(y, whole)
        q1 = np.cos(lon[:, None] - lon[None, :])
        q2 = np.cos(lat[:, None] - lat[None, :])
        q3 = np.cos(lat[:, None] + lat[None, :])
        return np.trunc(6378.388 * np.arccos(np.clip(0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3), -1.0, 1.0)) + 1.0)
    raise ValueError(f"distance function {kind} is not implemented")


def explicit_distances(layout: str, n: int, numbers) -> np.ndarray:
    """An explicit matrix in one of the published layouts, made full and symmetric."""
    w = np.array([float(t) for t in numbers])
    if layout == "FULL_MATRIX":
        if len(w) != n * n:
            raise ValueError("wrong number of weights")
        return w.reshape(n, n)
    rows = {"UPPER_ROW": lambda i: range(i + 1, n), "UPPER_DIAG_ROW": lambda i: range(i, n),
            "LOWER_ROW": lambda i: range(0, i), "LOWER_DIAG_ROW": lambda i: range(0, i + 1),
            "LOWER_COL": lambda i: range(i + 1, n), "LOWER_DIAG_COL": lambda i: range(i, n),
            "UPPER_COL": lambda i: range(0, i), "UPPER_DIAG_COL": lambda i: range(0, i + 1)}
    if layout not in rows:
        raise ValueError(f"matrix layout {layout} is not implemented")
    D, k = np.zeros((n, n)), 0
    for i in range(n):
        for j in rows[layout](i):
            D[i, j] = D[j, i] = w[k]
            k += 1
    if k != len(w):
        raise ValueError("wrong number of weights")
    return D


def distances(fields: dict, sections: dict, whole=np.trunc) -> np.ndarray:
    n, kind = int(fields["DIMENSION"]), fields["EDGE_WEIGHT_TYPE"]
    if kind == "EXPLICIT":
        D = explicit_distances(fields["EDGE_WEIGHT_FORMAT"], n, sections["EDGE_WEIGHT_SECTION"])
    else:
        rows = np.array([float(t) for t in sections["NODE_COORD_SECTION"]]).reshape(n, 3)
        if rows[:, 0].astype(int).tolist() != list(range(1, n + 1)):
            raise ValueError("cities are not numbered 1..n in order")
        D = coordinate_distances(kind, rows[:, 1], rows[:, 2], whole)
    if not np.array_equal(D, D.T):
        raise ValueError("not a symmetric instance")
    D = D.copy()
    np.fill_diagonal(D, 0.0)               # no tour reads d(i, i)
    return D


def parse_tour(text: str, n: int) -> np.ndarray:
    """A published tour as the cities (from 0) in the order they are visited."""
    _, sections = parse(text)
    cities = [int(t) for t in sections["TOUR_SECTION"]]
    if cities and cities[-1] == -1:
        cities = cities[:-1]
    tour = np.array(cities, dtype=np.int64) - 1
    if sorted(tour.tolist()) != list(range(n)):
        raise ValueError("the published tour is not a permutation of the cities")
    return tour


def positions(tour) -> np.ndarray:
    """The answer form of a tour given as cities in visiting order: the position of each city."""
    tour = np.asarray(tour, dtype=np.int64)
    p = np.empty(len(tour), dtype=np.int64)
    p[tour] = np.arange(len(tour))
    return p


def length(D: np.ndarray, p) -> float:
    """The length of the tour in which city i has position p[i] (a permutation)."""
    order = np.empty(len(p), dtype=np.int64)
    order[np.asarray(p, dtype=np.int64)] = np.arange(len(p))
    return float(D[order, np.roll(order, -1)].sum())


def random_length(D: np.ndarray) -> float:
    """The expected length of a uniformly random tour: n times the mean distance of two different cities (exact)."""
    n = len(D)
    return float((D.sum() - np.trace(D)) / (n - 1))


def optimal_lengths(text: str) -> dict:
    """The source's list 'name : length'. An entry that is not one plain number is not used."""
    plain = re.sub(r"<[^>]+>", "\n", text)
    found, twice = {}, set()
    for name, value in re.findall(r"^\s*([A-Za-z]+\d+)\s*:\s*(.+?)\s*$", plain, flags=re.M):
        if name in found or not re.fullmatch(r"\d+", value):
            twice.add(name)
        found[name] = value
    return {name: float(value) for name, value in found.items() if name not in twice}


def cycle(n: int) -> np.ndarray:
    """c(k, l) = 1 if position l follows position k on the cycle of n positions."""
    C = np.zeros((n, n))
    C[np.arange(n), (np.arange(n) + 1) % n] = 1.0
    return C


class TourProblem(AssignProblem):
    def __init__(self, D: np.ndarray, C: np.ndarray, meter):
        n = len(D)
        self.D, self.C = D, C
        self._after = np.argmax(C, axis=1)                   # the position that follows each position
        self._before = np.argmax(C, axis=0)                  # the position each position follows
        super().__init__(n_vars=n, n_opts=n, hard=[False], ordered=False, capacity=np.ones(n, dtype=np.int64),
                         var_var=(D,), opt_opt=(C,), meter=meter)

    def partial_totals(self, a):
        placed = np.flatnonzero(a >= 0)
        where = a[placed]
        return np.array([float((self.D[np.ix_(placed, placed)] * self.C[np.ix_(where, where)]).sum())])

    def _new(self):
        s = super()._new()
        s["G"] = np.zeros((self.n_vars, self.n_opts))        # change of the length if city v took position k
        return s

    def _rows(self, s, variables):
        rows = s["G"][np.asarray(variables, dtype=np.int64)][:, :, None].copy()
        rows[:, s["used"] >= self.capacity] = 0.0            # a position that is already taken
        return rows

    def _push(self, s, v, o):
        s["tot"] = s["tot"] + s["G"][v, o]
        s["a"][v] = o
        s["G"][:, self._before[o]] += self.D[:, v]           # a city placed just before o is followed by v
        s["G"][:, self._after[o]] += self.D[v, :]            # a city placed just after o follows v


class Tour(Environment):
    name = category = "tour"
    form = "assign"
    anchor = ("an operating point, not an external fact: the mean score that tours one tenth longer than the optimal tour "
              "length TSPLIB lists would have on the same instances (the score being the share of the way from the expected "
              "length of a uniformly random tour to that optimal length)")

    def __init__(self):
        manifest = fetch.fetch("tour", quiet=True)
        have = {e["path"] for e in manifest["files"] if not e.get("missing")}
        listed = optimal_lengths(read(fetch.path("tour", "TSP-BEST.html")))
        self.instances = {}
        for path in sorted(have):
            name = path[:-len(".tsp.gz")]
            if not path.endswith(".tsp.gz") or name not in listed:
                continue
            fields, sections = parse(read(fetch.path("tour", path)))
            n = int(fields["DIMENSION"])
            if fields.get("TYPE", "TSP").split()[0] != "TSP" or n * n > MAX_CELLS:
                continue
            D = distances(fields, sections)
            inst = {"D": D, "value": listed[name], "chance": random_length(D), "tour": None}
            if name + ".opt.tour.gz" in have:
                inst["tour"] = parse_tour(read(fetch.path("tour", name + ".opt.tour.gz")), n)
                if length(D, positions(inst["tour"])) != inst["value"]:
                    continue                 # a published tour must reproduce the listed length (it does for all 23)
            self.instances[name] = inst
        if len(self.instances) != N_INSTANCES:           # a file the source stopped serving must not shrink the set unseen
            raise RuntimeError(f"tour: {len(self.instances)} usable instances, {N_INSTANCES} expected")
        self.threshold = self.threshold_for(split(self, 16, 24)[1])

    def instance_ids(self):
        return sorted(self.instances)

    def threshold_for(self, instance_ids):
        """The mean score of tours ``EXCESS`` longer than the listed optimal length, on exactly these instances."""
        at = [(inst["chance"] - (1.0 + EXCESS) * inst["value"]) / (inst["chance"] - inst["value"])
              for inst in (self.instances[i] for i in instance_ids)]
        return float(np.mean(at))

    def reference(self, instance_id):
        return float(self.instances[instance_id]["value"])

    def reference_answer(self, instance_id):
        """The published optimal tour in the answer form, or ``None`` (kernel only, for audits)."""
        tour = self.instances[instance_id]["tour"]
        return None if tour is None else positions(tour)

    def group(self, instance_id):
        family = re.match(r"[a-z]+", instance_id).group(0)           # the family: gr, pr, kro, eil, ...
        return "bay" if family in ("bayg", "bays") else family       # one set of 29 cities, two distance tables

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        n = len(inst["D"])
        var_perm, _ = relabel(rng, n)                    # new city -> city of the file
        opt_perm, _ = relabel(rng, n)                    # new position -> position on the cycle
        problem = TourProblem(inst["D"][np.ix_(var_perm, var_perm)], cycle(n)[np.ix_(opt_perm, opt_perm)], meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[var_perm] = opt_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        n = len(inst["D"])
        a = np.asarray(answer)
        if a.shape != (n,) or a.dtype.kind not in "iu" or sorted(a.tolist()) != list(range(n)):
            return 0.0
        value, chance = length(inst["D"], a), inst["chance"]
        if chance <= inst["value"]:
            return 0.0
        return float(min(1.0, max(0.0, (chance - value) / (chance - inst["value"]))))
