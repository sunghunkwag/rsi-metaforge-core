"""Maximum clique: the benchmark graphs of the second DIMACS implementation challenge (1992-93).

Published form (gen_info.tex of the challenge, pinned): "Given an undirected graph, a clique of
the graph is a set of pairwise adjacent nodes. A maximum clique of a graph is a clique such that no
other clique has more vertices." An answer is a set of vertices; it is valid when every two of its
vertices are joined by an edge; its value is its number of vertices, to be made large. The graphs:
the files ``*.clq.b`` of graph/benchmarks/clique (66 graphs, listed in the table contents.tex
with a family code, nodes, edges and, for some, a clique size), and the graphs of
graph/benchmarks/volume/Clique that are not in that directory (gen*, C*, DSJC*); the volume's 23
graphs that are also in graph/benchmarks/clique (16 of them within the size rule) are byte-identical
copies of those files (checked) and are not fetched; C2000.5, C2000.9 and C4000.5 are above the size
rule (count corrected at the merge, from the second audit).

File format, as translators/binformat/README.binformat (pinned) states it: a first line with the
length of the preamble; the preamble, comment lines and one line ``p FORMAT NODES EDGES``; then
"the lower triangular part of the vertex-vertex adjacency matrix ... Each row of the matrix is
stored as sequence of bits, where the j'th bit is 1 if the edge (i,j) is in the graph ... (Note
that i >= j)". Two details the README leaves to code it points to (not fetched: it is code) were
read off the data, and ``read_graph`` raises an error on any file that breaks them: each row is
padded to whole bytes (row i, counted from 0, has i // 8 + 1 bytes; every binary block has exactly
that length), and the first bit of a row is the high bit of its first byte. Read so, none of the 69
files fetched has a bit on the diagonal or in the padding, and each has exactly as many 1 bits as
its p line has edges, except DSJC500.5 and DSJC1000.5 (not used), whose p lines count twice their
1 bits; read low bit first, 67 of the 69 have bits on or above the diagonal. The 51 graphs used
that the table lists have the nodes and edges it prints; the 39 cliques the source publishes
(below) are cliques of the graphs read so, of exactly the published size; and the four Hamming
graphs equal the graph contents.tex defines ("a node for each binary vector of length n ...
adjacent if and only if the corresponding bit vectors are hamming distance at least d apart"),
vertex k being the vector of value k (the builder's checks, outside this module). Here vertices
are numbered from 0, in the order of the rows.

Reference: the maximum clique size the source states for the graph, read by the scorer only. Five
kinds of statement are read, and all those found for a graph are kept in ``claims``:
  * solvers/results.dmclique (the steering committee's results file for its heuristic dmclique),
    which gives for each benchmark graph "the true maximum clique size, when known" as
    ``[OPT = k]``, and ``[OPT = ??]`` (or ``???``) where it is not known;
  * the column Clique Size of contents.tex: a plain number, or after ``$\\ge$`` a lower bound;
  * the column Max of solvers/results.dfmax, the sizes the exact branch and bound code dfmax
    reached on the graphs it finished ("Any benchmark graph not included ... either caused dfmax
    to run longer than 10 hours ... or was not run");
  * graph/benchmarks/clique/SOLUTIONS/<graph>.sol (J.-M. Bourjolly, P. Gill, G. Laporte, H.
    Mercure): the line ``s cqu k`` of doc/ccformat.tex and k lines ``v``, the comment "Solution is
    optimal."; their vertices are numbered from 0 (c-fat200-1.sol lists vertex 0, no file lists
    vertex n); the adapter raises an error unless the k vertices are a clique of the graph;
  * the comment lines of a graph file: "k max clique" (the san and gen graphs of L. Sanchis) and
    "Largest Clique: k" (keller) state the maximum; "Clique Size: k" followed by "Clique Elements
    are:" (brock, MANN) is the clique the generator built: a lower bound.
The reference is the value on which every statement of the maximum agrees; a graph with none is
left out, and the adapter raises an error if two of them disagree or a lower bound exceeds them.
None disagree. Of the 56 graphs used, 50 have ``[OPT = k]`` in results.dmclique, and their other
statements agree with it (32 in contents.tex, 28 in results.dfmax, 24 in a solution file, 13 in
their comment lines); hamming8-2 is one of the 50 ([OPT = 128] and a solution of 128), and the
table's "$\\ge$ 79" for it is a lower bound below it (contents.tex itself notes that the n-2
Hamming graphs have a maximum clique of 2^(n-1)). c-fat500-10 has only its solution file (126,
"Solution is optimal."; results.dmclique prints [OPT = ??] for it). The five gen graphs have only
their comment line ("44 max clique" and so on), files the source describes as "Artificially
generated instance with large, known embedded clique". The values are the source's; they were not
re-proved here. Where one is not the maximum, an answer can exceed it and the score is cut at 1.
The source publishes answers too: the 25 solution files and the clique lists in the comments of
the 12 brock files (numbered from 0) and of the 2 MANN files (numbered from 1, ended by "*"); each
is a clique of exactly the reference size and scores 1. LAST_UPDATESep23 says that the p_hat files
of 15 August were corrupted and were corrected; all 12 p_hat files fetched carry its note line, and
the five p_hat solution files are cliques of their stated sizes in them.

Answer form: the n vertices are the variables; each takes option 0 (out) or 1 (in); either option
may be taken by any number of vertices, in any order. An answer is the set of vertices with option
1. Every set of vertices is exactly one answer, so every published clique is an answer of the form;
an answer is a clique exactly when group [1] is 0, and its value is then minus group [0]: the valid
answers are the cliques of the graph, with their published value, and nothing else. (The empty set
is an answer with both groups 0; it is a clique of no vertices and scores 0.) Groups:
  [0] minus the number of vertices assigned option 1 (soft; one term per vertex);
  [1] the number of pairs of different vertices, both assigned option 1, that no edge joins (hard;
      one term per pair without an edge, counted as soon as both of its vertices are assigned).
Exposed array: var_var[0][u, v] = 1 where the file's bit for the pair (u, v) or (v, u) is 1, 0
elsewhere (diagonal 0): the adjacency matrix, the only field of the file besides its sizes. Nothing
else is exposed: no comment line, no edge count, no attribute of a vertex or an option. The
vertices are relabelled with the seed; the options are not (option 1 means "in").

One layout: every problem has two options, these two groups, one relation between variables and
nothing else; graphs differ only in their number of vertices, which the layout allows. Nothing is
padded.

Score: a valid answer with k vertices scores (k - 1) / (reference - 1), cut to [0, 1]: 1 at the
reference, 0 for a single vertex or none, increasing in k. The zero point is exact: a single vertex
is a clique of every graph, and no estimate is involved. An answer with two chosen vertices that no
edge joins scores 0, and so does anything that is not an integer array of 0s and 1s of length n
(no conversion, nothing repaired). For a reading of the scale, two rules with no search and no
learning were scored outside this module, on the benchmark graphs (the learner was not run): a
random maximal clique (vertices in a random order, each taken when it is adjacent to all taken so
far; 20 orders) averages 0.646 over the 56 graphs and 0.602 on the 24 fresh ones of the kernel's
split; the greedy rule (always take, among the vertices adjacent to all taken ones, one with the
most such neighbours; 5 runs) 0.827 and 0.845.

Threshold 0.90: an operating point, not an external fact (see ``anchor``), fixed knowing the two
rules' scores and no learner result: on average nine tenths of the way from a single vertex to the
published maximum (21 of 23 vertices on brock800_1 is 0.909, 7 of 8 on p_hat300-1 is 0.857), an
invalid answer counting 0. What the fresh instances can show: they are 11 brock, 7 p_hat, 4
hamming and 2 johnson graphs. The two johnson graphs (johnson8-2-4, johnson16-2-4) give 1 to every
maximal clique. contents.tex defines their vertices as the binary vectors of length n with two 1s,
two of them "adjacent if and only if their hamming distance is at least $d$", here 4, that is when
their 1s are in four different positions. A clique is then a set of disjoint pairs of positions,
and a maximal one leaves at most one of the n positions uncovered (n is even), so it has n/2
vertices, the published maximum. Both files equal that definition, vertex k being the k-th such
vector in increasing value, and the 105 maximal cliques of johnson8-2-4 all have 4 vertices
(checked outside this module). johnson8-2-4 (deciding half) is the subgraph of hamming8-4 (confirming
half) induced on its 28 weight-2 vectors, from the same contributor's generator; as every maximal
clique of it scores 1, the pair cannot carry a decision into its confirmation (second audit). The
four hamming graphs give 1 to the greedy rule in every run. The
greedy rule averages 0.87 on the p_hat and 0.74 on the brock graphs (whose generator "attempts to
'hide' cliques"). The kernel's halves put the brock and johnson graphs in the deciding half
(greedy 0.783). There the decision rests on the 11 brock graphs, which must average about 0.882
for the half to reach 0.90. The p_hat and hamming graphs form the confirming half, where the greedy
rule already averages 0.918 and would pass 0.90. So on a set that holds only hamming, johnson and
p_hat graphs, as that half does, the threshold is not 0.90 (``threshold_for``). Each hamming and
johnson graph counts at 1, the score a rule with no search reaches on it (the greedy rule in every
run on each hamming and johnson graph, and every maximal clique on the two johnson graphs above),
and each p_hat graph at 0.90; the threshold is their mean, 0.936 on the confirming half. A pass
there needs the p_hat graphs to average at least 0.90, as 0.90 asks of any other set, and more if
a hamming graph scores below 1; the greedy rule (0.87 on them, 0.918 on the half) does not pass.
The run record carries this threshold. Whether a pass on that half must also exceed the untrained
score by a stated margin is for the registration to say. On any other set, the deciding half and
the whole fresh set among them, the threshold stays 0.90, which the greedy rule does not reach
there; on the deciding half the johnson graphs are therefore not counted at 1, and the brock graphs
pass at about 0.882. The adapter did not choose the halves and does not select instances by
difficulty. The threshold of the confirming half was set knowing the greedy rule's score on it,
and no learner result.

Groups of instances: the family code of the table (Bro, CFat, Ham, Joh, Kel, PHat, San, Stein),
with two corrections from the source's own texts. First, the random graphs sanr*, coded (San) in
the table, form the family SanR of its notes ("random instances with sizes similar to those in
San"); their comment lines read "Randomly generated graph of similar size to "san" graphs, but with
differenct clique characteristics" (the source's spelling). san1000 carries the same DESCRIPTION
lines but stays in San. The table codes it (San) and gives it a clique size, 15. Its comment lines
have the form of the other san graphs: "1000 vertices 250500 edges 15 max clique" and a line of six
numbers, "c 1000 249000 985 1499 40473 7". A sanr graph instead has a line such as "random graph
200 vertices 13868 edges" and a line of three numbers, such as "c 200 0.300000 3769" (both from
sanr200_0.7). The choice matters to the split: SanR is a group of its fresh side and San one of
its training side, so san1000 in SanR would be a fresh instance of the deciding half, in the place
of p_hat500-1, and the confirming half would gain the two johnson graphs (checked outside this
module); san1000 stays where the table's code puts it. Second, the gen graphs, which the table
does not list, are put with San: the volume's instructions (instruct.tex) list them as the
"Sanchis graphs", and they share with the san graphs the contributor, the construction with a
known clique and the format of the comment lines, so that the split does not put siblings on both
sides. Sizes: Bro 12, CFat 7, Ham 4, Joh 4, Kel 2, PHat 7, San 16, SanR 2, Stein 2.
split(env, 16, 24) takes the groups Bro, Ham, Joh, SanR and PHat for the fresh side (29 graphs, of
which it keeps 24: brock200_2, johnson32-2-4, johnson8-4-4 and both sanr graphs are cut, so no
SanR graph is used) and draws the 16 training graphs from CFat, Kel, San and Stein.

Size rule (fixed before anything was scored): at most MAX_VERTICES = 1000 vertices; with two
options, vertices times options is at most 2,000, far below the 30,000 of the other adapters. The
largest graphs used, p_hat1000-1 and san1000, have 1,000 vertices (3,001 construction units).

Left out (69 graphs fetched, 56 used):
 * more than 1000 vertices by the table, not fetched (8): hamming10-2 and hamming10-4 (1,024),
   MANN_a45 (1,035), MANN_a81 (3,321), keller6 (3,361), p_hat1500-1, p_hat1500-2, p_hat1500-3
   (1,500); hamming10-2, MANN_a45 and p_hat1500-1 have a published maximum. From the volume,
   C2000.5, C2000.9 and C4000.5 (2,000 and 4,000 nodes by instruct.tex) are not fetched either; no
   value is published for them;
 * no maximum clique size published (13): p_hat500-3, p_hat700-2, p_hat700-3, p_hat1000-2,
   p_hat1000-3, sanr200_0.9 and sanr400_0.7, for which results.dmclique prints [OPT = ??] or
   [OPT = ???] and no other file gives a value; and C125.9, C250.9, C500.9, C1000.9, DSJC500.5 and
   DSJC1000.5 of the volume, for which no file of the source gives one (their comment lines state
   no clique size, and the volume's results form Appendix.tex is empty);
 * solution files not fetched (2 of 27): san2.sol, which names a graph san2.clq that the
   directory does not hold, has no ``s`` line and repeats its comment text in its ``v`` lines;
   hamming10-2.sol, whose graph is above the size rule.
"""
from __future__ import annotations

