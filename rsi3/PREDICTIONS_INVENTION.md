# Concept-invention study: pre-registered predictions

Registered 2026-10-29, before any run of either arm on the registered seeds
(11/22/33) at this commit. This file is committed together with the code
(`selfmodel.py`, plus wiring in `pathways.py` and `loop.py`) and
`experiment_config_invention.json`. That config matches
`experiment_config_failure_memory.json` except for three things: the arm
list, 12 generations instead of 8, and the `invention` block. Misses will be
scored in INVENTION_RESULTS.md and will not be reinterpreted.

## The question

Across 21 registered RSI-3 runs, RSI-2's library learning adopted nothing.
Its MDL rule needs a fragment to recur in two or more solutions and to shrink
the corpus, and 6–8 small solutions (2–8 nodes) never recur. So the language
the system searched in never changed, and VALIDATION stayed at the same one
or two tasks on every run (`caesar-cipher k=3 n=2`, and `sum` on some runs).

The new arm gives the system a model of itself and lets it rewrite its own
language from that model. Each generation it:

1. decomposes its verified TRAIN programs into closed parts;
2. runs candidate concepts on probe inputs from TRAIN public inputs;
3. invents concepts from its own parts: parts, powers (`f . f`,
   `f . f . f`), compositions, and integers the frozen grammar cannot name
   (the grammar names only -1, 0, 1, 2);
4. adds up to 24 concepts to that generation's search grammar at a tenth of
   RSI-2's pseudocount.

A concept is adopted into the permanent library only when a program using it
passes the frozen verifier on a TRAIN task's hidden examples. Concepts that
earn nothing leave at the end of the generation. Adopted concepts can be
parts of later inventions. Exact definitions are in `selfmodel.py`.

Does a language that grows from the system's own verified experience reach
tasks the fixed language cannot, at the same logical budget, and does that
change held-out capability?

## Arms

| Arm | Definition |
| --- | --- |
| RSI3_UNIFORM_FM | The best arm so far (8/36 on every seed at 8 generations); rerun here for 12 generations as the comparator |
| RSI3_UNIFORM_FM_INV | RSI3_UNIFORM_FM plus self-model concept invention |

- Seeds 11/22/33; B_wake = B_eval = 64.
- Per-generation cap of 2,304 logical evaluations; one verification per task
  per generation.
- Invention adds no logical evaluations. Probe runs that build the self-model
  are reported separately, as the integrator's probes already are.
- TEST is not opened. VALIDATION is reporting only: no component reads it.

## Disclosure: development before registration

All development used the unregistered seed 44. In order:

1. **Concepts at pseudocount weight 1, 8 generations: 6/36.**
   - The 14 concepts invented from the first six solutions were useless,
     because those solutions are trivial (identity, `cons 0`, `map (eq 1)`,
     `map (sub 1)`).
   - Those concepts pushed index-k (k=3) from candidate rank 273 to 820 under
     the generation-2 grammar, so it was never found.
   - Measured ranks at concept weight 0.3 / 0.1 / 0.03 were 381 / 317 / 290.
     Weight 0.1 was chosen.
2. **Weight 0.1, small parts and whole solutions excluded, 8 generations:
   8/36.**
   - This was the first library adoption in any RSI-3 run. `tail^4`,
     invented as a power of `tail (tail x)` from index-k (k=3), was adopted
     in generation 6 by a verified `head (tail^4 x)` for index-k (k=5).
   - prepend-k (k=4) was not reached by generation 8.
   - VALIDATION was 1, 2, 2, 1, 2, 2, 2, 1.
3. **Offline reach checks (TRAIN only, budget 600).**
   - Concepts invented from eight solutions verified index-k (k=5) and
     prepend-k (k=5). The fixed grammar verified neither.
   - Concepts invented from the generation-6 state of run 2 reached nothing
     new.
   - Two proposal sources were then added:
     - int -> int -> int primitives the system has used, applied to
       constants it can name;
     - whole solved programs of six or more nodes, as building blocks.
