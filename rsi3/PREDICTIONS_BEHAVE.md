# Behavioural-search study: pre-registered predictions

Registered 2026-10-30, before any run of these arms on the registered seeds
(11/22/33). This file is committed together with the final
`experiment_config_behave.json`. The runs use `python -m rsi3.longrun`.
Misses will be scored in BEHAVE_RESULTS.md and will not be reinterpreted.

## The question

The cascade study (CASCADE_RESULTS.md) reached 21/36 TRAIN, and its learned
solver reached 5/12 on VALIDATION. Its searches stayed shallow. Each
unsolved task's pathways reached only about 100–150 programs deep in the
enumeration order, because RSI-2's top-down enumerator charges every
syntactically distinct program. Many of those programs compute the same
values.

This study adds **behavioural search** (`behave.py`).

- **The search.** It builds programs bottom up and keeps one per behaviour
  on the public inputs (observational equivalence).
- **Deduction.** List outputs split through `cons`, booleans through `not`.
  Witness functions compute the constant argument of a binary operation
  from one behaviour and the target.
- **Use by the policy.** Each behavioural problem (the whole program, each
  pointwise skeleton hole) is one meta-RL action. The policy also practises
  these actions on its self-play tasks.

The arms:

| Arm | What | Kind |
| --- | --- | --- |
| RSI3_META_CONJ | the cascade arm (comparator, committed runs in `results_cascade/`) | baseline |
| **RSI3_META_BEH** | CONJ + behavioural search. It builds from the system's own library (RSI-2's MDL entries, the self-model's adopted and proposed concepts) and is ordered by RSI-2's grammar fitted on the system's own solutions | designer-given search, self-acquired material and order |
| RSI3_META_BEH_BASE | the same search from RSI-2's primitives and constants only, in a fixed order | designer-only control |

There are two questions:

- **B1, B2.** Does behavioural search move TRAIN and held-out capability
  beyond the cascade arm?
- **B3, B4.** Does what the system learned make the search stronger? This is
  BEH against BASE, the same algorithm with and without self-acquired
  material.

## Accounting

Each of the following is charged one logical candidate evaluation against
the same wake budget as every other pathway (B_wake = 64 per task per
generation, B_eval = 64 per VALIDATION task):

- every behaviour added to the pool;
- every program whose behaviour equals a target (kept as an alternative);
- every assembled program checked on the public examples.

Programs whose behaviour is already in the pool cost no logical budget. A
witness's computation is part of the behaviour it reads; only the programs
it proposes are charged. CPU is reported per run.

This is an accounting choice, stated here before the runs. Behavioural
search does more interpreter work per charged unit than top-down
enumeration. Self-play practice runs on imagined tasks are reported
(`practice_evaluations`) and are not wake budget, like the earlier
self-play program runs.

## Disclosure: what is already known

**TRAIN is determined.** TRAIN is seed-independent in both new arms, as in
every meta arm. The development runs (seed 44, 16 generations) therefore
fix TRAIN on the registered seeds:

| Arm | TRAIN g1–g16 | TRAIN g16 | CPU s (dev, TRAIN only) |
| --- | --- | --- | --- |
| RSI3_META_CONJ (committed) | 7 8 10 11 11 13 15 16 17 17 17 17 18 20 20 21 | 21 | 4,019 |
| RSI3_META_BEH | 11 14 15 16 23 23 24 24 25 25 25 25 25 25 25 25 | 25 | 3,344 |
| RSI3_META_BEH_BASE | 11 14 15 15 16 17 19 19 19 19 19 19 20 21 21 21 | 21 | 2,742 |

**What BEH solves.** Against CONJ, BEH gains these TRAIN tasks:

- all six `slice-k-n` tasks;
- `keep-mod-k (k=2)`;
- `is-mod-k (k=5)`, as `all (lambda x. mod x 5 == 0)`.

