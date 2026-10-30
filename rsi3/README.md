# RSI-3

A memory-feedback adaptive core on top of RSI-2's frozen program synthesizer,
with a self-model that grows the system's own library from its verified
programs.
It replaces only RSI-2's wake-phase compute allocation with a closed loop —
episodic memory, a replay-trained value model, a budget controller, pathways
created dormant from verified solutions, resumable searches, a binding
integrator, and a frozen external verifier — and measures, against
pre-registered predictions, whether that changes hidden-example verified
capability at equal logical budgets.

**Measured outcomes.**

| Study | Result |
| --- | --- |
| First study ([RESULTS.md](RESULTS.md)) | The learned controller matched RSI-2 at 6/36 TRAIN on every seed; all five registered comparisons failed. The only gain, 7/36 on every seed, came from resumption with an even budget split. |
| Failure memory ([FAILURE_MEMORY_RESULTS.md](FAILURE_MEMORY_RESULTS.md)) | Keeping each task's public failures across grammar changes and pathways: 8/36 on every seed with the even split; the learned controller rose to 7/8/7, and a pathway created from the system's own solution produced a verified solve on every seed. All 12 registered predictions hit. |
| Self-continuity ([PREDICTIONS_SELF_CONTINUITY.md](PREDICTIONS_SELF_CONTINUITY.md)) | Abandoned by the owner before any registered run finished: a guard that only prevents losses cannot produce a leap. No registered result exists. |
| Concept invention ([INVENTION_RESULTS.md](INVENTION_RESULTS.md)) | A self-model of the system's own verified programs invents library concepts; the verifier gates adoption. The first library growth in any RSI-3 run: `tail^4` and `add 2 . add 2` adopted on every seed, solving index-k (k=5) and prepend-k (k=5), never reached before; **10/36 vs 9/36** at 12 generations and equal logical budget. Registered VALIDATION comparison fails; on one seed a never-before-solved VALIDATION task (`add-k k=5`) appeared in the generation `add 2 . add 2` was adopted. All 16 registered predictions hit. |

| Long horizon ([PREDICTIONS_LONG.md](PREDICTIONS_LONG.md)) | Suspended at generation 18–19 and unscored: the invention arms stayed at 10/36 from generation 10–12, a plateau. |
| **Meta-RL, decomposition and transfer** ([METARL_RESULTS.md](METARL_RESULTS.md)) | Backward decomposition (from `verified-code-rsi`) plus a meta-RL policy over prior / invented / skeleton chunks. The policy is fitted across tasks on persistent replay, with a wiped-memory control (from `gated-self-improvement` v3). Results: **17/36 TRAIN** (the previous best was 9). The TRAIN-trained solver on VALIDATION at the same budget solved **4/12 on every seed**: fixed language 1, skeletons with a fixed split 3, wiped memory 3. Two of the four tasks had never been solved by any run, and all three non-trivial solves use concepts the system invented. Plain VALIDATION did not move. All 12 registered predictions hit. |

