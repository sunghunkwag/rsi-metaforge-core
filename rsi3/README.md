# RSI-3

A memory-feedback adaptive core on top of RSI-2's frozen program synthesizer.
It replaces only RSI-2's wake-phase compute allocation with a closed loop —
episodic memory, a replay-trained value model, a budget controller, pathways
created dormant from verified solutions, resumable searches, a binding
integrator, and a frozen external verifier — and measures, against
pre-registered predictions, whether that changes hidden-example verified
capability at equal logical budgets.

- [`OWNER_DIRECTIVE.md`](OWNER_DIRECTIVE.md) — scope and constraints
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — component map and the evidence behind each design decision
- [`PREDICTIONS.md`](PREDICTIONS.md) — registered before the final runs
- [`RESULTS.md`](RESULTS.md) — measured outcome, predictions scored
- [`studies/REGULATION_TOY_RESULTS.md`](studies/REGULATION_TOY_RESULTS.md) — the study behind design decision D1

Nothing in `rsi2/`, `docs/`, or `rsi_levels_metaforge_unified.py` is modified.
Python 3.11+ and NumPy; no model, no network.

```sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

# unit tests (about a minute)
python -m unittest discover -s rsi3/tests -t .

# the regulation study (about 4 minutes)
python -m rsi3.studies.regulation_toy

# the registered experiment: 5 arms x 3 seeds x 8 generations
python -m rsi3.experiment --config rsi3/experiment_config.json --output NEW_EMPTY_DIR
python -m rsi3.report --results NEW_EMPTY_DIR --output report.md
```

The runner refuses to overwrite a non-empty output directory. TEST is never
opened; VALIDATION is measured for reporting only.