4. **This commit's code, 12 generations, both arms on seed 44.**

   | Arm | TRAIN g1–g12 | VALIDATION g1–g12 | CPU s |
   | --- | --- | --- | --- |
   | INV | 6, 6, 6, 6, 7, 8, 8, 8, 8, 8, 9, 10 | 1, 2, 2, 1, 2, 2, 2, 1, 2, 1, 2, 2 | 1,031 |
   | UFM | 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 9, 9 | 1, 2, 2, 1, 2, 1, 2, 2, 2, 1, 1, 2 | 725 |

   - INV adopted two concepts:
     - `tail^4` in generation 6, via index-k (k=5);
     - `add 2 . add 2` in generation 12, via `cons (add2twice 1)` for
       prepend-k (k=5).
   - UFM's ninth solve was modulo-k (k=2); INV did not reach it.
   - UFM's first eight generations matched the earlier seed-44 runs exactly,
     which is a regression check that the wiring does not change the
     comparator.

The move from 8 to 12 generations was made because run 2 showed that each
invention step needs about two generations of the uniform budget (about 80
candidates per unsolved task per generation). Eight generations leave room
for one step.

## Numeric predictions (mean over three seeds)

| Arm | TRAIN g8 | TRAIN g12 | Plausible range g12 | VALIDATION g12 |
| --- | --- | --- | --- | --- |
| RSI3_UNIFORM_FM | 8 (identical to committed) | 9 | 8–10 | 1–2 |
| RSI3_UNIFORM_FM_INV | 8 | 10 | 9–11 | 1–2 |

## Decisive comparisons (every seed must satisfy the inequality)

| ID | Comparison | Predicted |
| --- | --- | --- |
| I1 | INV TRAIN g12 > UFM TRAIN g12 | PASS |
| I2 | INV VALIDATION g12 > UFM VALIDATION g12 | FAIL |

## Mechanism readouts

| ID | Readout | Predicted |
| --- | --- | --- |
| P0 | UFM TRAIN and VALIDATION in generations 1–8 identical to the committed `results_failure_memory/` RSI3_UNIFORM_FM runs | identical on all three seeds |
| J1 | INV runs with at least one adopted concept | 3 of 3 |
| J2 | Concepts adopted per INV run | 1–3 (point 2: `tail^4`, `add 2 . add 2`) |
| J3 | First adoption generation, INV | ≤ 7 on every seed |
| J4 | INV runs that solve a TRAIN task never solved in any committed RSI-3 run (index-k k=5 or prepend-k k=5) | 3 of 3 |
| J5 | INV runs in which an adopted concept is built from an earlier adopted concept | 0 of 3 |
| J6 | RSI-2 MDL library adoptions, both arms | 0 everywhere |
| J7 | CPU per run, INV relative to UFM | ≥ 1.2× |

## What the outcomes mean

- **I1 passes and I2 fails, as predicted.** A language that grows from
  verified experience reaches tasks the fixed language does not, at equal
  logical budget. That is new for RSI-3: the solved set gains members that
  no allocation, resumption or memory arm reached. But the gain does not
  transfer to VALIDATION at this scale, so it is not yet a qualitative leap
  in held-out capability. J5 = 0 would add that the invention has not yet
  compounded on itself within 12 generations.
- **I2 passes.** That would be the first VALIDATION change in any RSI-3 or
  RSI-2 study.
- **I1 fails.** If adoptions still occur (J1), the gain is real but does not
  outrun the cost: the wider grammar delays the deep prior searches (as for
  index-k k=3 on seed 44) by as much as the concepts gain. If no adoption
  occurs, the invented concepts did not fit these tasks.

The self-model is a functional model of the system's own programs and
behaviour, used to change its own language. It is not consciousness or
subjective experience, and the study makes no claim about either.
