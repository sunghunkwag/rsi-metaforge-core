# DUST-uncertainty action-routing ablation

Independent development arm against the exact PR #39 DUST Meta-RL baseline.

The original DUST activation-perturbation estimator estimates the probability
of a verified success after a search-action chunk. The proposed routing-only
intervention reduces the existing UCB exploration bonus for actions with
very certain predicted outcomes:
`uncertainty(p)=0.15 + 0.85 * 4*p*(1-p)`.
No action success labels, replay data, optimiser hyperparameters, verifier,
task corpus, search mechanism or candidate budgets are changed. This is
a derived bandit-routing heuristic, **not original Q Labs DUST code**.

### Pre-result protocol
Four generations on TRAIN at seed 11 with equal B_wake=64, 16 candidate
evaluations per action chunk; unchanged 256 honest-practice attempts.
Run full RSI-3 unit tests before comparing TRAIN solved count and CPU cost.
VALIDATION, RESERVE, FAR2 and TEST are never loaded for development.
Any result using already published RESERVE or FAR2 would be retrospective
and cannot establish fresh blind generalization.

A TRAIN null or regression is a negative result. No implicit code merging.
