"""Graph partitioning on the graphs of Johnson, Aragon, McGeoch and Schevon (1989).

Published form: an undirected graph without edge weights, and the sizes m_1, ..., m_k of k
parts that add up to the number of vertices n. An answer puts every vertex in one part so that
part j holds exactly m_j vertices; its value is the number of edges whose two ends are in
different parts, to be made small. Two kinds of size vector are published for these graphs: k
equal parts (k = 2, 4 or 5, each of n/k vertices) and two unequal parts (m_1, n - m_1).

Instances: a graph file together with one size vector. The graph files are the 24 files G124.*,
G250.*, G500.*, G1000.* (random graphs) and U500.*, U1000.* (random geometric graphs) of D. S.
Johnson's directory pub/dsj/partition of the DIMACS archive. The size vectors and the reference
values are the rows for these graphs in the result tables of de Meijer, Sotirov, Wiegele and
Zhao, "Partitioning through projections: strong SDP bounds for large graph partition problems"
(arXiv:2205.06788v2), read from the data files of the e-print's source archive: columns n, k
(or m1), UB and graph. 78 instances: 24 with k = 2, 8 with k = 4 or 5 on the small graphs, 16
with k = 4, 16 with k = 5, and 14 with two unequal parts.

Reference: the column UB of those tables, an upper bound on the minimum cut that the source
says was "obtained by heuristics or the optimal solution from the literature". The source
publishes no partition, so that a partition with this cut exists rests on its statement. It is
not a proven optimum (the same tables print lower bounds, which meet it on a few instances only
and are not read here), and it is loose: a plain swap tabu search written for the independent
audit of this adapter (eight seconds per instance) went below it on 22 of the 78 instances, 8
of them among the 24 fresh ones, and reached it on 16 more. A score of 1 therefore means "the
source's upper bound reached or beaten", nothing more.

Answer form: variable i is vertex i, option j is part j; option j can be taken by exactly
``capacity[j] = m_j`` variables (the capacities add up to n, so every well-formed complete
answer has exactly the published sizes, and every valid published answer is such an answer).
One term group: [0] the number of edges whose two ends are both assigned and lie in different
parts (soft). There is no hard group: the balance is the capacity.

Exposed arrays: ``var_var[0]`` is the adjacency matrix, entry (i, j) = 1 when j stands in the
neighbour list of the line of vertex i in the graph file (the files list every edge from both
ends; the parser refuses a file that does not), else 0; ``capacity`` is the size vector of the
table row. Nothing else: the files also print a coordinate pair per vertex (all zero for the G
graphs, the generator's points for the U graphs); the published problem and its value are a
function of the graph alone, so the coordinates are not exposed.

Score: the share of the way from the expected cut of a uniformly random valid answer to the
reference that an answer covers, cut to [0, 1]; 0 for an invalid answer. The expected cut is
exact: (number of edges) * (1 - sum_j m_j (m_j - 1) / (n (n - 1))). The plain ratio of the
reference to the cut is not used because a random valid answer would score above 0.5 on it on
the denser graphs (on 28 of the 78 instances; e.g. about 0.70 on G124.16 in two parts and 0.75
in four), and it is undefined at a cut of 0.

Threshold 0.90, an operating point and not an external fact: on average nine tenths of the way
from the expected cut of a random valid answer to the source's upper bound.

Groups: the published family and size of the graph (G124, G250, G500, G1000, U500, U1000). All
instances on one graph are in one group, so no graph is on both sides of a split. With the
kernel's split the 24 fresh instances stand on 8 graphs, all of them random graphs (G1000 in
the deciding half, G500 in the confirming half); no geometric graph is fresh. A mean over the
fresh instances is a mean over 8 graphs of one family, not over 24 independent samples.

Left out. By the size rule (at most 1,000 vertices and n * k at most 30,000, fixed before
anything was scored): nothing. Not instances of this benchmark: the file G.sub.500 of the DIMACS
directory, for which the tables give no value; the rows of the tables for graphs that are not
in the DIMACS directory (meshes, KKT, spin glass and planar graphs); the table of the appendix
(largeGraphSparse3n_datafile1.tex), which repeats the k = 2 rows of the large graphs with the
same UB.
"""
from __future__ import annotations

import gzip
import io
import re
import tarfile

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

MAX_VERTICES, MAX_CELLS = 1000, 30000
GRAPHS = ("G124.02", "G124.04", "G124.08", "G124.16", "G250.01", "G250.02", "G250.04", "G250.08",
          "G500.005", "G500.01", "G500.02", "G500.04", "G1000.0025", "G1000.005", "G1000.01", "G1000.02",
          "U500.05", "U500.10", "U500.20", "U500.40", "U1000.05", "U1000.10", "U1000.20", "U1000.40")
ARCHIVE = "arxiv-2205.06788v2.tar.gz"
# the table data files of the e-print, and the column that states the sizes of the parts
TABLES = (("Hager_datafile1.tex", "k"), ("Hager_datafile2.tex", "k"), ("largeGraphSparse5n_datafile3.tex", "k"),
          ("largeGraphSparse5n_datafile1.tex", "k"), ("largeGraphSparse5n_datafile2.tex", "k"),
          ("hagerBisection_datafile1.tex", "m1"), ("spinglass2pmBisection_datafile1.tex", "m1"))


