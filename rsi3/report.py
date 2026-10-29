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
             "RSI3_UNIFORM_FM", "RSI3_FM", "RSI3_UNIFORM_FM_SCM", "RSI3_UNIFORM_FM_SC",
             "RSI3_UNIFORM_FM_INV", "RSI3_UNIFORM_FM_INVP", "RSI3_UNIFORM_FM_DEC",
             "RSI3_META", "RSI3_META_WIPE", "RSI3_META_FOLD", "RSI3_META_PLAY", "RSI3_META_CONJ",
             "RSI3_META_BEH", "RSI3_META_BEH_BASE"]
COMPARISONS = [
    ("C1", "RSI3", "RSI2", "train"), ("C2", "RSI3", "RSI3_UNIFORM", "train"),
    ("C3", "RSI3", "RSI3_NO_REPLAY", "train"), ("C4", "RSI3", "RSI3_NO_GENESIS", "train"),
    ("C5", "RSI3", "RSI2", "validation"),
    # Failure-memory study (PREDICTIONS_FAILURE_MEMORY.md)
    ("F1", "RSI3_UNIFORM_FM", "RSI3_UNIFORM", "train"), ("F2", "RSI3_FM", "RSI3", "train"),
    ("F3", "RSI3_FM", "RSI3_UNIFORM_FM", "train"), ("F4", "RSI3_UNIFORM_FM", "RSI2", "train"),
    ("F5", "RSI3_UNIFORM_FM", "RSI2", "validation"),
    # Self-continuity study (PREDICTIONS_SELF_CONTINUITY.md)
    # The measure arm is trajectory-identical to RSI3_UNIFORM_FM (passive).
    ("S1", "RSI3_UNIFORM_FM_SC", "RSI3_UNIFORM_FM_SCM", "train"),
    ("S2", "RSI3_UNIFORM_FM_SC", "RSI3_UNIFORM_FM_SCM", "validation"),
    # Concept-invention study (PREDICTIONS_INVENTION.md)
    ("I1", "RSI3_UNIFORM_FM_INV", "RSI3_UNIFORM_FM", "train"),
    ("I2", "RSI3_UNIFORM_FM_INV", "RSI3_UNIFORM_FM", "validation"),
    # Long-horizon compounding study (PREDICTIONS_LONG.md)
    ("L1", "RSI3_UNIFORM_FM_INVP", "RSI3_UNIFORM_FM", "train"),
    ("L2", "RSI3_UNIFORM_FM_INV", "RSI3_UNIFORM_FM", "train"),
    ("L3", "RSI3_UNIFORM_FM_INVP", "RSI3_UNIFORM_FM_INV", "train"),
    ("L4", "RSI3_UNIFORM_FM_INVP", "RSI3_UNIFORM_FM", "validation"),
    # Meta-RL study (PREDICTIONS_METARL.md); "agent" = validation_agent, the
    # arm's own solver on VALIDATION (equal to VALIDATION for prior-only arms).
    ("X1", "RSI3_META", "RSI3_UNIFORM_FM", "agent"),
    ("X2", "RSI3_META", "RSI3_UNIFORM_FM_DEC", "agent"),
    ("X3", "RSI3_META", "RSI3_META_WIPE", "agent"),
    ("X4", "RSI3_META", "RSI3_UNIFORM_FM", "validation"),
    # Cascade study (PREDICTIONS_CASCADE.md)
    ("Z1", "RSI3_META_CONJ", "RSI3_META", "train"),
    ("Z2", "RSI3_META_CONJ", "RSI3_META_PLAY", "train"),
    ("Z3", "RSI3_META_CONJ", "RSI3_META", "agent"),
    ("Z4", "RSI3_META_CONJ", "RSI3_META_PLAY", "agent"),
    ("Z6", "RSI3_META_PLAY", "RSI3_META_FOLD", "agent"),
    # Behavioural-search study (PREDICTIONS_BEHAVE.md)
    ("B1", "RSI3_META_BEH", "RSI3_META_CONJ", "train"),
    ("B2", "RSI3_META_BEH", "RSI3_META_CONJ", "agent"),
    ("B3", "RSI3_META_BEH", "RSI3_META_BEH_BASE", "train"),
    ("B4", "RSI3_META_BEH", "RSI3_META_BEH_BASE", "agent"),
]


def validation_drops(record) -> int:
    """Generation-to-generation decreases in VALIDATION solved."""
    values = [g["validation"]["solved"] for g in record["generations"]]
    return sum(1 for a, b in zip(values, values[1:]) if b < a)