import os
import re

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

MAX_VERTICES = 1000              # the size rule; two options per vertex, so vertices * options is at most 2,000
CONFIRMING = ("Ham", "Joh", "PHat")   # a set of these groups only has its own threshold (threshold_for)
AT_MAXIMUM = ("Ham", "Joh")           # of them, those counted at 1: a rule with no search reaches their maximum
TABLE = "benchmarks/clique/contents.tex"
OPT = "solvers/results.dmclique"
DFMAX = "solvers/results.dfmax"
SOLUTIONS = "benchmarks/clique/SOLUTIONS/"


def read_graph(raw: bytes, decode: bool = True):
    """``(adjacent, preamble, nodes, edges)`` of a graph file in the DIMACS binary format
    (translators/binformat/README.binformat): a first line with the length of the preamble, the
    preamble (comment lines and the line ``p FORMAT NODES EDGES``), then the lower triangle of
    the adjacency matrix, row i (from 0) holding the bits of the pairs (i, j), j <= i, the first
    bit of a row the high bit of its first byte, each row padded to whole bytes. The diagonal and
    the padding must be zero and the number of 1 bits must be the EDGES of the ``p`` line."""
    end = raw.index(b"\n")
    length = int(raw[:end].decode("ascii"))
    preamble = raw[end + 1:end + 1 + length].decode("latin-1")
    lines = [line.split() for line in preamble.splitlines() if line.startswith("p")]
    if len(lines) != 1:
        raise ValueError("a graph file has one p line")
    n, edges = int(lines[0][2]), int(lines[0][3])
    if not decode:
        return None, preamble, n, edges
    block = np.frombuffer(raw, dtype=np.uint8, offset=end + 1 + length)
    width = np.arange(n) // 8 + 1                        # bytes of row i
    if len(block) != int(width.sum()):
        raise ValueError("the binary block does not have the published layout")
    start = np.concatenate([[0], np.cumsum(width)[:-1]])
    adjacent = np.zeros((n, n), dtype=bool)
    for i in range(n):
        bits = np.unpackbits(block[start[i]:start[i] + width[i]])
        if bits[i:].any():
            raise ValueError("a bit is set on the diagonal or in the padding")
        adjacent[i, :i] = bits[:i].astype(bool)
    adjacent |= adjacent.T
    if int(np.triu(adjacent).sum()) != edges:
        raise ValueError("the number of edges differs from the p line")
    return adjacent, preamble, n, edges


