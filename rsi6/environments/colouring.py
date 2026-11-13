"""Graph colouring instances of the DIMACS challenge, as collected by M. Trick (COLOR page).

Published form: an undirected graph in the DIMACS text format (a line ``p edge n m`` and lines
``e u v``, vertices numbered from 1). An answer gives every vertex a colour so that the two ends
of every edge have different colours; its value is the number of different colours used, to be
made small.

Reference: the number the instance page prints beside each instance under "optimal coloring"
(the chromatic number). The page is pinned as a data file and is read by the scorer only. It is
a value an answer of the form below can attain: a chromatic number is by definition attained by
a colouring and never exceeds the largest degree plus one. The source publishes no colourings.
The builder's own search (outside this module) found a colouring with exactly the page's number
for 39 of the 43 instances used; for le450_15c, le450_15d, le450_25c and le450_25d it did not,
and there the reference rests on the page alone, which calls them "Leighton graphs with
guaranteed coloring size". No colouring with fewer colours than the page's number was found.
The page's own markup is broken at le450_15a (its link sits inside an unterminated HREF of the
entry before it); ``parse_page`` drops the tags and reads the entry as a browser shows it,
"le450_15a.col (450,8168), 15, LEI". The page is pinned by hash, so the reading is stable.

Answer form: a colour index for every vertex. The number of colours on offer is instance data:
the largest degree of the graph plus one, which always suffices (whatever its neighbours have,
a vertex finds one of that many colours free). A colour may be taken by any number of vertices.
Every proper colouring that uses at most largest degree + 1 colours can be written in this form
by renaming its colours. A proper colouring that uses more cannot: that is the one restriction
of the form. Only dominated answers are lost by it: such a colouring uses more colours than
every answer of the form, and the page's number is below largest degree + 1 on every instance
used. ``score`` itself is not restricted: it accepts any non-negative integers as colour labels
and gives every proper colouring its published value, so a colouring with more than largest
degree + 1 colours has a positive score that no answer of the form produces.

Groups: [0] the number of colours in use by the vertices assigned so far (soft; for a complete
answer it is the published value). It is counted as the bin packing adapter counts bins in use:
a function of the partial assignment that rises by one exactly when a vertex takes a colour no
assigned vertex has. [1] the number of edges whose two ends are both assigned and have the same
colour (hard: one term per edge; a colouring with a conflict is not a colouring).

Exposed arrays: one relation between variables, the adjacency matrix of the graph (1 where an
``e`` line joins the two vertices, in either direction, 0 elsewhere). Every SGB file used lists
each edge in both directions and its ``p`` line counts both; the LEI, REG and MYC files list
each edge once. The matrix is the same either way. The page prints the doubled count for
queen9_9, queen11_11 and queen13_13 and the number of distinct edges for all the others. No
attribute columns and no relation between options: the format has no vertex or colour data.
The comment lines of the files and the edge count of the ``p`` line are not exposed.

Score: the plain ratio page's number / colours used, cut at 1 (so 1 when the page's number is
reached or beaten); 0 for a conflict or a malformed answer. It is the scale the bin packing
adapter uses for bins in use. The other scale of the package (the share of the way from the
expected value of a uniformly random valid answer to the reference) is not used, for two
reasons. It is not called for: in the builder's checks sampled random valid answers of the form
average 0.30 on the plain ratio over all instances, below one half. And it could not be exact:
that expectation needs the number of proper colourings by number of colours used, which no
formula gives. What the plain ratio does not do: it cannot fall below page's number / (largest
degree + 1) for an answer of the form, which is 0.51 on miles500, 0.64 on games120, 0.67 on
myciel3 and 0.68 on miles1500 (at most 0.48 elsewhere), and sampled random valid answers
average above one half on those four and on miles750 and miles1000. Of the six, games120 and
myciel3 are fresh instances of the kernel's split and the four miles graphs are training ones.

Threshold 0.95: an operating point, not an external fact (see ``anchor``). It was set with
knowledge of the score of a rule with no search and no learning, and of no learner result. The
rule: vertices in a random order, each takes a colour already in use that no coloured neighbour
has, else a new colour. With the lowest such colour (first-fit) it averages 0.89 on the 24 fresh
instances of the kernel's split, with a random such colour 0.83 (the auditor's run and the
builder's, outside this module, each with its own code, 20 orders per instance; the rule was
scored on benchmark instances, the learner was not). On the fresh instances 0.95
lies between one colour too many on each of the eight queen graphs with everything else exact
(0.965) and two too many (0.937). 0.95 is also what the p-median adapter uses for a ratio.

What the fresh instances can show. Of the 24, the REG (7), MYC (4) and SGB-book (4) graphs and
games120 are nearly solved by first-fit in a random order (0.92 to 1.00 each); the signal is
carried by the eight queen graphs (first-fit 0.64 to 0.79). The kernel's halves put all eight
queen graphs in the deciding half (first-fit 0.79 there; 0.95 asks for the page's number on some
queen graphs and one colour more on the rest) and REG, MYC and games120 in the confirming half,
where first-fit already averages 0.99 and passes the threshold: that half holds almost no
headroom, and what a confirmation on it is worth is for the owner of the experiment to decide.
Four of the REG graphs are near-duplicates of one another (mulsol.i.2 to .5: 184 to 188 vertices,
3,885 to 3,973 edges, number 31), so the 24 are fewer independent instances than the count says.
The adapter did not choose this and may not select instances by difficulty.

Groups of instances: the source code the page prints for each instance (REG register
allocation, LEI Leighton, MYC Mycielski), and for SGB the four kinds into which the page itself
divides the Stanford GraphBase graphs (book, game, miles, queen; the game kind has one graph).

Left out, by rules fixed before anything was scored (79 instances on the page, 43 used):
 * only in the binary ``.col.b`` format (21): DSJC125.1/.5/.9, DSJC250.1/.5/.9, DSJC500.1/.5/.9,
   DSJC1000.1/.5/.9, DSJR500.1/.1c/.5, flat300_20_0/26_0/28_0, flat1000_50_0/60_0/76_0;
 * the page prints "?" instead of a number, so there is no reference (8): latin_square_10,
   school1, school1_nsh, queen10_10, queen12_12, queen14_14, queen15_15, queen16_16;
 * size, more than MAX_VERTICES = 500 vertices (4): inithx.i.1, inithx.i.2, inithx.i.3, homer;
 * size, vertices * (largest degree + 1) above MAX_CELLS = 100,000 (3): fpsol2.i.1 (125,488),
   fpsol2.i.2 (156,497), fpsol2.i.3 (147,475). The package prefers about 30,000; under that
   limit 33 instances remain, and under 64,000 the kernel's split has 15 training instances
   instead of 16. 100,000 is the round limit at which it has 16. It was set after looking at the
   sizes and at the split and before any answer of any kind was scored; ten of the instances
   used are above 30,000 (the largest is le450_25c with 81,000).
"""
from __future__ import annotations

