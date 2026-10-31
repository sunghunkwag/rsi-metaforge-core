# Pre-registered independent-seed new-family transfer experiment

Protocol identifier: `FRESH-COMPOSE-20261031-V1`.
This protocol was committed **before any candidate solver was scored** on
the new suite. The generator source is frozen in
`rsi3/research_fresh/suite.py`; its full canonical dataset SHA-256 is
reported by `suite_sha256()`. None of the benchmark outputs are used
for training, curriculum, prompt selection or hyperparameter tuning.

## Why a new evaluation

Previously, RESERVE-FAR2 had only 21 tasks and its failures were publicly
inspected before the depth-two design. The score 6/21 versus 5/21 on that
benchmark is retrospective and cannot establish fresh blind transfer.

Here, a NEW self-contained Python reference-oracle suite is fixed before
first scoring, with 24 distinct list-to-list transformations in four
compositional task families, each with parameters k=1 through 6:

- trim-and-increment: add one to the suffix after dropping k values;
- append-reversed-prefix: append a reverse of the first k values;
- reverse-dropped-suffix: reverse the suffix after dropping k values;
- filter-nondivisible-and-shift: remove values divisible by k+1, then add one.

Each task gets a deterministic independent 24-input draw:
10 public for **inference-time search only**, 14 distinct hidden for the
frozen verifier. Reference oracles use Python list operations,
not RSI-2 or its candidate programs. Suite seed `2026103107`, no human
per-task selection or exclusions. All 24 tasks, including trivial and
unsolvable ones, remain in the denominator.

**Blindness caveat:** These functions were designed by the investigator
and committed in open source. They are *unscored/unseen by the trained
models until checkpoint freeze*, but they are not third-party-secret,
independently audited benchmark tasks.

## Exact training and comparisons

- Arms:
  `RSI3_META_HONEST` (published Honest Self-Play reference)
  and `RSI3_META_HONEST_DUST_DEPTH` (unchanged PR #43 port).
- Seeds: **11, 22, 33**. Six independent TRAIN trajectories: no
  shared-trajectory seed shortcut or recognition-only refit.
- Training: **16 generations**; B_wake=64 per unsolved TRAIN task per
  generation; selfplay=256, dreams=16, chunk=16, fixed search limits.
- During TRAIN, **never load** VALIDATION, RESERVE, FAR2, fresh suite or
  TEST. TRAIN hidden receipts come only from the unchanged FrozenVerifier.
- Only after each checkpoint reaches generation 16 does the evaluation
  script instantiate the new suite and perform one complete assessment.
- B_eval=64 per fresh task; the same agent_validation routing harness
  and frozen per-task verifier as before. No retries or adaptive
  evaluation budgets. Each runner reports CPU and work separately.
- No changes to frozen RSI-2, TEST, protected code, DSL, verifier or
  accepted solutions. All arms are fixed before execution.

## Registered prediction and decisions

**Primary endpoint:** paired difference in the 24-task verified solve
count, depth-DUST minus Honest, separately for each seed.

Hypothesis: DUST-depth has positive mean paired improvement and
nonnegative differences in at least two of three independent seeds.
A 0 or negative mean counts as a failed hypothesis; any overall
improvement with regressions on multiple seeds is not robust replication.
Report per-family solve names, resource usage and all nulls.

**Secondary endpoints:** TRAIN 16-generation solved count, runtime CPU,
per-task candidate budgets, and additional synthetic practice cost.
No claims of strong statistical significance at three seeds.

No tuning or code changes after first fresh-suite score. If any
implementation fault invalidates the test, document it prominently
and require a NEW unseen suite version for further comparison rather
than repeatedly testing and optimizing on this one.

The prior 5/21 is NOT directly compared numerically to this 24-task
suite because both task sets and difficulties differ. The proper
control is the matched Honest Self-Play arm evaluated on this exact suite.
