"""Development reading: how often the learner keeps what it learned, and what it gains when it does.

    python3 -I learned_rates.py DIR [DIR ...]

From the ``*.json`` rows and ``*.records.jsonl`` run reports of dev_landscape (landscape_* and pair_* files):
for generation 0 and for each named change of the pair files, per category: runs, the share of runs whose
report says ``learned`` (the held-back check kept the learned weights), the rounds of learning the budget
allowed (``iterations``), the mean gain over all runs, over the runs that kept and over those that did not.
"""
import glob, json, os, sys, statistics as st
from collections import defaultdict
rows, reports = defaultdict(dict), {}
for d in sys.argv[1:]:
    for path in sorted(glob.glob(os.path.join(d, "**", "*_*.json"), recursive=True)):
        name = os.path.basename(path)
        if not (name.startswith("pair_") or name.startswith("landscape_")):
            continue
        doc = json.load(open(path))
        if "rows" not in doc or doc.get("smoke"):
            continue
        for r in doc["rows"]:
            rows[doc["category"]][(r["seed"], r["field"], json.dumps(r["value"]))] = r
        rec = path[:-5] + ".records.jsonl"
        for line in open(rec):
            r = json.loads(line)
            if r.get("type") == "run":
                reports[(r["env"], r["seed"], r["version"])] = r.get("report", {})
names = [("", "null")] + [tuple(a.split("=", 1)) for a in os.environ.get("CHANGES", "").split() if a]
out = {}
for cat in sorted(rows):
    for field, value in names:
        sel = [(k, r) for k, r in rows[cat].items() if k[1] == field and k[2] == value]
        if not sel:
            continue
        rep = [(reports.get((cat, k[0], r["version"]), {}), r) for k, r in sel]
        rep = [(p, r) for p, r in rep if p.get("form") == "assign"]
        if not rep:
            continue
        kept = [r["gain"] for p, r in rep if p.get("learned")]
        lost = [r["gain"] for p, r in rep if not p.get("learned")]
        its = sorted(p.get("iterations", 0) for p, _ in rep)
        label = "generation 0" if field == "" else f"{field}={value}"
        out[(cat, label)] = (len(rep), len(kept))
        print(f"{cat:13s} {label:22s} runs {len(rep):3d} kept {len(kept):3d} ({len(kept) / len(rep):.2f})  rounds of learning {its[0]}-{its[-1]} (median {its[len(its) // 2]})"
              f"  gain {st.fmean(r['gain'] for _, r in rep):+.4f}  when kept {st.fmean(kept) if kept else float('nan'):+.4f}  when not {st.fmean(lost) if lost else float('nan'):+.4f}")
