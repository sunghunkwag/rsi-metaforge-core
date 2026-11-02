# SWARM: registered predictions for the final runs

Registered before any final run. The commit that carries this file and
`experiment_config.json` is the registration; RESULTS.md records its hash
and scores every prediction below as written, misses first.

## What will be run

`python -m swarm.experiment --config swarm/experiment_config.json` on
the development container (4 cores): six arms (S0 `SWARM_FULL`, S1
`SWARM_RECORDS`, S2 `SWARM_NO_MAPPER`, S3 `SWARM_NO_SELFEDIT`, S4
`SWARM_NO_BREAKER_REGRET`, S5 `SWARM_SHUFFLED_FIELD`), seeds 11, 22, 33,
G = 20 generations, with the constants chosen in
[`pilot/PILOT.md`](pilot/PILOT.md): D 8192, n_prop 4, B_gen 6000, B_inst
200, k_edit 1, horizon 8, 1024 MB per executor child. The kernel pins in
`experiment_config.json` are the ones the integrity test checks. One
sanity run of `SWARM_FROZEN` (no self-edit, no learning) on seed 11 is
run alongside and reported, not compared.

## What has been seen before registering

- The 30-minute pilot (`pilot/`): six arms, seed 11, 8-11 generations,
  at other constants (n_prop 6, B_gen 4000, 512 MB) and before the
  frontier checkpoint fix. Crossings: 0 (S0, S1, S2, S3), 2 (S4), 1
  (S5). Three arms were numerically identical for the whole run.
- One four-generation run of S0 at the registered constants after the
  fix: 0 crossings, 13 tasks admitted, wake 41-57 s.
- Two earlier development runs (smoke2, smoke3) at other constants:
  smoke3 produced the first crossing at g3 and two forge adoptions.
- One `SWARM_FROZEN` sanity run of 20 generations at the registered
  constants, on the code before the review fixes: 0 crossings, 57 tasks
  admitted, about 90 s per generation.
- An adversarial review of the package (two workflow runs, 6 confirmed
  findings, the rest unverified) was folded in before a first
  registration (commits 969d2be, 46308bf and 420a40e). A verification
  pass over those commits then confirmed further defects (an executor
  escape through the `_ctypes` extension and `os.mknod`/`os.mkfifo`, a
  per-generation Builder budget that could reach 1.25 B_gen, a dropped
  gate verdict after a failed wake, a judge cache keyed without task
  status, and two readings in this file that did not match `report.py`);
  these were fixed and this file corrected, which made the registration
  this commit. The first registration's runs (commit fb55d0c) were
  stopped by a session restart after 15-19 generations of four seed-11
  runs; their logs showed 0 crossings in every arm up to then and are
  not used. ARCHITECTURE.md §6 lists the disclosures. Its
  reproductions ran on the generation-0 tree with planted tasks, not on
  any arm's run. One three-generation end-to-end check of S0 and S1 at
  B_gen 2000 followed, to see the fixed loop run; its numbers are not
  used here.

No final-run output exists. Nothing in the predictions is derived from a
final run.

## Readings of the pass rules that the directive leaves open

These are the implementer's readings; `report.py` implements exactly
these and RESULTS.md scores them as such.

- K1-K4: `X_S0(G) > X_other(G)` strictly, on every seed; a tie on any
  seed fails.
- K5: on every seed, S0's mean generations-to-crossing is strictly lower
  than S4's AND S0's never-crossed fraction (tasks admitted and not
  crossed by G, markers included) is strictly lower than S4's. A seed on
  which S0 has no crossing has no mean and fails.
- K6: with `X(0) = 0`, the increments `ΔX(g) = X(g) - X(g-1)` are G
  values and their consecutive differences, the second differences, are
  G-1 = 19 values; all of the last half of that sequence (`report.py`
  takes the values from index 9 on, ten values) must be >= 0, on every
  seed. If any is < 0, the generation at which the increment peaked (the
  earliest maximum) and the archive state at that generation are
  reported.
- K7: `report.py --replay` recomputes the ledger chain and every
  certificate and crossing record from the ledger alone and compares
  them with the summaries; the kernel pins match `pins.json`; the AST
  audits in `tests/test_integrity.py` pass at the registration commit.
- "Retrieval hit rate": the fraction of crossings whose crossing program
  (the kernel's own unboosted solve from the generation's snapshot)
  references a fragment that the Builder's retrieval had boosted for
  that task in the same generation's wake.
- Budget: every arm's Builder spends at most B_gen candidate evaluations
  per generation, the wake and the forge together: a quarter of B_gen is
  reserved for the forge and the wake gets the rest; S3 has no forge and
  gives the wake all of B_gen. "Builder candidates" in the report is this
  sum.
- Kernel failures (a crashed or timed-out executor child during Kb, a
  mined check, a crossing check or the judge) are ledgered dispositions,
  not verdicts; they are reported per run and excluded from the
  rejection counts. Admission rate below is admitted / proposed, with
  kernel failures in the denominator.

