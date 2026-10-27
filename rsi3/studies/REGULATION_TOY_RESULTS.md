# Regulation study — measured results

Source: `rsi3/studies/regulation_toy.py`, 5 seeds (0–4), configuration printed
by the script. Run with `python -m rsi3.studies.regulation_toy`. Numbers are
test-set MSE, mean ± standard deviation over seeds; lower is better. The study
was first run in the Owner's chat session on 2026-10-27; this English port
reproduces those numbers exactly.

This is a toy-scale study (2-d inputs, at most 48 hidden units). Its purpose
is to decide one design question for RSI-3, not to make a claim about
continual learning in general. The ranking it finds (experience replay ahead
of parameter regularization) agrees with what the continual-learning
literature reports.

## Experiment 1 — an injected change, then new experience

A processor trained on task A (A 0.0053, B 1.4221) receives a patch written
directly into its parameters, then learns from 3,000 steps of task-B
experience. Every regulator records the same experience; they differ only in
how the record is used.

| Regulator | Beneficial patch: A | B | Harmful patch: A | B |
| --- | --- | --- | --- | --- |
| right after injection | 0.0030 | 0.0021 | 3.9182 | 4.3968 |
| no regulation | 0.0763 | 0.0006 | 3.0246 | 0.0007 |
| fixed reference, λ = 0.05 | 0.6608 | 0.0385 | 0.6558 | 0.0376 |
| fixed reference, λ = 0.5 | 0.4178 | 0.1993 | 0.4150 | 0.2042 |
| **memory replay only** | **0.0029** | **0.0007** | **0.0069** | **0.0006** |
| replay + fixed reference | 0.0433 | 0.0287 | 0.0486 | 0.0314 |
| replay + evidence-gated reference | 0.0231 | 0.0128 | 0.0486 | 0.0314 |

Log-scale retention of the beneficial patch's B ability (1 = kept, 0 =
reverted): no regulation 1.22, weak fixed 0.55, strong fixed 0.29, replay
1.17, replay + fixed 0.59, gated 0.88 ± 0.26. Log-scale recovery of A after
the harmful patch (1 = full): none 0.03, weak fixed 0.26, strong fixed 0.35,
replay 0.97, replay + fixed 0.67, gated 0.67.

Findings:

1. Replay alone was best on both patches and both tasks.
2. Pulling parameters toward a reference was harmful whether the reference was
   fixed or gated. While new experience keeps arriving, a parameter-space
   anchor did not even protect the old ability: A rose from 0.005 to 0.42–0.66.
3. The evidence gate (update the reference only when memory shows no loss)
   passed on 3 of 5 seeds after the beneficial patch and on 0 of 5 seeds in
   3,000 steps after the harmful patch. In the harmful case, gated and
   replay + fixed are identical: all recovery came from replay.

## Experiment 2 — dormant unit creation

A processor meets tasks A → B → C (3,000 steps each). When memory-replay loss
plateaus, it adds four hidden units with zero output weights. They leave the
function unchanged at insertion (difference ≤ 1e-12, asserted at every
insertion) and receive gradient only through their output weights until those
grow. All three tasks are measured at the end.

| Arm | A | B | C | Final hidden units | Params |
| --- | --- | --- | --- | --- | --- |
| replay, fixed 4 | 0.1584 | 0.1524 | 0.0409 | 4 | 29 |
| replay, fixed 48 | 0.0094 | 0.0042 | 0.0009 | 48 | 337 |
| replay, fixed 28 | 0.0113 | 0.0066 | 0.0012 | 28 | 197 |
| replay, growth 4 → ≤ 48 | 0.0128 | 0.0073 | 0.0014 | 20–36 (mean 27.2) | 141–253 (mean 191) |
| gated reference, fixed 48 | 0.0738 | 0.1471 | 0.0175 | 48 | 337 |
| gated reference, growth | 0.1202 | 0.1211 | 0.0216 | 48 | 337 |
| no regulation, growth | 1.4164 | 0.8080 | 0.0012 | 48 | 337 |

Findings:

1. The dormant-unit mechanism works as designed: function-preserving at
   insertion, woken by the error signal.
2. Growth reached about 57% of the large network's parameters with errors 1.4–1.7×
   higher, and was slightly worse than a network fixed at the same final size
   from the start. Its only measured benefit is choosing its own size.
3. Growth without replay forgot earlier tasks (A 1.42, B 0.81).
4. The gated reference cost an order of magnitude in error against replay alone.

## Consequence for RSI-3

The value model is refit from scratch on a full replay of memory every
generation, with no anchor, gate, or rollback on the model (ARCHITECTURE.md,
D1–D2). New pathways are created dormant and must earn budget through evidence
(D3); this study's growth result is the reason RSI-3 does not assume that
adding pathways helps, and measures it with the `RSI3_NO_GENESIS` arm.