def table_rows(text: str) -> dict:
    """contents.tex: ``{graph: (code, nodes, edges, claim)}``; the claim is ``("exact", k)`` for a
    plain number in the column Clique Size, ``("lower", k)`` for a number after ``$\\ge$``, None
    for an empty cell."""
    out = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.split("&")]
        if len(cells) != 5 or ".clq" not in cells[0]:
            continue
        name = cells[0].replace("\\_", "_").split(".clq")[0]
        size = cells[4].replace("\\\\", "").strip()
        claim = None
        if size:
            match = re.fullmatch(r"(\$\\ge\$)?\s*(\d+)", size)
            claim = ("lower" if match.group(1) else "exact", int(match.group(2)))
        out[name] = (cells[1].strip("()"), int(cells[2]), int(cells[3]), claim)
    return out


def opt_annotations(text: str) -> dict:
    """results.dmclique, section CLIQUE BENCHMARKS: the annotation ``[OPT = k]`` ("the true
    maximum clique size, when known") of each graph; ``[OPT >= k]`` is a lower bound and
    ``[OPT = ??]`` (or ``???``) no value."""
    section = text.split("CLIQUE BENCHMARKS:")[1].split("RANDOM GRAPHS")[0]
    out = {}
    for name, sign, value in re.findall(r"^\s*(\S+?)(?:\.clq\.b)?\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+\s+\(\d+\)\s+"
                                        r"\[OPT\s*(>=|=)\s*(\?+|\d+)\]", section, re.M):
        claim = None if value.startswith("?") else ("exact" if sign == "=" else "lower", int(value))
        if out.get(name, claim) != claim:
            raise ValueError(f"{name}: two OPT annotations")
        out[name] = claim
    return out