## Predictions

Point forecasts are for seed-level values; a prediction with a range
hits if every seed's value lies inside the range.

| ID | Quantity or comparison | Predicted | Confidence |
| --- | --- | --- | --- |
| P1 | `X_S0(20)` per seed | 4 (range 1-9) | moderate |
| P2 | K1, `X_S0(20) > X_S3(20)` on every seed | FAIL as an every-seed rule; S0 > S3 on at least 2 of 3 seeds; `X_S3(20)` 2 (range 0-5) | moderate |
| P3 | K2, `X_S0(20) > X_S1(20)` on every seed | FAIL; `X_S1(20)` 4 (range 1-9); on every seed `|X_S0 - X_S1| <= 2` | moderate |
| P4 | K3, `X_S0(20) > X_S2(20)` on every seed | FAIL; `X_S2(20)` 4 (range 1-9) | moderate |
| P5 | K4, `X_S0(20) > X_S5(20)` on every seed | FAIL; `X_S5(20)` 3 (range 0-8) | low |
| P6 | K5 | FAIL; S0's never-crossed fraction 0.92 (range 0.80-1.00); S4 admits fewer tasks than S0 on every seed | moderate |
| P7 | K6 | FAIL on at least one seed: increments are sparse 0/1 values and every isolated crossing is followed by a negative second difference; the peak-increment generation is reported | high |
| P8 | K7 | PASS: replay reproduces every certificate and crossing, pins unchanged, AST audits pass | high |
| P9 | S0 retrieval hit rate, pooled over seeds | 0.25 (range 0.0-0.6) | low |
| P10 | S0 self-edits adopted in 20 generations, per seed | 3 (range 1-6); every adopted edit is a forge (parameter edits cannot show a strict gain in the judge) | moderate |
| P11 | Wake failures (`live_call_failed`) across all 18 runs | 0 | high |
| P12 | S0 admission rate (admitted / proposed) pooled over seeds | 0.85 (range 0.70-0.95); Kb (too easy) is the most frequent rejection | moderate |
| P13 | `SWARM_FROZEN` sanity, seed 11 | 0 crossings | high |
| P14 | Three channel arms identical until the channel has something to carry | S0, S1 and S2 have identical archives and meters on every seed up to and including the generation of the first crossing or the first adopted self-edit in any of them, whichever comes first | high |
| P15 | Kernel failures across all 18 runs (admission K!, failed mined, crossing or judge checks) | at most 3 in total | moderate |
| P16 | Crossings credited with an empty credit chain (no fragment and no source task) across all 18 runs | 0 | high |

## Reasons

- **P1-P5.** Crossings need a substrate change that reorders the search
  (a forged stage primitive or a learned library entry) on a task whose
  relatives share the structure; both happened in the pilot and smoke3,
  at a rate of a few per ten generations. The channel and the mapper act
  only after crossings exist (P14), so with single-digit crossings the
  channel arms will differ by at most a couple of crossings, in either
  direction, and the strict every-seed rules will fail on ties or
  reversals. I expect the design's own hypothesis (latent beats records)
  not to be decided at this scale.
- **P6.** Admission credit (S4) drives the lineage multipliers from the
  first generation; regret (S0) only after crossings. In the pilot S4
  admitted fewer tasks (more Kc rejections) and crossed first. I do not
  expect regret to keep tasks closer to the frontier at this scale.
- **P7.** With X(20) in single digits the increments are mostly zeros
  and ones; a sequence like 0 1 0 has second difference -2 at the
  crossing. Compounding in the directive's sense needs increments that
  grow, which needs crossings that enable further crossings faster than
  the archive grows; nothing seen so far suggests it within 20
  generations.
- **P10.** Only forges change the search order in a way the judge can
  see within one generation; `learn.*`, `allocation.*` and `search.*`
  parameter edits are either inert in the judge or regress (ARCHITECTURE
  §6).
- **P12.** The Breaker's proposals straddle the generation-0 language by
  construction, and Kb rejects the ones the snapshot already solves.
- **P15-P16.** The executor's timeouts are generous (step budgets bind
  first) and the machine is otherwise idle; a crossing now requires a
  fragment sourced from another task or a weight refit on other tasks'
  solutions, so an empty credit chain would mean a defect in the
  exclusion, not a result.

## Interpretation rules (OWNER_DIRECTIVE.md §8, verbatim)

> K1 fail → crossings come from search depth, not substrate change; K2 fail → the latent channel did not beat records at this scale; K6 negative → saturation, with the peak generation and the state of the archive at the peak.

## Claim boundary

What is reported is the crossing curve of a self-posed task archive under
a frozen executor; it is not a benchmark result and not a
general-capability claim. Scale: 20 generations, at most about 70
self-posed tasks per run, 6000 Builder candidates per generation, three
seeds. No claim about recursive self-improvement, a leap, or the
singularity.
