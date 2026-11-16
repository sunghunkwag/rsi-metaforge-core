"""Development: a merged library in tiers, at one budget, on development sets (pool reading printed).

    python tier_eval.py <out.json> <budget> <variant> [workers]
variants:  new-list        the 19 symbols of Addendum 8 in the list space (P off)
           union-list      those and the 9 of Addendum 7, all in the list space (P off)
           union-listP     the same with P
           union-P         every symbol used by P alone
           new-list+old-P  the 19 in the list space, the 9 by P alone
"""
import json, sys, time
from math import comb
from expert_ablate import spec_without
from hybrid import ALL, Harness, summary
from rsi5.dsl.vocabulary import VOCABULARIES
out_path, budget, variant = sys.argv[1], int(sys.argv[2]), sys.argv[3]
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 2
E = "exploratory/shift_loop_20261110/results/"
reg = json.load(open(E + "confirm.json"))
old = json.load(open(E + "replication.json"))
new_lib, old_lib = reg["loop"]["library"], old["loop"]["library"]
harness = Harness(workers, ALL)
import confirm, fresh3, fresh4
t3, t4 = fresh3.make(), fresh4.make()
harness.add_partition("fresh3", t3, [t.public_view() for t in t3])
harness.add_partition("fresh4", t4, [t.public_view() for t in t4])
library = dict(new_lib) if variant.startswith("new-list") and "+old" not in variant else {**new_lib, **old_lib}
components = "SCfRP" if variant.endswith("P") else "SCfR"
spec = spec_without({"library": library}, budget, variant, set(), components)
base = VOCABULARIES["restored"]
ints = list(base.integer_constants) + [c for c in spec["constants"] if c not in base.integer_constants]
plain = list(base.primitives) + [f"int:{c}" for c in ints]
names = [name for name, _, _ in spec["abstractions"]]
core = {"new-list": names, "union-list": names, "union-listP": names, "union-P": [],
        "new-list+old-P": [n for n in names if n in new_lib]}[variant]
spec["keep"] = {"elem": plain, "list": plain + core, "symbols": plain + names}
started = time.perf_counter()
result = harness.run(spec, partition_names=["fresh3", "fresh2", "compose24", "fresh4"])
row = {"variant": variant, "budget": budget, "components": components, "core": core, "library": names, "counts": summary(result),
       "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]] for p, rs in result.items() for r in rs if r["solved"]},
       "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
       "spent": sum(r["candidates"] for rs in result.values() for r in rs), "seconds": round(time.perf_counter() - started)}
sound = confirm.Sound({"fresh3": t3, "fresh4": t4})
row["sound"] = sorted(k for k, v in row["programs"].items() if sound.verdict(k, v[0])[0])
row["pool"] = sorted(k for k in row["sound"] if k.split("/")[0] in ("fresh3", "fresh4") and sound.on_pool(k, row["programs"][k][0]))
json.dump(row, open(out_path, "w"), indent=1)
def p1(a, b):
    n = a + b
    return sum(comb(n, k) for k in range(a, n + 1)) / 2 ** n if n else 1.0
def line(x, y):
    a, b = len(x - y), len(y - x)
    return f"{len(x)} vs {len(y)} ({a} vs {b}, p={p1(a, b):.3g})"
rows = reg["rows"]
g0s, g0p = set(), set()
for l in ("gen0@student", "gen0@deploy", "gen0@C2old", "gen0@C2new", "gen0@top"):
    r = rows[l + ":fresh4"]
    g0s |= set(r["sound"]); g0p |= {k for k in r["sound"] if sound.on_pool(k, r["programs"][k][0])}
f4 = lambda keys: {k for k in keys if k.startswith("fresh4/")}
routes = {}
for k, v in row["programs"].items():
    if k.startswith("fresh4/"): routes[v[1]] = routes.get(v[1], 0) + 1
print(variant, budget, "verified", row["counts"], "|", row["seconds"], "s")
print("  FRESH-4 sound:", line(f4(row["sound"]), g0s), "| pool:", line(f4(row["pool"]), g0p), "| routes", routes)
print("  FRESH-3 sound", len([k for k in row["sound"] if k.startswith("fresh3/")]), "pool", len([k for k in row["pool"] if k.startswith("fresh3/")]),
      "| held-out B sound", len([k for k in row["sound"] if k.split("/")[0] in ("fresh2", "compose24")]))
harness.close()
