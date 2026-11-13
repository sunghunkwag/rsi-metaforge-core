"""Generation 0 (the machinery with no learned symbol) on a development set at given budgets.

Development only: the rows are the control of ``deepen3_eval.py`` on sets that the registered
runs do not cover. Never the registered half of FRESH-5.

    python gen0_rows.py <out.json> <set: fresh5dev> <budgets, comma separated> [workers]

The largest budget runs first. The output file is rewritten after every row, and a row already
in it is kept.
"""
from __future__ import annotations

import json
import os
import sys
import time

from hybrid import ALL, Harness, spec_of, summary

LABELS = {10_000: "student", 100_000: "deploy", 1_126_452: "top"}


def main() -> None:
    out_path, name = sys.argv[1], sys.argv[2]
    budgets = sorted((int(b) for b in sys.argv[3].split(",")), reverse=True)
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    if name != "fresh5dev":
        raise SystemExit("only the development half of FRESH-5 is run here")
    harness = Harness(workers, ALL)
    import fresh5                                    # loads the FRESH partitions: after the fork
    tasks = fresh5.make("development")
    harness.add_partition(name, tasks, [t.public_view() for t in tasks])
    out = json.load(open(out_path)) if os.path.exists(out_path) else {"set": name, "rows": {}}
    for budget in budgets:
        label = f"gen0@{LABELS.get(budget, 'r' + str(budget))}:{name}"
        if label in out["rows"]:
            continue
        started = time.perf_counter()
        result = harness.run(spec_of(label, budget, "SCfR"), partition_names=[name])
        out["rows"][label] = {
            "budget": budget, "partitions": [name], "counts": summary(result),
            "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                         for p, rs in result.items() for r in rs if r["solved"]},
            "rejected": {f"{p}/{r['name']}": r["program"] for p, rs in result.items() for r in rs
                         if r["term"] is not None and not r["solved"]},
            "spent": sum(r["candidates"] for rs in result.values() for r in rs),
            "ceiling": budget * len(tasks), "seconds": round(time.perf_counter() - started)}
        json.dump(out, open(out_path, "w"), indent=1)
        print(label, out["rows"][label]["counts"], out["rows"][label]["seconds"], "s", flush=True)
    harness.close()


if __name__ == "__main__":
    main()
