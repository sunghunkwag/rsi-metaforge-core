# Independent review of the relay driver, report and registration generator (2026-11-16)

Before the relay experiment (design r, amendment 6) was registered, four reviewer agents read an
isolated copy of the code against the panel's specification (`../design_panel_20261116/synthesize.json`),
one lens each: the driver's fidelity to the specification, the report's statistics and the scoring
of predictions, replay and robustness, validity and leakage. A skeptic agent was to re-check every
finding of a lens. The skeptic of the driver lens finished and confirmed all four of its findings;
the other three skeptics did not run (the session's usage limit ended the workflow), so the
findings of those three lenses were judged by the session itself. Every finding was judged real
and acted on. The agents ran no learner; they read the code, ran the two test modules and pure
functions, and returned the structured findings kept here as returned (scratch paths written
`<scratch>/`).

| file | what |
|---|---|
| `review_driver.json`, `verify_driver.json` | 4 findings on `relay.py` and `make_dev_r.py`; all 4 confirmed by the skeptic |
| `review_report.json` | 11 findings on `relay_report.py` and `design_r.py` (not re-checked by a skeptic) |
| `review_replay.json` | 9 findings (5 of them repeat findings of the other lenses; not re-checked by a skeptic) |
| `review_validity.json` | 10 findings (not re-checked by a skeptic) |

## What was done (commit c84cf75 and the development scripts in `../../results/dev_r_20261116/scripts`)

Driver.
- The CPU projection left out frozen raised to relay's CPU. It is now counted: in the plan when
  frozen is raised on every category, and before primary-b from the measured CPU of primary-a's
  raise.
- Compared arms of an item ran as consecutive batches. They are now one batch interleaved pair by
  pair (relay and frozen; the two references).
- With fewer than 64 primary chains, a futility stop left items 4 and 7 registered on chains the
  primary did not hold. The items that still run now cover the chains below J/2.
- A stage stopped while writing a line could not be restarted: the driver now refuses a torn last
  line with the repair. Submissions go 16 runs at a time, so a stop repeats at most one submission.
- A development run could share the machine with a registered driver. It now waits for the
  registered ledgers' writer lock and holds it shared.

Report.
- The CPU ratio of a comparison was taken over all rows of both arms. It is now over the pairs
  that enter the comparison.
- The CPU rule replaced a comparator by a run at a raised budget, which in development did not
  always help the comparator. A comparison now uses the raised comparator and the comparator at
  the registered budget, and both tests must hold; o0's runs at the registered budget are the
  first level of its raise.
- m_net was given a value when comparators were missing, and mixed two and three seeds. It has no
  value unless every registered comparator was measured on the registered chains, and uses seeds
  0 and 1.
- The slope of the depth curve was fitted on two depths when one was dropped. It needs all three.
- Design a's comparisons averaged a per-pair minimum. They take the smaller of the two mean changes.
- The untrained-identity check skipped the raised arms and changed nothing when it failed. It
  covers every arm of designs r and o, and no endpoint is met if it fails.
- Resamplings used fixed seeds. They are seeded by the CRC-32 of the comparison's label.
- The sign-flip test that development check D6 prescribes did not exist. It is implemented and
  chosen by the registration.
- An endpoint's `met` was its single test. It is the gate's decision; the single test is
  `single_test`.
- L1 compared frozen at the registered budget with o0 raised. Both variants are reported.
- The 2x2's sums depended on the hash seed. They run in a fixed order.

Placebo and learner.
- A random placebo block did not keep the length and the number of new constants of every block
  shape, and a block that recurred across entries became several blocks. Both are corrected; the
  library the shuffled arm rebuilds has the size and the shapes of the real one.
- A spliced block counted as kept after a later switch had removed it. It counts only if all of
  it is live in the kept programs.

Development rules and registration.
- The layout choice and the cap check read the construction units of the held-out categories in
  development. That step had not been run; it was removed. Planning uses the specification's
  planning cost (39 s for o0 at train 200, times the measured r0/o0 ratio); only the registered
  held-out stage reads held-out sizes.
- Rule D2 (b) removed the library's arms and left the library in the design. It now also sets
  `lib_per_run` to 0.
- Rules D2 (b), (c) and (d) were applied to summaries of the three left-out categories'
  summaries. They are applied to the 24 development chains pooled.
- The registration generator wrote a registration whatever rule D2 (e) said and whether or not D6
  had run. It refuses unless both allow it.

Tests.
- The specification's T10 was only a manual dry run. `tests/test_relay.py` now stops the held-out
  stage during each of its submissions in turn, on a deterministic cache, and starts it again: the
  same ledger, with the CPU rule applied, with a futility stop on fewer primary chains than
  secondaries, and with the cap dropping items and stopping the stage.

A second review, of the acceptance rule that development added (`accept: hard_first`) and of the
registration itself, follows in this directory when it has run.
