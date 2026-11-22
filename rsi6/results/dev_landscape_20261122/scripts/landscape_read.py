"""Read the landscape files (my own script; reads JSON only).

    python3 -I landscape_read.py DIR [DIR ...]
For each category: per change, the mean over seeds of (gain of the changed version - gain of generation 0 on
the same seed), its standard error over seeds, and the CPU ratio.
"""
import json, sys, glob, os, statistics as st
from collections import defaultdict

def load(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "**", "landscape_*.json"), recursive=True)):
        if f.endswith(".records.jsonl"):
            continue
        with open(f) as h:
            out.append(json.load(h))
    return out

def main(dirs):
    cats = defaultdict(list)
    for d in dirs:
        for doc in load(d):
            cats[doc["category"]].append(doc)
    for cat, docs in sorted(cats.items()):
        rows = [r for doc in docs for r in doc["rows"]]
        seeds = sorted({r["seed"] for r in rows})
        base = {r["seed"]: r for r in rows if r["field"] == ""}
        by = defaultdict(list)
        for r in rows:
            if r["field"] == "":
                continue
            b = base[r["seed"]]
            by[(r["field"], json.dumps(r["value"]))].append(
                (r["gain"] - b["gain"], r["acquired"] - b["acquired"], r["untrained"] - b["untrained"],
                 r["cpu"] / b["cpu"] if b["cpu"] else float("nan")))
        print(f"== {cat}: seeds {len(seeds)}, changes {len(by)}; generation 0: "
              f"untrained {st.mean(b['untrained'] for b in base.values()):.4f} acquired {st.mean(b['acquired'] for b in base.values()):.4f} "
              f"gain {st.mean(b['gain'] for b in base.values()):+.4f} (sd over seeds {st.pstdev([b['gain'] for b in base.values()]):.4f}) cpu {st.mean(b['cpu'] for b in base.values()):.2f}s")
        table = []
        for k, v in by.items():
            d = [x[0] for x in v]
            m = st.mean(d)
            se = (st.stdev(d) / len(d) ** 0.5) if len(d) > 1 else float("nan")
            table.append((m, se, st.mean(x[1] for x in v), st.mean(x[2] for x in v), st.mean(x[3] for x in v), k, len(d)))
        table.sort(reverse=True)
        nz = sum(1 for t in table if abs(t[0]) > 1e-12)
        print(f"   changes with any effect on gain: {nz}/{len(table)}")
        for t in table[:8] + [None] + table[-5:]:
            if t is None:
                print("   ...")
                continue
            m, se, da, du, cr, k, n = t
            print(f"   {k[0]:28s} {k[1]:>12s}  dgain {m:+.4f} (se {se:.4f}, n {n})  dacq {da:+.4f} duntr {du:+.4f}  cpu x{cr:.2f}")

if __name__ == "__main__":
    main(sys.argv[1:])
