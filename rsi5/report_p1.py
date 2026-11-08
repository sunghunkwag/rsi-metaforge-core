"""Tables for RESULTS_P1.md from the Phase 1 result files.

    python -m rsi5.report_p1 --results rsi5/results_p1 [--markdown]

Reads every ``<vocabulary>_<partition>.json`` the run wrote, scores the registered
predictions of PREDICTIONS_P1.md, and prints the tables RESULTS_P1.md embeds. It
computes; it does not interpret.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .partitions import PARTITIONS, PHASE1_ORDER

CORPUS_LACKING = ("intersperse-k", "positions", "uniq", "identify-is-prime", "replace-index-k-with-n")


def load_results(results: Path) -> dict:
    found = {}
    for path in sorted(Path(results).glob("*_*.json")):
        if path.name.startswith("replay_") or path.name == "throughput.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "vocabulary" in data and "partition" in data:
            found[(data["vocabulary"], data["partition"])] = data
    return found


def solved_at(result: dict, budget: int) -> list:
    return [r for r in result["records"] if r["solved"] and r["candidates_to_solution"] <= budget]


def headline_table(found: dict, budgets=(1000, 10000, 100000, 1000000)) -> str:
    lines = ["| Partition | Tasks | Vocabulary | " + " | ".join(f"B = 10^{len(str(b)) - 1}" for b in budgets) + " | Public matches rejected |",
             "| --- | --- | --- | " + " | ".join("---" for _ in budgets) + " | --- |"]
    for partition in PHASE1_ORDER:
        for vocabulary in ("original", "restored"):
            result = found.get((vocabulary, partition))
            if result is None:
                continue
            counts = " | ".join(str(len(solved_at(result, b))) for b in budgets)
            lines.append(f"| {PARTITIONS[partition][0]} | {result['tasks']} | {vocabulary} | {counts} | "
                         f"{result['public_matches_rejected']} |")
    return "\n".join(lines)


def per_task_table(found: dict, partition: str, budget: int) -> str:
    original = found.get(("original", partition))
    restored = found.get(("restored", partition))
    if original is None or restored is None:
        return "(missing)"
    by_name = {r["name"]: r for r in restored["records"]}
    lines = ["| Task | Family | original: candidates to solution | restored: candidates to solution | Program (restored, else original) |",
             "| --- | --- | --- | --- | --- |"]
    for r in original["records"]:
        s = by_name[r["name"]]

        def cell(record):
            if record["solved"] and record["candidates_to_solution"] <= budget:
                return f"{record['candidates_to_solution']:,}"
            if record["public_match"] and not record["solved"]:
                return "public match, rejected"
            return "—"
        program = s["program"] if s["solved"] else (r["program"] if r["solved"] else "")
        lines.append(f"| `{r['name']}` | `{r['family']}` | {cell(r)} | {cell(s)} | `{program}` |" if program
                     else f"| `{r['name']}` | `{r['family']}` | {cell(r)} | {cell(s)} | |")
    return "\n".join(lines)


def closure_escape(found: dict, partition: str, budget: int) -> dict:
    """E: restored-solved tasks whose family has zero original solves at the same budget."""
    original = found.get(("original", partition))
    restored = found.get(("restored", partition))
    if original is None or restored is None:
        return {"E": None}
    original_families = {r["family"] for r in solved_at(original, budget)}
    escapes = [r for r in solved_at(restored, budget) if r["family"] not in original_families]
    lost = [r for r in solved_at(original, budget)
            if not any(s["name"] == r["name"] and s["solved"] and s["candidates_to_solution"] <= budget
                       for s in restored["records"])]
    return {"E": len(escapes), "escapes": [(r["name"], r["family"], r["program"]) for r in escapes],
            "families_escaped": sorted({r["family"] for r in escapes}),
            "lost_by_restored": [(r["name"], r["candidates_to_solution"]) for r in lost]}


def corpus_lacking(found: dict, budget: int) -> dict:
    restored = found.get(("restored", "fresh1"))
    original = found.get(("original", "fresh1"))
    out = {}
    for routine in CORPUS_LACKING:
        for label, result in (("restored", restored), ("original", original)):
            if result is None:
                continue
            hits = [r for r in solved_at(result, budget) if r["family"] == routine]
            out[(routine, label)] = len(hits)
    return out


def score_predictions(found: dict, throughput: dict | None) -> list:
    b5, b6 = 100000, 1000000
    rows = []

    def n(vocab, part, b):
        result = found.get((vocab, part))
        return None if result is None else len(solved_at(result, b))

    r1 = n("restored", "fresh1", b5)
    rows.append(("P1-1", "restored FRESH-1 at 10^5 >= 15", "PASS (moderate)", f"{r1} of 33",
                 None if r1 is None else ("hit" if r1 >= 15 else "**miss**")))
    o1 = n("original", "fresh1", b5)
    rows.append(("P1-2", "original FRESH-1 at 10^5 <= 10", "PASS (moderate)", f"{o1} of 33",
                 None if o1 is None else ("hit" if o1 <= 10 else "**miss**")))
    lacking = corpus_lacking(found, b5)
    solved_routines = sum(1 for routine in CORPUS_LACKING if lacking.get((routine, "restored"), 0) > 0)
    rows.append(("P1-3", ">= 2 of the 5 corpus-lacking FRESH-1 routines solved (restored, 10^5)", "PASS (low)",
                 f"{solved_routines} routine(s): " + ", ".join(
                     f"{r} {lacking.get((r, 'restored'), 0)}" for r in CORPUS_LACKING),
                 "hit" if solved_routines >= 2 else "**miss**"))
    f2 = n("restored", "far2", b5)
    rows.append(("P1-4", "RESERVE-FAR2 >= 10 of 21 (restored, 10^5)", "PASS (moderate)", f"{f2} of 21",
                 None if f2 is None else ("hit" if f2 >= 10 else "**miss**")))
    if throughput:
        rate = throughput["candidates_per_second"]
        rows.append(("P1-5", "throughput >= 10^4 candidates/s/core", "PASS (low)", f"{rate:,.0f}/s",
                     "hit" if rate >= 10000 else "**miss**"))
    # secondary
    r6 = n("restored", "fresh1", b6)
    rows.append(("S1", "restored FRESH-1 at 10^6: 10 (range 7-14)", "—", f"{r6} of 33",
                 None if r6 is None else ("hit" if 7 <= r6 <= 14 else "**miss**")))
    o6 = n("original", "fresh1", b6)
    rows.append(("S2", "original FRESH-1 at 10^6 <= 8", "PASS (moderate)", f"{o6} of 33",
                 None if o6 is None else ("hit" if o6 <= 8 else "**miss**")))
    esc = closure_escape(found, "fresh1", b6)
    prime = any(f == "identify-is-prime" for _, f, _ in esc.get("escapes", []))
    rows.append(("S3", "E >= 1 at 10^6 on FRESH-1, identify-is-prime among the escapes", "PASS (moderate)",
                 f"E = {esc.get('E')}; families {esc.get('families_escaped')}",
                 None if esc.get("E") is None else ("hit" if esc["E"] >= 1 and prime else "**miss**")))
    s4 = []
    for part in ("fresh1", "far2"):
        a, b = n("restored", part, b6), n("original", part, b6)
        if a is not None and b is not None:
            s4.append((part, a, b))
    rows.append(("S4", "restored >= original on FRESH-1 and FAR2 at 10^6", "PASS (moderate)",
                 "; ".join(f"{p}: {a} vs {b}" for p, a, b in s4),
                 "hit" if s4 and all(a >= b for _, a, b in s4) else ("**miss**" if s4 else None)))
    rejected = sum(res["public_matches_rejected"] for res in found.values())
    rows.append(("S5", "zero public matches rejected by the verifier", "FAIL expected (1-5 rejections)",
                 f"{rejected} rejection(s) over {len(found)} result files",
                 "hit (prediction was FAIL)" if 1 <= rejected <= 5 else ("**miss** (0 rejections)" if rejected == 0 else "**miss** (more than 5)")))
    c24 = [n(v, "compose24", b6) for v in ("original", "restored")]
    rows.append(("S6", "COMPOSE-24 at 10^6 <= 4 with either vocabulary", "PASS (moderate)",
                 f"original {c24[0]}, restored {c24[1]}",
                 None if None in c24 else ("hit" if max(c24) <= 4 else "**miss**")))
    return rows


def predictions_table(rows) -> str:
    lines = ["| ID | Registered | Expected | Observed | Score |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) if c is not None else "(not run)" for c in row) + " |")
    return "\n".join(lines)


def compute_table(found: dict) -> str:
    lines = ["| Partition | Vocabulary | Tasks | Candidates evaluated | Wall s (4 workers) | Mean completed size (top) | Mean pool size | Digest |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for partition in PHASE1_ORDER:
        for vocabulary in ("original", "restored"):
            result = found.get((vocabulary, partition))
            if result is None:
                continue
            records = result["records"]
            cands = sum(r["candidates"] for r in records)
            size = sum(r["completed_size"] for r in records) / len(records)
            pool = sum(r["pool_size"] for r in records) / len(records)
            lines.append(f"| {PARTITIONS[partition][0]} | {vocabulary} | {len(records)} | {cands:,} | "
                         f"{result['wall_seconds']:,.0f} | {size:.1f} | {pool:,.0f} | `{result['digest'][:16]}` |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results_p1")
    args = parser.parse_args(argv)
    found = load_results(args.results)
    throughput_path = args.results / "throughput.json"
    throughput = json.loads(throughput_path.read_text()) if throughput_path.exists() else None
    print("## Headline\n")
    print(headline_table(found))
    print("\n## Predictions\n")
    print(predictions_table(score_predictions(found, throughput)))
    for budget in (100000, 1000000):
        print(f"\n## Closure escape at B = {budget:,}\n")
        for partition in PHASE1_ORDER:
            esc = closure_escape(found, partition, budget)
            if esc.get("E") is not None:
                print(f"- {PARTITIONS[partition][0]}: E = {esc['E']} {esc['families_escaped']}; "
                      f"lost by restored: {len(esc['lost_by_restored'])}")
    print("\n## FRESH-1 per task (B = 10^6)\n")
    print(per_task_table(found, "fresh1", 1000000))
    print("\n## RESERVE-FAR2 per task (B = 10^6)\n")
    print(per_task_table(found, "far2", 1000000))
    print("\n## Compute\n")
    print(compute_table(found))


if __name__ == "__main__":
    main()
