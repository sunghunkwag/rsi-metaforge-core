# Domain-conditioned mutation replay: development preflight, 2026-11-10

**NOT an independent RSI audit.** Synthetic task-name oracles using pre-existing TRAIN names, not upstream examples or independent holdouts.

Preregistration: [PREREG_DOMAIN_POLICY_DEV_20261110.md](PREREG_DOMAIN_POLICY_DEV_20261110.md).
Disclosure of inspected local engineering run: [DISCLOSURE_DOMAIN_POLICY_DEV_20261110.md](DISCLOSURE_DOMAIN_POLICY_DEV_20261110.md).
40 independent paired seed trajectories; 3 checkpoints; 32 synthetic shifted inputs; 16 unique candidates per task/checkpoint.

| Generation | persistent_domain | frozen_mutation | no_memory | wiped_each_generation | single_generation | inverted_feedback |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 41/240 | 43/240 | 45/240 | 41/240 | 45/240 | 48/240 |
| 2 | 46/240 | 43/240 | 53/240 | 43/240 | 53/240 | 54/240 |
| 3 | 43/240 | 43/240 | 45/240 | 42/240 | 41/240 | 45/240 |

## Paired wins / losses / ties and seed-clustered 95% CI

- gen1_vs_frozen_mutation: 31/33/176; -0.8333 pp; CI [-6.6667, 5.4167]
- gen1_vs_no_memory: 4/8/228; -1.6667 pp; CI [-5.0, 1.6667]
- gen1_vs_wiped_each_generation: 0/0/240; +0.0000 pp; CI [0.0, 0.0]
- gen1_vs_single_generation: 4/8/228; -1.6667 pp; CI [-5.0, 1.6667]
- gen1_vs_inverted_feedback: 5/12/223; -2.9167 pp; CI [-7.0833, 0.8333]
- gen2_vs_frozen_mutation: 35/32/173; +1.2500 pp; CI [-5.0, 7.5]
- gen2_vs_no_memory: 4/11/225; -2.9167 pp; CI [-5.8333, 0.0]
- gen2_vs_wiped_each_generation: 6/3/231; +1.2500 pp; CI [-0.8333, 3.3333]
- gen2_vs_single_generation: 4/11/225; -2.9167 pp; CI [-5.8333, 0.0]
- gen2_vs_inverted_feedback: 5/13/222; -3.3333 pp; CI [-6.25, -0.0]
- gen3_vs_frozen_mutation: 34/34/172; -0.0000 pp; CI [-6.6667, 7.0833]
- gen3_vs_no_memory: 9/11/220; -0.8333 pp; CI [-4.1667, 2.9167]
- gen3_vs_wiped_each_generation: 5/4/231; +0.4167 pp; CI [-1.6667, 2.5]
- gen3_vs_single_generation: 5/3/232; +0.8333 pp; CI [-1.25, 2.9167]
- gen3_vs_inverted_feedback: 10/12/218; -0.8333 pp; CI [-4.5833, 2.9167]

## Measured compute

- persistent_domain: counts={'support_candidates': 44160, 'support_vm_calls': 353280, 'support_oracle_calls': 353280, 'eval_candidates': 11520, 'eval_vm_calls': 460800, 'eval_oracle_calls': 460800}; CPU_ns={'generator_ns': 551373777, 'interpreter_ns': 778505547, 'oracle_ns': 688491134}; wall_ns=3826359581; CPU/frozen=1.08339
- frozen_mutation: counts={'support_candidates': 44160, 'support_vm_calls': 353280, 'support_oracle_calls': 353280, 'eval_candidates': 11520, 'eval_vm_calls': 460800, 'eval_oracle_calls': 460800}; CPU_ns={'generator_ns': 382281195, 'interpreter_ns': 791362134, 'oracle_ns': 689370975}; wall_ns=3671083470; CPU/frozen=1.0
- no_memory: counts={'support_candidates': 44160, 'support_vm_calls': 353280, 'support_oracle_calls': 353280, 'eval_candidates': 11520, 'eval_vm_calls': 460800, 'eval_oracle_calls': 460800}; CPU_ns={'generator_ns': 400704697, 'interpreter_ns': 782166283, 'oracle_ns': 686838888}; wall_ns=3669865072; CPU/frozen=1.00359
- wiped_each_generation: counts={'support_candidates': 44160, 'support_vm_calls': 353280, 'support_oracle_calls': 353280, 'eval_candidates': 11520, 'eval_vm_calls': 460800, 'eval_oracle_calls': 460800}; CPU_ns={'generator_ns': 470313999, 'interpreter_ns': 770553071, 'oracle_ns': 686322275}; wall_ns=3731403884; CPU/frozen=1.03445
- single_generation: counts={'eval_candidates': 11520, 'eval_vm_calls': 460800, 'eval_oracle_calls': 460800, 'support_candidates': 44160, 'support_vm_calls': 353280, 'support_oracle_calls': 353280}; CPU_ns={'generator_ns': 537040493, 'interpreter_ns': 779942125, 'oracle_ns': 685961155}; wall_ns=3824911911; CPU/frozen=1.07511
- inverted_feedback: counts={'support_candidates': 44160, 'support_vm_calls': 353280, 'support_oracle_calls': 353280, 'eval_candidates': 11520, 'eval_vm_calls': 460800, 'eval_oracle_calls': 460800}; CPU_ns={'generator_ns': 550316141, 'interpreter_ns': 783235043, 'oracle_ns': 687313852}; wall_ns=3827834137; CPU/frozen=1.08473

Retention loss=0.108333
Hypotheses={'H1': False, 'H2': False, 'H3': False, 'H4': True, 'H5': True}
**preregistered_success=false**

Limitations: generated task-name oracles are NOT the external upstream examples; shifted inputs are synthetic; interpreter calls are toy Python functions, not RSI-2 VM calls; OS CPU timing is noisy. Neither the inspected local engineering run nor this repository replay is independent confirmatory evidence of multi-generation RSI or AGI. Spent tasks and original hidden holdouts were not opened.

Tested source SHA: `a328ce8303058ae781779b4862ac407dec5d3231`. [One-shot CI](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42745552138); [Draft PR #60](https://github.com/sunghunkwag/rsi-metaforge-core/pull/60).
