#!/usr/bin/env python3
"""Phase J4 instrument generator: docs/frozen_holdout_extJ.json.

Extended-ISA holdout instrument for the certified wall tasks T29-T32
(DIRECTIVE v5 Phase J4; approved spec docs/ISA_EXTENSION_SPEC.md). This
instrument judges the Phase J5 crossing claims: any wall program adopted by
the two-arm evaluation must also pass every pair recorded here. It is
created and SHA-256-hashed BEFORE any Phase J5 search runs, then read-only.

Content: for each wall task, two evaluation streams generated with the same
RNG protocol as the sealed gates (_make_gate) but with FRESH seeds and
length grids disjoint from every stream the Phase 0 instrument materializes:

  - extj_holdout: seed J_HOLDOUT_SEED=71293, lengths (7, 11, 17, 26, 40),
    8 trials per length, values in [0, 9]
  - extj_cf:      seed J_CF_SEED=90407, lengths (10, 15, 23, 31, 44),
    6 trials per length, values in [0, 15]

Expected outputs come from the pre-existing designer oracle definitions
(ORACLES) only; nothing here depends on any search result, granted
primitive, or adopted program. Serialization is deterministic; the SHA-256
is pinned by test_extj_instrument_frozen_and_consistent.

Usage:  python3 docs/make_frozen_holdout_extJ.py
        (run from the repository root; writes docs/frozen_holdout_extJ.json)
"""
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rsi_levels_metaforge_unified as m

J_HOLDOUT_SEED = 71293
J_HOLDOUT_LENGTHS = (7, 11, 17, 26, 40)
J_HOLDOUT_TRIALS = 8
J_HOLDOUT_VALMAX = 9
J_CF_SEED = 90407
J_CF_LENGTHS = (10, 15, 23, 31, 44)
J_CF_TRIALS = 6
J_CF_VALMAX = 15

WALL_TIDS = ("T29", "T30", "T31", "T32")


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
        if tid not in WALL_TIDS:
            continue
        tasks[tid] = {
            "name": name,
            "family": family,
            "extj_holdout": gate_pairs(fn, J_HOLDOUT_SEED, J_HOLDOUT_LENGTHS,
                                       J_HOLDOUT_TRIALS, J_HOLDOUT_VALMAX),
            "extj_cf": gate_pairs(fn, J_CF_SEED, J_CF_LENGTHS,
                                  J_CF_TRIALS, J_CF_VALMAX),
        }
    return {
        "meta": {
            "instrument": "frozen_holdout_extJ",
            "description": ("Phase J4 extended-ISA holdout instrument for "
                            "the certified wall tasks T29-T32. Judges the "
                            "Phase J5 crossing claims; frozen before any "
                            "Phase J5 search run. Read-only after Phase J4."),
            "source_file": "rsi_levels_metaforge_unified.py",
            "approved_spec": "docs/ISA_EXTENSION_SPEC.md",
            "convention": ("materialized _make_gate RNG streams: "
                           "rng=random.Random(seed); for L in lengths: "
                           "for _ in range(trials): "
                           "xs=[rng.randint(0, valmax) for _ in range(L)]"),
            "extj_holdout": {"seed": J_HOLDOUT_SEED,
                             "lengths": list(J_HOLDOUT_LENGTHS),
                             "trials": J_HOLDOUT_TRIALS,
                             "valmax": J_HOLDOUT_VALMAX},
            "extj_cf": {"seed": J_CF_SEED,
                        "lengths": list(J_CF_LENGTHS),
                        "trials": J_CF_TRIALS, "valmax": J_CF_VALMAX},
            "n_tasks": len(WALL_TIDS),
        },
        "tasks": tasks,
    }


def main():
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "frozen_holdout_extJ.json")
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
