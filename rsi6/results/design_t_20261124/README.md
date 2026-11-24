# Design t in development (2026-11-24 to 25): the first half shows, the second does not

Development only. Nothing here was registered and nothing here is evidence for the hypothesis.
Every number is from kinds of problem used in development, with one kind left out in turn.

## Why this design

Where design s ended (`../design_s_20261124/README.md`): what the first design acquires is
bounded by what its policy can express, and a better search of the same weights is not a
better improver. Design t (`learner/design_t.py`) is a different learner, in the prediction
form: the first design acquires nothing there above the nearest observed value, a run costs
about a second, and the noise between seeds is small.

A capability is at most four passes of small *programs* over a fresh problem (unordered: one
to three fitted stages, each one of four generic models after a transform; ordered: one of five
forecasters with an optional seasonal part), combined problem by problem. An acquisition tries
programs on the training problems of a kind and builds the capability from what it tried.
A version carries what the learner knows about its own programs.

Six kinds of prediction problem were added for this work (adapters `environments/tabular.py`,
`environments/series.py`; manifests by `scripts/make_manifests.py`): `friedman`, `table`,
`binary` (PMLB) and `cif`, `nn5`, `fredmd` (Monash archive), beside `regression` and
`forecasting`. All eight were used in development; none is a test kind.

## What was tried, in order

All readings: one kind left out; a version is made from the other kinds of its form and
measured on the kind left out (kernel `measure`, fresh instances). Arms of a chain:
*recursive* (the step is made by the current version), *frozen* (by generation 0), *shuffled*
(the current version without its own ranking). No gate: every step is taken.

**1. A proposal distribution fitted to what the runs found** (`earlier/*_parametric.py`).
Training budget 40, unordered kinds, 32 seeds. Mean over the kinds left out: generation 0
0.6821, generation 1 0.6802, recursive 0.6811, frozen 0.6804, shuffled 0.6785. Nothing.

**2. A library: the programs tried first, made from the learner's own runs**
(`earlier/*_library.py`). Training budget 12.

| kinds left out | generation 0 | generation 1 | recursive 3 | frozen 3 | shuffled 3 |
|---|---|---|---|---|---|
| unordered (32 seeds) | 0.6460 | 0.6637 | 0.6521 | 0.6775 | 0.6642 |
| ordered (48 seeds) | 0.9159 | 0.9161 | 0.9162 | 0.9166 | 0.9150 |

Generation 1 against generation 0, unordered: regression +0.0066 (0.0125), friedman +0.0598
(0.0143), table −0.0046 (0.0059), binary +0.0092 (0.0022). The chain whose steps are made from
the current version's runs ends *below* the one whose steps are made from generation 0's runs
(−0.048, −0.052, −0.004, +0.001 at generation 3): a learner that starts from its library tries
fewer new programs, and what it offers the next library is narrower.

**3. Memory and a model of its own programs** (the code as it stands). A version also remembers
programs with their skill where they were tried, and carries a model that predicts the value of
a program from its settings; the model is acquired by the learner itself, by one ordinary
acquisition on prediction problems made from its memory (`self_model`), and a run tries the
programs the model puts first of 256 drawn evenly. The library may take at most half of a run.
Training budget 12, 32 seeds.

| kinds left out | generation 0 | generation 1 | library alone | model alone | recursive 3 | frozen 3 | shuffled 3 |
|---|---|---|---|---|---|---|---|
| unordered | 0.6460 | 0.6549 | 0.6533 | 0.6627 | 0.6585 | 0.6829 | 0.6548 |
| ordered | 0.9152 | 0.9176 | 0.9185 | 0.9182 | 0.9178 | 0.9190 | 0.9203 |

Again the frozen arm is the best improver (unordered, recursive − frozen at generation 3:
regression −0.061 (0.015), friedman −0.048 (0.007), table +0.021 (0.009), binary −0.010
(0.001)), and the recursive arm is no better than its shuffled control.

## Three checks on a pool of programs

A pool of 600 programs per form, drawn evenly, each run on the training problems of the four
kinds of its form (`scripts/t_pool.py`).

**The learner can model its own programs, and a learner that knows more models them better**
(`scripts/u_landscape.py`, `u_landscape2.py`). Rank correlation between the model's prediction
and the value of programs it has not seen, on the kinds it knows: unordered 0.57 to 0.63 for
generation 0 at budget 12 (nearest known program: 0.24 to 0.33); 0.68 to 0.74 when the learner
that makes the model carries a library made on the other kinds; ordered 0.84 to 0.88.

**But a better guide finds nothing more that carries over** (`scripts/u_chain_sim2.py`, 24
chains). When the next programs to evaluate are chosen by a *perfect* model of their value on
the kinds in use, the library that results covers the kind left out no better than when they
are drawn at random: unordered +0.0015 (0.0062) and −0.0024 (0.0039) for two ways of choosing,
ordered −0.0110 (0.0051) and −0.0112 (0.0041). On the kinds in use the gain is +0.006 to
+0.008. A hundred programs drawn at random already hold what carries over.

**So which learner made the model does not matter for what is acquired** (`scripts/e2_maker.py`;
same library, same memory, only the maker of the model differs; 48 seeds, 3 models each).

| kind left out | no knowledge | library + model by generation 0 | model by the modified learner | difference |
|---|---|---|---|---|
| regression | 0.6884 | 0.7320 | 0.7380 | +0.0060 (0.0043) |
| friedman | 0.4668 | 0.5093 | 0.5087 | −0.0005 (0.0018) |
| table | 0.5744 | 0.5825 | 0.5821 | −0.0003 (0.0011) |
| binary | 0.8335 | 0.8480 | 0.8484 | +0.0004 (0.0005) |