def dfmax_rows(text: str) -> dict:
    """results.dfmax, section CLIQUE BENCHMARKS: the column Max of the graphs the exact code solved."""
    section = text.split("CLIQUE BENCHMARKS:")[1].split("RANDOM GRAPHS")[0]
    return {name: int(k) for name, k in re.findall(r"^(\S+?)(?:\.clq\.b)?\s+(\d+)\s+[\d.]+\s+[\d.]+\s*$", section, re.M)}


def solution(text: str):
    """A solution file (doc/ccformat.tex, output lines): the value of its ``s cqu`` line (None
    unless there is exactly one), its ``v`` lines, and whether its comment says it is optimal."""
    values = re.findall(r"^s\s+cqu\s+(\d+)\s*$", text, re.M)
    vertices = [int(v) for v in re.findall(r"^v\s+(\d+)\s*$", text, re.M)]
    optimal = re.search(r"^c\s+COMMENT:\s*Solution is optimal\.", text, re.M) is not None
    return (int(values[0]) if len(values) == 1 else None), vertices, optimal


def preamble_claims(text: str) -> list:
    """Clique sizes stated in the comment lines of a graph file: ``k max clique`` (Sanchis) and
    ``Largest Clique: k`` (Shor) state the maximum; ``Clique Size: k`` (Brockington and
    Culberson, Mannino) is the size of the clique the generator built, listed after it."""
    return ([("exact", int(k)) for k in re.findall(r"(\d+) max clique", text)]
            + [("exact", int(k)) for k in re.findall(r"Largest Clique:\s*(\d+)", text)]
            + [("lower", int(k)) for k in re.findall(r"Clique Size:\s*(\d+)", text)])


