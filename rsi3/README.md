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

VALIDATION was unchanged on the registered comparisons of every study. TEST was not opened.

- [`OWNER_DIRECTIVE.md`](OWNER_DIRECTIVE.md) — scope and constraints
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — component map and the evidence behind each design decision
- [`PREDICTIONS.md`](PREDICTIONS.md), [`PREDICTIONS_FAILURE_MEMORY.md`](PREDICTIONS_FAILURE_MEMORY.md), [`PREDICTIONS_SELF_CONTINUITY.md`](PREDICTIONS_SELF_CONTINUITY.md) (abandoned), [`PREDICTIONS_INVENTION.md`](PREDICTIONS_INVENTION.md) — registered before each study's final runs
- [`RESULTS.md`](RESULTS.md), [`FAILURE_MEMORY_RESULTS.md`](FAILURE_MEMORY_RESULTS.md), [`INVENTION_RESULTS.md`](INVENTION_RESULTS.md) — measured outcomes, predictions scored
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
python -m rsi3.report --results NEW_EMPTY_DIR --output report.md
```

A learned-arm failure-memory run peaks at about 4.5 GB of memory; on a machine
with less than about 10 GB, run those seeds one at a time (`--workers 1`).

The runner refuses to overwrite a non-empty output directory. TEST is never
opened; VALIDATION is measured for reporting only.
