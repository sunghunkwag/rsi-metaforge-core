"""Development: does the proof form have depth? (2026-11-28)

The question the measurements of designs s, t and v left open (``rsi6/OWNER_DIRECTIVE.md``,
instruction 20, "The obstacle"): a second step needs something whose first part makes the rest
easier to find. This asks it of the proof form, at the object level, before any learner is
built there: does a theorem the search proved itself make a later theorem provable that the
same search, at the same budget, cannot prove without it; and does that go on for more than one
step?

Three libraries, one search (``rsi6/learner/prover.py``), the same budget per theorem, the
theorems of the pool in the database's order:

* ``A``: the axioms and definitions stated before the theorem, nothing else.
* ``B``: those, and every earlier theorem of the pool that this run proved itself and the checker
  accepted. What it proves is what its own earlier proofs made reachable.
* ``C``: those, and every earlier theorem of the database, proved by people. A reference, not a
  competitor: it shows what the database's own lemmas reach with this search.

Every proof is checked by the kernel (``rsi6/kernel/metamath.py``); a rejected proof counts as
none and is reported. The rules that read the result are in
``rsi6/results/dev_proof_depth_20261128/PLAN.md``, committed before the full run.

    python -m rsi6.experiments.dev_proof_depth --arm B --budget 200000 --out OUT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

from rsi6.kernel.metamath import Database, Rejected
from rsi6.kernel.problem import Meter
from rsi6.learner.prover import Entry, Library, Prover

HERE = os.path.dirname(os.path.abspath(__file__))
SETMM = os.path.join(os.path.dirname(HERE), "data", "setmm", "set.mm")
# the pool: everything before the section "Other axiomatizations related to classical propositional
# calculus" (the start of that section's opening comment); it ends the section "Propositional calculus"
POOL_END_MARK = "\n  Other axiomatizations related to classical propositional calculus\n"


def pool_text(text: str) -> str:
    k = text.find(POOL_END_MARK)
    if k < 0:
        raise RuntimeError("the end of the pool is not where the plan says it is")
    return text[:text.rfind("$(", 0, k)]


def run(arm: str, budget: float, limit: int | None = None) -> dict:
    sys.setrecursionlimit(20000)
    raw = open(SETMM, "rb").read()
    text = raw.decode()
    db = Database.read(pool_text(text))
    lib = Library()
    rows, t0 = [], time.time()
    proved = set()
    for label in db.order:
        a = db.assertions[label]
        if a.typecode != "|-":
            continue
        try:
            entry = Entry(db, label)
        except Exception:
            entry = None
        if a.kind == "a":
            if entry is not None:
                lib.add(entry)
            continue
        if entry is None:
            rows.append({"label": label, "readable": False})
            continue
        if limit is not None and len(rows) >= limit:
            break
        meter = Meter(budget)
        proof = Prover(db, lib).prove(label, meter)
        ok, note = False, None
        if proof is not None:
            try:
                ok = db.verify(label, proof)
            except Rejected as e:
                note = f"rejected: {e}"
        lemmas = sorted({s for s in proof or () if s in db.assertions and db.assertions[s].kind == "p"}) if ok else []
        rows.append({"label": label, "readable": True, "proved": ok, "units": meter.used, "steps": len(proof) if ok else None,
                     "lemmas": lemmas, "note": note})
        if ok:
            proved.add(label)
        if arm == "C" or (arm == "B" and ok):
            lib.add(entry)
    return {"arm": arm, "budget": budget, "set.mm sha256": hashlib.sha256(raw).hexdigest(),
            "pool_end_mark": POOL_END_MARK.strip(), "seconds": round(time.time() - t0, 1),
            "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("A", "B", "C"), required=True)
    ap.add_argument("--budget", type=float, default=200000)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = run(args.arm, args.budget, args.limit)
    json.dump(out, open(args.out, "w"), indent=0)
    n = sum(1 for r in out["rows"] if r.get("proved"))
    print(f"arm {args.arm}: {n} of {sum(1 for r in out['rows'] if r['readable'])} proved in {out['seconds']} s")


if __name__ == "__main__":
    main()
