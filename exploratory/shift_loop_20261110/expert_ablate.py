"""Re-run the final vocabulary of an expert-iteration report with symbols dropped (exploratory,
report-only, post hoc).

    python expert_ablate.py <expert report.json> <out.json> <budget> <label>=<a,b,..|none> ...
                            [--held-only] [--components SCfR]

Each ``label=names`` is one run of every task (or of the held-out partitions only) with the
report's final library minus the named symbols. A symbol defined on a dropped symbol keeps
working: its witness is a closed base-language term.
"""
from __future__ import annotations

import json
import sys
import time

from hybrid import ALL, CONST_RANGE, Harness, spec_of, summary
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse
from rsi5.dsl.terms import term_to_dict
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

TYPES = {"int": INT, "bool": BOOL, "list[int]": ListOf(INT), "list[bool]": ListOf(BOOL)}
COMPONENTS = "SCf"


def spec_without(report, budget, label, drop, components=COMPONENTS):
    abstractions, constants = [], []
    for name, a in report["library"].items():
        if name in drop:
            continue
        witness = parse(a["witness"])
        if not a["params"]:
            value = evaluate(witness, ())
            if value.ok and type(value.value) is int and abs(value.value) <= CONST_RANGE and value.value not in constants:
                constants.append(value.value)
            continue
        type_ = arrows(*[TYPES[p] for p in a["params"]], TYPES[a["result"]])
        abstractions.append((name, type_.to_dict(), term_to_dict(witness)))
    return spec_of(label, budget, components, abstractions, constants)


if __name__ == "__main__":
    report = json.load(open(sys.argv[1]))
    out_path, budget = sys.argv[2], int(sys.argv[3])
    variants = [a.split("=", 1) for a in sys.argv[4:] if "=" in a]
    learn = report["learn"]
    held = [p for p in ALL if p not in learn]
    names = held if "--held-only" in sys.argv else list(ALL)
    components = sys.argv[sys.argv.index("--components") + 1] if "--components" in sys.argv else COMPONENTS
    harness = Harness(4, ALL)
    out = {"report": sys.argv[1], "budget": budget, "partitions": names, "components": components, "rows": []}
    for label, dropped in variants:
        drop = set() if dropped == "none" else set(dropped.split(","))
        unknown = drop - set(report["library"])
        if unknown:
            raise SystemExit(f"not in the library: {sorted(unknown)}")
        started = time.perf_counter()
        result = harness.run(spec_without(report, budget, label, drop, components), partition_names=names)
        counts = summary(result)
        row = {"label": label, "dropped": sorted(drop), "budget": budget, "counts": counts,
               "learn": sum(counts[p] for p in learn if p in counts),
               "held_out": sum(counts[p] for p in held if p in counts),
               "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                            for p, rows in result.items() for r in rows if r["solved"]},
               "used": {f"{p}/{r['name']}": r["used"] for p, rows in result.items() for r in rows if r["solved"]},
               "seconds": round(time.perf_counter() - started)}
        out["rows"].append(row)
        print(f"{label:16s} budget {budget:>7} learn {row['learn']:3d} held-out {row['held_out']:3d} {counts} | "
              f"{row['seconds']} s", flush=True)
        json.dump(out, open(out_path, "w"), indent=1)
    harness.close()
