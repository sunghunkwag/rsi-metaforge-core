"""Re-run one state of a loop report (exploratory): the best state's library and kept symbols,
optionally with abstractions dropped, the cut lifted, or another budget.

    python state_run.py <loop report.json> <budget> <label> [--drop a,b] [--no-keep] [--no-library]
"""
import json, sys
import hybrid
from hybrid import ALL, Harness, spec_of, summary
from rsi5.dsl.pretty_parse import parse
from rsi5.dsl.terms import term_to_dict
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

TYPES = {"int": INT, "bool": BOOL, "list[int]": ListOf(INT), "list[bool]": ListOf(BOOL)}


def state_spec(report, budget, label, drop=(), keep=True, library=True):
    abstractions = []
    if library:
        for name, a in report["library"].items():
            if name in drop or not a["params"]:
                continue
            type_ = arrows(*[TYPES[p] for p in a["params"]], TYPES[a["result"]])
            abstractions.append((name, type_.to_dict(), term_to_dict(parse(a["witness"]))))
    kept = None
    if keep and report.get("best_keep"):
        names = {n for n, _, _ in abstractions}
        kept = {space: [s for s in symbols if s in names or s not in report["library"]]
                for space, symbols in report["best_keep"].items()}
    return spec_of(label, budget, report["components"], abstractions, (), keep=kept)


if __name__ == "__main__":
    report = json.load(open(sys.argv[1]))
    budget, label = int(sys.argv[2]), sys.argv[3]
    drop = tuple(sys.argv[sys.argv.index("--drop") + 1].split(",")) if "--drop" in sys.argv else ()
    harness = Harness(4, ALL)
    result = harness.run(state_spec(report, budget, label, drop, "--no-keep" not in sys.argv, "--no-library" not in sys.argv))
    counts = summary(result)
    learn = sum(counts[p] for p in report["learn"])
    held = sum(counts[p] for p in ALL if p not in report["learn"])
    print(f"{label:34s} budget {budget:>6} learn {learn:3d} held-out {held:3d} {counts}", flush=True)
    out = {"label": label, "budget": budget, "counts": counts, "learn": learn, "held_out": held,
           "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                        for p, rows in result.items() for r in rows if r["solved"]}}
    json.dump(out, open(sys.argv[1].replace(".json", f".{label}.json"), "w"), indent=1)
    harness.close()
