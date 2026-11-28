"""Development: a learned component of the proof form, and whether what it learns compounds (2026-11-28).

The depth measurement (``dev_proof_depth.py``) asks whether theorems the search proved make
later theorems provable. This asks the next question: the search's order of candidates is
learned from its own accepted proofs (``Usage`` in ``rsi6/learner/prover.py``, updated after
every proof), and a generation hands what it learned to the next. Does a generation whose
learned order came from a better generation's proofs acquire more on sections of the database
it has not seen, at the same budget, than one whose order came from a worse one, or from a
search that never learned but was given the same total compute?

Two parts of the pool (``dev_proof_depth.pool_text``), split where the plan says
(``rsi6/results/dev_proof_learn_20261128/PLAN.md``):

* **train**: the sections the generations learn on;
* **test**: the later sections, on which every generation is measured and none has learned.

A *pass* runs the search through theorems in the database's order, with a library built from
the axioms and the theorems this pass itself proved (as in arm B of the depth measurement); its
``Usage`` starts from what it is handed and is updated after each accepted proof.

    python -m rsi6.experiments.dev_proof_learn train --out chain.json
    python -m rsi6.experiments.dev_proof_learn control --out q.json
    python -m rsi6.experiments.dev_proof_learn test --usage chain.json --key P2 --out e2.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

from rsi6.experiments.dev_proof_depth import SETMM, pool_text
from rsi6.kernel.metamath import Database, Rejected
from rsi6.kernel.problem import Meter
from rsi6.learner.prover import Entry, Library, Prover, Usage

TEST_FROM = "\n  The conditional operator for propositions\n"


def split(text: str, db: Database) -> int:
    """Index of the first assertion of the test part."""
    k = text.find(TEST_FROM)
    head = Database.read(text[:text.rfind("$(", 0, k)])
    return len(head.order)


def run_pass(db: Database, budget: float, start_usage: dict | None, learn: bool, until: int | None,
             count_from: int = 0) -> dict:
    """One pass in database order over the assertions with index < ``until`` (all when ``None``)."""
    usage = Usage(**start_usage) if start_usage else Usage()
    lib = Library()
    proved, rows, rejected, t0 = [], [], [], time.time()
    for label in db.order:
        a = db.assertions[label]
        if until is not None and a.index >= until:
            break
        if a.typecode != "|-":
            continue
        try:
            entry = Entry(db, label)
        except Exception:
            continue
        if a.kind == "a":
            lib.add(entry)
            lib.resort(usage.key)
            continue
        meter = Meter(budget)
        proof = Prover(db, lib).prove(label, meter)
        ok = False
        if proof is not None:
            try:
                ok = db.verify(label, proof)
            except Rejected:
                ok = False
                rejected.append(label)
        if a.index >= count_from:
            rows.append({"label": label, "proved": ok, "units": meter.used})
        if ok:
            proved.append(label)
            if learn:
                usage.update(proof, lib)
            lib.add(entry)
            lib.resort(usage.key)
    return {"proved": proved, "rows": rows, "rejected": rejected, "usage": usage.state(),
            "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("train", "control", "test"))
    ap.add_argument("--budget", type=float, default=50000)
    ap.add_argument("--generations", type=int, default=3)
    ap.add_argument("--usage", default=None, help="test: a JSON file written by train or control")
    ap.add_argument("--key", default=None, help="test: which usage of that file (P1, P2, ... or Q); none: E0")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.setrecursionlimit(20000)
    raw = open(SETMM, "rb").read()
    text = pool_text(raw.decode())
    db = Database.read(text)
    cut = split(text, db)
    out = {"stage": args.stage, "budget": args.budget, "set.mm sha256": hashlib.sha256(raw).hexdigest(),
           "test_from": TEST_FROM.strip(), "test_first_index": cut}
    if args.stage == "train":
        # generations learning on the train part; each starts from what the previous one learned
        handed, out["generations"] = None, {}
        for g in range(1, args.generations + 1):
            p = run_pass(db, args.budget, handed, True, cut)
            out["generations"][f"P{g}"] = {"proved": len(p["proved"]), "rejected": p["rejected"], "seconds": p["seconds"],
                                           "usage": p["usage"]}
            print(f"train P{g}: {len(p['proved'])} proved, {p['seconds']} s", flush=True)
            handed = p["usage"]
            json.dump(out, open(args.out, "w"), indent=0)
    elif args.stage == "control":
        # the compute-matched control (directive, section 5, item 5): one generation that learns the same way
        # with the chain's total budget in its single pass; nothing is handed from generation to generation
        q = run_pass(db, args.budget * args.generations, None, True, cut)
        out["generations"] = {"Q": {"proved": len(q["proved"]), "rejected": q["rejected"], "seconds": q["seconds"],
                                    "usage": q["usage"]}}
        print(f"control Q: {len(q['proved'])} proved, {q['seconds']} s", flush=True)
        json.dump(out, open(args.out, "w"), indent=0)
    else:
        start = None
        if args.key:
            start = json.load(open(args.usage))["generations"][args.key]["usage"]
        e = run_pass(db, args.budget, start, True, None, count_from=cut)
        n = sum(1 for r in e["rows"] if r["proved"])
        out.update({"start": args.key or "none", "proved_on_test": n, "of": len(e["rows"]), "rejected": e["rejected"],
                    "proved_whole_pool": len(e["proved"]), "seconds": e["seconds"],
                    "proved": sorted(r["label"] for r in e["rows"] if r["proved"])})
        print(f"test from {args.key or 'nothing'}: {n} of {len(e['rows'])}, {e['seconds']} s", flush=True)
        json.dump(out, open(args.out, "w"), indent=0)


if __name__ == "__main__":
    main()