It **loses CONJ's reverse cascade**: reverse, append-k ×2 and
append-index-k. Its policy spent more chunks on the fold skeleton for
reverse than CONJ's did (28 against 18), under a grammar and library
reshaped by its other solutions, and did not reach the hole. BASE solves
three slices and `keep-mod-k`, and none of the reverse family.

**VALIDATION in development.** The development runs of this study used
`--skip-validation`: VALIDATION was never loaded, and no VALIDATION outcome
of either new arm exists. Earlier exposure, disclosed in full:

- **Task names.** The names of the 12 VALIDATION tasks, and which of them
  CONJ's agent missed, are in PREDICTIONS_CASCADE.md and the committed
  `results_cascade/` files. The `results_cascade/` files also record CONJ's
  agent's per-action spending on each VALIDATION task, which I read.
- **Witness design.** The witness functions were designed after that
  exposure, in particular after seeing the names of the missed
  caesar-cipher, `bool-identify-is-mod-k` and `slice-k-n` tasks. They are
  generic inverses of `add`, `sub`, `mul`, `div`, `mod` and the
  comparisons, with a constant argument, and name no task. They were also
  motivated by the TRAIN tasks `modulo-k`, `keep-mod-k`, `is-mod-k` and
  `caesar-cipher`.
- **Untouched data.** No VALIDATION example has been read, and TEST was
  never opened.
- **Prototype.** The prototype was measured offline on TRAIN public examples
  only, using the CONJ generation-16 checkpoint's library.

**Comparator.** The comparator is the committed CONJ run files, which are
not re-run. Their config differs from this study's only in the arm list and
the `behave` block, which CONJ does not read. TRAIN is deterministic.

## Predictions (seeds 11/22/33, generation 16)

### Determined

| ID | Comparison (every seed) | Predicted |
| --- | --- | --- |
| B1 | BEH TRAIN > CONJ TRAIN | PASS (25 vs 21) |
| B3 | BEH TRAIN > BASE TRAIN | PASS (25 vs 21) |

### Open

`agent` is `validation_agent`, the arm's own solver on VALIDATION at
B_eval = 64.

| ID | Comparison or readout (every seed) | Predicted |
| --- | --- | --- |
| B2 | BEH agent > CONJ agent (5 / 5 / 5) | PASS |
| B4 | BEH agent > BASE agent | PASS (moderate confidence) |
| B5 | BEH agent ≥ 6 | PASS |
| B6 | BEH plain VALIDATION > CONJ plain VALIDATION (2 / 2 / 1) | FAIL |
| B7 | BEH agent, point forecast | 8 (range 6–10) |
| B8 | BASE agent, point forecast | 6 (range 4–8) |

B7's basis is what the mechanism should reach at 64 behaviours, given
TRAIN's concepts. I expect BEH's agent to solve:

- CONJ's five tasks: `add-k (k=5)`, `has-k (k=2)`,
  `caesar-cipher (k=3, n=2)`, `prepend-index-k (k=3)` and `sum`. `sum` is
  the uncertain one: it needs the fold skeleton, and the policy may spend
  chunks on behavioural search first.
- `slice-k-n (k=3, n=3)`, through cons deduction with the index concepts.
- `bool-identify-is-mod-k (k=2)`, through the `eq` witness.
- Some of `caesar-cipher (k=1, n=3)`, `(k=1, n=4)` and `(k=2, n=5)`,
  through the `mod` witness.

I do not expect `repeat-k (k=2)` or `kth-largest (k=5)`.

## What the outcomes mean

- **B2 and B5 pass.** Held-out capability rises above the cascade arm, to
  the stated target of 6 or more. The cause is a designer-given search
  algorithm running on self-acquired material. Neither result alone shows
  self-improvement.
- **B3 and B4 pass.** The same algorithm is measurably stronger with what
  the system learned (its concepts, MDL entries and fitted grammar). That
  is the self-directed part, the one this study can attribute.
- **B4 fails.** The held-out gain belongs to the algorithm, not to learning,
  and would be reported as such.
- **The reverse family.** Its loss is a cost of this arm, reported as it is.

No claim about superintelligence, the singularity or consciousness is made
or tested.
