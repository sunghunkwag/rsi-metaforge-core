#!/usr/bin/env python3
"""Ascent Phase L holdout-corpus snapshot (run once at spec-freeze).

Builds docs/frozen_holdout_ascentL.json: a frozen corpus of fully expanded
base-token programs over the SC-1 unit grammars, used ONLY to validate MDL
master-gate adoptions (docs/ASCENT_L_SPEC.md). The corpus is disjoint from
the live loop's minting stream by construction: it is drawn from its own
committed seed, and the loop's task identity stream (ASCK_MASTER_SEED
lineage) never touches it. After this snapshot the file is read-only; its
SHA-256 is pinned inside the runtime and verified at battery start.

Usage (from the repository root):
    python3 docs/make_frozen_holdout_ascentL.py > docs/frozen_holdout_ascentL.json
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rsi_levels_metaforge_unified as M

HOLDOUT_SEED = 553211
N_TRACK_A = 24
N_TRACK_B = 24
BANDS = (2, 3, 4, 5, 6)

rng = random.Random(HOLDOUT_SEED)
programs = []
seen = set()

steps_a = [f for _, f, _ in M.SC_STEPS_A]
units_b = [toks for _, toks in M.SC_UNITS_B]

while sum(1 for p in programs if p["track"] == "A") < N_TRACK_A:
    band = BANDS[rng.randrange(len(BANDS))]
    body = (M._SC_OP["INPUT"], M._SC_OP["HEAD"])
    for _ in range(band):
        body = body + steps_a[rng.randrange(len(steps_a))]
    if body in seen:
        continue
    seen.add(body)
    programs.append({"track": "A", "band": band, "tokens": list(body)})

while sum(1 for p in programs if p["track"] == "B") < N_TRACK_B:
    band = BANDS[rng.randrange(len(BANDS))]
    body = (M._SC_OP["INPUT"],)
    w = 0
    while w < band:
        u = units_b[rng.randrange(len(units_b))]
        body = body + u
        w += 1
    if body in seen:
        continue
    seen.add(body)
    programs.append({"track": "B", "band": band, "tokens": list(body)})

doc = {
    "meta": {
        "instrument": "frozen_holdout_ascentL",
        "seed": HOLDOUT_SEED,
        "n_track_a": N_TRACK_A,
        "n_track_b": N_TRACK_B,
        "bands": list(BANDS),
        "note": "MDL master-gate holdout corpus; read-only after the "
                "Phase L spec-freeze; SHA-256 pinned in the runtime.",
    },
    "programs": programs,
}
print(json.dumps(doc, indent=2, sort_keys=True))
