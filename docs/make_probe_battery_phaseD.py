#!/usr/bin/env python3
"""Phase D instrument generator: docs/probe_battery_phaseD.json.

Seeded, then frozen, set of input vectors spanning arities (input lengths)
and sizes, against which every Track 2 behavioral measurement is taken.

Structure:
  - base probes: for each length L in LENGTHS, PER_LENGTH vectors with
    values uniform in [0, VALMAX] from one random.Random(SEED) stream;
  - paired probes for every base with L >= 2, generated from the same
    stream in base order:
      * "perm": a seeded shuffle of the base vector (rotated by one if the
        shuffle fixes the vector) -- order-sensitivity partner;
      * "perturb": the base vector with one seeded position replaced by a
        different seeded value -- value-sensitivity partner.

Deterministic serialization (sort_keys, fixed indent). The SHA-256 of the
file is recorded in docs/descriptor_spec_phaseD.md and checked by a test.
This instrument is read-only after Phase D freeze; the exploration engine
verifies the hash before every run.

Usage:  python3 docs/make_probe_battery_phaseD.py
"""
import hashlib
import json
import os
import random

SEED = 90901
LENGTHS = (0, 1, 2, 3, 4, 5, 6, 8, 13, 21, 34)
PER_LENGTH = 4
VALMAX = 15


def build():
    rng = random.Random(SEED)
    probes = []
    bases = []
    for L in LENGTHS:
        for _ in range(PER_LENGTH):
            xs = [rng.randint(0, VALMAX) for _ in range(L)]
            pid = f"P{len(probes):03d}"
            probes.append({"pid": pid, "kind": "base", "base": None,
                           "xs": xs})
            bases.append((pid, xs))
    for pid, xs in bases:
        if len(xs) < 2:
            continue
        perm = list(xs)
        rng.shuffle(perm)
        if perm == xs:
            perm = perm[1:] + perm[:1]
        probes.append({"pid": f"P{len(probes):03d}", "kind": "perm",
                       "base": pid, "xs": perm})
        pos = rng.randrange(len(xs))
        newv = (xs[pos] + 1 + rng.randint(0, VALMAX - 2)) % (VALMAX + 1)
        pert = list(xs)
        pert[pos] = newv
        probes.append({"pid": f"P{len(probes):03d}", "kind": "perturb",
                       "base": pid, "xs": pert})
    return {
        "meta": {
            "instrument": "probe_battery_phaseD",
            "description": ("Frozen probe battery for Track 2 exploration. "
                            "Every behavioral descriptor is computed against "
                            "these vectors. Read-only after Phase D freeze."),
            "seed": SEED,
            "lengths": list(LENGTHS),
            "per_length": PER_LENGTH,
            "valmax": VALMAX,
            "n_probes": len(probes),
        },
        "probes": probes,
    }


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "probe_battery_phaseD.json")
    text = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"WROTE {out}")
    print(f"BYTES {len(text.encode('utf-8'))}")
    print(f"SHA256 {hashlib.sha256(text.encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
