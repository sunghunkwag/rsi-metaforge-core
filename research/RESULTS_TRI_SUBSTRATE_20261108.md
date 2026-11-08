# Multi-strategy conservative search across three distinct substrates

Date: 2026-11-08. Baseline main SHA: `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`.

## Frozen design and run
- Exact runnable source: [research/tri_substrate_portfolio_20261108.py](tri_substrate_portfolio_20261108.py)
- Verified initial CI: https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42469630944
- List, string and directed-graph DSLs, each with 6 development target programs and 6 distinct independent-audit target programs.
- 24 paired seeds per target, 48 candidate evaluation slots per task/seed/arm, 12 public training examples and 24 independently seeded distribution-shift examples.
- Six policies: untyped legacy; typed-uniform; incumbent-preserving typed-uniform replacement; behavior-archive novelty; failure-memory-biased replacement; novelty+failure-memory hybrid.
- The replacement arms preserve **every distinct syntactically type-valid incumbent program**. They replace only invalid/duplicate legacy slots; they also give the first incumbent train-exact program priority in the selected output. That preserves incumbent correctness on deterministic training and shift evaluations for any task that the incumbent already solves.
- Development selection required strictly positive OOD gain on **each** of the three domains, no individual task loss **relative to the legacy incumbent**, higher aggregate OOD than typed-uniform, same charged candidate/probe slots, and no excessive CPU time. The audit stage is executed after development selection is frozen.
- No production runtime changes; no sealed TEST/J, RSI-4 Phase 1, or previous audit tasks used.

## Results: development shift pass counts, 432 paired task/seed cases
| Arm | Independent shift passes |
|---|---:|
| Legacy | 122 |
| Typed-uniform | 265 |
| Conservative uniform | **297** |
| Conservative novelty | 227 |
| Conservative failure memory | 284 |
| Conservative hybrid | 249 |

The selected development candidate was **conservative_failure**. Conservatively filtered negative results were computed only from earlier public input evaluations within the same run. No hidden oracle or independent audit results were consulted by the search policy.

## Independent audit, 432 NEW task/seed cases
| Arm | TRAIN exact | Independent shift |
|---|---:|---:|
| Legacy | 82 | 80 |
| Typed-uniform | 220 | 212 |
| Conservative uniform | 251 | 242 |
| Conservative novelty | 208 | 204 |
| Conservative failure memory | **272** | **266** |
| Conservative hybrid | 244 | 239 |

Independent audit shifts by substrate for selected candidate vs typed-uniform:
- Integer lists: 60/144 versus 39/144.
- Strings: 126/144 versus 104/144.
- Directed graphs: 80/144 versus 69/144.

**Critical counterexample:** a directed-graph individual audit task regressed from 7/24 typed-uniform OOD successes to 5/24 under selected failure memory. Consequently, this is **NOT taskwise Pareto dominance over typed-uniform**.

The stricter gate was passed **relative to the legacy incumbent on every audited task** and in aggregate against typed-uniform, but not relative to typed-uniform on every task. The preregistered finite benchmark criterion was met; universal generalization was **not** established.

## Resource accounting and limitations
All six arms used 20,736 charged proposal-evaluation slots and 248,832 charged training-input probe slots per stage. However, invalid legacy candidates do not execute the VM at all:
- Legacy actual train VM calls: **70,788** in each stage.
- All typed arms' actual train VM calls: **248,832** per stage.
- Independent-audit CPU totals: legacy 0.614472 s, typed-uniform 1.401082 s, selected failure memory 1.948680 s.

Thus **equal charged logical evaluation opportunities do NOT imply equal interpreter calls or CPU cost**. The strongest comparison for matching actual VM calls is typed-uniform versus the selected typed failure-memory portfolio, not untyped legacy versus the portfolio. Even that matching does not equalize proposal-generation overhead or wall time. The exploratory criterion must not be advertised as CPU-matched general RSI.

This benchmark uses three data substrates but a shared finite typed DSL abstraction and one-generation program search. It measures neither recursively improved learning rules nor continual-learning forgetting across generations. No general AGI/RSI breakthrough or production recommendation follows.

## Next clean iteration
Run a separate typed-incumbent-preserving experiment, replacing only **duplicate typed candidates**, with exactly the same number of valid VM program evaluations as typed-uniform. Freeze a new set of benchmark tasks before inspecting independent results and require no per-task audit regression relative to typed-uniform. Measure the marginal benefit, if any, under fair interpreter-query cost and report the failure even if no candidate passes. All tasks from this run's audit are now spent and must never be used as tuning inputs.
