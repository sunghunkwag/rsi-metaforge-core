"""Development evaluation of a loop report (``deepen.py`` or ``deepen2.py``) on sets that have
already been read: held-out B, FRESH-3 and, with ``--fresh4``, FRESH-4 (a development set since
the registered run of Addendum 8 was scored). Not part of any registered protocol.

    python deepen2_eval.py <loop report.json> <out.json> [workers] [--scope all|list] [--fresh4]
                           [--student-only] [--deploy-only]

The scope is the report's own unless ``--scope`` is given. The comparisons printed at the end use
stored rows: generation 0 and the earlier loop on FRESH-3 and held-out B from
``results/replication.json``; on FRESH-4 the rows of ``results/confirm.json``.
"""
import json
import os
import sys
import time

import confirm
import deepen2
import fresh3
from expert_ablate import spec_without
from hybrid import ALL, Harness, summary
from loop import CONFIGS
from replicate import paired

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTERED = os.path.join(HERE, "results", "confirm.json")


def main() -> None:
    report = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 4
    scope = sys.argv[sys.argv.index("--scope") + 1] if "--scope" in sys.argv else report.get("scope", "all")
    learn = CONFIGS["B"]
    held = [p for p in ALL if p not in learn]
    harness = Harness(workers, ALL)
    third = fresh3.make()
    harness.add_partition("fresh3", third, [t.public_view() for t in third])
    generated = {"fresh3": third}
    parts = ["fresh3"] + held
    if "--fresh4" in sys.argv:
        import fresh4
        fourth = fresh4.make()
        harness.add_partition("fresh4", fourth, [t.public_view() for t in fourth])
        generated["fresh4"] = fourth
        parts.append("fresh4")
    rows = {}

    def measure(label, budget):
        started = time.perf_counter()
        spec = spec_without({"library": report["library"]}, budget, label, set(), report.get("components", "SCfR"))
        spec["keep"] = deepen2.keep_for(scope, spec["constants"])
        result = harness.run(spec, partition_names=parts)
        rows[label] = {"budget": budget, "scope": scope, "partitions": parts, "counts": summary(result),
                       "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                                    for p, rs in result.items() for r in rs if r["solved"]},
                       "rejected": {f"{p}/{r['name']}": [r["program"], r["route"]]
                                    for p, rs in result.items() for r in rs if r["term"] is not None and not r["solved"]},
                       "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
                       "spent": sum(r["candidates"] for rs in result.values() for r in rs),
                       "seconds": round(time.perf_counter() - started)}
        print(label, budget, rows[label]["counts"], rows[label]["seconds"], "s", flush=True)

    if "--deploy-only" not in sys.argv:
        measure("new@student", 10_000)
    if "--student-only" not in sys.argv:
        measure("new@deploy", 100_000)
    sound = confirm.Sound(generated)
    for label, row in rows.items():
        row["sound"] = sorted(k for k, v in row["programs"].items() if sound.verdict(k, v[0])[0])
        row["sound_counts"] = {p: sum(1 for k in row["sound"] if k.startswith(p + "/")) for p in row["partitions"]}
        print(label, "verified", row["counts"], "sound", row["sound_counts"])
    json.dump({"report": sys.argv[1], "scope": scope, "rows": rows}, open(out_path, "w"), indent=1)

    earlier = json.load(open(confirm.EARLIER))["rows"]
    within = lambda keys, parts_: {k for k in keys if k.split("/", 1)[0] in parts_}
    gen0 = {"fresh3": within(set().union(*(set(r["sound"]) for l, r in earlier.items()
                                           if l.startswith("gen0@") and "fresh3" in r["partitions"])), ["fresh3"]),
            "held-out B": within(set().union(*(set(r["sound"]) for l, r in earlier.items() if l.startswith("gen0@"))), held)}
    before = {}
    if os.path.exists(REGISTERED):
        registered = json.load(open(REGISTERED))["rows"]
        gen0["held-out B"] |= within(set().union(*(set(r["sound"]) for l, r in registered.items()
                                                   if l.startswith("gen0@") and l.endswith(":heldB"))), held)
        gen0["fresh4"] = set().union(*(set(r["sound"]) for l, r in registered.items()
                                       if l.startswith("gen0@") and l.endswith(":fresh4")))
        before = {("new@student", "fresh4"): set(registered["new@student:fresh4"]["sound"]),
                  ("new@deploy", "fresh4"): set(registered["new@deploy:fresh4"]["sound"]),
                  ("new@student", "held-out B"): set(registered["new@student:heldB"]["sound"]),
                  ("new@deploy", "held-out B"): set(registered["new@deploy:heldB"]["sound"]),
                  ("new@student", "fresh3"): set(registered["new@student:fresh3"]["sound"]),
                  ("new@deploy", "fresh3"): set(registered["new@deploy:fresh3"]["sound"])}
    groups = {"fresh3": ["fresh3"], "held-out B": held, "fresh4": ["fresh4"]}
    for label, row in rows.items():
        for name, parts_ in groups.items():
            if not all(p in row["partitions"] for p in parts_):
                continue
            mine = within(row["sound"], parts_)
            if name in gen0:
                print(f"{label} on {name} against generation 0 at any budget run: {paired(mine, gen0[name])}")
            if (label, name) in before:
                print(f"{label} on {name} against the loop of Addendum 8 at the same budget: "
                      f"{paired(mine, before[(label, name)])}")
    harness.close()


if __name__ == "__main__":
    main()