def continuity_lines(arm, records) -> list[str]:
    lines = []
    if not records or "continuity" not in records[0]["generations"][0]:
        return lines
    for r in records:
        rows = [g["continuity"] for g in r["generations"]]
        if rows[0].get("mode") in (None, "off"):
            return lines
        retained = [f"{c.get('retained', 0)}/{c.get('audited', 0)}" for c in rows]
        exams = [f"{c['old']['exam']['count']}->{c['new']['exam']['count']}/"
                 f"{c['new']['exam']['sat']}" if "old" in c else "-" for c in rows]
        lost = [len(c.get("lost", [])) for c in rows]
        lost_exams = [len(c.get("lost_exams", [])) for c in rows]
        flagged = [int(bool(c.get("old_better"))) for c in rows]
        decisions = [c.get("decision", "-") for c in rows]
        charged = sum(c.get("charged", 0) for c in rows)
        lines.append(f"  - {arm} seed {r['seed']}: TRAIN retained per generation {retained}; "
                     f"exams passed old->new/sat {exams}; TRAIN lost {lost}; exams lost "
                     f"{lost_exams}; old self scored higher {flagged}; decisions {decisions}; "
                     f"audit and exam work charged {charged}; VALIDATION per generation "
                     f"{[g['validation']['solved'] for g in r['generations']]}, "
                     f"drops {validation_drops(r)}.")
    return lines


def alignment_lines(records) -> list[str]:
    """Does the passive guard's alarm coincide with VALIDATION drops? (R3)"""
    flagged = drops = both = 0
    for r in records:
        gens = r["generations"]
        for previous, g in zip(gens, gens[1:]):
            alarm = bool(g["continuity"].get("old_better"))
            drop = g["validation"]["solved"] < previous["validation"]["solved"]
            flagged += alarm
            drops += drop
            both += alarm and drop
    if not records:
        return []
    precision = f"{both}/{flagged}" if flagged else "void (no alarms)"
    recall = f"{both}/{drops}" if drops else "void (no drops)"
    return ["Alarm alignment in the measure arm (R3), generations 2-8 pooled over seeds: "
            f"alarms that coincide with a VALIDATION drop {precision}; VALIDATION drops "
            f"that coincide with an alarm {recall}.", ""]


def invention_lines(arm, records) -> list[str]:
    lines = []
    for r in records:
        adopted = r["final"].get("adopted_concepts")
        if adopted is None or not any("invention" in g["wake"] and g["wake"]["invention"]
                                      for g in r["generations"]):
            continue
        library = r["final"].get("library", {})
        items = "; ".join(f"g{a['generation']} via {a['task']}: {library.get(name, name)}"
                          for name, a in sorted(adopted.items(),
                                                key=lambda kv: kv[1]["generation"]))
        proposed = [len(g["wake"]["invention"].get("proposed", [])) for g in r["generations"]]
        mdl = sum(len(g["sleep"]["adopted_library"]) for g in r["generations"])
        built = [name for name in adopted
                 if any(other != name and other in library.get(name, "")
                        for other in adopted)]
        lines.append(f"  - {arm} seed {r['seed']}: concepts adopted {len(adopted)} "
                     f"({items or 'none'}); built from an earlier adopted concept "
                     f"{len(built)}; proposed per generation {proposed}; "
                     f"RSI-2 MDL library adoptions {mdl}.")
    return lines


def load(directory: Path) -> dict:
    runs = {}
    for path in sorted(directory.glob("*_seed*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        runs[(record["arm"], record["seed"])] = record
    return runs


def final(record, metric):
    last = record["generations"][-1]
    if metric == "train":
        return last["train_solved"]
    if metric == "agent":
        # Prior-only arms have no validation_agent; theirs equals VALIDATION
        # (tests/test_metarl.py::test_agent_validation_equals_validation...).
        return last.get("validation_agent", last["validation"])["solved"]
    return last["validation"]["solved"]


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

    if any(k[0] == "RSI3_UNIFORM_FM_SC" for k in runs):
        pairs = [(s, validation_drops(runs[("RSI3_UNIFORM_FM_SC", s)]),
                  validation_drops(runs[("RSI3_UNIFORM_FM_SCM", s)]))
                 for s in seeds if ("RSI3_UNIFORM_FM_SC", s) in runs
                 and ("RSI3_UNIFORM_FM_SCM", s) in runs]
        if pairs:
            verdict = "PASS" if all(a < b for _, a, b in pairs) else "FAIL"
            detail = "; ".join(f"{s}: {a} vs {b}" for s, a, b in pairs)
            out.append("Generation-to-generation VALIDATION drops (S3, fewer is better):\n")
            out.append("| ID | Comparison | Per seed | Result |")
            out.append("| --- | --- | --- | --- |")
            out.append(f"| S3 | RSI3_UNIFORM_FM_SC drops < RSI3_UNIFORM_FM_SCM drops | {detail} "
                       f"| {verdict} |")
            out.append("")

    out.extend(alignment_lines([runs[("RSI3_UNIFORM_FM_SCM", s)] for s in seeds
                                if ("RSI3_UNIFORM_FM_SCM", s) in runs]))

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
        out.extend(continuity_lines(arm, records))
        out.extend(invention_lines(arm, records))
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
    parser.add_argument("--results", type=Path, nargs="+", required=True,
                        help="one or more result directories (later ones add arms)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    runs = {}
    for directory in args.results:
        runs.update(load(directory))
    args.output.write_text(render(runs), encoding="utf-8")


if __name__ == "__main__":
    main()