import re

import numpy as np

from rsi6 import fetch
from rsi6.kernel.environment import Environment, relabel
from rsi6.kernel.problem import AssignProblem

PAGE = "instances.html"
MAX_VERTICES = 500
MAX_CELLS = 100000               # vertices * colours on offer; see the module text for how it was set
ENTRY = re.compile(r"(\S+?)\.col(\.b)?\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*(\?|\d+)\s*,\s*([A-Z]{3})?")
SGB_KINDS = {"miles": "miles", "queen": "queen", "games": "game"}       # every other SGB graph is a book graph


def parse_page(html: str) -> dict:
    """The instance list of the page: name -> format, vertices, edges as printed, the number
    under "optimal coloring" (None where the page prints "?"), and the source code."""
    text = re.sub(r"<[^>]+>", "", html)
    out = {}
    for name, binary, n, m, number, code in ENTRY.findall(text):
        out[name] = {"binary": bool(binary), "n": int(n), "m": int(m), "number": None if number == "?" else int(number),
                     "code": code}
    return out


def family(name: str, code: str) -> str:
    if code != "SGB":
        return code
    return "SGB-" + SGB_KINDS.get(name.rstrip("0123456789_"), "book")


def parse(text: str) -> np.ndarray:
    """The adjacency matrix of a DIMACS ``.col`` text file."""
    n, ends = 0, []
    for line in text.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "p":
            n = int(tokens[2])
        elif tokens[0] == "e":
            ends.append((int(tokens[1]) - 1, int(tokens[2]) - 1))
    ends = np.array(ends, dtype=np.int64).reshape(-1, 2)
    adjacent = np.zeros((n, n), dtype=bool)
    adjacent[ends[:, 0], ends[:, 1]] = True
    adjacent[ends[:, 1], ends[:, 0]] = True
    return adjacent


