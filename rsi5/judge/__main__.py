"""Entry point of J's process: ``python -m rsi4.judge --request R.json --response S.json``."""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi4.judge.service import main  # noqa: E402

main()
