# Development of design r (the relay): checks D1 to D6, 2026-11-16

Development runs on source categories only, on scratch ledgers; nothing here is evidence. The registered
test of design r is on four categories no process had used (`rsi6/registry/registration_r.json` when it
is recorded). The checks and their rules were written by the design panel's synthesis before any of them
ran (`rsi6/audit/design_panel_20261116/synthesize.json`, `development_checks`).

## D1: design r with an empty memory (r0) against design o's generation 0 (o0)

Job shop, quadratic assignment, p-median; seeds 9201 to 9206 (the specification named 600001 to 600006);
training budget 200, all fresh instances. o0@r0 is o0 raised to r0's CPU (the schedule doubles the budget,
so o0 ends with more CPU than r0). Differences are paired by category and seed; the interval is the
bootstrap interval of `open/evaluate.compare`; the last column is the first arm's CPU over the second's.

| comparison | mean | interval | job shop | quadratic assignment | p-median | CPU ratio |
|---|---|---|---|---|---|---|
| **first run: acceptance rule `rank` (design q's)** | | | | | | |
| r0 minus o0 | +0.0110 | -0.0051 to +0.0249 | -0.0018 | +0.0166 | +0.0184 | 1.26 |
| r0 minus o0@r0 | +0.0123 | -0.0042 to +0.0270 | -0.0023 | +0.0190 | +0.0203 | 0.62 |
| r0@800 minus r0 | -0.0140 | -0.0477 to +0.0052 | -0.0067 | -0.0018 | -0.0337 | 4.38 |
| **repeated: acceptance rule `hard_first`** | | | | | | |
| r0 minus o0 | +0.0103 | -0.0020 to +0.0228 | +0.0048 | +0.0117 | +0.0145 | 1.22 |
| r0 minus o0@r0 | +0.0106 | -0.0035 to +0.0259 | +0.0006 | +0.0142 | +0.0169 | 0.62 |
| r0@800 minus r0 | +0.0125 | -0.0050 to +0.0321 | +0.0043 | +0.0006 | +0.0325 | 4.31 |

Instances scored 0 after acquisition, repeated run: r0 0 of 348, r0@800 0 of 348, o0 0 of 348. Switches refused by the test on every other problem: 0 at budget 200 and 2 at budget 800, in 18 runs each.

### What the first run showed, and the change it led to

With the first rule, four times the training budget acquired less (-0.0140). The loss is carried by instances
scored 0: in the first run 5 p-median instances at budget 800 (two runs) and none at budget 200. Over the
instances scoring above 0 in both arms the same comparison is +0.0066 (p-median +0.028). One of the two runs
(p-median, seed 9203, budget 800) was repeated with design o's `construct` wrapped to record how each
construction ended (`scripts/diag_fragile.py`, `one_run_with_constructions_recorded.json`): 318 of the
acquisition's 6,938 constructions (4.6%) broke a hard constraint; with the programs the run kept, 3 of the
10 constructions on its own training problems and 3 of the 10 on fresh instances broke one, and those 3
fresh instances are the ones scored 0. Design o's batch fitness is the mean rank over the batch's problems:
a construction that breaks a hard constraint is last on its problem and no worse, so a copy of the programs
that wins narrowly on most problems and breaks a hard constraint on the others is taken.

Generation 0 of design r now judges a batch hard constraints first (`accept: hard_first`, `learner/design_r.py`).
D1 was run again and D2 was run in full on the changed design. The first-rule D2 had been stopped after 56
chain acquisitions, before any arm on a left-out category ran (`d2_first_rule_stopped_runs.jsonl`): no
development effect of the relay under the first rule was seen. The repeated D1 uses the seeds of the first,
so it is a check that the repair does what the diagnosis says, not an independent estimate.

D1 rule (a) (an r0/o0 CPU ratio above 1.25 means adding a compile cache) held in the first run (1.26) and
was not followed: a profile of one run of each design (`profile_r0_quadassign.txt`, `profile_o0_quadassign.txt`)
shows the extra CPU in running the longer edited programs inside design o's constructions, not in compilation.

## Files

| file | what |
|---|---|
| `d1_first_rule_summary.json`, `d1_repeated_hard_first_summary.json` | the two D1 summaries |
| `d1_runs.jsonl` | every run record of both D1s (purposes `dev:r:d1:` and `dev:r:d1h:`) |
| `d2_first_rule_stopped_runs.jsonl` | the chain runs and memory records of the first-rule D2 that was stopped |
| `one_run_with_constructions_recorded.json`, `profile_*.txt` | the diagnostic run and the two profiles |
| `d5/` | dry runs of the driver and report (D5): A (every CPU rule applied), B (futility stop, plan lowering), C (A stopped by SIGTERM and restarted), with the code before the review's corrections |
| `scripts/` | the development scripts, as run (paths written `<scratch>` and `<repo>`) |

D2 to D6 on the changed design, the decisions of the pre-written rules and the registration follow.
