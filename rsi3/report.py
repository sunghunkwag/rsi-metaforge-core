"""Turn RSI-3 experiment JSON files into markdown tables and score the predictions.

    python -m rsi3.report --results RESULTS_DIR --output report.md

The reporter reads only the run files; it executes no task.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

ARM_ORDER = ["RSI2", "RSI3", "RSI3_NO_REPLAY", "RSI3_NO_GENESIS", "RSI3_UNIFORM",
             "RSI3_UNIFORM_FM", "RSI3_FM"]
COMPARISONS = [
    ("C1", "RSI3", "RSI2", "train"), ("C2", "RSI3", "RSI3_UNIFORM", "train"),
    ("C3", "RSI3", "RSI3_NO_REPLAY", "train"), ("C4", "RSI3", "RSI3_NO_GENESIS", "train"),
    ("C5", "RSI3", "RSI2", "validation"),
    # Failure-memory study (PREDICTIONS_FAILURE_MEMORY.md)
    ("F1", "RSI3_UNIFORM_FM", "RSI3_UNIFORM", "train"), ("F2", "RSI3_FM", "RSI3", "train"),
    ("F3", "RSI3_FM", "RSI3_UNIFORM_FM", "train"), ("F4", "RSI3_UNIFORM_FM", "RSI2", "train"),
    ("F5", "RSI3_UNIFORM_FM", "RSI2", "validation"),
]


def load(directory: Path) -> dict:
    runs = {}
    for path in sorted(directory.glob("*_seed*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        runs[(record["arm"], record["seed"])] = record
    return runs


def final(record, metric):
    last = record["generations"][-1]
    return last["train_solved"] if metric == "train" else last["validation"]["solved"]


def render(runs: dict) -> str:
    arms = [a for a in ARM_ORDER if any(k[0] == a for k in runs)]
    seeds = sorted({k[1] for k in runs})
    generations = max(len(r["generations"]) for r in runs.values())
    out = []

    out.append("## TRAIN hidden-verified solved, per generation\n")
    out.append("| Arm | Seed | " + " | ".join(f"g{g + 1}" for g in range(generations))
               + " | VALIDATION g-final | CPU s |")
    out.append("| --- | --- | " + " | ".join("---" for _ in range(generations)) + " | --- | --- |")
    for arm in arms:
        for seed in seeds:
            record = runs.get((arm, seed))
            if record is None:
                continue
            cells = [str(g["train_solved"]) for g in record["generations"]]
            out.append(f"| {arm} | {seed} | " + " | ".join(cells)
                       + f" | {final(record, 'validation')}/12 | {record['cpu_seconds']:.0f} |")
    out.append("")

    out.append("## Means over seeds\n")
    out.append("| Arm | TRAIN g1 | TRAIN final | VALIDATION final | CPU s per run |")
    out.append("| --- | --- | --- | --- | --- |")
    for arm in arms:
        records = [runs[(arm, s)] for s in seeds if (arm, s) in runs]
        out.append(f"| {arm} | {mean(r['generations'][0]['train_solved'] for r in records):.2f} | "
                   f"{mean(final(r, 'train') for r in records):.2f} | "
                   f"{mean(final(r, 'validation') for r in records):.2f} | "
                   f"{mean(r['cpu_seconds'] for r in records):.0f} |")
    out.append("")

    out.append("## Decisive comparisons (every seed)\n")
    out.append("| ID | Comparison | Per seed | Result |")
    out.append("| --- | --- | --- | --- |")
    for cid, left, right, metric in COMPARISONS:
        pairs = [(s, final(runs[(left, s)], metric), final(runs[(right, s)], metric))
                 for s in seeds if (left, s) in runs and (right, s) in runs]
        if not pairs:
            continue
        verdict = "PASS" if all(a > b for _, a, b in pairs) else "FAIL"
        detail = "; ".join(f"{s}: {a} vs {b}" for s, a, b in pairs)
        out.append(f"| {cid} | {left} > {right} ({metric}) | {detail} | {verdict} |")
    out.append("")

    out.append("## Mechanism readouts\n")
    baseline = [runs[("RSI2", s)] for s in seeds if ("RSI2", s) in runs]
    if baseline:
        spent = sum(g["wake"]["spent"] for r in baseline for g in r["generations"])
        unsolved = sum(g["wake"]["spent_on_unsolved_after"] for r in baseline for g in r["generations"])
        out.append(f"- M1: RSI2 spent {unsolved} of {spent} wake candidates "
                   f"({100 * unsolved / spent:.1f}%) on tasks unsolved after that generation.")
    for arm in arms:
        if arm == "RSI2":
            continue
        records = [runs[(arm, s)] for s in seeds if (arm, s) in runs]
        depth = [max(g["wake"]["max_depth"] for g in r["generations"]) for r in records]
        kinds = {}
        for r in records:
            for item in r["final"]["provenance"].values():
                key = f"{item['kind']}({item['origin']})"
                kinds[key] = kinds.get(key, 0) + 1
        rejected = [r["final"]["memory"]["rejected"] for r in records]
        skipped = [r["generations"][-1]["integrator"]["skipped_equivalent"] for r in records]
        genesis = [r["generations"][-1]["pathways"]["genesis"] for r in records]
        awake = [sum(1 for p in r["final"]["pathways"].values()
                     if p["origin"] == "genesis" and p["status"] == "active") for r in records]
        out.append(f"- {arm}: max searched depth per seed {depth}; verified solves by pathway "
                   f"{dict(sorted(kinds.items()))}; verifier rejections {rejected}; "
                   f"integrator skips {skipped}; genesis pathways created {genesis}, "
                   f"woken {awake}.")
        if any(r["final"].get("failure_memory") for r in records):
            known = [sum(g["wake"].get("skipped_known", 0) for g in r["generations"])
                     for r in records]
            widest = [max(r["final"]["failure_memory"].values(), default=0) for r in records]
            total = [sum(r["final"]["failure_memory"].values()) for r in records]
            out.append(f"  - {arm} failure memory: known failures skipped free {known}; "
                       f"distinct failed programs, largest task {widest}, all tasks {total}.")
    if baseline:
        base_cpu = mean(r["cpu_seconds"] for r in baseline)
        ratios = {arm: mean(runs[(arm, s)]["cpu_seconds"] for s in seeds if (arm, s) in runs) / base_cpu
                  for arm in arms if arm != "RSI2"}
        out.append("- M6: CPU per run relative to RSI2: "
                   + ", ".join(f"{arm} {ratio:.2f}x" for arm, ratio in ratios.items()) + ".")
    out.append("")

    out.append("## Solved TRAIN tasks at the final generation\n")
    for arm in arms:
        for seed in seeds:
            record = runs.get((arm, seed))
            if record is not None:
                out.append(f"- {arm} seed {seed}: " + ", ".join(record["final"]["solutions"]))
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render RSI-3 results")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.write_text(render(load(args.results)), encoding="utf-8")


if __name__ == "__main__":
    main()