def family(name: str, code: str) -> str:
    """The published family: the code of the table, except that the random graphs sanr*, coded
    (San) in the table, form the family SanR of its notes, and that the graphs gen* of the volume
    directory (not in the table) are Sanchis graphs (instruct.tex)."""
    if name.startswith("sanr"):
        return "SanR"
    if name.startswith("gen"):
        return "San"
    return code


def is_clique(adjacent: np.ndarray, vertices) -> bool:
    w = np.asarray(vertices, dtype=np.int64)
    if len(np.unique(w)) != len(w) or (len(w) and (w.min() < 0 or w.max() >= len(adjacent))):
        return False
    return int(adjacent[np.ix_(w, w)].sum()) == len(w) * (len(w) - 1)


class CliqueProblem(AssignProblem):
    """``adjacent[u, v]``: 1 where an edge joins vertices u and v (symmetric, zero diagonal).
    Option 0: the vertex is out of the clique; option 1: it is in."""

    def __init__(self, adjacent, meter):
        self.adjacent = np.asarray(adjacent, dtype=float)
        n = len(self.adjacent)
        self.apart = 1.0 - self.adjacent - np.eye(n)          # 1 where two different vertices are not adjacent
        super().__init__(n_vars=n, n_opts=2, hard=[False, True], ordered=False, capacity=None,
                         var_var=(self.adjacent,), meter=meter)

    def partial_totals(self, a):
        inside = np.flatnonzero(a == 1)
        return np.array([-float(len(inside)), float(self.apart[np.ix_(inside, inside)].sum() / 2.0)])

    def _new(self):
        s = super()._new()
        s["apart"] = np.zeros(self.n_vars)        # per vertex: the vertices in the clique, other than itself, not adjacent to it
        return s

    def _rows(self, s, variables):
        variables = np.asarray(variables, dtype=np.int64)
        out = np.zeros((len(variables), 2, 2))
        out[:, 1, 0] = -1.0
        out[:, 1, 1] = s["apart"][variables]
        inside = s["a"][variables] == 1                         # a vertex already in: the change if it left
        out[inside, 0, 0] = 1.0
        out[inside, 0, 1] = -s["apart"][variables[inside]]
        out[inside, 1] = 0.0
        return out

    def _push(self, s, v, o):
        s["a"][v] = o
        if o == 1:
            s["tot"] = s["tot"] + np.array([-1.0, s["apart"][v]])
            s["apart"] = s["apart"] + self.apart[v]