class ColouringProblem(AssignProblem):
    def __init__(self, adjacent: np.ndarray, n_colours: int, meter):
        self.adjacent = np.asarray(adjacent, dtype=float)
        super().__init__(n_vars=len(adjacent), n_opts=n_colours, hard=[False, True], ordered=False, capacity=None,
                         var_var=(self.adjacent,), meter=meter)

    def partial_totals(self, a):
        placed = np.flatnonzero(a >= 0)
        colour = a[placed]
        same = colour[:, None] == colour[None, :]
        return np.array([float(np.count_nonzero(np.bincount(colour, minlength=self.n_opts))),
                         float((self.adjacent[np.ix_(placed, placed)] * same).sum() / 2.0)])

    def _new(self):
        s = super()._new()
        s["count"] = np.zeros(self.n_opts, dtype=np.int64)        # vertices that have each colour
        s["near"] = np.zeros((self.n_vars, self.n_opts))          # assigned neighbours of each vertex, by colour
        return s

    def _rows(self, s, variables):
        out = np.empty((len(variables), self.n_opts, 2))
        out[:, :, 0] = (s["count"] == 0)[None, :]
        out[:, :, 1] = s["near"][variables]
        return out

    def _push(self, s, v, o):
        s["tot"] = s["tot"] + np.array([1.0 if s["count"][o] == 0 else 0.0, s["near"][v, o]])
        s["count"][o] += 1
        s["near"][:, o] += self.adjacent[:, v]
        s["a"][v] = o


class Colouring(Environment):
    name = category = "colouring"
    form = "assign"
    threshold = 0.95
    anchor = ("an operating point, not an external fact, set knowing that a rule with no search (first-fit in a random "
              "vertex order) scores 0.89 on the fresh instances and knowing no learner result: a mean ratio of the "
              "chromatic number printed on the instance page to the colours used of 0.95, which is between one and two "
              "colours too many on every queen graph with the rest exact; the queen graphs carry the signal, the other "
              "fresh graphs are nearly solved by first-fit, and the confirming half holds almost no headroom")

    def __init__(self):
        manifest = fetch.fetch("colouring", quiet=True)
        have = {e["path"] for e in manifest["files"] if not e.get("missing")}
        listing = parse_page(open(fetch.path("colouring", PAGE), encoding="latin-1").read())
        self.instances, self.left_out_by_cells = {}, []
        for name, entry in sorted(listing.items()):
            if entry["binary"] or entry["number"] is None or entry["n"] > MAX_VERTICES or name + ".col" not in have:
                continue
            adjacent = parse(open(fetch.path("colouring", name + ".col"), encoding="latin-1").read())
            if len(adjacent) != entry["n"] or adjacent.diagonal().any():
                raise RuntimeError(f"colouring/{name}: the file is not the graph the page lists")
            colours = int(adjacent.sum(axis=1).max()) + 1
            if len(adjacent) * colours > MAX_CELLS:
                self.left_out_by_cells.append(name)
                continue
            self.instances[name] = {"adjacent": adjacent, "colours": colours, "number": entry["number"],
                                    "family": family(name, entry["code"])}

    def instance_ids(self):
        return sorted(self.instances)

    def reference(self, instance_id):
        return float(self.instances[instance_id]["number"])

    def group(self, instance_id):
        return self.instances[instance_id]["family"]

    def problem(self, instance_id, meter, seed, training):
        inst = self.instances[instance_id]
        rng = np.random.default_rng(seed)
        vertex_perm, _ = relabel(rng, len(inst["adjacent"]))        # new vertex -> old vertex
        colour_perm, _ = relabel(rng, inst["colours"])              # new colour -> old colour
        problem = ColouringProblem(inst["adjacent"][np.ix_(vertex_perm, vertex_perm)], inst["colours"], meter)

        def decode(answer):
            out = np.empty(len(vertex_perm), dtype=np.int64)
            out[vertex_perm] = colour_perm[np.asarray(answer, dtype=np.int64)]
            return out

        return problem, decode

    def score(self, instance_id, answer):
        inst = self.instances[instance_id]
        a = np.asarray(answer)
        if a.shape != (len(inst["adjacent"]),) or a.dtype.kind not in "iu" or a.min() < 0:
            return 0.0
        if np.any(inst["adjacent"] & (a[:, None] == a[None, :])):
            return 0.0                                              # two adjacent vertices have one colour
        return float(min(1.0, inst["number"] / len(np.unique(a))))  # the page's number over the colours used
