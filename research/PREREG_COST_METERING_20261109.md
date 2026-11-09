# Preregistration: instrumented compute-parity preflight (2026-11-09)

## Scope and integrity
This is an **engineering calibration only**, not an audit of synthesis success, RSI, transfer, or held-out tasks. No TEST, J, RSI-4, PR #50–57 spent audit IDs, or PR #58 data are read. The branch begins at main `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`. PR #57's negative result is preserved unchanged. The purpose is to prevent a later fresh externally frozen audit from confusing nominal proposal counts with measured interpreter work or CPU time.

No audit task IDs are selected in this study. Synthetic arithmetic calls below are **meter fixtures only**, never benchmark tasks. A later actual RSI study requires its own independently frozen task manifest committed before any runner and its own separate preregistration.

## Frozen pre-execution protocol
- 40 independently initialized paired seed trajectories, integer seeds 0–39; three generations and 16 candidate evaluations per generation per arm. Each candidate performs eight public interpreter fixture calls; shifted-verification fixture calls are deliberately excluded from correctness claims. Each generation performs four support-learning interpreter fixture calls.
- Four arms: `reference`, `same_work`, `extra_training_call` (one extra support-learning interpreter call per generation), `extra_generator_cpu` (same VM calls but an additional deterministic 200,000-iteration integer loop per seed in proposal generation).
- Record **actual**, incremented-at-call-site counters for candidates, public VM, support-learning VM, verification VM, generator CPU, training CPU, VM CPU, verification CPU, total process CPU, and wall time, per seed and arm. Charge extra support-learning work; no candidate-slot inference of VM counts.
- Paired comparison requires equality of all interpreter-call and candidate counters **and** actual aggregate CPU ratio <=1.10. Per-seed CPU ratios and per-arm CPU and wall totals must be reported; actual CPU noise is never erased by an assumed parity label.
- Stop after 40 seeds, regardless of outcome; no reruns or changes to thresholds after observing results. Code and smoke tests may be repaired before the first calibration run, with the preregistration unchanged and the repair documented. Once raw results are committed, this calibration is frozen.
- Predict `extra_training_call` will be rejected for unequal VM work on all 40 seeds. Predict `extra_generator_cpu` will be rejected by the measured CPU gate on >=38/40 paired seeds, even though VM counts match. `same_work` is not guaranteed CPU parity under OS scheduling; report its observed pass count without post-hoc threshold change.
- Negative control: a deliberately unmetered extra call should be detected by a test requiring that all calls go through the metered wrapper, but **runtime detection of arbitrary bypasses is not claimed**. A wrapper cannot police calls made outside it.
- CI: standard-library `unittest`; report pass/fail and exact tested SHA. Raw per-seed JSON is committed, never merely an Actions artifact.

## Prospective interpretation
The sole success criterion is the two negative controls satisfying their predeclared rejection rates and the counter unit tests passing. This does not validate a future RSI result, demonstrate CPU equality in PR #57, or repair its spent audit. Report the result, including failures, in the root README and a separate report. No cherry-picking of seeds or revisions after results.
