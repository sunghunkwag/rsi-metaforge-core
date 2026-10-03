# RSI-2

Independent offline synthesizer. It does not import the legacy runtime or alter
its instruments. Python 3.11 or newer and NumPy are the only dependencies.

From the repository root:

```sh
UV_CACHE_DIR=/workspace/.cache/uv uv venv /workspace/.venvs/rsi2
UV_CACHE_DIR=/workspace/.cache/uv uv pip install --system-certs \
  --python /workspace/.venvs/rsi2/bin/python -r rsi2/requirements.txt
source /workspace/.venvs/rsi2/bin/activate
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m unittest discover -s rsi2/tests -v
```

No running service or model connection is required. Existing cloud checkouts are
already isolated; do not create another worktree unless explicitly requested.

Implementation follows the Owner's Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5
order. A stage acceptance failure permits one documented correction, then stops
the experiment if the gate still fails. Scientific results are reported only
from completed, preregistered runs.

The committed external corpus and calibrated budgets require no download at
runtime. A development smoke run uses only TRAIN and VALIDATION:

```sh
python -m rsi2.learning --seed 11 --output /workspace/scratch/rsi2/smoke.json
```

The final experiment uses the unchanged preregistered configuration. Choose a
new, empty output directory for an independent reproduction; the runner refuses
to overwrite results. It checkpoints each arm and seed after every generation,
uses at most five processes, and stops at the aggregate CPU limit.

```sh
python -m rsi2.experiment --config rsi2/experiment_config.json \
  --workers 5 --output /workspace/scratch/rsi2/reproduction
python -m rsi2.report --results /workspace/scratch/rsi2/reproduction \
  --output /workspace/scratch/rsi2/reproduction-results.md
```

TEST measurements are report outputs; they never select training updates or
heuristic adoption. Do not alter the frozen protocol after viewing them.
See `RESULTS.md` and `results/` for the original final experiment.
