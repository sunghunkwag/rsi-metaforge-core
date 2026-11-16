"""What limits discovery: the noise of a step's measurements against the effects of its edits.

    python -m rsi6.open.diagnose [--ledger PATH] [--stage discovery] [--json OUT]

Post hoc and read-only: it reads the ledger (a last line still being written is left out) and
prints, from the recorded steps and runs of the open experiment,

* per lineage: steps, CPU, candidates, the share whose screening value is exactly zero (edits
  that change nothing the runs measure), confirmations tried and passed;
* the noise of one run: the spread over seeds of one mechanism's acquired score on one category
  (the fresh instances do not depend on the seed, so this is the run's own randomness), and of a
  paired difference, candidate minus parent on the same seed;
* the reliability of screening: the correlation of a candidate's value on the screening seed
  with its value on the two other discovery seeds;
* the winner's curse: what a confirmed candidate was worth on the discovery seeds and what it
  was worth on the four confirmation seeds, which no selection touched;
* the smallest mean difference that the registered rule can accept with the measured noise, and
  the effect of the edits the step chose, estimated without selection bias.

None of this is evidence for or against an endpoint of the registration; it describes the
measurements that decided the steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.open import edits

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "ledger", "live.jsonl")


def read(path: str) -> list:
    """The complete records of a ledger that may be written while it is read, chain checked."""
    records = []
    with open(path) as handle:
        lines = handle.read().split("\n")
    for k, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if k >= len(lines) - 2:          # the last line, still being written
                break
            raise
    prev = ledgers.GENESIS
    for i, r in enumerate(records):
        body = {k: v for k, v in r.items() if k != "h"}
        if r["idx"] != i or r["prev"] != prev or hashlib.sha256((prev + ledgers.canon(body)).encode()).hexdigest() != r["h"]:
            raise AssertionError(f"ledger chain broken at {i}")
        prev = r["h"]
    return records


def corr(x, y) -> float | None:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def diagnose(records: list, stage: str = "discovery", t_rule: float = 2.6, margin: float = 0.005) -> dict:
    runs = {r["key"]: r for r in records if r.get("type") == "run" and "key" in r}
    steps = [r for r in records if r.get("type") == "o_step" and r["lineage"].startswith(stage + ":")]
    out = {"steps": len(steps), "lineages": {}}

    # per lineage
    for s in steps:
        L = out["lineages"].setdefault(s["lineage"], {"steps": 0, "spent": 0.0, "candidates": 0, "zero": 0, "positive": 0,
                                                       "promoted": 0, "confirmations": 0, "passed": 0, "accepted": 0})
        L["steps"] += 1
        L["spent"] = s["spent"]
        L["accepted"] += int(bool(s.get("accepted")))
        for c in s["candidates"]:
            if c.get("screen") is None:
                continue
            L["candidates"] += 1
            L["zero"] += int(c["screen"] == 0.0)
            L["positive"] += int(c["screen"] > 0.0)
            L["promoted"] += int(c.get("promoted") is not None)
            if c.get("confirmation"):
                L["confirmations"] += 1
                L["passed"] += int(bool(c["confirmation"]["passed"]))

    # the noise of one run: one mechanism, one category, several seeds, the same budget and part
    by_cell = {}
    for r in runs.values():
        b = r.get("budget", {})
        if b.get("part") not in ("A", "B"):
            continue
        by_cell.setdefault((r["env"], r["version"], b.get("part"), b.get("n_train")), []).append(r["acquired"])
    spread = {}
    for (env, _, _, _), values in by_cell.items():
        if len(values) >= 3:
            spread.setdefault(env, []).append(float(np.std(values, ddof=1)))
    out["run_sd_by_category"] = {e: float(np.median(v)) for e, v in sorted(spread.items())}

    # paired differences in the confirmations: candidate minus parent, per category
    diffs, conf = {}, []
    for s in steps:
        for c in s["candidates"]:
            m = c.get("confirmation")
            if not m:
                continue
            cand = [runs[k] for k in m["runs"] if k in runs]
            base = {(runs[k]["env"], runs[k]["seed"]): runs[k] for k in m["parent_runs"] if k in runs}
            for r in cand:
                b = base.get((r["env"], r["seed"]))
                if b is not None:
                    diffs.setdefault(r["env"], []).append(r["acquired"] - b["acquired"])
            conf.append({"lineage": s["lineage"], "step": s["step"], "screen": c["screen"], "promoted": c.get("promoted"),
                         "confirmed_mean": m["mean"], "sd": m["sd"], "t": m["t"], "passed": m["passed"],
                         "cpu_ratio": m.get("cpu_ratio_to_parent")})
    out["paired_sd_by_category"] = {e: float(np.std(v, ddof=1)) for e, v in sorted(diffs.items()) if len(v) >= 3}
    out["paired_mean_by_category"] = {e: float(np.mean(v)) for e, v in sorted(diffs.items()) if v}
    sds = [c["sd"] for c in conf]
    out["confirmation_sd_median"] = float(np.median(sds)) if sds else None
    if sds:
        n = 16
        out["smallest_acceptable_mean"] = float(max(margin / 2, t_rule * np.median(sds) / np.sqrt(n)))

    # reliability of screening and the winner's curse
    promoted = [(c["screen"], c["promoted"]) for s in steps for c in s["candidates"] if c.get("promoted") is not None]
    out["screen_vs_promoted"] = {"n": len(promoted), "correlation": corr(*zip(*promoted)) if len(promoted) >= 3 else None}
    if conf:
        out["confirmations"] = {
            "n": len(conf), "passed": int(sum(c["passed"] for c in conf)),
            "mean_value_on_discovery_seeds": float(np.mean([c["promoted"] for c in conf])),
            "mean_value_on_confirmation_seeds": float(np.mean([c["confirmed_mean"] for c in conf])),
            "share_confirmed_positive": float(np.mean([c["confirmed_mean"] > 0 for c in conf])),
            "t": [round(c["t"], 2) for c in conf]}
        out["confirmation_rows"] = conf

    # the edits: by cell, the screening value (all candidates screened; none of this is selected)
    cells = {}
    for s in steps:
        for c in s["candidates"]:
            if c.get("screen") is None:
                continue
            for cell in c.get("cells", []):
                name = "/".join(edits.CELLS[cell]) if isinstance(cell, int) else str(cell)
                cells.setdefault(name, []).append(c["screen"])
    out["cells"] = {k: {"n": len(v), "mean_screen": float(np.mean(v)), "zero": float(np.mean(np.array(v) == 0.0))}
                    for k, v in sorted(cells.items(), key=lambda kv: -len(kv[1]))}

    # the spread of the true effects of screened candidates: variance of the screening values
    # minus the variance that noise alone gives one seed over the categories
    screens = np.array([c["screen"] for s in steps for c in s["candidates"] if c.get("screen") not in (None, 0.0)])
    if len(screens) >= 5 and out["paired_sd_by_category"]:
        k = len(out["paired_sd_by_category"])
        noise_var = float(np.mean([v ** 2 for v in out["paired_sd_by_category"].values()]) / k)
        out["screen_spread"] = {"n_nonzero": int(len(screens)), "sd_screen": float(screens.std(ddof=1)),
                                "sd_noise_one_seed": float(np.sqrt(noise_var)),
                                "sd_true_effect_estimate": float(np.sqrt(max(0.0, screens.var(ddof=1) - noise_var))),
                                "mean_screen": float(screens.mean())}
    out["cpu"] = {"total_spent_by_lineages": float(sum(L["spent"] for L in out["lineages"].values()))}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LIVE)
    parser.add_argument("--stage", default="discovery")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    out = diagnose(read(args.ledger), args.stage)
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)
    print(f"{out['steps']} steps of {args.stage}")
    for name, L in sorted(out["lineages"].items()):
        print(f"  {name:26s} steps {L['steps']:3d} spent {L['spent']:7.0f} candidates {L['candidates']:3d} zero {L['zero']:3d} "
              f"positive {L['positive']:3d} promoted {L['promoted']:3d} confirmations {L['passed']}/{L['confirmations']} accepted {L['accepted']}")
    print("run noise (median sd over seeds of one mechanism's acquired score):", {k: round(v, 4) for k, v in out["run_sd_by_category"].items()})
    print("paired noise in confirmations (sd of candidate minus parent):", {k: round(v, 4) for k, v in out["paired_sd_by_category"].items()})
    print("paired mean in confirmations:", {k: round(v, 4) for k, v in out["paired_mean_by_category"].items()})
    print("confirmation sd (median):", out["confirmation_sd_median"], "| smallest mean the rule accepts:", out.get("smallest_acceptable_mean"))
    print("screen vs promoted:", out["screen_vs_promoted"])
    if "confirmations" in out:
        c = out["confirmations"]
        print(f"confirmations: {c['passed']}/{c['n']} passed; value on discovery seeds {c['mean_value_on_discovery_seeds']:+.4f}, "
              f"on confirmation seeds {c['mean_value_on_confirmation_seeds']:+.4f}; positive there {c['share_confirmed_positive']:.2f}; t {c['t']}")
    if "screen_spread" in out:
        print("screening values (non-zero):", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out["screen_spread"].items()})
    print("cells (n, mean screening value, share exactly zero):")
    for k, v in out["cells"].items():
        print(f"  {k:24s} {v['n']:4d} {v['mean_screen']:+.4f} {v['zero']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
