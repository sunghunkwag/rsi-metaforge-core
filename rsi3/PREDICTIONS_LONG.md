# Long-horizon compounding study: pre-registered predictions

Registered 2026-10-29, before any run longer than 12 generations of any arm
on any seed. This file is committed together with
`experiment_config_long.json`. That config matches
`experiment_config_invention.json` except for two things: 30 generations
instead of 12, and three arms. Misses will be scored in LONG_RESULTS.md and
will not be reinterpreted.

## The question

The concept-invention study (INVENTION_RESULTS.md) ended at 10/36 TRAIN after
12 generations, against 9/36 for the comparator. Its adopted concepts were
never built from earlier adopted concepts.

A second design, RSI3_UNIFORM_FM_INVP, searches the invented concepts in a
separate pathway at full weight and gives it half of each task's uniform
budget. The prior pathway stays undiluted. On the development seed, INVP
produced the first concept built from an adopted concept (generation 4), but
it also ended at 10/36, because halving the prior pathway delayed
index-k (k=3) from generation 5 to generation 9.

The repository owner chose to answer one question on the current corpus
rather than build a new one: **does self-invention keep compounding over a
long horizon, or does it plateau like the fixed language?** The answer is
read from the slope of TRAIN after generation 12, from concepts built from
concepts, and from VALIDATION.

## Arms

| Arm | Definition |
| --- | --- |
| RSI3_UNIFORM_FM | Fixed language: failure memory, even budget split, prior pathway only |
| RSI3_UNIFORM_FM_INV | Plus self-model invention, concepts inside the prior pathway at weight 0.1 |
| RSI3_UNIFORM_FM_INVP | Plus self-model invention, concepts in a separate pathway at weight 1.0 with half of each task's budget |

- Seeds 11/22/33, 30 generations; B_wake = B_eval = 64.
- Per-generation cap of 2,304 logical evaluations; one verification per task
  per generation.
- TEST is not opened. VALIDATION is reporting only.

The selfmodel code has changed since the registered invention study:

- an `iterate` kind generalizes repetition the system used
  (`f (f x)` in a verified program or an adopted concept) into
  `lambda n x. fold (lambda acc _. f acc) x (range n)`;
- type variables in concept bodies are canonicalized so that names are
  stable.

The INV arm here is therefore not byte-identical to the registered INV arm.
Concept names for concrete types are unchanged (for example `tail^4` is
`c_ee68300b0a` in both).

Execution note: the runner refuses to write into a non-empty directory, and
one background job may run for at most two hours. Each (arm, seed) job is
therefore run into its own empty directory, and the nine JSON files are then
copied into `results_long/`. The code and configuration are the same for
every job.

## Execution amendment (2026-10-29, before any 30-generation result)

The first two jobs ran together and failed on memory. The INVP seed-11 job
was killed by the machine's memory limit (about 6 GB in total). The INV
seed-11 job, running alone, passed 5.7 GB by minute 33 and was stopped.
Each task keeps a live enumeration frontier that grows with search depth.
Neither job produced a result file.

The jobs are now run with `python -m rsi3.longrun`. The predictions, arms
and configuration are unchanged. The runner differs in three ways:

1. **Compact searches.** Each live search is released after its window and
   rebuilt by fast-forwarding. Memory stays bounded and the logical
   behaviour is the same:
   - `tests/test_resumable.py` checks that a rebuilt search continues
     identically, and that three arms over three generations produce
     identical episodes;
   - a full 12-generation RSI3_UNIFORM_FM seed-11 run in this mode
     reproduced the committed run's wake episodes and VALIDATION exactly.
   The cost is CPU: re-enumeration grows with depth, from 20 s to 204 s per
   generation over 12 generations.
2. **One TRAIN trajectory per arm.** In these arms the wake never reads the
   recognition model, so TRAIN is the same for every seed. The runner
   computes the trajectory once with seed 11. After each generation it
   refits seeds 22 and 33's dreams and recognition exactly as RSI-2's sleep
   would, then measures their VALIDATION. `tests/test_longrun.py` checks
   that this equals separate runs.
3. **Checkpoints.** The runtime is checkpointed after every generation,
   because one background job may run for at most two hours. A job resumes
   exactly from its checkpoint, which the same test checks.

Generations 1–12 will also be compared with the committed
`results_invention/` runs on all three seeds.