| **Cascade** ([CASCADE_RESULTS.md](CASCADE_RESULTS.md)) | Fold skeletons, self-play meta-RL (the policy trains on tasks it imagines through its own skeletons) and conjugation (an unsolved task is transformed by one of the system's own verified involutions). The first cascade: reverse (g13) → append-k ×2 by conjugation (g14) → append-index-k (g16), while RSI-2's MDL learner compresses the shared structure into a library (first `lambda acc x. cons x acc`, then reverse built on it). **21/36 TRAIN**; held-out 5/12 on every seed (+1, `sum`, from the fold skeleton; the cascade itself transfers nothing). All 12 registered predictions hit. |

| **Behavioural search** ([BEHAVE_RESULTS.md](BEHAVE_RESULTS.md)) | Bottom-up search that keeps one program per behaviour on the public inputs (observational equivalence), with deduction through `cons`, `not` and witness functions that compute a binary operation's constant argument. One meta-RL action per problem. Built from the system's own library: **25/36 TRAIN** (all six slices, `keep-mod-k`, `is-mod-k`), but the reverse cascade is lost and held-out drops to **4/12**. The same search from RSI-2's primitives only: 21/36 TRAIN and **7/12 held-out on every seed**, the best held-out score so far, with two caesar tasks no run had solved. The library helps where budget accumulates (TRAIN) and hurts at 64 candidates per held-out task. 4 of 8 predictions hit; every open forecast about the library arm's held-out score missed. |

| **Behavioural fold** ([BEHAVE_FOLD_RESULTS.md](BEHAVE_FOLD_RESULTS.md)) | One more designer-given action: closed fold steps built bottom up by behaviour and folded over pool lists. Reverse returns (g12), and the system's own conjugation rebuilds the append cascade on it (g13, g15) while RSI-2's MDL learner compresses it: **29/36 TRAIN**, the most so far, and held-out 5/12 on every seed. 3 of 6 predictions hit (the three determined ones); every open held-out forecast missed. |

| **Honest self-play** ([HONEST_RESULTS.md](HONEST_RESULTS.md)) | One change to how the meta-policy is trained: on the tasks the system imagines, every action is credited by its actual one-chunk outcome, none by construction. TRAIN stays **29/36**, and the learned solver reaches **9/12 held-out on every seed** (from 5), including a caesar task no run had solved: both stated targets in one arm. Caveat: this change was designed after earlier arms' per-task VALIDATION outcomes were read, so VALIDATION was no longer unseen. 5 of 6 predictions hit; the point forecast (6) was too low. |

| **Portfolio** ([PORTFOLIO_RESULTS.md](PORTFOLIO_RESULTS.md)) | Every behavioural problem offered twice, built from the library and from RSI-2's primitives only, for the honestly trained policy to choose per shape. TRAIN **29/36**, held-out **8/12** on every seed: above the designer-only control's 7, one below honest self-play. The policy preferred the cheap library-free pools, which cannot build the self-learned constant 5 that one held-out caesar task needs. 7 of 8 predictions hit. |

Plain VALIDATION (RSI-2's `assess`) did not improve on the registered comparison of any study. Held-out gains appear only when the learned solver is used at test time (`validation_agent`). TEST was not opened.

- [`OWNER_DIRECTIVE.md`](OWNER_DIRECTIVE.md) — scope and constraints
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — component map and the evidence behind each design decision
- [`PREDICTIONS.md`](PREDICTIONS.md), [`PREDICTIONS_FAILURE_MEMORY.md`](PREDICTIONS_FAILURE_MEMORY.md), [`PREDICTIONS_SELF_CONTINUITY.md`](PREDICTIONS_SELF_CONTINUITY.md) (abandoned), [`PREDICTIONS_INVENTION.md`](PREDICTIONS_INVENTION.md), [`PREDICTIONS_LONG.md`](PREDICTIONS_LONG.md) (suspended), [`PREDICTIONS_METARL.md`](PREDICTIONS_METARL.md), [`PREDICTIONS_CASCADE.md`](PREDICTIONS_CASCADE.md), [`PREDICTIONS_BEHAVE.md`](PREDICTIONS_BEHAVE.md), [`PREDICTIONS_BEHAVE_FOLD.md`](PREDICTIONS_BEHAVE_FOLD.md), [`PREDICTIONS_HONEST.md`](PREDICTIONS_HONEST.md), [`PREDICTIONS_PORTFOLIO.md`](PREDICTIONS_PORTFOLIO.md) — registered before each study's final runs
- [`RESULTS.md`](RESULTS.md), [`FAILURE_MEMORY_RESULTS.md`](FAILURE_MEMORY_RESULTS.md), [`INVENTION_RESULTS.md`](INVENTION_RESULTS.md), [`METARL_RESULTS.md`](METARL_RESULTS.md), [`CASCADE_RESULTS.md`](CASCADE_RESULTS.md), [`BEHAVE_RESULTS.md`](BEHAVE_RESULTS.md), [`BEHAVE_FOLD_RESULTS.md`](BEHAVE_FOLD_RESULTS.md), [`HONEST_RESULTS.md`](HONEST_RESULTS.md), [`PORTFOLIO_RESULTS.md`](PORTFOLIO_RESULTS.md) — measured outcomes, predictions scored
- [`studies/REGULATION_TOY_RESULTS.md`](studies/REGULATION_TOY_RESULTS.md) — the study behind design decision D1

Nothing in `rsi2/`, `docs/`, or `rsi_levels_metaforge_unified.py` is modified.
Python 3.11+ and NumPy; no model, no network.

```sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

# unit tests (about a minute)
python -m unittest discover -s rsi3/tests -t .

# the regulation study (about 4 minutes)
python -m rsi3.studies.regulation_toy

# the registered experiments: 5 arms, then 2 failure-memory arms (3 seeds x 8 generations),
# then the concept-invention pair (3 seeds x 12 generations, about 50 minutes on 2 workers)
python -m rsi3.experiment --config rsi3/experiment_config.json --output NEW_EMPTY_DIR
python -m rsi3.experiment --config rsi3/experiment_config_failure_memory.json --output NEW_EMPTY_DIR2
python -m rsi3.experiment --config rsi3/experiment_config_invention.json --output NEW_EMPTY_DIR3

# the meta-RL study (one shared TRAIN trajectory per arm, per-seed VALIDATION,
# checkpointed; rerun the same command to resume a stopped job)
for arm in RSI3_UNIFORM_FM_DEC RSI3_META RSI3_META_WIPE; do
  python -m rsi3.longrun --config rsi3/experiment_config_metarl.json --arm $arm --output NEW_DIR4
done
# the cascade study (16 generations)
for arm in RSI3_META RSI3_META_FOLD RSI3_META_PLAY RSI3_META_CONJ; do
  python -m rsi3.longrun --config rsi3/experiment_config_cascade.json --arm $arm --output NEW_DIR5
done
# the behavioural-search study (16 generations; comparator: the cascade study's CONJ runs)
for arm in RSI3_META_BEH RSI3_META_BEH_BASE; do
  python -m rsi3.longrun --config rsi3/experiment_config_behave.json --arm $arm --output NEW_DIR6
done
# the behavioural fold follow-up (16 generations)
python -m rsi3.longrun --config rsi3/experiment_config_behave_fold.json --arm RSI3_META_BEH_FOLD --output NEW_DIR7
# honest self-play (16 generations)
python -m rsi3.longrun --config rsi3/experiment_config_honest.json --arm RSI3_META_HONEST --output NEW_DIR8
# portfolio (16 generations)
python -m rsi3.longrun --config rsi3/experiment_config_portfolio.json --arm RSI3_META_PORTFOLIO --output NEW_DIR9
python -m rsi3.report --results NEW_EMPTY_DIR --output report.md
```

A learned-arm failure-memory run peaks at about 4.5 GB of memory; on a machine
with less than about 10 GB, run those seeds one at a time (`--workers 1`).

The runner refuses to overwrite a non-empty output directory. TEST is never
opened; VALIDATION is measured for reporting only.
