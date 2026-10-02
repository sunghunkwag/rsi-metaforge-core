# RSI-2

Independent offline synthesizer. It does not import the legacy runtime or alter
its instruments. Python 3.11 or newer and NumPy are the only dependencies.

From the repository root:

```sh
UV_CACHE_DIR=/workspace/.cache/uv uv venv /workspace/.venvs/rsi2
UV_CACHE_DIR=/workspace/.cache/uv uv pip install --system-certs \
  --python /workspace/.venvs/rsi2/bin/python -r rsi2/requirements.txt
source /workspace/.venvs/rsi2/bin/activate
python -m unittest discover -s rsi2/tests -v
```

No running service or model connection is required. Existing cloud checkouts are
already isolated; do not create another worktree unless explicitly requested.

Implementation follows the Owner's Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5
order. A stage acceptance failure permits one documented correction, then stops
the experiment if the gate still fails. Scientific results are reported only
from completed, preregistered runs.
