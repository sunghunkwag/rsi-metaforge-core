# Registered development pilot: forward-tested verified-program transfer

## Frozen base and provenance

This study extends experimental PR #37 and leaves RSI-2, the verifier,
the corpus and TEST sealed. Q Labs Noise / Dust algorithm source remains
vendored and pinned as recorded in QLABS_DUST_PORT.md. This new search
mechanism is **not** Q Labs' neural DUST speedrun: it is a separate
type-preserving symbolic program transfer experiment motivated by the
previous null result.

## Mechanism

1. Snapshot only verifier-accepted TRAIN solution ASTs before each generation.
2. Find type-compatible donors using RSI-3's public-feature similarity.
3. Generate legal single-site substitutions of integer/boolean literals.
   Integers outside frozen literal set are expressed as syntax trees of
   frozen `add`, `sub` and `mul` primitives plus frozen constants.
4. Verify type correctness and grammar derivability. No handwritten target
   templates, task-name parsing or hidden data access.
5. Inject at most 48 unique donor variants ahead of each task's normal
   enumerator. Every forward public-example evaluation is charged to
   the same logical budget, and every public success requires an
   external verifier receipt. The regular search frontier is resumed.
6. Record TRAIN, VALIDATION reporting, CPU, inference and verified library
   adoption. New solution proposals are a search intervention, not
   a change of verifier, DSL, or acceptance conditions.

## Prior predictions (development-only)

- The transfer arm may solve at least one further TRAIN task before the
  three-generation horizon, compared with the identical-budget uniform
  failure-memory baseline (hypothesis, **not a guaranteed result**).
- If it does not, the arm is considered a null result, not a success.
- Any early TRAIN gain without a VALIDATION gain is a budget-efficiency
  demonstration only, not evidence of generalization or true RSI.
- The 4,000-fold historical Noise contest claim is not used as an
  expected gain here: it compared Q Labs iterations on a different task.

## Pilot

One seed (11), 3 generations, B_wake = B_eval = 64, 36 TRAIN and 12
VALIDATION tasks. Compare `RSI3_UNIFORM_FM` and
`RSI3_UNIFORM_TRANSFER_FM`, frozen search sizes and step budgets.
No TEST open or evaluation-conditioned revision to the frozen baseline.
This exploratory protocol is not a substitute for three-seed eight-
generation pre-registered confirmation.
