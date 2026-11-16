"""The numbers of the open experiment (amendment 5), recomputed from the ledger.

    python -m rsi6.open.report [--ledger PATH] [--json OUT]

Prints the registered predictions (misses first), what every lineage of discovery did, the
selection, the swap test, the held-out comparisons with their intervals, signs and CPU, and the
success condition part by part. Nothing is typed by hand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.open import discovery, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def build(ledger, registration=None) -> dict | None:
    registered = find(ledger, type="registration_o")
    if registered is None and registration is None:
        return None
    reg = registered["registration"] if registered is not None else registration
    out = {"lineages": {}, "registration_digest": registered["digest"] if registered is not None else "development"}
    for r in ledger.select(type="o_lineage_done", stage="discovery"):
        steps = [s for s in ledger.select(type="o_step") if s["lineage"] == r["lineage"]]
        confirms = [c.get("confirmation") for s in steps for c in s["candidates"] if c.get("confirmation")]
        out["lineages"][r["lineage"]] = {
            "arm": r["arm"], "steps": r["steps"], "spent": r["spent"], "accepted": len(r["accepted"]),
            "principle_changes": int(sum(a["principle_changed"] for a in r["accepted"])),
            "confirmations_tried": len(confirms), "confirmations_passed": int(sum(c["passed"] for c in confirms)),
            "candidates": int(sum(1 for s in steps for c in s["candidates"] if c.get("digest"))),
            "final_digest": r["final_digest"], "final_score_on_discovery_seeds": r["final_score"]}
    sel = find(ledger, type="o_stage_done", stage="selection")
    if sel:
        out["selection"] = {"finals": sel["finals"], "table": sel["table"]}
    swap = find(ledger, type="o_stage_done", stage="swap")
    if swap:
        out["swap"] = {k: swap.get(k) for k in ("exercised", "why", "pairs", "mean_difference", "positive", "from")}
    for label, stage in (("heldout", "heldout"), ("heldout_later", "heldout_later")):
        held = find(ledger, type="o_stage_done", stage=stage)
        if held:
            out[label] = heldout_section(ledger, held, stage)
    return endpoints(reg, out)


def heldout_section(ledger, held, stage) -> dict:
    if True:
        by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}
        arms = {name: [dict(by_key[k]) for k in keys] for name, keys in held["arms"].items()}
        matched = {r["arm"]: r for r in ledger.select(type="o_matched") if r.get("stage", "heldout") == stage}
        for name, m in matched.items():
            for row, reached in zip(arms[name], m["reached"]):
                row["reached"] = reached
        comp = {}
        # the registered comparisons: the recursive arm against every control given its CPU
        pairs = [("recursive", f"{c}@recursive", True) for c in ("o0", "a0", "frozen", "uniform", "shuffled", "tune")]
        # reported beside them, not evidence: equal counted units, and the other lineage of every arm
        pairs += [("recursive", c, False) for c in ("o0", "a0", "frozen", "uniform", "shuffled", "tune")]
        pairs += [(arm, "o0", False) for arm in ("frozen", "uniform", "shuffled", "tune")]
        pairs += [(f"{arm}:other", arm, False) for arm in ("recursive", "frozen", "uniform", "shuffled", "tune") if f"{arm}:other" in arms]
        for a, b, control in pairs:
            comp[f"{a} minus {b}"] = evaluate.compare(arms[a], arms[b], name=f"{a} minus {b}", control=control)
        versions = held.get("versions", {})
        return {"envs": held["envs"], "seeds": held["seeds"], "comparisons": comp,
                "finals_other_than_o0": sorted(a for a in ("recursive", "frozen", "uniform", "shuffled", "tune")
                                               if versions.get(a) and versions.get(a) != versions.get("o0")),
                "arms": {name: {"acquired": float(np.mean([r["acquired"] for r in rows])),
                                "untrained": float(np.mean([r["untrained"] for r in rows])),
                                "gain": float(np.mean([r["gain"] for r in rows])),
                                "cpu_per_run": float(np.mean([evaluate.cpu(r) for r in rows]))} for name, rows in arms.items()},
                "matched": {name: {"reached": int(sum(m["reached"])), "of": len(m["reached"])} for name, m in matched.items()}}


def endpoints(reg, out) -> dict:
    """The endpoints and the success condition of registration_o.json, from the first held-out stage."""
    parts = {}
    rec = [v for v in out["lineages"].values() if v["arm"] == "recursive"]
    if "heldout" in out:
        e1 = out["heldout"]["comparisons"]["recursive minus o0@recursive"]
        point, low, _ = e1["min_change"]
        parts["E1"] = bool(not e1["void"] and point >= 0.01 and low > 0.0)      # a void comparison does not meet E1
        e3b = out["heldout"]["comparisons"]["recursive minus frozen@recursive"]
        parts["E3b"] = bool(not e3b["void"] and e3b["min_change"][0] > 0.0)
    if rec and "swap" in out:
        parts["E3a"] = bool(sum(v["principle_changes"] for v in rec) > 0) and bool(out["swap"]["exercised"])
        parts["E3c"] = bool(out["swap"]["exercised"] and out["swap"]["mean_difference"] >= reg["swap"]["threshold"]) \
            if out["swap"]["exercised"] else False
    keys = ("E1", "E3a", "E3b", "E3c")
    if all(k in parts for k in keys):
        out["success"] = False if any(parts[k] is False for k in keys) else (True if all(parts[k] is True for k in keys) else None)
    else:
        out["success"] = None
    out["success_parts"] = parts
    out["predictions"] = predictions(reg, out)
    return out


def predictions(reg, out) -> list:
    texts = {p["id"]: p for p in reg["predictions"]}
    res = []

    def add(pid, holds, detail):
        res.append({"id": pid, "text": texts[pid]["text"], "criterion": texts[pid]["criterion"], "holds": holds, "detail": detail})

    rec = {k: v for k, v in out["lineages"].items() if v["arm"] == "recursive"}
    add("O1", bool(rec and all(v["accepted"] >= 1 for v in rec.values())) if rec else None, {k: v["accepted"] for k, v in rec.items()})
    held = out.get("heldout")
    if held:
        others = held["finals_other_than_o0"]
        e1 = held["comparisons"]["recursive minus o0@recursive"]
        add("O2", bool(e1["void"] or e1["min_change"][0] < 0.01 or e1["min_change"][1] <= 0.0),
            {"interval": e1["min_change"], "void": e1["void"], "arms whose final is not generation 0": others})
        e2 = held["comparisons"]["recursive minus uniform@recursive"]
        add("O3", bool(e2["void"] or e2["min_change"][1] <= 0.0 <= e2["min_change"][2]),
            {"interval": e2["min_change"], "void": e2["void"], "arms whose final is not generation 0": others})
    else:
        add("O2", None, "the held-out stage has not run")
        add("O3", None, "the held-out stage has not run")
    add("O4", bool(sum(v["principle_changes"] for v in rec.values()) >= 1) if rec else None,
        {k: v["principle_changes"] for k, v in rec.items()})
    swap = out.get("swap")
    add("O5", None if swap is None else bool((not swap["exercised"]) or swap["mean_difference"] < reg["swap"]["threshold"]),
        swap and (swap.get("mean_difference"), swap.get("positive"), swap.get("why")))
    return res


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--json", default=None)
    parser.add_argument("--registration", default=None, help="development only: a registration file for a ledger that holds none")
    args = parser.parse_args()
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    out = build(ledger, json.load(open(args.registration)) if args.registration else None)
    if out is None:
        print("the open experiment is not registered in this ledger")
        return 0
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)
    print("PREDICTIONS (misses first)")
    for p in sorted(out["predictions"], key=lambda p: (p["holds"] is not False, p["id"])):
        mark = {True: "held", False: "MISSED", None: "not scored"}[p["holds"]]
        print(f"  {p['id']} {mark:10s} {p['text']} | {p['criterion']} | measured: {p['detail']}")
    print("\nDISCOVERY, per lineage (the score on the discovery seeds is the selected one, biased upward)")
    for name, v in out["lineages"].items():
        print(f"  {name:24s} steps {v['steps']:3d} spent {v['spent']:7.0f} candidates {v['candidates']:3d} confirmations "
              f"{v['confirmations_passed']}/{v['confirmations_tried']} accepted {v['accepted']} (principle changes {v['principle_changes']}) "
              f"final {v['final_digest'][:12]} {v['final_score_on_discovery_seeds']:.4f}")
    if "selection" in out:
        print("\nSELECTION on the confirming half of the discovery categories, fresh seeds: minus o0")
        for name, v in out["selection"]["table"].items():
            print(f"  {name:24s} {v['minus_o0']:+.4f}{'  <- final of its arm' if out['selection']['finals'][v['arm']] == name else ''}")
    if "swap" in out:
        print("\nSWAP TEST:", out["swap"])
    for label in ("heldout", "heldout_later"):
        if label not in out:
            continue
        h = out[label]
        print(f"\n{label.upper()} {h['envs']} seeds {h['seeds']}; matched controls {h['matched']}")
        for name, a in h["arms"].items():
            print(f"  {name:14s} untrained {a['untrained']:.4f} acquired {a['acquired']:.4f} gain {a['gain']:+.4f} cpu/run {a['cpu_per_run']:.1f}")
        for name, c in h["comparisons"].items():
            m = c["min_change"]
            print(f"  {name:30s} min-change {m[0]:+.4f} [{m[1]:+.4f}, {m[2]:+.4f}] all categories positive {c['all_categories_positive']}"
                  f" | acquired {c['acquired_change'][0]:+.4f} untrained {c['untrained_change'][0]:+.4f} gain {c['gain_change'][0]:+.4f}"
                  f" | cpu x{c['cpu_ratio']:.2f}" + (" | VOID" if c["void"] else "") + f" | per category {c['per_env']}")
    print("\nSUCCESS CONDITION, part by part:", out["success_parts"], "->", {True: "met", False: "not met", None: "not decided"}[out["success"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