The first half of the hypothesis shows in development: knowledge made on three kinds raises
what is acquired on a fourth (+0.044, +0.043, +0.008, +0.015; budget 12). The second half does
not: the modified learner makes a model that is measurably more accurate, and nothing follows
from it.

## Why, as far as these measurements say

The space of programs is flat. The best program of one stage is as good as the best of two or
three (regression 0.638, 0.636, 0.595; friedman 0.343, 0.348, 0.333; table 0.583, 0.575, 0.582;
binary 0.386, 0.370, 0.393, mean skill over the training problems): which model, which
transform and a few settings decide, and a hundred random draws find them. What can be known
about such a space in general is known after one step; there is no second step for a better
improver to find, whatever the improver is. That is the same end as design s, reached in a
place where it could be measured directly.

Two limits of these numbers. (a) Compute was matched in the learner's own units (passes), not
in CPU: a stage costs 0.03 (ridge) to 0.33 (local linear) CPU-seconds per 60 problems, and
versions that prefer the expensive models used up to 3.4 times the CPU of generation 0 on one
kind. The comparison between arms above is not fit for a gate as it stands; the cost of a stage
has to follow its work before anything is registered. (b) The kinds are few (four per form), so
a kind left out has three to learn from.

## What follows

A further attempt needs a space in which finding one thing makes the next findable: programs
built from parts, where a part that was found is reused inside larger ones. A first look says
the development kinds have such a space (`scripts/fx_probe.py`): a plain ridge fit on
attributes *constructed* from the columns (a map of one column, or a product, difference or
ratio of two; then the same again over what was constructed), chosen greedily by leave-one-out
skill, reaches a mean skill of 0.56 on `friedman`, where the best of the 600 flat programs
reaches 0.35 and the best per problem 0.40. Construction of depth one gives 0.16 there: the
gain is in the second level, which is only reachable through the first. On `regression` it
recovers laws exactly where they are products and ratios (`scripts/sr_probe.py`: a fitted
monomial alone recovers 36 of the 118 laws).

Two cautions, measured after that look (`scripts/fx_fast.py`). With every candidate of a step
scored at once, six steps cost 1.4 passes on `regression`, about 5 on `table` and `binary`, and
15.5 on `friedman`, against the four a fresh problem allows; so the order of trying matters only
where the columns are many. And the gain is one kind's: 0.46 on `friedman`, level with the best
flat program on `table`, below it on `regression` and `binary`. Greedy construction mostly finds
what there is, which leaves little for knowledge to add. Constructed attributes alone are not
the space this needs.

What the measurements ask for is narrower: parts that recur, a search too large to exhaust, and
solutions that can be checked exactly. Two places were looked at.

**The laws of the `regression` kind: too few** (`scripts/sr_proto.py`; every candidate tried,
76 seconds for all 118 laws). As a monomial with signs, 60 laws are recovered exactly; with one
part more (1 + k·m, sin, cos or an exponential factor, on a monomial of one or two variables,
the constant inside found by a scan) 17 more; with two parts 8 more; 33 are not recovered in
this language. A learned order of trying would raise what a fresh problem's budget finds
(about 200 fits of the 2,500 that all candidates of one part cost). But the second step rests
on 25 laws, the search of the improver is cheap enough to try everything, and the law kinds no
learner has run on would carry a difference of one or two laws. Not pursued.

**The assignment kinds, with a learner that searches: a long way up** (`scripts/ls_probe.py`;
six training instances per kind). After a greedy construction, a plain local search that
exchanges the options of two random variables and keeps what is not worse, with E·n full
evaluations:

| kind | greedy | E = 5 | E = 20 | E = 50 |
|---|---|---|---|---|
| quadassign | 0.382 | 0.664 | 0.749 | 0.829 |
| jobshop | 0.751 | 0.820 | 0.873 | 0.892 |
| knapsack | 0.852 | 0.902 | 0.938 | 0.954 |
| setcover | 0.086 | 0.089 | 0.093 | 0.108 |
| pmedian, binpacking | 0.698, 0.950 | no change | no change | no change |

Which move works depends on the kind (`scripts/lns_probe.py`; four training instances, equal
units E·n²). Unassigning a few variables and assigning them again greedily by the exact changes
the problem reports does nothing on quadassign (0.335 with twelve variables taken out, where
exchanges reach 0.518 at E = 1 and 0.765 at E = 5), is the better move on knapsack (0.938 at
E = 1 and 0.965 at E = 5, against 0.875 and 0.930 for exchanges; greedy 0.824), and is the only
one that moves p-median at all (0.665 to 0.685). So what such a learner acquires on a kind is
which moves to make there, and E = 1 is the test budget the first design already had.

The first design acquires about 0.52 on quadassign, and 16 times its training budget adds 0.02.
Here ten times the evaluations still add 0.17: what is acquired is no longer bounded by a
policy but by how well the evaluations are spent, and moves drawn at random spend them badly.
Which move to try next can be learned from the search's own record (what a move looked like,
what it gained); a search that is better guided reaches assignments an unguided one does not,
and what is worth trying there can only be learned from there. That is a space with the three
properties, inside the benchmark families of this repository. The registered budget of the
first design allows one evaluation per variable (E = 1); a design that searches needs its own.
That is the next design.

`data.tar.gz` holds the measurements behind the tables (one file per reading);
`scripts/show_loko.py FILE` prints a reading.
