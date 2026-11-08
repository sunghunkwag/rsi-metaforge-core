# Initial MetaForge commit audit: proposal-weight gate disconnect (2026-11-08)

## Immutable source and scope
- Root commit: [3cfc329eca17a08e1a1565064b61a5bd4a1dd520](https://github.com/sunghunkwag/rsi-metaforge-core/commit/3cfc329eca17a08e1a1565064b61a5bd4a1dd520) (2026-06-13).
- Root files: README.md, .gitignore, rsi_levels_metaforge_unified.py.
- Python original: 33,879 lines, 447 top-level functions parsed by AST, zero duplicate *top-level* symbols in executable AST. Naive textual matches against embedded source strings are misleading.
- This iteration is a **targeted historical audit**, not a full line-by-line validation of every embedded subsystem.
- The experimental loader executes complete historical kernel definitions through line 2288 and uses historical stack-VM and searcher functions. Full-file CLI \`--help\` was also checked successfully. It does not run any sealed TEST/J evaluation.

## Reproducible protocol
Run:
\`\`\`bash
python research/root_weight_gate_audit_20261108.py \
  --repo . --seeds 32 --iterations 120 \
  --out historical_weight_gate_results.json
\`\`\`
The repository must contain the full Git history because the experiment uses \`git show\` at the immutable root SHA. The workflow uses Python 3.11 and \`actions/checkout@v4\` with \`fetch-depth: 0\`.

Paired search: synthetic \`len(xs)\` on the original public training inputs. Arms:
1. Implicit unit-weight baseline.
2. Explicit uniform null weights; required to reproduce baseline byte-for-byte.
3. Opt-in length-targeted weights: token 4 (INPUT) and 16 (LEN) have weight 6.0; all others 0.25.

Each seed/arm uses one exploit restart and 120 mutation iterations, **not necessarily equal executed candidate evaluations or CPU**. Out-of-distribution checking uses 25 separately constructed inputs at lengths 5, 8, 13, 21 and 34, with values beyond the training range.

## CI results
- [First successful pilot run](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42466176530).
- [Extended audit and equal-proposal-count run](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42466567813).
- Paired 32-seed full stochastic attempt: baseline 0/32 TRAIN and 0/32 shift; uniform null 0/32 and 0/32; targeted weights 3/32 and 3/32.
- Mean *executed candidate score evaluations* per arm/seed: baseline 1.000, uniform null 1.000, targeted 1.15625. The fixed mutation-iteration allowance **is not** an identical executed-evaluation budget.
- Strict 256-seed, one-proposal-per-seed **initialization ablation** (four public synthetic tasks per arm; 1,024 scored program/task pairs per arm): LENGTH baseline 0/256, uniform null 0/256, targeted 2/256; SUM, HEAD and MAX all 0/256 in all three arms. Both targeted LENGTH solutions passed all 25 separate shift examples.
- This second comparison matches the *number of scored program proposals*, **not CPU**, and is not an equal-CPU full-search benchmark. The tiny effect sizes and task-targeted weights do not support a general learning or transfer claim.

## Root cause isolated
1. Original \`_sample_token\` consumes \`SearcherState.weight(t)\` to bias stochastic proposals.
2. Original \`build_enum_table\` does **not** consume \`SearcherState.weights\`; its program list comes from a deterministic vocabulary and fixed class caps.
3. Original \`meta_gate\` accepts only when an enumerable candidate program yields a new verified solved task. When \`new_macros=[]\`, a weight-only proposal changes neither enumeration vocabulary nor its frontier, so it cannot pass on the strength of its stochastic-search benefit.
4. Actual historical \`meta_gate\` on a bounded synthetic task rejected the weight-only proposal: two rejection records, 0 gained tasks, 0 screen extensions and 204 full-table extensions, incumbent digest unchanged.
5. The root documentation's "same budget and seeds" description is not an adequate resource-parity proof for this gate. In the bounded case, recorded incumbent extensions were 0 and candidate extensions 204, and the gate never compared stochastic-search outcomes.

## Interpretation
The *capacity to alter proposal weights* existed in the original searcher, but the original **acceptance pathway did not measure their direct effect** for a weight-only proposal. This is a specific, experimentally reproducible historical capability/gate mismatch, **not** evidence of general recursive self-improvement.

The 256-seed probe shows that extreme task-specific initialization can occasionally solve a targeted trivial program, while SUM/HEAD/MAX show no improvement in this sample. No claim about transfer or forgetting can be supported by these four toy tasks.

## Next falsifiable experiment (separate opt-in branch)
Introduce a candidate *weight-only* A/B gate on newly generated **development** tasks using exactly equal counts of executed candidate evaluations, paired seeds, and a separate CPU budget report. Keep the incumbent, candidate and explicit uniform null arms. Reject a proposal if the mean improvement does not replicate on an independent distribution shift or if previously solved task regressions exceed a preregistered bound. Never use sealed TEST/J, archived experiments or RSI-4 Phase 1 as tuning feedback. Compare type-directed sampling against the existing validity filter as a separate ablation.

### Stop conditions
Treat 0/0 parity, failed independent replication, increased forgetting, or unfair evaluation budgets as a negative result. Do not merge a real gate change on the strength of this audit alone.
