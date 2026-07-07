#!/usr/bin/env python3
"""Ascent Phase N holdout-corpus snapshot (run once at spec-freeze).

Builds docs/frozen_holdout_ascentN.json: a frozen corpus of prefix-encoded
tautologies over the N-1 formula alphabet, used ONLY to validate
abbreviation adoptions on the theorem corpus (docs/ASCENT_N_SPEC.md §5).
Classic tautology schemas are instantiated over the three canonical
variables; every entry is verified to be a tautology by the complete
truth-table check before it enters the corpus. After this snapshot the
file is read-only; its SHA-256 is pinned inside the runtime.

Usage (from the repository root):
    python3 docs/make_frozen_holdout_ascentN.py > docs/frozen_holdout_ascentN.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rsi_levels_metaforge_unified as M

V = [("v", i) for i in range(M.AN_MAX_VARS)]


def imp(a, b):
    return ("imp", a, b)


def neg(a):
    return ("not", a)


schemas = []
for a in V:
    for b in V:
        schemas.append(imp(a, imp(b, a)))                      # K
        schemas.append(imp(imp(a, b), imp(a, b)))              # I on imp
        schemas.append(imp(neg(neg(a)), a))                    # DNE
        schemas.append(imp(a, neg(neg(a))))                    # DNI
        schemas.append(imp(imp(neg(a), neg(b)), imp(b, a)))    # A3 shape
        schemas.append(imp(neg(a), imp(a, b)))                 # EFQ
        for c in V:
            schemas.append(imp(imp(a, imp(b, c)),
                               imp(imp(a, b), imp(a, c))))     # S

seen = set()
programs = []
for f in schemas:
    if not M.an_formula_ok(f):
        continue
    c = M.an_canon(f)
    if c in seen:
        continue
    if M.an_countermodel(f) is not None:
        raise AssertionError(f"non-tautology in the holdout: {c}")
    seen.add(c)
    programs.append({"tokens": list(M.an_encode_formula(f)),
                     "size": M.an_size(f)})

doc = {
    "meta": {
        "instrument": "frozen_holdout_ascentN",
        "n_programs": len(programs),
        "alphabet": M.AN_ALPHA,
        "note": "abbreviation-gate holdout corpus of verified "
                "tautologies; read-only after the Phase N spec-freeze; "
                "SHA-256 pinned in the runtime.",
    },
    "programs": programs,
}
print(json.dumps(doc, indent=2, sort_keys=True))
