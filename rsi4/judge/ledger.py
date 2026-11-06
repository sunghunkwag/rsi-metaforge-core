"""J's hash-chained decision log (``judge_log.jsonl``), the ledger pattern of Phase K and swarm.

Each line is one JSON object:

    {"index": n, "prev": <hash of line n-1 or 64 zeros>, "entry": {...}, "hash": h}

with h = sha256(prev + canonical(entry)). Changing, removing or reordering
any line breaks every later hash, so ``verify`` finds it. Lines are only ever
appended. Nothing here carries wall-clock time: J's cost records go to a
separate ``judge_costs.jsonl`` beside the ledger, so a ledger replays exactly.

Two ledgers are in use:

- a run's own ledger (in the run's output directory) for ``run_start``,
  ``evaluate``, ``sleep_check`` and ``run_end``;
- the canonical ledger ``rsi4/ledger/judge_log.jsonl`` for every operation
  that consumes a single-use pool (``select``, ``confirm``, ``final_test``)
  and for ``compare`` and ``metrics``. A request cannot redirect these; a
  burned pool stays burned for as long as this file's history exists.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .registry import PACKAGE_DIR, canonical

GENESIS = "0" * 64
CANONICAL_LEDGER = PACKAGE_DIR / "ledger" / "judge_log.jsonl"


class LedgerError(RuntimeError):
    """The ledger's chain is broken."""


def _hash(prev: str, entry: dict) -> str:
    return hashlib.sha256(prev.encode("ascii") + canonical(entry)).hexdigest()


def read(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def verify(path: Path) -> list[dict]:
    """Every line, after checking the whole chain; raises LedgerError on any break."""
    lines = read(path)
    prev = GENESIS
    for index, line in enumerate(lines):
        if line.get("index") != index or line.get("prev") != prev:
            raise LedgerError(f"{path}: line {index} is out of order")
        if _hash(prev, line["entry"]) != line.get("hash"):
            raise LedgerError(f"{path}: line {index} was altered")
        prev = line["hash"]
    return lines


def append(path: Path, entry: dict) -> dict:
    path = Path(path)
    lines = verify(path)
    prev = lines[-1]["hash"] if lines else GENESIS
    line = {"index": len(lines), "prev": prev, "entry": entry, "hash": _hash(prev, entry)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(line).decode("ascii") + "\n")
    return line


def entries(path: Path, op: str | None = None) -> list[dict]:
    return [line["entry"] for line in verify(path) if op is None or line["entry"].get("op") == op]


def entry_at(path: Path, index: int) -> dict:
    lines = verify(path)
    if not 0 <= index < len(lines):
        raise LedgerError(f"{path}: no line {index}")
    return lines[index]["entry"]


def cost(path: Path, record: dict) -> None:
    """J's own evaluation cost, logged apart from the ledger and from every budget."""
    costs = Path(path).with_name("judge_costs.jsonl")
    costs.parent.mkdir(parents=True, exist_ok=True)
    with costs.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
