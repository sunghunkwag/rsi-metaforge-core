# Completed coordinate diagnostic: independent TRAIN replay

The registered diagnostic completed all six conditions within its 600 aggregate
CPU-second ceiling. The proposed coordinate kernel fails its admission gate:
it ties population at B64 and loses one verified task at B640. This is a
completed negative engineering result, not a recursive improvement.

## Eleven-field cycle record

1. **Current performance.** Each B64 condition solves the same 5/36 TRAIN tasks.
   Cold population at B640 solves 6/36; cold coordinates solves 5/36. All selected
   programs were independently replayed against public and hidden TRAIN examples.

   | Condition | Verified tasks | Complete candidates | Descendant edges | Kernel CPU seconds |
   | --- | ---: | ---: | ---: | ---: |
   | Cold population B64 | 5/36 | 2,016 | 1,488 | 90.09 |
   | Cold coordinates B64 | 5/36 | 2,016 | 1,488 | 38.29 |
   | Bank population B64 | 5/36 | 1,990 | 1,488 | 96.38 |
   | Bank coordinates B64 | 5/36 | 1,990 | 1,488 | 28.62 |
   | Cold population B640 | 6/36 | 4,638 | 4,110 | 160.66 |
   | Cold coordinates B640 | 5/36 | 3,417 | 2,889 | 54.53 |

2. **Main failure clusters.** Each B64 arm exhausts the candidate budget on 31
   unsolved tasks. At B640, population reaches the normalization/compiler cap
   on 30 tasks and coordinates on 31. No recorded public or heuristic trial is
   interrupted. The extra population solution is
   `caesar-cipher-k-modulo-n with k=1 and n=2`; coordinates loses this task in
   the matched B640 comparison. There are no B64 solved-set gains or losses.

3. **Bottleneck abstraction.** More candidate allowance alone does not expand
   this coordinate search: its shared compiler cap binds before B640 is spent.
   The measured limits leave 3,417 coordinate candidates versus 4,638 population
   candidates across all tasks. These counts diagnose coverage and resource
   limits; they do not establish which untried program would solve an unsolved
   task. Structural and compiler units differ between methods.

4. **Why prior attempts were insufficient.** The prior recursive pilot completed
   only generation 0, and generation 1 wake retained the same five TRAIN tasks.
   The present generic coordinate edits do not add a verified task at B64,
   with either cold roots or the same reverified prior bank. Neither bank reuse
   nor faster coordinate execution establishes a capability increase.

5. **Intervention.** The frozen revision uses typed head substitutions, compatible
   argument permutations, unary insertion/removal and generic eta exposure.
   Both kernels receive the same fresh frozen grammar, zero scorer, seed 11,
   root policy, task order, complete-candidate budgets and common limits.

6. **Expected mechanism.** Preserving existing arguments while changing local
   derivation choices was expected to reach useful nearby programs that whole
   subtree replacement misses. The observed solved sets do not support that
   expectation at the registered limits.

7. **Verification plan and completed checks.** The separate replay reconstructed
   all six journal records with zero ignored bytes and no interrupted journal.
   It replayed 16,067 complete candidate records and reconstructed 12,951 parent
   edges, including every coordinate edge's operator provenance. It checked
   term types, size and normalization, public outputs and evaluator steps,
   incumbent zero-scorer outputs/cache accounting, independently reverified the
   source bank and selected public/hidden TRAIN programs, and reconciled every
   integer search/proof work counter with the recorded totals. All checks pass.
   The portable entry point also checks the registered configuration, phase
   order, B640 selection rule, unopened evaluation flags and CPU ceiling.

8. **Regression risks and scope.** Equal candidate ceilings are not equal physical
   work. Compiler caps are active at B640. Finite public/hidden TRAIN examples
   do not establish semantic equivalence on all inputs. This is seed 11 only;
   seeds 22/33, final generalization and a complete common-kernel recursive
   campaign remain unrun. Independent replay validates the recorded execution;
   it does not turn a human-designed operator into a learned improvement.

9. **Result after testing.** Strict solved-set expansion without a lost task is
   **FAIL** for both B64 comparisons and the cold B640 comparison. Aggregate
   diagnostic CPU was **487.17 seconds**, including workers, persistence and
   parent reconstruction; recorded wall time was **489.00 seconds**. The first
   independent replay took **17.15 CPU seconds**, separately charged as audit
   work. No VALID, TEST or external audit partition was opened. Original RSI
   criteria (a)–(e) are not reassessed by this TRAIN diagnostic; the original
   study remains a measured null. This diagnostic contains no generations and
   cannot establish an eight-generation curve or a new flattening generation.

10. **Keep/revert/revise decision.** Preserve all frozen source, journals, negative
    outcomes and independent evidence. Reject admission of the coordinate kernel
    as a capability improvement. Further generative-priority or arity revisions
    require separate registration and controls; their results must not be
    attributed to the frozen diagnostic.

11. **Updated reusable rule.** A candidate generator earns capability credit only
    through a complete, independently verified solved-set expansion at the
    registered limits without losing prior tasks. Report active resource caps
    alongside candidate ceilings. Learned priority changes and structural
    operator extensions need separate factors before assigning causal credit.

## Evidence and reproduction

The authoritative historical results are
`coordinate_diagnostic_results/summary.json` and its six journal/checkpoint
pairs. New independent evidence is in
`coordinate_diagnostic_results/independent/`, including a summary, one replay
record per condition, and a portable auditor. From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m \
  rsi2.research.coordinate_diagnostic_results.independent.replay \
  --output /tmp/coordinate-independent-new
```

Use a new output directory. This replays existing candidates and TRAIN examples;
it does not run search or open evaluation partitions. The auditor's `PASS`
means the evidence reconciles, while the candidate-kernel admission remains
`FAIL`.
