"""Results tables from run directories, and the gate statistics J computes from them.

    python -m rsi4.report --runs rsi4/results_p1 --phase 1

A run directory is one arm's ``rsi4.stages`` output (downloaded from Actions):
``STATUS.json``, ``<ARM>_seed<s>.json`` (TRAIN), ``<ARM>_stream.json``,
``evaluations/<key>.json`` (J's responses) and ``J/judge_log.jsonl`` (the
run's J ledger). This module reads them and renders tables; every count it
shows is J's. The score-matrix metrics and their intervals are computed by J
(``metrics`` request) from the run ledgers, and logged in J's canonical ledger.

The base check (Gate 1) compares the TRAIN phase with the registered rsi3
files byte for byte after removing the timing fields (``cpu_seconds``,
``wall_seconds``), the comparison rsi3's FRESH plan prescribed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .stages import STAGES, strip_timing

REPO = Path(__file__).resolve().parents[1]
REGISTERED_TRAIN = {"RSI3_META_HONEST": REPO / "rsi3" / "results_honest"}
REGISTERED_FRESH1 = {"RSI3_META_HONEST": REPO / "rsi3" / "results_fresh"
                     / "RSI3_META_HONEST_seed11-22-33_fresh1.json"}


def _load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def base_check(run: Path, arm: str) -> dict:
    """TRAIN records and FRESH-1 against the registered rsi3 files (timing removed)."""
    status = _load(run / "STATUS.json")
    seeds = [int(s) for s in status.get("seeds", [11, 22, 33])] if "seeds" in status else [11, 22, 33]
    out = {"train": {}, "fresh1_rsi3": {}, "fresh1_J": {}}
    registered = REGISTERED_TRAIN.get(arm)
    for seed in seeds:
        ours = _load(run / f"{arm}_seed{seed}.json")
        row = {"train_solved_g16": ours["generations"][-1]["train_solved"],
               "trajectory": [g["train_solved"] for g in ours["generations"]]}
        if registered is not None:
            theirs = _load(registered / f"{arm}_seed{seed}.json")
            row["generations_identical"] = (canonical(strip_timing(ours["generations"]))
                                            == canonical(strip_timing(theirs["generations"])))
            row["final_identical"] = (canonical(strip_timing(ours["final"]))
                                      == canonical(strip_timing(theirs["final"])))
            row["config_identical"] = ours["config"] == theirs["config"]
        out["train"][seed] = row
    fresh = run / f"{arm}_seed{'-'.join(map(str, seeds))}_fresh1.json"
    if fresh.exists() and arm in REGISTERED_FRESH1:
        ours, theirs = _load(fresh), _load(REGISTERED_FRESH1[arm])
        for seed in map(str, seeds):
            out["fresh1_rsi3"][seed] = {
                "solved": ours["seeds"][seed]["solved"],
                "identical": canonical(strip_timing(ours["seeds"][seed]))
                == canonical(strip_timing(theirs["seeds"][seed]))}
    j_fresh = run / "evaluations" / "train_fresh1.json"
    if j_fresh.exists():
        result = _load(j_fresh)["result"]
        for seed, r in result["seeds"].items():
            row = {"solved": r["solved"]}
            if arm in REGISTERED_FRESH1:
                theirs = _load(REGISTERED_FRESH1[arm])["seeds"][seed]
                row["solver_record_identical"] = (canonical(strip_timing(r["solver_record"]))
                                                  == canonical(strip_timing(
                                                      {k: theirs[k] for k in theirs
                                                       if k != "cpu_seconds"})))
            out["fresh1_J"][seed] = row
    return out


def score_matrix(run: Path) -> dict:
    """R[i][j] pooled (2 of 3 seeds) and per seed, from J's responses."""
    status = _load(run / "STATUS.json")
    matrix = {}
    for i in range(4):
        for j in range(1, 4):
            entry = status["evaluations"].get(f"R{i}{j}")
            if entry:
                matrix[(i, j)] = {"pooled": entry["solved"], "per_seed": entry["per_seed"],
                                  "ref": [str(run / "J" / "judge_log.jsonl"),
                                          entry["ledger_index"]]}
    return matrix


def plasticity(run: Path, arm: str) -> dict:
    stream = _load(run / f"{arm}_stream.json")
    return stream["stage_train_receipts"]


def cost(run: Path) -> dict:
    status = _load(run / "STATUS.json")
    workers = status.get("workers", [])
    return {"segments": len(status.get("segments", [])),
            "worker_cpu_seconds": round(sum(s.get("cpu_seconds", 0) for s in status["segments"]), 1),
            "peak_rss_mb": round(max([w.get("peak_rss_bytes", 0) for w in workers]
                                     + [s.get("peak_rss_bytes", 0) for s in status["segments"]])
                                 / 2 ** 20),
            "breaches": sum(1 for w in workers if w.get("breach"))}


def reported(run: Path) -> dict:
    status = _load(run / "STATUS.json")
    return {key: {"solved": e["solved"], "per_seed": e["per_seed"], "pool": e["pool"]}
            for key, e in status["evaluations"].items()
            if key.startswith(("final_", "train_"))}


def ask_metrics(matrix: dict, workdir: Path, label: str) -> dict:
    from .client import ask
    refs = {f"{i},{j}": v["ref"] for (i, j), v in matrix.items()}
    return ask({"op": "metrics", "R": refs, "label": label}, workdir)


def ask_compare(family: list, workdir: Path, label: str) -> dict:
    from .client import ask
    return ask({"op": "compare", "family": family, "label": label}, workdir)


def matrix_table(matrix: dict) -> str:
    lines = ["| after | S1 eval | S2 eval | S3 eval |", "| --- | --- | --- | --- |"]
    for i, name in enumerate(("TRAIN",) + STAGES):
        cells = []
        for j in range(1, 4):
            cell = matrix.get((i, j))
            cells.append("—" if cell is None else
                         f"{cell['pooled']} ({' / '.join(str(cell['per_seed'][s]) for s in sorted(cell['per_seed']))})")
        lines.append(f"| {name} (i={i}) | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=Path, required=True, help="directory of arm run directories")
    parser.add_argument("--metrics", action="store_true", help="ask J for the metrics (logged)")
    args = parser.parse_args(argv)
    summary = {}
    for run in sorted(p for p in args.runs.iterdir() if (p / "STATUS.json").exists()):
        arm = _load(run / "STATUS.json")["arm"]
        matrix = score_matrix(run)
        row = {"complete": _load(run / "STATUS.json")["complete"], "cost": cost(run),
               "base_check": base_check(run, arm), "matrix": matrix_table(matrix),
               "plasticity": plasticity(run, arm), "reported": reported(run)}
        if args.metrics and len(matrix) == 12:
            row["metrics"] = ask_metrics(matrix, args.runs / "J_requests", f"{arm} {run.name}")
        summary[f"{run.name}:{arm}"] = row
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
