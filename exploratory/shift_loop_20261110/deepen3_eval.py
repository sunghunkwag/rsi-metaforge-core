"""Development evaluation of a two-tier loop report (``deepen3.py``) on development sets.

Not part of any registered protocol. Sets: ``fresh4`` and ``fresh3`` (development sets since
their registered runs), ``heldB`` (the 124 held-out tasks of configuration B) and ``fresh5dev``
(the development half of FRESH-5: new parameter values). Never the registered half of FRESH-5.

    python deepen3_eval.py <loop report.json> <out.json> [workers] [--sets fresh4,fresh3,heldB,fresh5dev]
                           [--budgets 10000,100000] [--cycles] [--gen0 <gen0 rows.json>]

``--cycles`` also evaluates the vocabulary after each accepting cycle at the first budget.
``--gen0`` names a file of generation-0 rows made by ``gen0_rows.py`` for sets that
``results/confirm.json`` does not cover. Every count is given under four measures: verified,
sound, sound and right on the whole pool, and right (``strict.py``).
"""
from __future__ import annotations

import json
import os
import sys
import time
from math import comb

from expert_ablate import spec_without
from hybrid import ALL, Harness
from loop import CONFIGS
from rsi5.dsl.vocabulary import VOCABULARIES

HERE = os.path.dirname(os.path.abspath(__file__))
MEASURES = ("verified", "sound", "pool", "right")


def spec_from_report(report: dict, label: str, budget: int, upto: int | None = None, role: str = "student") -> dict:
    """The harness spec of a ``deepen3`` report: its library and core, or those of the symbols
    accepted up to cycle ``upto``."""
    names = [n for n, entry in report["library"].items() if upto is None or (entry["cycle"] or 0) <= upto]
    core = set(report["core"]) if upto is None else set(next(c["core"] for c in report["cycles"] if c["cycle"] == upto))
    spec = spec_without({"library": report["library"]}, budget, label, set(report["library"]) - set(names), "SCfRP")
    base = VOCABULARIES["restored"]
    integers = list(base.integer_constants) + [c for c in spec["constants"] if c not in base.integer_constants]
    plain = list(base.primitives) + [f"int:{c}" for c in integers]
    symbols = [name for name, _, _ in spec["abstractions"]]
    listed = symbols if role == "teacher" else [n for n in symbols if n in core]
    spec["keep"] = {"elem": plain, "list": plain + listed, "symbols": plain + symbols}
    spec["p_share"] = report.get("p_share", 20)
    return spec


def p_one_sided(a: int, b: int) -> float:
    n = a + b
    return sum(comb(n, k) for k in range(a, n + 1)) / 2 ** n if n else 1.0


def line(x, y) -> str:
    a, b = len(x - y), len(y - x)
    return f"{len(x)} against {len(y)} ({a} against {b}, p = {p_one_sided(a, b):.3g})"


def main() -> None:
    report = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 4
    option = lambda flag, default: sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default
    sets = option("--sets", "fresh4,fresh3,heldB").split(",")
    budgets = [int(b) for b in option("--budgets", "10000").split(",")]
    held = [p for p in ALL if p not in CONFIGS["B"]]
    harness = Harness(workers, ALL)
    import fresh3                                    # loads the FRESH partitions: after the fork
    import fresh4
    import fresh5
    import strict
    generated = {}
    if "fresh3" in sets:
        generated["fresh3"] = fresh3.make()
    if "fresh4" in sets:
        generated["fresh4"] = fresh4.make()
    if "fresh5dev" in sets:
        generated["fresh5dev"] = fresh5.make("development")
    for name, tasks in generated.items():
        harness.add_partition(name, tasks, [t.public_view() for t in tasks])
    parts = [p for s in sets for p in (held if s == "heldB" else [s])]
    right = strict.Right(generated)

    def measured(programs: dict) -> dict:
        out = {m: [] for m in MEASURES}
        for key, entry in programs.items():
            verdict = right.verdict(key, entry[0])
            out["verified"].append(key)
            if verdict["sound"]:
                out["sound"].append(key)
            if verdict["pool"] or (verdict["pool"] is None and verdict["sound"]):
                out["pool"].append(key)
            if verdict["right"]:
                out["right"].append(key)
        return {m: sorted(keys) for m, keys in out.items()}

    rows = {}

    def run(label, budget, upto=None):
        started = time.perf_counter()
        result = harness.run(spec_from_report(report, label, budget, upto), partition_names=parts)
        programs = {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                    for p, rs in result.items() for r in rs if r["solved"]}
        rows[label] = {"budget": budget, "upto": upto, "partitions": parts, "programs": programs,
                       "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
                       "spent": sum(r["candidates"] for rs in result.values() for r in rs),
                       "seconds": round(time.perf_counter() - started), **measured(programs)}
        counts = {s: {m: sum(1 for k in rows[label][m] if k.split("/")[0] in (held if s == "heldB" else [s]))
                      for m in MEASURES} for s in sets}
        print(label, budget, counts, rows[label]["seconds"], "s", flush=True)

    for budget in budgets:
        run(f"final@{budget}", budget)
    if "--cycles" in sys.argv:
        for cycle in report["cycles"]:
            if cycle["accepted"]:
                run(f"cycle{cycle['cycle']}@{budgets[0]}", budgets[0], upto=cycle["cycle"])
    json.dump({"report": sys.argv[1], "sets": sets, "rows": rows}, open(out_path, "w"), indent=1)

    # generation 0 at any budget run, under each measure
    gen0 = {}
    stored = json.load(open(os.path.join(HERE, "results", "confirm.json")))["rows"]
    extra = json.load(open(option("--gen0", ""))) ["rows"] if "--gen0" in sys.argv else {}
    for s in sets:
        source = {l: r for l, r in stored.items() if l.startswith("gen0@") and l.endswith(":" + s)}
        source.update({l: r for l, r in extra.items() if l.startswith("gen0@") and l.endswith(":" + s)})
        if not source:
            continue
        union = {m: set() for m in MEASURES}
        for row in source.values():
            got = measured({k: v for k, v in row["programs"].items()
                            if k.split("/")[0] in (held if s == "heldB" else [s])})
            for m in MEASURES:
                union[m] |= set(got[m])
        gen0[s] = (union, sorted(source))
    for label, row in rows.items():
        for s in sets:
            if s not in gen0:
                continue
            union, labels = gen0[s]
            mine = lambda m: {k for k in row[m] if k.split("/")[0] in (held if s == "heldB" else [s])}
            print(f"{label} on {s} against generation 0 at any budget ({len(labels)} runs): " + "; ".join(
                f"{m} {line(mine(m), union[m])}" for m in MEASURES))
    harness.close()


if __name__ == "__main__":
    main()
