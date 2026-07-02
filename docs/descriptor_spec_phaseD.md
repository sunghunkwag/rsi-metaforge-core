# Phase D Descriptor Specification (frozen instrument)

Deterministic functions of `(program, probe outputs)` mapping every program
to a **cell** — a tuple of the six descriptors below. Computed exclusively
against the frozen probe battery `docs/probe_battery_phaseD.json`
(SHA-256 `b11b14dfe4616a3c13a1ac872d08b181c532e796c19f74bafe6c050d9e0c0d01`,
116 probes: 44 base across lengths 0–34, plus permutation and
value-perturbation partners for every base of length ≥ 2).

The reference implementation is `explore_descriptor` and its helpers in
`rsi_levels_metaforge_unified.py`; the SHA-256 of their exact source text
is pinned by `test_explore_frozen_instruments_intact`. Instrument and
implementation are read-only after the Phase D freeze; any edit fails the
hash test by construction.

## Execution model

- A program is a token sequence over the exploration vocabulary (base ops
  plus, optionally, searcher macro tokens supplied as building blocks —
  GR9: vocabulary yes, task data no). It is macro-expanded before
  execution.
- Step budget: `EXPLORE_STEP_BUDGET = 512` expanded base ops. A program
  whose expansion exceeds the budget (or fails to expand) is
  `over_budget`: no probe is executed, `total_steps = 0`, and the
  expanded length used by `cost_bucket` is the true expanded length, or
  `EXPLORE_STEP_BUDGET + 1` when expansion itself failed.
- Executor: the top VM's op implementations at the default stack bound
  (`MAX_STACK = 32`, explicitly pinned for the duration of each
  execution), with per-probe outcome one of:
  - `completed` — terminal stack is a single int within the budget;
  - `crashed` — any `VMCrash` or non-single-int terminal state.
  Peak stack depth and executed-op count are recorded per probe.
- Screening rule (frozen): probes are evaluated in battery order; if the
  first 8 probes all fail to complete, the program is assigned
  `halt_bucket = 0`, `output_class = (0, 0, 0)`, `entropy_bucket = 0`,
  `dependence = (0, 0, 0, 0)`, `stack_bucket = 0` without executing the
  remaining probes. `cost_bucket` is always computed from the program.

## Descriptors

Let `N` = number of battery probes, `C` = set of completed probes,
`out(p)` the int output of a completed probe `p`.

1. **halt_bucket** ∈ 0..8 — `floor(8 * |C| / N)`.
2. **output_class** — triple of buckets, each `floor(4 * frac)` clamped
   to 0..4, fractions over `C` (all 0 if `C` empty):
   `zero_frac` (`out == 0`), `neg_frac` (`out < 0`), `big_frac`
   (`|out| > 15`, i.e. outside the probe value range).
3. **entropy_bucket** ∈ 0..4 — `min(4, floor(4 * distinct(out over C) / |C|))`;
   0 if `C` is empty.
4. **dependence** — four booleans encoded 0/1:
   - `constant`: `|C| ≥ 2` and all outputs equal;
   - `order_sensitive`: some (base, perm) pair, both completed, with
     different outputs;
   - `value_sensitive`: some (base, perturb) pair, both completed, with
     different outputs;
   - `echo_like`: `C` nonempty and for ≥ 90% of completed probes with
     nonempty input, the output occurs in the input vector.
5. **cost_bucket** ∈ 1..10 — `min(10, bit_length(expanded_len))`
   (`over_budget` programs use their true expanded length).
6. **stack_bucket** ∈ 0..6 — from the maximum peak stack over completed
   probes: 0 none completed; 1 peak ≤ 1; 2 peak = 2; 3 peak ∈ 3..4;
   4 peak ∈ 5..8; 5 peak ∈ 9..16; 6 peak ≥ 17.

A **cell** is the tuple `(halt_bucket, output_class, entropy_bucket,
dependence, cost_bucket, stack_bucket)`, serialized canonically as
`"h{..}|z{..}n{..}b{..}|e{..}|d{....}|c{..}|s{..}"`.

## Elite total order (frozen)

Within a cell the elite is the program minimizing
`(surface_length, total_steps, lexicographic token tuple)` where
`total_steps` is the sum of executed expanded ops across all executed
probes. The third component makes the order total; determinism follows.

A candidate replaces an incumbent **iff its key is strictly smaller**.

## Exploration loop constants (budgets, not instruments)

`EXPLORE_SEED = 424243`, `EXPLORE_EVALS_PER_RUN = 60000`,
`EXPLORE_MAX_SURFACE_LEN = 14`, `EXPLORE_CHECKPOINT_EVERY = 5000`.
Proposal mix per iteration from one `random.Random(seed)` stream:
mutation of an archive elite (p = 0.4, 1–3 seeded point edits),
fresh random program (p = 0.3, length 1–14), composition of two archive
elites (p = 0.3, concatenation truncated to the surface cap); random
fallback while the archive is empty. Every insertion is logged with
iteration, cell, cost key, and parent lineage (SHA-16 of parent token
tuples). The archive serializes deterministically (sorted cells, sorted
keys, fixed indent).
