# Concept-invention study: measured results

All six registered runs completed: RSI3_UNIFORM_FM and RSI3_UNIFORM_FM_INV ×
seeds 11/22/33 × 12 generations, using `experiment_config_invention.json`,
unchanged since the pre-registration commit 7cb0038. The runs took 3,125 s of
wall time on 2 workers. Raw run files are in
[`results_invention/`](results_invention/), and the tables are
`python -m rsi3.report` output.

**Headline.** For the first time in RSI-3, the system's language grew from
its own experience. On every seed the self-model invented two concepts that
were later adopted, each through a verified solve:

- `tail^4`, a power of a part of its own index-k (k=3) program;
- `add 2 . add 2`, a power of a part of its own prepend-k (k=4) program.

With them it solved index-k (k=5) and prepend-k (k=5), which no allocation,
resumption or memory arm had reached in any committed run. TRAIN ended at
10/36 against the comparator's 9/36 on every seed, at equal logical budget.

VALIDATION did not improve on the registered every-seed criterion, as
predicted. Outside the registered comparisons, on seed 11 at generation 12,
the system solved a VALIDATION task, `add-k (k=5)`, that no run in this
repository (RSI-2 or RSI-3) had ever solved; see below. All 16 registered
predictions hit.

## TRAIN hidden-verified solved, per generation

| Arm | Seed | g1 | g2 | g3 | g4 | g5 | g6 | g7 | g8 | g9 | g10 | g11 | g12 | VALIDATION g12 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RSI3_UNIFORM_FM | 11 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 | 8 | 8 | 9 | 9 | 1/12 | 759 |
| RSI3_UNIFORM_FM | 22 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 | 8 | 8 | 9 | 9 | 1/12 | 726 |
| RSI3_UNIFORM_FM | 33 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 | 8 | 8 | 9 | 9 | 1/12 | 723 |
| RSI3_UNIFORM_FM_INV | 11 | 6 | 6 | 6 | 6 | 7 | 8 | 8 | 8 | 8 | 8 | 9 | 10 | 2/12 | 1041 |
| RSI3_UNIFORM_FM_INV | 22 | 6 | 6 | 6 | 6 | 7 | 8 | 8 | 8 | 8 | 8 | 9 | 10 | 1/12 | 1014 |
| RSI3_UNIFORM_FM_INV | 33 | 6 | 6 | 6 | 6 | 7 | 8 | 8 | 8 | 8 | 8 | 9 | 10 | 1/12 | 1009 |

**The three seeds are not three independent replications of TRAIN.** In
these uniform, prior-only arms the wake phase does not use the seed. The
seed enters only through the recognition model and the dreams, which these
arms use for VALIDATION but not to search TRAIN. The TRAIN trajectories are
therefore identical across seeds by construction, as they were in the
failure-memory study. The TRAIN result is one deterministic trajectory per
arm; VALIDATION is where the seeds differ.

## Means over seeds

| Arm | TRAIN g8 | TRAIN g12 | VALIDATION g12 | CPU s per run | Logical evaluations, 12 generations |
| --- | --- | --- | --- | --- | --- |
| RSI3_UNIFORM_FM | 8.00 | 9.00 | 1.00 | 736 | 27,217 |
| **RSI3_UNIFORM_FM_INV** | 8.00 | **10.00** | 1.33 | 1,021 (1.39×) | 27,125 |

The invention arm's self-model ran 3,528 probe evaluations per run. These
are reported separately and are not candidate evaluations, like the
integrator's probes.

## What the self-model did

| Generation | Event (identical on every seed) |
| --- | --- |
| 1 | the six tasks RSI-2 solves; nothing to invent from yet |
| 2–5 | 14 concepts per generation from those six trivial programs; none earned a solve. index-k (k=3) is found in generation 5, one generation later than the comparator (generation 4), because the wider grammar delays the deep prior search |
| 6 | 18 concepts, including `tail (tail x)` and its powers, from `head (tail (tail x))`. **`tail^4` adopted** through a verified `head (tail^4 x)` for index-k (k=5) |
| 7–10 | 19 concepts; no new solve |
| 11 | prepend-k (k=4), `cons (add 2 2)`, by the prior search (the comparator found it in generation 8) |
| 12 | 22 concepts, including powers of `add 2` from that program. **`add 2 . add 2` adopted** through a verified `cons (add2twice 1)`, i.e. prepend 5, for prepend-k (k=5) |

