# Review of the drivers that follow process c

Before any of it was run on the registered ledger, the code written during process c was
reviewed by three independent agents, one per part, each working in an isolated copy with no
access to the experiment's working directory, no network and no learner run on a reserve or a
target:

* `review_targets.json`: `experiments/targets.py` (arms of process c, compute matching, the
  checks before the unlock).
* `review_external-recursion.json`: `experiments/external.py` and `experiments/recursion.py`.
* `review_report.json`: `experiments/report.py` (process c, predictions C1 to C6, comparisons).

Every finding rated blocking or major was then given to a separate agent told to refute it
(`verification_*.json`). No finding was rated blocking. Of eight major findings all eight were
confirmed as real; four kept the rating major and four were rated minor by their verifier.

## Confirmed as major, and what was changed

| finding | change |
|---|---|
| The list of targets was checked too weakly: with the flag for a shorter list any subset passed, duplicates passed, nothing compared the list with the categories that have the role of a target. | `targets.check_list`: the list must be exactly the categories with the role of a target once the replacements are applied, less the categories it states as missing with a reason; no duplicates; an adapter for each. |
| The record that lets a reserve replace a target was written before the list was checked, and neither side was checked. | The list and every replacement are checked in memory first (drawn role and present role of both sides, no run on the reserve); the `replace` records and the unlock are written only afterwards. |
| A comparison against an arm with a matched budget was never voided when that arm received too little CPU, although the registration says such a comparison is void; the success condition of process c read "not behind the compute-matched arm" from it regardless. | `report.targets_section`: every comparison in which one side is a matched arm carries `void` (the arm fell short of its matched CPU in a pair, or received less measured CPU than the other side in a pair) and prints it; the targets part of the success condition is `void`, and success is then not established. The `matched` record now holds, per pair, the matched CPU, the measured CPU, the levels and the final budget. |

## Confirmed, rated minor by the verifier, changed all the same

* Nothing tied a later start of the target test to the list recorded at the unlock, and every
  start wrote its summary records again. Now: a later start must present the recorded list; a
  `matched` record is written once; after the closing record the driver measures nothing.
* No protection against two drivers writing one ledger. Now: `experiments/guard.py` holds an
  exclusive lock for the lifetime of every driver, the recursion check requires the record of
  the external gate, and the target test refuses beside an unfinished recursion check.
* The drivers had different default ledgers and the checkpoint was a manual step. Now: all
  drivers default to the working ledger, refuse to continue the shorter of two histories, and
  `python -m rsi6.experiments.guard checkpoint` is the checkpoint, as code.
* Prediction C6 is registered on the list file; it is now compared with the list the ledger
  unlocked, and left unscored if the two differ.

## Minor findings and notes acted on

* `alternating.py` (the running driver of process c): a stop between an adoption record and
  the closing record of its generation would have let a restart run that generation again from
  the newly adopted version. The start version of a generation is now the last one adopted in
  an earlier generation, an existing adoption record is not written twice, and no generation is
  run after the freeze record. This changes nothing unless the driver is stopped in that
  window; the running process started before the change.
* `external.py`: the role is released before the outcome is recorded; a recorded freeze, gate
  or outcome must agree with what a later start computes; the record of amendment 4 is written
  before the freeze, in the shape of the earlier amendment records.
* `recursion.py`: its records have their own types, so that the readers of searches and gates
  do not pick them up; the recorded climb of a generation must have started from the version
  the check computes for it; the summary counts in how many compared generations the climb
  named a nominee at all (a missing nominee counts as 0, as registered).
* `targets.py`: `--dev 0` no longer counts as a registered run; what the first two processes
  spent now includes the runs of the version a search started from (44 and 142 CPU-seconds
  more for the controls); where the last two levels of a matched budget show no rise of CPU
  the factor is the largest allowed, as amendment 4 words it; the closing record lists the
  categories that filled the memory arms.
* `report.py`: adopting generations are counted as generations; runs of two arms are paired by
  seed and the seeds must agree; the recorded outcome of the external gate is recomputed from
  its two measurements; an adoption lists every technique that named the adopted version.

## Stated, not changed

* The factor of a matched budget aims a tenth above the matched CPU, and the first of the
  twelve levels is the registered budget itself. Amendment 4 does not say either. Both are
  written into the text of `targets.py` and are repeated with the result.
* The memory arms acquire first on every category that is in the source pool when the target
  test runs. Tour and colouring are in it only if the external gate ran. The closing record of
  the target test lists the categories used.
* Observed in the development runs, properties of the frozen learner and not of this code:
  the memory arms collapse (recall across categories replaces the starting point and is not
  checked against the untrained prior), and the arm with a raised test-time budget and no
  training does not change its scores with the budget.