class Clique(Environment):
    name = category = "clique"
    form = "assign"
    threshold = 0.90
    anchor = ("an operating point, not an external fact, fixed knowing that two rules with no search score 0.602 (a random "
              "maximal clique) and 0.845 (greedy by the number of candidate neighbours) on the fresh instances, and knowing "
              "no learner result: on average nine tenths of the way from a single vertex to the maximum clique size the source "
              "publishes, an invalid answer counting 0. On the deciding half (11 brock, 2 johnson graphs; greedy 0.783) the "
              "decision rests on the 11 brock graphs: the two johnson graphs give 1 to every maximal clique, so the brock "
              "graphs must average about 0.882 for the half to reach 0.90. On the confirming half (4 hamming, 7 p_hat graphs) "
              "the greedy rule already averages 0.918, above 0.90, so there the threshold is 0.936 (threshold_for, on any set "
              "of hamming, johnson and p_hat graphs only): the four hamming graphs, which give 1 to the greedy rule in every "
              "run, count at 1 (and so would johnson graphs) and the p_hat graphs at 0.90 (greedy 0.87 on them). Whether a "
              "pass on that half must also exceed the untrained score by a stated margin is for the registration to say")

    def __init__(self):
        manifest = fetch.fetch("clique", quiet=True)
        read = lambda path: open(fetch.path("clique", path), encoding="latin-1").read()
        table = table_rows(read(TABLE))
        opt = opt_annotations(read(OPT))
        dfmax = dfmax_rows(read(DFMAX))
        paths = [entry["path"] for entry in manifest["files"] if not entry.get("missing")]
        self.instances, self.left_out, self.claims = {}, {}, {}
        for path in paths:
            if not path.endswith(".clq.b"):
                continue
            name = os.path.basename(path)[:-len(".clq.b")]
            raw = open(fetch.path("clique", path), "rb").read()
            _, preamble, n, edges = read_graph(raw, decode=False)
            claims = []                                            # (file, kind, value)
            row = table.get(name)
            if row is not None and row[3] is not None:
                claims.append((TABLE, *row[3]))
            if opt.get(name) is not None:
                claims.append((OPT, *opt[name]))
            if name in dfmax:
                claims.append((DFMAX, "exact", dfmax[name]))
            claims += [(path, kind, k) for kind, k in preamble_claims(preamble)]
            sol = SOLUTIONS + name + ".sol"
            stated = solution(read(sol)) if sol in paths else (None, [], False)
            if stated[0] is not None:                             # "Solution is optimal." in its comment, or a lower bound
                claims.append((sol, "exact" if stated[2] else "lower", stated[0]))
            self.claims[name] = claims
            exact = {k for _, kind, k in claims if kind == "exact"}
            if not exact:
                self.left_out[name] = "no maximum clique size is published for it"
                continue
            if len(exact) > 1:
                raise ValueError(f"clique/{name}: the published values disagree: {claims}")
            best = exact.pop()
            if any(k > best for _, kind, k in claims if kind == "lower"):
                raise ValueError(f"clique/{name}: a published lower bound exceeds the published maximum")
            if n > MAX_VERTICES:                                       # the size rule
                self.left_out[name] = "more than 1000 vertices"
                continue
            adjacent = read_graph(raw)[0]
            if row is not None and (row[1], row[2]) != (n, edges):
                raise ValueError(f"clique/{name}: the file is not the graph the table lists")
            if stated[0] is not None and not (len(stated[1]) == stated[0] and is_clique(adjacent, stated[1])):
                raise ValueError(f"clique/{name}: the published solution is not a clique of its stated size")
            if best < 2:
                raise ValueError(f"clique/{name}: no scale")
            code = row[0] if row is not None else ""
            self.instances[name] = {"adjacent": adjacent, "best": best, "family": family(name, code)}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["best"])

    def group(self, instance_id):
        return self.instances[instance_id]["family"]

    def threshold_for(self, instance_ids):
        """``threshold`` (0.90), except on a set of hamming, johnson and p_hat graphs only (groups
        ``CONFIRMING``), such as the confirming half of the kernel's split (4 hamming, 7 p_hat graphs),
        where the greedy rule with no search already averages above 0.90. There each hamming and
        johnson graph counts at 1 and each p_hat graph at ``threshold``, and the threshold is their
        mean: 0.936 on that half."""
        groups = [self.group(i) for i in instance_ids]
        if not groups or not set(groups) <= set(CONFIRMING):
            return float(self.threshold)
        top = sum(g in AT_MAXIMUM for g in groups) / len(groups)          # the share counted at 1
        return float(self.threshold + (1.0 - self.threshold) * top)

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        perm, _ = relabel(rng, len(inst["adjacent"]))                # new vertex -> old vertex
        problem = CliqueProblem(inst["adjacent"][np.ix_(perm, perm)], meter)

        def decode(answer):
            if type(answer) is not np.ndarray or answer.shape != perm.shape:
                return answer                                        # not an answer of this problem: left as it is
            out = np.empty_like(answer)                              # same dtype: nothing is converted
            out[perm] = answer
            return out

        return problem, decode

    def score(self, instance_id, answer):
        """``answer[v]``: 1 if vertex v (from 0, in the file's order) is in the clique, 0 if not."""
        inst = self.instances[instance_id]
        a = answer
        if type(a) is not np.ndarray or a.shape != (len(inst["adjacent"]),) or a.dtype.kind not in "iu" \
                or not np.all((a == 0) | (a == 1)):
            return 0.0
        chosen = np.flatnonzero(a == 1)
        if not is_clique(inst["adjacent"], chosen):
            return 0.0                                               # two chosen vertices are not adjacent
        return float(min(1.0, max(0.0, (len(chosen) - 1) / (inst["best"] - 1))))
