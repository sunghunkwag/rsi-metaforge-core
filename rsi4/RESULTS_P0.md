# Phase 0 results: the harness, before any agent code

**Gate 0 passes.** The stages and J's pools are built by registered rules,
pairwise disjoint and hashed; the exclusion audit passes; red-team tests R1,
R2 and R3 pass. No rsi4 agent learning code exists yet. Every number below
comes from the committed builder output (`rsi4/judge/pools/BUILD.json`) or
the test suite at the commit that adds this file.

| Gate 0 condition | Result |
| --- | --- |
| Pools built, disjoint and hashed | built from the registered source (174,258 records, sha256 0dce7f82…); 15 sets pairwise disjoint by name; `MANIFEST.sha256` covers every pool, J's seed, J's code and the stage-train file |
| Exclusion audit passes | no record is a FRESH-1/FRESH-2 name, a corpus name or a COMPOSE-24 task (R2) |
| R1 sealing | pass (18 tests) |
| R2 exposure | pass (9 tests, including a full rebuild of every file from the source) |
| R3 instruments | pass (4 tests) |

Commits, in the directive's order: directive 73355d5; pools and manifest
f9a28eb; J and its tests 9183407; workflow 3025e04; this file.

## Stages and pools

Source: DreamCoder's `data/list_tasks2.json` at cb0e63f, 174,258 records,
fetched once and not committed. Rules: `rsi4/judge/pools.py` (docstring),
applied to names, declared types and example counts only; no task was run
to select anything. Example protocol: `rsi3.fresh`'s (first 8 distinct
inputs public, the rest hidden).

