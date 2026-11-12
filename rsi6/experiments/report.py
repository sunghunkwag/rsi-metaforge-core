"""Every reported number, recomputed from the ledger.

    python -m rsi6.experiments.report [--ledger PATH] [--json OUT]

Prints, in this order: the registered predictions scored (misses first), the rounds (what each
improver found, what the gate decided, what the confirmation half measured), the comparison in
which only the improver differs, and the test on the target categories with its controls.
Nothing here is typed by hand: a table that cannot be computed from the ledger is not printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.learner import version as versions

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration.json")


def paired_min(base, other) -> np.ndarray:
    return np.array([min(o["acquired"] - b["acquired"], o["gain"] - b["gain"]) for b, o in zip(base, other)])


def by_key(ledger) -> dict:
    return {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}


def blocked_interval(values: dict, rng, draws: int = 5000, level: float = 0.95):
    """``values``: category -> array over seeds. Mean over categories of the mean over seeds,
    with an interval that resamples categories and, within each, seeds."""
    names = sorted(values)
    point = float(np.mean([np.mean(values[n]) for n in names]))
    means = []
    for _ in range(draws):
        chosen = rng.choice(len(names), size=len(names))
        means.append(np.mean([np.mean(rng.choice(values[names[k]], size=len(values[names[k]]))) for k in chosen]))
    low, high = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return point, float(low), float(high)


def changes_by_function(changes: dict) -> dict:
    out = {}
    for name, change in (changes or {}).items():
        out.setdefault(change["function"], []).append(f"{name}: {change['from']} -> {change['to']}")
    return out


def rounds_section(ledger) -> dict:
    out = {"rounds": []}
    for done in ledger.select(type="round_done"):
        g = done["round"]
        entry = {"round": g, "searches": {}, "gates": {}, "confirmations": {}, "adopted": {}}
        for record in ledger.select(type="search", round=g):
            entry["searches"][record["name"]] = {
                "improver": record["improver"], "evaluated": record["evaluated"], "improving": record["improving"],
                "best_cost": record["best_cost"], "cpu_used": round(record["cpu_used"], 1), "cpu_limit": record["cpu_limit"],
                "nominee": record["nominee"], "changes": changes_by_function(record["nominee_changes"]),
                "brier": record["brier"]}
        for record in ledger.select(type="gate", round=g):
            entry["gates"][record["name"]] = {k: record[k] for k in ("adopted", "conditions", "mean_min", "mean_gain_change",
                                                                    "mean_acquired_change", "gain_lower_bound", "cpu_ratio", "per_env")}
        for record in ledger.select(type="confirm", round=g):
            entry["confirmations"][record["name"]] = {k: record[k] for k in ("mean_min", "mean_gain_change", "mean_acquired_change", "runs")}
        for record in ledger.select(type="adopt", round=g):
            entry["adopted"][record["lineage"]] = {"digest": record["digest"], "changes": changes_by_function(record["changes"])}
        out["rounds"].append(entry)
    return out


def targets_section(ledger, reg) -> dict | None:
    done = ledger.select(type="target_done")
    if not done:
        return None
    done, runs = done[-1], by_key(ledger)
    arms = {arm: [runs[k] for k in keys] for arm, keys in done["arms"].items()}
    rng = np.random.default_rng(0)
    table = {}
    for arm, records in arms.items():
        envs = sorted({r["env"] for r in records})
        table[arm] = {"per_env": {}, "cpu_per_run": float(np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in records]))}
        for env in envs:
            rows = [r for r in records if r["env"] == env]
            table[arm]["per_env"][env] = {
                "untrained": float(np.mean([r["untrained"] for r in rows])), "acquired": float(np.mean([r["acquired"] for r in rows])),
                "gain": float(np.mean([r["gain"] for r in rows])), "train_acquired": float(np.mean([r["train_acquired"] for r in rows])),
                "threshold": rows[0]["threshold"],
                "reached": bool(np.mean([r["acquired"] for r in rows]) >= rows[0]["threshold"] > np.mean([r["untrained"] for r in rows]))}
        for field in ("untrained", "acquired", "gain"):
            table[arm][field] = float(np.mean([v[field] for v in table[arm]["per_env"].values()]))
        table[arm]["categories_reached"] = int(sum(v["reached"] for v in table[arm]["per_env"].values()))
    comparisons = {}
    base = arms["frozen"]

    def compare(name, other, reference=base):
        values, acquired, gain = {}, {}, {}
        for env in sorted({r["env"] for r in reference}):
            b = sorted((r for r in reference if r["env"] == env), key=lambda r: r["seed"])
            o = sorted((r for r in other if r["env"] == env), key=lambda r: r["seed"])
            values[env] = paired_min(b, o)
            acquired[env] = np.array([y["acquired"] - x["acquired"] for x, y in zip(b, o)])
            gain[env] = np.array([y["gain"] - x["gain"] for x, y in zip(b, o)])
        comparisons[name] = {"min_change": blocked_interval(values, rng), "acquired_change": blocked_interval(acquired, rng),
                             "gain_change": blocked_interval(gain, rng)}

    for arm in arms:
        if arm != "frozen":
            compare(f"{arm} minus frozen", arms[arm])
    primary = done["primary_arm"]
    for arm in ("fixed", "random", "skills", "compute", "search"):
        if arm in arms and primary in arms and primary != "frozen":
            compare(f"{primary} minus {arm}", arms[primary], arms[arm])
    gen0 = {env: np.array([r["gain"] for r in base if r["env"] == env]) for env in sorted({r["env"] for r in base})}
    matched = {r["arm"]: {"share_per_run": r["share_per_run"], "reached": int(sum(r["reached"])), "of": len(r["reached"])}
               for r in ledger.select(type="matched")}
    return {"arms": table, "comparisons": comparisons, "primary_arm": primary, "generation0_gain": blocked_interval(gen0, rng),
            "matched": matched, "targets": done["targets"], "seeds": done["seeds"]}


def score_predictions(reg, rounds, targets, ledger) -> list:
    out = []
    by_round = {r["round"]: r for r in rounds["rounds"]}

    def add(pid, outcome, detail):
        text = next(p for p in reg["predictions"] if p["id"] == pid)
        out.append({"id": pid, "text": text["text"], "criterion": text["criterion"], "holds": outcome, "detail": detail})

    if 1 in by_round:
        s = by_round[1]["searches"].get("self")
        add("R1", None if s is None else bool(s["best_cost"] is not None and s["best_cost"] <= -0.005), s and s["best_cost"])
        g = by_round[1]["gates"].get("self")
        add("R2", (s is not None and s["nominee"] is None) or (g is not None and not g["adopted"]), g and g["mean_min"])
    if len(by_round) >= reg["rounds_planned"]:
        count = len(ledger.select(type="adopt", lineage="self"))
        add("R3", count <= 1, count)
        seen = []
        for g, entry in by_round.items():
            a, b = entry["searches"].get("self"), entry["searches"].get("random")
            if a and b and a["best_cost"] is not None and b["best_cost"] is not None:
                seen.append(b["best_cost"] <= a["best_cost"])
        add("R4", any(seen) if seen else None, seen)
    if targets:
        primary = targets["comparisons"].get(f"{targets['primary_arm']} minus frozen")
        if primary:
            point, low, high = primary["min_change"]
            add("R5", bool(point < 0.01 or low <= 0.0), [point, low, high])
        else:
            add("R5", True, "no version was adopted by the self lineage, so there is nothing to compare")
        if "skills minus frozen" in targets["comparisons"]:
            point = targets["comparisons"]["skills minus frozen"]["acquired_change"][0]
            add("R6", bool(point < 0.005), point)
        reached = targets["arms"]["frozen"]["categories_reached"]
        add("R7", bool(1 <= reached <= len(targets["targets"]) - 1), reached)
        point, low, high = targets["generation0_gain"]
        add("R8", bool(point > 0 and low > 0), [point, low, high])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    reg = json.load(open(REGISTRATION))
    rounds = rounds_section(ledger)
    targets = targets_section(ledger, reg)
    predictions = score_predictions(reg, rounds, targets, ledger)
    runs = [r for r in ledger.records if r.get("type") == "run"]
    report = {"ledger_head": ledger.head(), "records": len(ledger.records), "runs": len(runs),
              "cpu_seconds": round(float(sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in runs)), 1),
              "predictions": predictions, **rounds, "targets": targets}
    if args.json:
        json.dump(report, open(args.json, "w"), indent=1)
    print(f"ledger: {len(ledger.records)} records, {len(runs)} runs, {report['cpu_seconds']} CPU-seconds, head {ledger.head()[:16]}")
    print("\nPREDICTIONS (misses first)")
    for p in sorted(predictions, key=lambda p: (p["holds"] is not False, p["id"])):
        mark = {True: "held", False: "MISSED", None: "not scored"}[p["holds"]]
        print(f"  {p['id']} {mark:10s} {p['text']} | {p['criterion']} | measured: {p['detail']}")
    for entry in rounds["rounds"]:
        print(f"\nROUND {entry['round']}")
        for name, s in entry["searches"].items():
            print(f"  search {name:12s} evaluated {s['evaluated']:3d} improving {s['improving']:3d} best {s['best_cost']} cpu {s['cpu_used']} "
                  f"changes {s['changes'] if s['changes'] else None}")
        for name, g in entry["gates"].items():
            print(f"  gate   {name:12s} adopted {g['adopted']} | min-change {g['mean_min']:+.4f} gain {g['mean_gain_change']:+.4f} "
                  f"acquired {g['mean_acquired_change']:+.4f} lower bound {g['gain_lower_bound']:+.4f} cpu x{g['cpu_ratio']:.2f} {g['conditions']}")
            for env, v in g["per_env"].items():
                print(f"           {env:12s} gain {v['gain_change']:+.4f} acquired {v['acquired_change']:+.4f}")
        for name, c in entry["confirmations"].items():
            print(f"  confirm {name:11s} min-change {c['mean_min']:+.4f} gain {c['mean_gain_change']:+.4f} acquired {c['mean_acquired_change']:+.4f} ({c['runs']} runs)")
        for name, a in entry["adopted"].items():
            print(f"  ADOPTED by {name}: {a['changes']}")
    if targets:
        print(f"\nTARGETS {targets['targets']}, seeds {targets['seeds']}; primary arm {targets['primary_arm']}")
        for arm, t in targets["arms"].items():
            print(f"  {arm:10s} untrained {t['untrained']:.4f} acquired {t['acquired']:.4f} gain {t['gain']:+.4f} "
                  f"categories reached {t['categories_reached']} cpu/run {t['cpu_per_run']:.1f}")
            for env, v in t["per_env"].items():
                print(f"      {env:14s} untrained {v['untrained']:.4f} acquired {v['acquired']:.4f} gain {v['gain']:+.4f} "
                      f"(training instances {v['train_acquired']:.4f}) threshold {v['threshold']:.3f} reached {v['reached']}")
        for name, c in targets["comparisons"].items():
            print(f"  {name:28s} min-change {c['min_change'][0]:+.4f} [{c['min_change'][1]:+.4f}, {c['min_change'][2]:+.4f}] "
                  f"acquired {c['acquired_change'][0]:+.4f} [{c['acquired_change'][1]:+.4f}, {c['acquired_change'][2]:+.4f}] "
                  f"gain {c['gain_change'][0]:+.4f} [{c['gain_change'][1]:+.4f}, {c['gain_change'][2]:+.4f}]")
        print("  generation 0 gain on targets: %+.4f [%+.4f, %+.4f]" % tuple(targets["generation0_gain"]))
        print("  compute matching:", targets["matched"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
