"""Replay a J ledger: recompute every logged decision from the logged inputs (red-team R7).

    python -m rsi4.judge.replay PATH/judge_log.jsonl

The chain is checked first (``ledger.verify``). Then each decision is derived
again from what the ledger itself recorded, with J's decision functions:

- ``evaluate``: the pooled count from the per-seed verdicts (2 of 3 seeds);
- ``sleep_check``: keep or revert from the before/after pooled outcomes;
- ``select``: the selected candidate from the logged solve counts, in the
  logged candidate order;
- ``confirm`` and ``final_test``: the pairs, the sign test and the decision
  from the two sides' pooled outcomes and the pool size;
- ``compare`` and ``metrics``: recomputed from the evaluations they cite.

Any difference is reported as a mismatch. An empty list means every decision
in the ledger follows from its inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import adopt, ledger, metrics, pools, sleep_check
from .registry import JUDGE_DIR, SOLVED_MIN_SEEDS


def _union(results):
    merged = {}
    for result in results:
        for name, solved in result["pooled"]["tasks"].items():
            merged[f"{result['pool']}/{name}"] = solved
    return merged


def _pairs_match(logged: dict, again: dict) -> bool:
    return all(logged[k] == again[k] for k in ("tasks", "wins", "losses", "p"))


def _check(op: str, r: dict, judge_dir: Path) -> list[str]:
    bad = []
    if op == "evaluate":
        names = list(r["pooled"]["tasks"])
        for name in names:
            count = sum(bool(s["verdicts"].get(name)) for s in r["per_seed"].values())
            if (count >= SOLVED_MIN_SEEDS) != r["pooled"]["tasks"][name]:
                bad.append(f"pooled verdict of {name}")
        if sum(r["pooled"]["tasks"].values()) != r["pooled"]["solved"]:
            bad.append("pooled count")
    elif op == "sleep_check":
        again = sleep_check.decide(r["before"]["pooled"]["tasks"], r["after"]["pooled"]["tasks"])
        bad += [k for k in ("decision", "wins", "losses") if again[k] != r[k]]
    elif op == "select":
        again = adopt.decide_select(r["incumbent"]["pooled"]["solved"],
                                    [(c, r["candidates"][c]["pooled"]["solved"])
                                     for c in r["candidate_order"]])
        bad += [k for k in ("selected", "best") if again[k] != r[k]]
    elif op == "confirm":
        paired = adopt.pairs(r["incumbent"]["pooled"]["tasks"], r["candidate"]["pooled"]["tasks"])
        complete = r["incumbent"]["complete"] and r["candidate"]["complete"]
        expected = len(pools.load_records(r["pool"], judge_dir)) if complete else -1
        again = adopt.decide_confirm(paired, expected)
        if not _pairs_match(r["pairs"], paired):
            bad.append("pairs")
        bad += [k for k in ("adopt", "complete", "significant", "within_budget") if again[k] != r[k]]
    elif op == "final_test":
        base = _union([r["parts"][p]["theta_0"] for p in sorted(r["parts"])])
        star = _union([r["parts"][p]["theta_star"] for p in sorted(r["parts"])])
        paired = adopt.pairs(base, star)
        complete = all(v["complete"] for part in r["parts"].values() for v in part.values())
        expected = sum(len(pools.load_records(p, judge_dir)) for p in r["parts"]) if complete else -1
        again = adopt.decide_final(paired, expected)
        if not _pairs_match(r["pairs"], paired):
            bad.append("pairs")
        bad += [k for k in ("pass", "complete", "significant", "within_budget") if again[k] != r[k]]
    elif op == "compare":
        ps = []
        for row in r["comparisons"]:
            cand = [ledger.entry_at(Path(p), int(i))["result"] for p, i in row["candidate_refs"]]
            base = [ledger.entry_at(Path(p), int(i))["result"] for p, i in row["baseline_refs"]]
            paired = adopt.pairs(_union(base), _union(cand))
            if not _pairs_match(row["pairs"], paired):
                bad.append(f"pairs of {row['name']}")
            ps.append(paired["p"])
        for row, reject in zip(r["comparisons"], adopt.holm(ps)):
            if row["holm_reject_null"] != reject:
                bad.append(f"Holm decision of {row['name']}")
    elif op == "metrics":
        outcomes = {}
        for key, (p, i) in r["refs"].items():
            a, b = (int(x) for x in key.split(","))
            outcomes[(a, b)] = ledger.entry_at(Path(p), int(i))["result"]["pooled"]["tasks"]
        again = metrics.compute(outcomes)
        bad += [k for k in ("R", "point", "ci95") if again[k] != r[k]]
    return bad


def replay(path: Path, judge_dir: Path = JUDGE_DIR) -> dict:
    lines = ledger.verify(path)
    mismatches, checked = [], 0
    for line in lines:
        entry = line["entry"]
        op, result = entry.get("op"), entry.get("result")
        if result is None or op not in ("evaluate", "sleep_check", "select", "confirm",
                                        "final_test", "compare", "metrics"):
            continue
        checked += 1
        for problem in _check(op, result, Path(judge_dir)):
            mismatches.append(f"line {line['index']} ({op}): {problem}")
    return {"entries": len(lines), "decisions_checked": checked, "mismatches": mismatches}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(replay(args.ledger), indent=1))


if __name__ == "__main__":
    main()
