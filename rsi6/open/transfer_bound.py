"""How much of an edit's effect is shared across categories: the correlation of true effects.

    python -m rsi6.open.transfer_bound [--ledger PATH] [--stage discovery]

Post hoc and read-only. For every candidate screened in discovery, the paired difference of the
acquired score from its parent on the screening seed, per category, is read from the runs. Over
candidates, the covariance of these differences between two categories estimates the covariance
of the candidates' true effects (the runs of two categories share no instance and no draw, so
their noises are independent), while the variance within a category is the true variance plus
the noise variance. The noise variance per category is estimated from the confirmations (the
spread over seeds of one candidate's paired difference). Then

    rho(i, j) = cov(i, j) / sqrt((var(i) - noise(i)) * (var(j) - noise(j)))

is the correlation of true effects between categories i and j. Why it matters: a mechanism
accepted for its mean over the discovery categories helps a new category in expectation only to
the extent that its effect there is correlated with its effect on the categories it was chosen
on. Reported for all candidates, and for the candidates of edit cells chosen in advance (not by
their values) as the mild ones: the constants, the scalar numbers and the learning programs'
update, and the growth edits of the pick and score programs.

Categories whose differences are all zero are left out. Bootstrap intervals resample candidates.
The raw correlation of the observed differences is reported beside rho: noise only attenuates
it, so its size is a lower bound on the size of rho. Where the observed variance of a category
is not above the noise variance estimated from the confirmations (the noise of mild candidates
can differ from that of the confirmed ones), rho is not defined and the category is listed as
degenerate. A positive rho over all candidates can come from harm alone: an edit that breaks the
construction breaks it in every category.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from rsi6.open import edits
from rsi6.open.diagnose import LIVE, read

MILD = {("theta", "perturb"), ("theta", "grow"), ("scalar", "pop"), ("scalar", "batch"), ("scalar", "holdback"),
        ("scalar", "select"), ("update", "mutarg"), ("update", "mutop"), ("pick", "term"), ("pick", "cross"),
        ("score", "term"), ("score", "cross")}


def per_category(records, stage):
    runs = {r["key"]: r for r in records if r.get("type") == "run" and "key" in r}
    steps = [r for r in records if r.get("type") == "o_step" and r["lineage"].startswith(stage + ":")]
    rows, noise = [], {}
    for s in steps:
        parent_screen = None
        for c in s["candidates"]:
            if not c.get("runs_screen"):
                continue
            cand = [runs[k] for k in c["runs_screen"] if k in runs]
            rows.append({"cells": [tuple(edits.CELLS[i]) for i in c.get("cells", [])], "runs": cand, "step": s, "c": c})
            m = c.get("confirmation")
            if m:
                base = {(runs[k]["env"], runs[k]["seed"]): runs[k]["acquired"] for k in m["parent_runs"] if k in runs}
                for k in m["runs"]:
                    r = runs.get(k)
                    if r is not None and (r["env"], r["seed"]) in base:
                        noise.setdefault((id(c), r["env"]), []).append(r["acquired"] - base[(r["env"], r["seed"])])
    return runs, rows, noise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LIVE)
    parser.add_argument("--stage", default="discovery")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    records = read(args.ledger)
    runs, rows, noise = per_category(records, args.stage)
    # the parent's screening runs of each step: the lineage's start records on the screening seed
    by_version_cell = {}
    for r in runs.values():
        by_version_cell[(r["version"], r["env"], r["seed"], json.dumps(r["budget"], sort_keys=True))] = r
    table = []
    for row in rows:
        s = row["step"]
        diffs = {}
        for r in row["runs"]:
            p = by_version_cell.get((s["parent"], r["env"], r["seed"], json.dumps(r["budget"], sort_keys=True)))
            if p is not None:
                diffs[r["env"]] = r["acquired"] - p["acquired"]
        if diffs:
            table.append((row["cells"], diffs))
    envs = sorted({e for _, d in table for e in d})
    envs = [e for e in envs if any(abs(d.get(e, 0.0)) > 0 for _, d in table)]
    # noise per category: within-candidate spread over the four confirmation seeds
    nv = {}
    for (cid, e), v in noise.items():
        if len(v) >= 2:
            nv.setdefault(e, []).append(np.var(v, ddof=1))
    noise_var = {e: float(np.mean(nv[e])) for e in envs if e in nv}
    out = {"categories": envs, "noise_var_one_seed": noise_var}
    rng = np.random.default_rng(20261116)
    for label, keep in (("all candidates", lambda cells: True), ("mild cells (chosen in advance)", lambda cells: cells and all(c in MILD for c in cells))):
        X = np.array([[d.get(e, 0.0) for e in envs] for cells, d in table if keep(cells) and any(d.get(e, 0.0) != 0.0 for e in envs)])
        if len(X) < 8:
            out[label] = {"n": int(len(X))}
            continue

        def rho_of(M):
            C = np.cov(M, rowvar=False)
            res = {}
            for a in range(len(envs)):
                for b in range(a + 1, len(envs)):
                    ta = C[a, a] - noise_var.get(envs[a], 0.0)
                    tb = C[b, b] - noise_var.get(envs[b], 0.0)
                    res[f"{envs[a]}~{envs[b]}"] = float(C[a, b] / np.sqrt(ta * tb)) if ta > 0 and tb > 0 else None
            return res, C
        point, C = rho_of(X)
        boot = {k: [] for k in point}
        for _ in range(2000):
            idx = rng.integers(0, len(X), len(X))
            got, _ = rho_of(X[idx])
            for k, v in got.items():
                if v is not None and np.isfinite(v):
                    boot[k].append(v)
        raw = np.corrcoef(X, rowvar=False)
        out[label] = {"n": int(len(X)), "rho": point,
                      "raw_correlation": {f"{envs[a]}~{envs[b]}": float(raw[a, b]) for a in range(len(envs)) for b in range(a + 1, len(envs))},
                      "degenerate": [e for i, e in enumerate(envs) if C[i, i] <= noise_var.get(e, 0.0)],
                      "interval": {k: ([float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None) for k, v in boot.items()},
                      "covariance": np.round(C, 6).tolist(),
                      "true_sd": {e: (float(np.sqrt(max(0.0, C[i, i] - noise_var.get(e, 0.0))))) for i, e in enumerate(envs)},
                      "mean": {e: float(X[:, i].mean()) for i, e in enumerate(envs)}}
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