def parse_graph(text: str) -> np.ndarray:
    """The adjacency matrix. A line of the file reads: vertex number, "(x,y)", number of
    neighbours, the neighbours."""
    chunks = re.split(r"\([^)]*\)", text)                # between two coordinate pairs: degree, neighbours, next vertex
    n = len(chunks) - 1
    A = np.zeros((n, n), dtype=bool)
    number = int(chunks[0])
    for i in range(n):
        values = [int(x) for x in chunks[i + 1].split()]
        degree, neighbours = values[0], values[1:1 + values[0]]
        if number != i + 1 or len(values) != degree + (1 if i == n - 1 else 2) or len(set(neighbours)) != degree:
            raise ValueError("graph file not in the expected form")
        A[i, np.array(neighbours, dtype=np.int64) - 1] = True
        number = values[-1]
    if not np.array_equal(A, A.T) or A.diagonal().any():
        raise ValueError("graph file does not list every edge from both ends")
    return A


def parse_tables(raw: bytes):
    """Rows (graph, sizes of the parts, UB) of the e-print's table data files."""
    tar = tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw)))
    rows = []
    for member, column in TABLES:
        lines = [line for line in tar.extractfile(member).read().decode("latin-1").splitlines() if line.strip()]
        head = [x.strip() for x in lines[0].split(",")]
        for line in lines[1:]:
            row = dict(zip(head, [x.strip() for x in line.split(",")]))
            if row["graph"] not in GRAPHS:
                continue
            n, m = int(row["n"]), int(row[column])
            sizes = [n // m] * m if column == "k" else [m, n - m]
            rows.append((row["graph"], f"{column[0]}{m}", sizes, float(row["UB"])))
    return rows


def cut(ends: np.ndarray, a: np.ndarray) -> float:
    """The number of edges whose ends are in different parts."""
    return float(np.count_nonzero(a[ends[0]] != a[ends[1]]))


def random_cut(n_edges: int, sizes: np.ndarray) -> float:
    """The expected cut of a uniformly random answer with these part sizes (exact)."""
    n = int(sizes.sum())
    return float(n_edges * (1.0 - float((sizes * (sizes - 1)).sum()) / (n * (n - 1))))


class PartitionProblem(AssignProblem):
    def __init__(self, A: np.ndarray, sizes: np.ndarray, meter):
        super().__init__(n_vars=len(A), n_opts=len(sizes), hard=[False], ordered=False, capacity=sizes, var_var=(A,),
                         meter=meter)

    def partial_totals(self, a):
        placed = np.flatnonzero(a >= 0)
        part = a[placed]
        between = self.var_var[0][np.ix_(placed, placed)] * (part[:, None] != part[None, :])
        return np.array([float(between.sum()) / 2.0])       # every edge stands twice in the matrix

    def _new(self):
        s = super()._new()
        s["in"] = np.zeros((self.n_vars, self.n_opts))      # assigned neighbours of each vertex, by part
        s["all"] = np.zeros(self.n_vars)                    # assigned neighbours of each vertex
        return s

    def _rows(self, s, variables):
        v = np.asarray(variables, dtype=np.int64)
        rows = (s["all"][v][:, None] - s["in"][v])[:, :, None]
        rows[:, s["used"] >= self.capacity] = 0.0           # a part that is full
        return rows

    def _push(self, s, v, o):
        s["tot"] = s["tot"] + (s["all"][v] - s["in"][v, o])
        s["a"][v] = o
        s["in"][:, o] += self.var_var[0][:, v]
        s["all"] += self.var_var[0][:, v]


class Partitioning(Environment):
    name = category = "partitioning"
    form = "assign"
    threshold = 0.90
    anchor = ("an operating point, not an external fact: on average nine tenths of the way from the expected cut of a "
              "uniformly random valid partition to the upper bound printed in the tables of arXiv:2205.06788v2, which is "
              "a published upper bound, not a proven optimum: a plain local search goes below it on some instances")

    def __init__(self):
        fetch.fetch("partitioning", quiet=True)
        self.graphs = {}
        for name in GRAPHS:
            A = parse_graph(open(fetch.path("partitioning", name)).read())
            self.graphs[name] = {"A": A, "ends": np.array(np.nonzero(np.triu(A)))}
        self.instances = {}
        for graph, tag, sizes, value in parse_tables(open(fetch.path("partitioning", ARCHIVE), "rb").read()):
            n = len(self.graphs[graph]["A"])
            sizes = np.array(sizes, dtype=np.int64)
            if sizes.sum() != n or sizes.min() < 1:
                raise ValueError(f"{graph} {tag}: the sizes of the table do not fit the graph file")
            if n > MAX_VERTICES or n * len(sizes) > MAX_CELLS:      # the size rule
                continue
            self.instances[f"{graph}-{tag}"] = {"graph": graph, "sizes": sizes, "value": value}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["value"])

    def group(self, instance_id):
        return instance_id.split(".")[0]                 # the family and size of the graph: G124 ... U1000

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        A = self.graphs[inst["graph"]]["A"]
        rng = np.random.default_rng(seed)
        n, k = len(A), len(inst["sizes"])
        var_perm, _ = relabel(rng, n)                    # new vertex -> old vertex
        opt_perm, _ = relabel(rng, k)                    # new part -> old part
        problem = PartitionProblem(A[np.ix_(var_perm, var_perm)].astype(float), inst["sizes"][opt_perm], meter)

        def decode(answer):
            out = np.empty(n, dtype=np.int64)
            out[var_perm] = opt_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        graph, sizes = self.graphs[inst["graph"]], inst["sizes"]
        n, k = len(graph["A"]), len(sizes)
        a = np.asarray(answer)
        if a.shape != (n,) or a.dtype.kind not in "iu" or a.min() < 0 or a.max() >= k \
                or not np.array_equal(np.bincount(a, minlength=k), sizes):
            return 0.0
        value, chance = cut(graph["ends"], a), random_cut(graph["ends"].shape[1], sizes)
        if chance <= inst["value"]:
            return 0.0
        return float(min(1.0, max(0.0, (chance - value) / (chance - inst["value"]))))
