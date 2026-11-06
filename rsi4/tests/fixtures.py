"""Shared test fixtures: a tiny trained checkpoint and a copy of J's tree."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "rsi3" / "experiment_config_honest.json"
_cache: dict = {}


def scratch() -> Path:
    if "dir" not in _cache:
        _cache["dir"] = Path(tempfile.mkdtemp(prefix="rsi4-tests-"))
        atexit.register(shutil.rmtree, _cache["dir"], True)
    return _cache["dir"]


def tiny_checkpoint() -> Path:
    """RSI3_META_HONEST, one generation on six TRAIN tasks, 16 self-play tasks (about 5 s).

    A test object only: its config differs from the registered one in
    ``generations`` and ``meta.selfplay``.
    """
    if "checkpoint" not in _cache:
        from rsi2.corpus import load_train
        from rsi3 import longrun
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        config["generations"] = 1
        config["meta"] = dict(config["meta"], selfplay=16)
        out = scratch() / "tiny"
        longrun.run("RSI3_META_HONEST", config, out, train=load_train()[:6],
                    skip_validation=True)
        _cache["checkpoint"] = out / "RSI3_META_HONEST.checkpoint.pkl"
    return _cache["checkpoint"]


def judge_copy(planted: dict | None = None) -> Path:
    """A copy of rsi4/judge (and the stage-train file) under a fresh rsi4/ directory.

    ``planted`` maps a path relative to the copy's rsi4/ to file text (agent
    modules for the audit tests). Returns the copy's judge directory.
    """
    root = Path(tempfile.mkdtemp(prefix="rsi4-judge-copy-", dir=scratch())) / "rsi4"
    shutil.copytree(REPO / "rsi4" / "judge", root / "judge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "data").mkdir(parents=True)
    shutil.copyfile(REPO / "rsi4" / "data" / "stage_train.json", root / "data" / "stage_train.json")
    for rel, text in (planted or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root / "judge"
