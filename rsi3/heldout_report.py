"""Render held-out evaluations (reserve_eval output) and check that a rerun reproduced a registered run.

    python -m rsi3.heldout_report --partition fresh1 --evals DIR/*_fresh1.json \\
        [--runs DIR/*_seed*.json --committed rsi3/results_honest] --output tables.md

Reads run files and evaluation files only; executes no task and opens no
partition. Family names come from task names alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def family(partition: str, name: str) -> str:
    """The routine family of a task name, per partition."""
    if partition.startswith("fresh"):
        from .fresh import components
        parts = components(name)
        return " then ".join(routine for routine, _ in parts) if parts else name
    if partition == "compose24":
        return name.split("::")[1] if "::" in name else name
    return name.split(" with ")[0]


def load_eval(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summary(evaluation: dict) -> dict:
    """Solved per seed, solves by family per seed, spend by action, and new-action provenance."""
    partition = evaluation["partition"]
    out = {"arm": evaluation["arm"], "partition": partition, "tasks": evaluation["tasks"],
           "solved": {}, "by_family": {}, "spent": {}, "via": {}, "names": {}}
    for seed, record in evaluation["seeds"].items():
        out["solved"][seed] = record["solved"]
        out["names"][seed] = sorted(record["solved_names"])
        fam = {}
        spent = {}
        via = []
        for task in record["tasks"]:
            f = family(partition, task["name"])
            fam.setdefault(f, [0, 0])
            fam[f][1] += 1
            fam[f][0] += bool(task["solved"])
            for action, units in task["spent"].items():
                spent[action] = spent.get(action, 0) + int(units)
            for key in ("analogy_from", "chain_from"):
                if task.get(key):
                    via.append((task["name"], key.split("_")[0], list(task[key])))
        out["by_family"][seed] = fam
        out["spent"][seed] = spent
        out["via"][seed] = via
    return out


def reproduction(rerun: dict, committed: dict) -> dict:
    """Compare a rerun's run file with a committed registered run file (same arm and seed)."""
    def series(record, key):
        rows = []
        for g in record["generations"]:
            value = g.get(key)
            rows.append(None if value is None else value.get("solved"))
        return rows
    checks = {
        "train": ([g["train_solved"] for g in rerun["generations"]],
                  [g["train_solved"] for g in committed["generations"]]),
        "validation": (series(rerun, "validation"), series(committed, "validation")),
        "validation_agent": (series(rerun, "validation_agent"), series(committed, "validation_agent")),
        "solutions": (rerun["final"]["solutions"], committed["final"]["solutions"]),
        "library": (sorted(rerun["final"]["library"]), sorted(committed["final"]["library"])),
    }
    return {name: {"match": a == b, "rerun": a, "committed": b} for name, (a, b) in checks.items()}


def render(summaries: list[dict], reproductions: dict | None = None) -> str:
    """Markdown: a solved table, a by-family table (first seed), spend by action, provenance."""
    if not summaries:
        return ""
    partition = summaries[0]["partition"]
    total = summaries[0]["tasks"]
    seeds = sorted({s for r in summaries for s in r["solved"]}, key=int)
    lines = [f"### {partition} ({total} tasks): solved per seed\n",
             "| Arm | " + " | ".join(f"seed {s}" for s in seeds) + " |",
             "| --- | " + " | ".join("---" for _ in seeds) + " |"]
    for r in summaries:
        lines.append(f"| {r['arm']} | " + " | ".join(str(r["solved"].get(s, "—")) for s in seeds) + " |")
    lines.append("")
    first = seeds[0]
    families = sorted({f for r in summaries for f in r["by_family"].get(first, {})})
    lines += [f"### {partition} by family, seed {first} (solved / tasks)\n",
              "| Family | " + " | ".join(r["arm"] for r in summaries) + " |",
              "| --- | " + " | ".join("---" for _ in summaries) + " |"]
    for f in families:
        cells = []
        for r in summaries:
            got = r["by_family"].get(first, {}).get(f)
            cells.append("—" if got is None else f"{got[0]}/{got[1]}")
        lines.append(f"| {f} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"### Candidates spent by action, seed {first}\n")
    for r in summaries:
        spent = r["spent"].get(first, {})
        items = ", ".join(f"{a} {n}" for a, n in sorted(spent.items(), key=lambda kv: -kv[1]))
        lines.append(f"- {r['arm']}: {items}")
    lines.append("")
    for r in summaries:
        via = r["via"].get(first, [])
        if via:
            lines.append(f"### Solves by the new actions, {r['arm']}, seed {first}\n")
            for name, action, source in via:
                lines.append(f"- {name}: {action} from {source}")
            lines.append("")
    if reproductions:
        lines.append("### Reproduction of the registered runs\n")
        lines.append("| Arm | Seed | TRAIN trajectory | VALIDATION | validation_agent | Final solutions | Library names |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for (arm, seed), checks in sorted(reproductions.items()):
            cells = ["match" if checks[k]["match"] else "**differs**"
                     for k in ("train", "validation", "validation_agent", "solutions", "library")]
            lines.append(f"| {arm} | {seed} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--evals", type=Path, nargs="+", required=True)
    parser.add_argument("--runs", type=Path, nargs="*", default=[],
                        help="rerun files <ARM>_seed<seed>.json to compare with --committed")
    parser.add_argument("--committed", type=Path, nargs="*", default=[],
                        help="directories holding the registered <ARM>_seed<seed>.json files")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    summaries = [summary(load_eval(p)) for p in args.evals]
    reproductions = {}
    committed = {}
    for directory in args.committed:
        for path in Path(directory).glob("*_seed*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            committed[(record["arm"], record["seed"])] = record
    for path in args.runs:
        record = json.loads(path.read_text(encoding="utf-8"))
        key = (record["arm"], record["seed"])
        if key in committed:
            reproductions[key] = reproduction(record, committed[key])
    args.output.write_text(render(summaries, reproductions), encoding="utf-8")
    print(json.dumps({r["arm"]: r["solved"] for r in summaries}))


if __name__ == "__main__":
    main()
