"""Development: arm D, an acquisition that allocates its own budget (2026-11-28).

The rule is in ``rsi6/results/dev_proof_gate_20261128/PLAN.md``, committed before the run:
the search and the library are arm B's (``dev_proof_depth.py``); every theorem brings B's
allowance, is tried once with half of it, and leaves the rest in a bank; when ten first attempts
in a row fail, one failed theorem is tried again with four times its last units, chosen by how
blocked the constructs of its statement are; after a retry proves a theorem, the failures after
it are tried once more. Nothing is spent that is not in the bank, so the total stays within B's.

    python -m rsi6.experiments.dev_proof_gate --out D.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time

from rsi6.experiments.dev_proof_depth import SETMM, pool_text
from rsi6.kernel.metamath import Database, Rejected
from rsi6.kernel.problem import Meter
from rsi6.learner.prover import Entry, Library, Prover

ALLOWANCE = 200000.0
FIRST = 100000.0
STALL = 10
GROWTH = 4.0


def constructors(tree, out: set) -> set:
    if isinstance(tree, tuple):
        out.add(tree[0])
        for c in tree[1:]:
            constructors(c, out)
    return out


def earlier(lib: Library, index: int) -> Library:
    """The library as it would be at ``index``: what in it comes before that position."""
    out = Library()
    for e in sorted(lib.entries.values(), key=lambda x: x.index):
        if e.index < index:
            out.add(e)
    return out


def run(limit: int | None = None) -> dict:
    sys.setrecursionlimit(20000)
    raw = open(SETMM, "rb").read()
    db = Database.read(pool_text(raw.decode()))
    lib = Library()
    entries, rows = {}, {}
    bank = spent = allowance = 0.0
    proved_with, unproved_with = {}, {}         # constructor -> count proved / set of labels not yet proved
    frontier = {}                               # failed label -> units of its last attempt
    syms = {}
    retries, consec, t0 = [], 0, time.time()

    def attempt(label, units, library):
        nonlocal bank, spent
        meter = Meter(units)
        proof = Prover(db, library).prove(label, meter)
        bank -= meter.used
        spent += meter.used
        ok = False
        if proof is not None:
            try:
                ok = db.verify(label, proof)
            except Rejected as e:
                rows[label]["rejected"] = str(e)
        lemmas = sorted({s for s in proof or () if s in db.assertions and db.assertions[s].kind == "p"}) if ok else []
        return ok, meter.used, lemmas

    def mark_proved(label, how, lemmas):
        rows[label].update({"proved": True, "how": how, "lemmas": lemmas})
        lib.add(entries[label])
        frontier.pop(label, None)
        for s in syms[label]:
            proved_with[s] = proved_with.get(s, 0) + 1
            unproved_with.get(s, set()).discard(label)

    def priority(label):
        return max((len(unproved_with.get(s, ())) / (proved_with.get(s, 0) + 1.0) for s in syms[label]), default=0.0)

    n = 0
    for label in db.order:
        a = db.assertions[label]
        if a.typecode != "|-":
            continue
        try:
            e = Entry(db, label)
        except Exception:
            if a.kind == "p":
                rows[label] = {"label": label, "readable": False}
            continue
        if a.kind == "a":
            lib.add(e)
            continue
        if limit is not None and n >= limit:
            break
        n += 1
        entries[label] = e
        syms[label] = constructors(e.concl, set())
        for h in e.hyps:
            constructors(h, syms[label])
        rows[label] = {"label": label, "readable": True, "proved": False, "first_units": None, "retries": []}
        allowance += ALLOWANCE
        bank += ALLOWANCE
        ok, used, lemmas = attempt(label, FIRST, lib)
        rows[label]["first_units"] = used
        if ok:
            mark_proved(label, "first", lemmas)
            consec = 0
            continue
        frontier[label] = FIRST
        for s in syms[label]:
            unproved_with.setdefault(s, set()).add(label)
        consec += 1
        if consec < STALL or not frontier:
            continue
        # stalled: one retry, of the failed theorem whose constructs are most blocked
        idx = db.assertions
        pick = max(frontier, key=lambda f: (priority(f), -frontier[f], -idx[f].index))
        units = GROWTH * frontier[pick]
        if bank < units:
            continue
        ok, used, lemmas = attempt(pick, units, earlier(lib, idx[pick].index))
        frontier[pick] = units if not ok else frontier.get(pick, units)
        rows[pick]["retries"].append({"units": units, "used": used, "proved": ok, "at": label})
        retries.append({"label": pick, "units": units, "used": used, "proved": ok, "at": label,
                        "priority": round(priority(pick), 3)})
        if not ok:
            continue
        mark_proved(pick, "retry", lemmas)
        consec = 0
        for g in sorted((f for f in frontier if idx[f].index > idx[pick].index), key=lambda f: idx[f].index):
            if bank < FIRST:
                break
            ok, used, lemmas = attempt(g, FIRST, earlier(lib, idx[g].index))
            rows[g]["retries"].append({"units": FIRST, "used": used, "proved": ok, "at": label, "catch_up": True})
            if ok:
                mark_proved(g, "catch-up", lemmas)
    assert spent <= allowance + 1e-6, "spent more than the allowance"
    return {"arm": "D", "allowance_per_theorem": ALLOWANCE, "first": FIRST, "stall": STALL, "growth": GROWTH,
            "set.mm sha256": hashlib.sha256(raw).hexdigest(), "allowance_total": allowance, "spent_total": spent,
            "bank_left": bank, "seconds": round(time.time() - t0, 1), "retries": retries,
            "rows": [rows[l] for l in db.order if l in rows]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = run(args.limit)
    json.dump(out, open(args.out, "w"), indent=0)
    n = sum(1 for r in out["rows"] if r.get("proved"))
    print(f"arm D: {n} of {sum(1 for r in out['rows'] if r.get('readable'))} proved in {out['seconds']} s; "
          f"spent {out['spent_total']:.0f} of {out['allowance_total']:.0f}; retries {len(out['retries'])}")


if __name__ == "__main__":
    main()