- **UFM:** TRAIN, wake episodes and per-seed VALIDATION must be identical.
  This is P0, extended to per-seed VALIDATION. A mismatch would invalidate
  the run, and it would be reported as such.
- **INV:** not byte-identical, because of the `iterate` kind added since the
  invention study. Only TRAIN and per-seed VALIDATION are compared, and
  differences there are reported, not treated as invalidating. On seed 11,
  a 12-generation compact run of this commit's INV had the same TRAIN, the
  same solves in the same generations and the same VALIDATION as the
  committed run. Its wake episodes differ from generation 7 on, but only in
  known-failure skip counts and one window length (prepend-k k=4 found at
  candidate 40 instead of 38). The cause is the extra iterate concept.

## Disclosure: development before registration

All on seed 44, at most 12 generations:

| Arm | TRAIN g1–g12 | Adopted concepts | VALIDATION g12 |
| --- | --- | --- | --- |
| UFM | 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 9, 9 | none | 2 |
| INV (registered-study code) | 6, 6, 6, 6, 7, 8, 8, 8, 8, 8, 9, 10 | `tail^4` (g6), `add 2 . add 2` (g12) | 2 |
| INVP (this commit's code) | 6, 6, 7, 8, 8, 8, 8, 8, 9, 10, 10, 10 | see below | 2 |

INVP adopted, in order:

- generation 3: `(sub 1)^3` and the constant `sub -1 2`, via prepend-k (k=4);
- generation 4: `sub c 1`, built from the adopted constant `c`, via
  prepend-k (k=5). This is the first concept built from a concept.
- generation 10: `tail^4`, via index-k (k=5).

Offline reach checks (TRAIN, from the generation-6 state, 1,000 candidates):

- at concept weight 0.1, nothing new is reached;
- at weight 1.0, prepend-index-k (k=5) is reached at candidate 725 through
  the invented index-5 concept (`head . tail^4`);
- the iterate concepts reached nothing within 1,000 candidates.

No run has gone past generation 12, so everything below about generations
13–30 is a forecast.

## Numeric predictions (mean over seeds)

| Arm | TRAIN g12 | TRAIN g30 | Plausible range g30 | VALIDATION g30 |
| --- | --- | --- | --- | --- |
| RSI3_UNIFORM_FM | 9 | 10 | 9–12 | 1–2 |
| RSI3_UNIFORM_FM_INV | 10 | 11 | 10–13 | 1–2 |
| RSI3_UNIFORM_FM_INVP | 10 | 12 | 10–14 | 1–2 |

The TRAIN wake of these arms does not use the seed: the seed enters only
through recognition and dreams, which they use only for VALIDATION. TRAIN
is therefore expected to be identical across seeds within each arm.

## Decisive comparisons (every seed, generation 30)

| ID | Comparison | Predicted |
| --- | --- | --- |
| L1 | INVP TRAIN > UFM TRAIN | PASS |
| L2 | INV TRAIN > UFM TRAIN | PASS |
| L3 | INVP TRAIN > INV TRAIN | PASS (low confidence) |
| L4 | INVP VALIDATION > UFM VALIDATION | FAIL |

## Mechanism readouts

| ID | Readout | Predicted |
| --- | --- | --- |
| P0 | UFM generations 1–12 identical (TRAIN, VALIDATION, wake episodes) to `results_invention/` RSI3_UNIFORM_FM | identical on all seeds |
| K1 | INVP adopted concepts built from an earlier adopted concept, per run | ≥ 1 on every seed |
| K2 | Concepts adopted per run, INVP | 4–8 |
| K3 | TRAIN gained after generation 12 (g30 − g12): UFM / INV / INVP | ≤ 1 / 1–2 / 2–3 |
| K4 | RSI-2 MDL library adoptions, all arms | 0 everywhere |
| K5 | Last generation with a new TRAIN solve, INVP | ≥ 20 |

## What the outcomes mean

- **K3 shows INVP still gaining after generation 12 while UFM has
  stopped, with L1 passing.** Self-invention keeps the system moving after
  the fixed language plateaus. That is the compounding signature this corpus
  can show.
- **INVP also plateaus by about generation 15, with K5 < 20.** Invention
  from the system's own parts has a ceiling on this corpus. The remaining
  tasks need structure (folds, sorting) that no part it owns contains, and
  the next step would have to be a new source of parts, not more
  generations.
- **L4 passes.** That would be the first registered VALIDATION gain in any
  RSI-2 or RSI-3 study.

No claim about consciousness or subjective experience is made or tested.
