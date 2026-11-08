# Type-directed sampling and weight-only A/B gate: 2026-11-08

## Sources
- Root code: https://github.com/sunghunkwag/rsi-metaforge-core/commit/3cfc329eca17a08e1a1565064b61a5bd4a1dd520
- Executed code: https://github.com/sunghunkwag/rsi-metaforge-core/blob/research/type-directed-ab-gate-20261108/research/typed_weight_ab_gate_20261108.py
- Successful CI and raw JSON artifact: https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42467255946

## Hypothesis, design and budget
The historical stochastic proposal generator responds to SearcherState weights, but the original meta-gate's enumerator does not. We implement an **isolated** candidate weight-only A/B gate and a type-directed postfix program generator using the immutable root VM. Production gates, verifiers, archived evidence, sealed TEST/J, and RSI-4 Phase 1 are never altered or tuned.

Arms: original untyped sampler; typed implicit-uniform; typed explicit-uniform null; typed learned weights.

Support training uses only two public synthetic tasks: length and sum, seed 91, 96 candidates per task (192 proposals and 3,840 charged input probes). The discovered programs are INPUT LEN and INPUT RED_ADD. Learned weights are INPUT=6, LEN=4, RED_ADD=4. No development or audit labels are used to update these weights.

Preregistered evaluation: paired seeds 100..131, 20 candidates per seed/task/arm, exactly 20 charged training-input slots per candidate. The typed grammar produces all valid 2-, 3-, and 4-token postfix programs within a restricted subset of the 34 original base opcodes; the untyped control samples those lengths as well. Each task-stage-arm receives 2,560 candidate evaluations and 51,200 charged probe slots. These are **equal logical budgets, not equal actual CPU work**. A uniform 0.5 CPU-second ceiling per task/seed/arm is checked after the run; no arm breached it.

Development tasks are even_sum, odd_sum, even_length, odd_length with training seed 113. Independent audit tasks are tail_sum, tail_length, head, max with training seed 211. For a separate distribution-shift check, 24 independent inputs use lengths 0,5,8,13,21,34 and values from -11 to +23. Shift inputs do not train or select weights.

The A/B development gate requires at least +3 solved cases for learned versus typed-uniform, no single task worse than -1, equal charged logical budgets and no CPU cap breaches. Production eligibility additionally requires a *positive* audit total delta and no audit task worse than -1.

## CI results (each phase: 128 task/seed cases)
| Arm | Development TRAIN | Development shift | Independent audit TRAIN | Audit shift |
| --- | ---: | ---: | ---: | ---: |
| Original untyped | 0/128 | 0/128 | 0/128 | 0/128 |
| Typed uniform | 15/128 | 15/128 | 66/128 | 63/128 |
| Typed explicit-uniform null | 15/128 | 15/128 | 66/128 | 63/128 |
| Typed learned | **41/128** | **41/128** | 59/128 | 58/128 |

Development learned-minus-uniform: **+26 successes**. Per-task deltas: even_length +9, even_sum +5, odd_length +6, odd_sum +6. Development gate returned accept=true.

Independent audit learned-minus-uniform: **-7 successes**, with tail_sum +5, tail_length +3, head -6, max -9. Audit replication returned false and production_eligible=false.

CPU seconds, development: original 0.104422; typed uniform 0.096312; typed null 0.093009; typed learned 0.097173.
CPU seconds, audit: original 0.102217; typed uniform 0.090999; typed null 0.090542; typed learned 0.094545.

Typed programs meeting static validity: 2,560/2,560; untyped original: 12/2,560, in each phase. The exact typed-uniform/null equivalence is asserted for every seed and task. CI self-tests pass.

## Interpretation
The typed generator is much more likely to produce valid candidates than unconstrained token sampling under the tested tiny grammar. The learned weights dramatically improve *related* tasks on the development set, but reduce accuracy on some independently held-out task families. **This is a demonstrated negative transfer/forgetting effect, not a general RSI gain**.

Limitations: restricted synthetic grammar, only 32 paired seeds, task-specific support tasks, training cost not charged to inference arms, differences in actual executed VM instructions and CPU costs, no real-world tasks, and a CPU ceiling checked after rather than enforced mid-execution. These observations do not establish statistically robust generalization, AGI, or recursive self-improvement.

## Decision and next falsifiable experiment
**Keep as Draft. Do not merge or modify the production gate.** Independent replication is negative, although the development gate passed.

Next fresh-data hypothesis: support-only selection of a diversity-preserving mixture of learned and type-uniform proposal probabilities can retain gains on new composed tasks without suppressing primitives important for unseen families. Freeze mixture parameters *before* an entirely new independent audit. The above audit tasks are spent and must never be used to tune that candidate. Match counted candidate and input-probe budgets, report CPU and training costs separately, and treat any forgotten tasks or failed replication as a negative result.
