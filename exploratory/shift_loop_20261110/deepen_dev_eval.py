"""Development check of a deepening-loop report on the sets that have already been run:
FRESH-3 (dev) and held-out B. Not part of any registered protocol.

    python dev_eval.py <deepen report.json> <out.json> [workers] [--deploy-only] [--no-held]
"""
import json, sys, time
from expert_ablate import spec_without
from hybrid import ALL, Harness, summary
from loop import CONFIGS
from replicate import paired
import confirm

report = json.load(open(sys.argv[1]))
out_path = sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 4
learn = CONFIGS["B"]; held = [p for p in ALL if p not in learn]
harness = Harness(workers, ALL)
import fresh3
third = fresh3.make()
harness.add_partition("fresh3", third, [t.public_view() for t in third])
earlier = json.load(open(confirm.EARLIER))
rows = {}
def measure(label, budget, parts):
    started = time.perf_counter()
    result = harness.run(spec_without({"library": report["library"]}, budget, "new", set(), "SCfR"), partition_names=parts)
    rows[label] = {"budget": budget, "partitions": parts, "counts": summary(result),
                   "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]] for p, rs in result.items() for r in rs if r["solved"]},
                   "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
                   "seconds": round(time.perf_counter() - started)}
    print(label, budget, rows[label]["counts"], rows[label]["seconds"], "s", flush=True)
parts = ["fresh3"] + ([] if "--no-held" in sys.argv else held)
measure("new@deploy", 100_000, parts)
if "--deploy-only" not in sys.argv:
    measure("new@student", 10_000, parts)
sound = confirm.Sound({"fresh3": third})
for label, row in rows.items():
    row["sound"] = sorted(k for k, v in row["programs"].items() if sound.verdict(k, v[0])[0])
    row["sound_counts"] = {p: sum(1 for k in row["sound"] if k.startswith(p + "/")) for p in row["partitions"]}
    print(label, "verified", row["counts"], "sound", row["sound_counts"])
e = earlier["rows"]
gen0_any3 = set().union(*(set(r["sound"]) for l, r in e.items() if l.startswith("gen0@") and "fresh3" in r["partitions"]))
gen0_any3 = {k for k in gen0_any3 if k.startswith("fresh3/")}
old3 = {k for k in e["trained@deploy"]["sound"] if k.startswith("fresh3/")}
new3 = {k for k in rows["new@deploy"]["sound"] if k.startswith("fresh3/")}
print("FRESH-3 new@1e5 vs gen0 any:", paired(new3, gen0_any3))
print("FRESH-3 new@1e5 vs old@1e5:", paired(new3, old3))
if "new@student" in rows:
    new3s = {k for k in rows["new@student"]["sound"] if k.startswith("fresh3/")}
    print("FRESH-3 new@1e4 vs gen0 any:", paired(new3s, gen0_any3))
    print("FRESH-3 new@1e4 vs old@1e5:", paired(new3s, old3))
if "--no-held" not in sys.argv:
    heldkeys = lambda keys: {k for k in keys if k.split("/", 1)[0] in held}
    gen0_anyH = set().union(*(heldkeys(r["sound"]) for l, r in e.items() if l.startswith("gen0@")))
    first = earlier["loop"]["timeline"][0]
    oldH = heldkeys(e["trained@deploy"]["sound"])
    newH = heldkeys(rows["new@deploy"]["sound"])
    print("held-out B new@1e5 vs gen0 any (rows of Addendum 7, without its student row):", paired(newH, gen0_anyH))
    print("held-out B new@1e5 vs old@1e5:", paired(newH, oldH))
    if "new@student" in rows:
        print("held-out B new@1e4 vs gen0 any:", paired(heldkeys(rows["new@student"]["sound"]), gen0_anyH))
# by routine on FRESH-3
import collections
tab = collections.defaultdict(lambda: [0, 0, 0, 0])
for t in third:
    k = "fresh3/" + t.name
    for routine in {t.stages[0][0], t.stages[1][0]}:
        tab[routine][0] += 1; tab[routine][1] += k in new3; tab[routine][2] += k in old3; tab[routine][3] += k in gen0_any3
print("routine: tasks new old gen0any")
for routine, v in sorted(tab.items(), key=lambda kv: -kv[1][0]):
    print(f"  {routine:26s} {v[0]:3d} {v[1]:3d} {v[2]:3d} {v[3]:3d}")
json.dump({"rows": rows}, open(out_path, "w"), indent=1)
harness.close()