| Step | Count |
| --- | --- |
| Eligible two-stage records (as FRESH counted them) | 5,835 |
| Eligible three-stage records | 123,628 |
| Records dropped as repeats of an earlier name | 26,857 |
| Excluded: FRESH-1/FRESH-2 names | 100 (all FRESH-2; FRESH-1 holds single routines) |
| Excluded: corpus-style name in RSI-2's corpus | 0 (the corpus holds single routines) |
| Excluded: behaviourally equal to a COMPOSE-24 task | 32 |
| **Eligible two-stage names** | **3,910** |
| **Eligible three-stage names** | **98,564** |
| Routines in eligible two-stage pipelines | 51, split 17 / 20 / 14 by sha256(name + J seed) mod 3 |
| Stage candidates (both routines in the stage's group) | S1 279, S2 838, S3 266 |
| Per stage | 36 stage-train + 100 stage-eval (no group was short, so no stage shrank) |
| Remaining two-stage names for J's pools | 3,502 |
| Probe / selection ×3 / confirmation ×3 / final test | 60 / 100 each / 200 each / 200 |
| Final test, three-stage | 100 |
| Two-stage names used in all | 1,568 of 3,910 |

Every stage and pool is mostly list-to-list (stage-train: 28, 32 and 28 of
36), with list-to-bool and list-to-int pipelines making up the rest.

**Differences from the directive's estimates, recorded, not tuned.**

- The directive estimated "roughly 5,700 eligible" two-stage pipelines. That
  counts records. The source repeats names (the same program with other
  example inputs), so a name could otherwise sit in two pools at once. One
  record per name leaves 3,910 eligible names. The registered plan uses
  1,568 of them, as the directive's arithmetic (about 1,570) expected.
- COMPOSE-24 is not a record of the source file (`rsi3/compose24.py` builds
  it from reference oracles), so its exclusion is behavioural: 32 records
  whose every distinct example agrees with one of the 24 oracles were removed.
- The corpus-name rule removes no pipeline, as expected; the count is
  recorded so the rule is visibly applied.

**J's seed.** `secrets.randbits(62)`, drawn once before any pool existed,
stored in `rsi4/judge/seed.json`. It was not redrawn.

## Red-team tests

| Test | Planted fault or null | Observed |
| --- | --- | --- |
| R1a | 14 planted agent modules: `import rsi4.judge`, `from rsi4 import judge`, `from .judge import …`, `from . import judge`, a deep import, `open('rsi4/judge/pools/…')`, a `'judge'` path part, `'seed.json'`, `'list_tasks2.json'`, `importlib.import_module`, `__import__`, `exec`, `.hidden`, `.__closure__`; one in a subpackage (`from .. import judge`) | every one caught by the audit; the live package has no finding; J refuses `run_start` for a tree with a planted module and logs the refusal |
| R1a, run time | an agent process with `guard.install()` opens a pool through a path assembled at run time, reads the seed file, lists the pools directory, imports J's package | all four blocked (`PermissionError` / `ImportError`); a normal file opens |
| R1b | a judge file modified during a run; the same with the manifest rewritten to match; the registered config modified during a run | J refuses every request while its files differ from the manifest; `run_end` voids the run in all three cases ("rsi4/judge/** changed during the run", "the registered config changed during the run"); an untouched run is valid |
| R1c | self-issued, forged and mismatched receipts | rejected (rsi3's 7 verifier-memory tests, run unchanged inside this suite) |
| R1c, J | a solver that claims every task and never asks the verifier; a solver that asks twice for one task | J counts 0 solved and lists every claim as differing from its verdict; the second query raises and the evaluation is logged as an error |
| R2 | every record of every pool and stage | no FRESH-1/FRESH-2 name, no corpus name, no COMPOSE-24 task; all 15 sets pairwise disjoint by name and of the registered sizes; every record has the registered shape (two-stage, or three-stage for `final_test_3`) and 8 public examples with at least one hidden; every stage record's routines lie in that stage's group; the final-test pool shows zero draws in every ledger; the rules rebuild every committed file from the source byte for byte |
| R3a | the same checkpoint and request sent to J twice, through `rsi4.client` (two spawned J processes, each with its own hash seed) | byte-identical responses (same SHA-256); the ledger replays with no mismatch |
| R3a, sleep check | a sleep check whose before and after selves are the same checkpoint | 0 wins, 0 losses, keep; identical per-seed verdicts |
| R3b | a synthetic worker that makes 400 MB resident, under a 150 MB cap; a small worker under a 1 GB cap | the first is killed and one breach record is logged with its RSS; the second runs to completion with nothing logged |

Also in the suite: J's statistics (the directive's sign-test examples,
8 vs 1 → p = 0.0195 and 7 vs 2 → p = 0.0898; Holm), the rule bounds (every
registered rule's out-of-range values rejected; budgets, limits and seeds
are not rules), the confirmation and sleep rules, ledger tamper and removal
detection, the score-matrix metrics on a hand-computed matrix, and one
end-to-end flow of every decision operation (select with an out-of-bounds
candidate rejected, one-use pools, confirm and burn, the final test once,
compare with Holm, metrics, replay of both ledgers) on a judge copy whose
pools hold TRAIN tasks. That flow found one defect before J was committed
(a select decision's counts overwrote the logged summaries) and it was fixed.

## Exposure

- No pool or stage task has been run by any solver. The tests run J on a
  test checkpoint (RSI3_META_HONEST, one generation on six TRAIN tasks)
  against exposed partitions (FRESH-1 during development, RESERVE-FAR2 in
  R1c and R3a), TRAIN, and judge copies whose pools hold TRAIN tasks.
- The one exception is R3a's sleep-check test, which runs the probe pool on
  that test checkpoint. It asserts only that identical selves give no win
  and no loss. No probe outcome was printed, read or recorded outside the
  test's temporary ledger.
- While building, only counts were printed: the table above and the
  input/output type mix per set. No pool task name was printed.

## Implementation choices the directive left open

- **Process isolation.** `rsi4/client.py` starts J with `multiprocessing`'s
  spawn start method and runs the package only in the child
  (`runpy.run_module`); requests and responses are files. The agent process
  never imports `rsi4.judge` (checked in the end-to-end run).
- **The path audit** has a run-time half (`rsi4/guard.py`, a PEP 578 audit
  hook), because a path assembled at run time escapes any static audit.
- **Two ledgers.** A run's own ledger (in its output directory) holds
  `run_start`, `evaluate`, `sleep_check` and `run_end`. Single-use pools
  (`select`, `confirm`, `final_test`) and gate statistics (`compare`,
  `metrics`) always go to `rsi4/ledger/judge_log.jsonl`, which a request
  cannot redirect, so a burned pool stays burned.
- **Report-only partitions.** Besides the exposed partitions, J evaluates
  `report:train` and `report:stage_train_S<k>` for TRAIN and stage-train
  retention (§6 "TRAIN retention"). None of them enters a decision.
- **Branch.** The directive names `rsi4/four-loop`. This session's work goes
  on its designated branch, `claude/dazzling-ptolemy-8xdlhm`, created from
  the same base (`rsi3/analogy` at 1e6868a). Run branches follow the
  directive (`rsi4/run-*`).

## Suites

| Suite | Command | Result |
| --- | --- | --- |
| rsi4 | `python -m unittest discover -s rsi4/tests -t .` | 50 tests OK (49 + 1 skipped without the source file) |
| rsi2 | `python -m unittest discover -s rsi2/tests` | 470 OK |
| rsi3 | `python -m unittest discover -s rsi3/tests -t .` | 118 OK, 1 skipped (the root README's "86" predates the last rsi3 studies; the rsi3 directory is unchanged from the base) |

`git diff rsi3/analogy -- rsi2 rsi3 docs rsi_levels_metaforge_unified.py EVIDENCE.md OUTER_LOOP_CONSTITUTION.md`
is empty, and the existing workflow files are unchanged.

## Claim boundary

Phase 0 builds and tests the harness. It makes no claim about learning,
transfer or forgetting; those are measured from Phase 1 on, against
predictions registered before each phase's final runs.