The comparator's ninth solve was modulo-k (k=2), in generation 11. The
invention arm did not reach it in 12 generations, and its own seventh and
ninth solves came later. The wider grammar is a real cost and the concepts
outran it by one task.

RSI-2's MDL library learner adopted nothing in either arm (0 of 72
sleeps). Every library entry in RSI-3 so far came from the self-model.

## Held-out observation (not a registered comparison)

On seed 11, generation 12, VALIDATION solved `add-k (k=5)`. This task is
solved nowhere else in the repository: not in RSI-2's 891 committed
assessment records of it, and not in any earlier RSI-3 run. It appeared in
the generation in which `add 2 . add 2` was adopted.

A deterministic replay of the seed-11 run, which reads VALIDATION after each
generation for this analysis only, shows the program:

    map (add (c_4152c76895 1))        c_4152c76895 = lambda x. add 2 (add 2 x)

That is `map (add 5)`, with 5 built as the invented +4 applied to 1. It was
found at candidate 54 of 64 and accepted on the hidden examples. In
generations 1–11 the replay's VALIDATION search spent all 64 candidates on
this task without a match. The held-out solve therefore uses the concept
the system invented from its own TRAIN program and admitted through a
TRAIN solve: invented on TRAIN, transferred to a task it never saw.

On seeds 22 and 33 the same library did not reach it within B_eval = 64.
Those seeds differ only in the recognition model that conditions the
grammar. On seed 11 the same generation also lost `sum`, so its VALIDATION
count rose only from 1 to 2. It is one seed, at the last generation, and
was not predicted. It is reported as an observation, not as a passed test.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| UFM TRAIN g8 | 8, identical to committed | 8, identical | hit |
| UFM TRAIN g12 | 9 (8–10) | 9 | hit |
| INV TRAIN g8 | 8 | 8 | hit |
| INV TRAIN g12 | 10 (9–11) | 10 | hit |
| VALIDATION g12, both arms | 1–2 | UFM 1, 1, 1; INV 2, 1, 1 | hit |
| I1 INV TRAIN > UFM TRAIN, every seed | PASS | 10 vs 9 on every seed: PASS | hit |
| I2 INV VALIDATION > UFM VALIDATION, every seed | FAIL | 2 vs 1, 1 vs 1, 1 vs 1: FAIL | hit |
| P0 UFM generations 1–8 identical to committed runs | identical | TRAIN, VALIDATION and every wake episode identical on all three seeds | hit |
| J1 runs with an adopted concept | 3 of 3 | 3 of 3 | hit |
| J2 concepts adopted per run | 1–3, point 2 | 2, 2, 2 (`tail^4`, `add 2 . add 2`) | hit |
| J3 first adoption generation | ≤ 7 | 6 on every seed | hit |
| J4 runs solving a never-solved TRAIN task | 3 of 3 | 3 of 3 (index-k k=5, prepend-k k=5) | hit |
| J5 concept built from an earlier adopted concept | 0 of 3 | 0 of 3 | hit |
| J6 RSI-2 MDL adoptions | 0 everywhere | 0 everywhere | hit |
| J7 CPU INV / UFM | ≥ 1.2× | 1.39× | hit |

16 of 16 registered predictions hit.

## What this does and does not show

It shows the following.

- A program synthesizer whose language was frozen in all 21 earlier runs
  can grow that language from a model of its own verified programs.
- Each growth step is gated by the frozen verifier, so no concept enters the
  library without a hidden-example solve.
- The grown language reaches TRAIN tasks the fixed language does not reach at
  the same logical budget: +1 net over the best previous arm at 12
  generations, with two tasks gained and one delayed past the horizon.

It does not show any of the following.

- A qualitative leap in held-out capability. The registered VALIDATION
  comparison fails, and the one new VALIDATION task is a single-seed
  observation.
- Compounding. No adopted concept was built from an earlier one (J5 = 0),
  and each invention step took about two generations of the uniform budget.
- Independence across seeds for TRAIN (see above).

The concepts are small: a fourfold tail and a +4. Their value is that the
system made them from its own programs, kept them only when they worked, and
used them on tasks it could not otherwise reach.

The next bottleneck is visible in the data. The remaining TRAIN tasks need
list construction by folding (append, reverse, take, sort), and no verified
program contains a fold yet. The self-model can only invent from parts it
has, so a step that obtains those parts (for example, inventing from
near-miss programs in failure memory) is the natural next study.

The self-model is a functional model of the system's own programs and
behaviour. It is not consciousness or subjective experience, and no claim is
made about either.
