#!/usr/bin/env python3
"""Phase 0 instrument generator: docs/frozen_holdout_phase0.json.

Materializes the designer sealed suite's existing dual-gate evaluation data
for the top synthesis core of rsi_levels_metaforge_unified.py:

  - holdout gate: seed GATE_SEED, lengths HOLDOUT_LENGTHS, GATE_TRIALS
    trials per length, values in [0, 7]  (mirrors seal_task/_make_gate)
  - counterfactual gate: seed CF_GATE_SEED, lengths CF_LENGTHS, CF_TRIALS
    trials per length, values in [0, CF_VALMAX]

For each designer task Tnn the input vectors are exactly the vectors an
invocation of the sealed gate generates (same RNG protocol as _make_gate:
one random.Random(seed) stream, lengths outer loop, trials inner loop),
and the expected output is the task oracle applied to that vector.

Only pre-existing designer task definitions (ORACLES) are used. Generated
(minted) tasks are excluded by construction. Output serialization is
deterministic (sort_keys, fixed indent); the SHA-256 of the file is
recorded in docs/BASELINE_FRONTIER.md and checked by a test.

Usage:  python3 docs/make_frozen_holdout_phase0.py
        (run from the repository root; writes docs/frozen_holdout_phase0.json)
"""
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rsi_levels_metaforge_unified as m


def gate_pairs(oracle, seed, lengths, trials, valmax):
    rng = random.Random(seed)
    pairs = []
    for L in lengths:
        for _ in range(trials):
            xs = [rng.randint(0, valmax) for _ in range(L)]
            pairs.append([xs, int(oracle(list(xs)))])
    return pairs


def build():
    tasks = {}
    for i, (name, family, fn) in enumerate(m.ORACLES):
        tid = f"T{i:02d}"
        tasks[tid] = {
            "name": name,
            "family": family,
            "holdout": gate_pairs(fn, m.GATE_SEED, m.HOLDOUT_LENGTHS,
                                  m.GATE_TRIALS, 7),
            "cf": gate_pairs(fn, m.CF_GATE_SEED, m.CF_LENGTHS,
                             m.CF_TRIALS, m.CF_VALMAX),
        }
    return {
        "meta": {
            "instrument": "frozen_holdout_phase0",
            "description": ("Frozen evaluation set for the designer sealed "
                            "suite of the top synthesis core. Sole evidence "
                            "base for designer-suite transition claims. "
                            "Read-only after Phase 0."),
            "source_file": "rsi_levels_metaforge_unified.py",
            "convention": ("materialized _make_gate RNG streams: "
                           "rng=random.Random(seed); for L in lengths: "
                           "for _ in range(trials): "
                           "xs=[rng.randint(0, valmax) for _ in range(L)]"),
            "holdout_gate": {"seed": m.GATE_SEED,
                             "lengths": list(m.HOLDOUT_LENGTHS),
                             "trials": m.GATE_TRIALS, "valmax": 7},
            "cf_gate": {"seed": m.CF_GATE_SEED,
                        "lengths": list(m.CF_LENGTHS),
                        "trials": m.CF_TRIALS, "valmax": m.CF_VALMAX},
            "train_lengths": list(m.TRAIN_LENGTHS),
            "n_tasks": len(m.ORACLES),
        },
        "tasks": tasks,
    }


def main():
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "frozen_holdout_phase0.json")
    payload = build()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"WROTE {out_path}")
    print(f"BYTES {len(text.encode('utf-8'))}")
    print(f"SHA256 {digest}")


if __name__ == "__main__":
    main()
