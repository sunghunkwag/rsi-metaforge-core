"""Development: arm E, an acquisition that estimates what a missing theorem would unlock (2026-11-28).

The rule is in ``rsi6/results/dev_proof_leverage_20261128/PLAN.md``: arm D
(``dev_proof_gate.py``) with one change in what an investment does. Before spending deep on a
failed theorem, each of a few candidates is tried as an assumption: its statement is taken as
given for a moment, and a sample of later failures is tried with it. What goes through counts;
nothing found that way is kept. The candidate that would unlock the most is then pursued with
growing budgets, from the bank, within half of what the bank holds.

    python -m rsi6.experiments.dev_proof_leverage --out E.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time

from rsi6.experiments.dev_proof_depth import SETMM, pool_text
from rsi6.experiments.dev_proof_gate import ALLOWANCE, FIRST, GROWTH, STALL, constructors, earlier
from rsi6.kernel.metamath import Database, Rejected
from rsi6.kernel.problem import Meter
from rsi6.learner.prover import Entry, Library, Prover

CANDIDATES = 8
PROBES = 8
PROBE_UNITS = 20000.0
SHARE = 0.5


def run(limit: int | None = None) -> dict:
    sys.setrecursionlimit(20000)
    raw = open(SETMM, "rb").read()
    db = Database.read(pool_text(raw.decode()))
    idx = db.assertions
    lib = Library()
    entries, rows = {}, {}
    acc = {"bank": 0.0, "spent": 0.0, "allowance": 0.0, "probe_units": 0.0, "invest_units": 0.0}
    proved_with, unproved_with = {}, {}
    frontier, syms, order = {}, {}, []
    events, consec, t0 = [], 0, time.time()

    def spend(units_used):
        acc["bank"] -= units_used
        acc["spent"] += units_used

    def attempt(label, units, library):
        meter = Meter(units)
        proof = Prover(db, library).prove(label, meter)
        spend(meter.used)
        ok = False
        if proof is not None:
            try:
                ok = db.verify(label, proof)
            except Rejected as e:
                rows[label]["rejected"] = str(e)
        lemmas = sorted({s for s in proof or () if s in idx and idx[s].kind == "p"}) if ok else []
        return ok, meter.used, lemmas

    def probe(goal, assumed):
        """Try ``goal`` with the library at its position and ``assumed`` taken as given; nothing is kept."""
        library = earlier(lib, idx[goal].index)
        library.add(entries[assumed])
        meter = Meter(PROBE_UNITS)
        proof = Prover(db, library).prove(goal, meter)
        spend(meter.used)
        acc["probe_units"] += meter.used
        return proof is not None

    def mark_proved(label, how, lemmas):
        rows[label].update({"proved": True, "how": how, "lemmas": lemmas})
        lib.add(entries[label])
        frontier.pop(label, None)
        for s in syms[label]:
            proved_with[s] = proved_with.get(s, 0) + 1
            unproved_with.get(s, set()).discard(label)

    def priority(label):
        return max((len(unproved_with.get(s, ())) / (proved_with.get(s, 0) + 1.0) for s in syms[label]), default=0.0)

    def catch_up(after, at):
        for g in sorted((f for f in frontier if idx[f].index > idx[after].index), key=lambda f: idx[f].index):
            if acc["bank"] < FIRST:
                break
            ok, used, lemmas = attempt(g, FIRST, earlier(lib, idx[g].index))
            rows[g]["retries"].append({"units": FIRST, "used": used, "proved": ok, "at": at, "catch_up": True})
            if ok:
                mark_proved(g, "catch-up", lemmas)

    def invest(at):
        ranked = sorted(frontier, key=lambda f: (-priority(f), idx[f].index))[:CANDIDATES]
        leverage = {}
        for f in ranked:
            later = [g for g in order if g in frontier and idx[g].index > idx[f].index][-PROBES:]
            hits = 0
            for g in later:
                if acc["bank"] < PROBE_UNITS:
                    break
                hits += probe(g, f)
            leverage[f] = hits
        event = {"at": at, "leverage": {f: leverage[f] for f in ranked}, "pursued": None, "attempts": []}
        best = max(ranked, key=lambda f: (leverage[f], priority(f), -idx[f].index)) if ranked else None
        if best is not None and leverage[best] >= 1:
            event["pursued"] = best
            cap, used_here = SHARE * acc["bank"], 0.0
            units = GROWTH * frontier[best]
            while acc["bank"] >= units and used_here + units <= cap:
                ok, used, lemmas = attempt(best, units, earlier(lib, idx[best].index))
                used_here += used
                acc["invest_units"] += used
                rows[best]["retries"].append({"units": units, "used": used, "proved": ok, "at": at})
                event["attempts"].append({"units": units, "used": used, "proved": ok})
                if ok:
                    mark_proved(best, "investment", lemmas)
                    catch_up(best, at)
                    break
                frontier[best] = units
                units *= GROWTH
        elif ranked:
            pick = max(frontier, key=lambda f: (priority(f), -frontier[f], -idx[f].index))
            units = GROWTH * frontier[pick]
            if acc["bank"] >= units:
                ok, used, lemmas = attempt(pick, units, earlier(lib, idx[pick].index))
                acc["invest_units"] += used
                rows[pick]["retries"].append({"units": units, "used": used, "proved": ok, "at": at})
                event["fallback"] = {"label": pick, "units": units, "proved": ok}
                if ok:
                    mark_proved(pick, "retry", lemmas)
                    catch_up(pick, at)
                else:
                    frontier[pick] = units
        events.append(event)

    n = 0
    for label in db.order:
        a = idx[label]
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
        order.append(label)
        syms[label] = constructors(e.concl, set())
        for h in e.hyps:
            constructors(h, syms[label])
        rows[label] = {"label": label, "readable": True, "proved": False, "first_units": None, "retries": []}
        acc["allowance"] += ALLOWANCE
        acc["bank"] += ALLOWANCE
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
        if consec >= STALL:
            invest(label)
            consec = 0
    assert acc["spent"] <= acc["allowance"] + 1e-6, "spent more than the allowance"
    return {"arm": "E", "allowance_per_theorem": ALLOWANCE, "first": FIRST, "stall": STALL, "growth": GROWTH,
            "candidates": CANDIDATES, "probes": PROBES, "probe_units": PROBE_UNITS, "share": SHARE,
            "set.mm sha256": hashlib.sha256(raw).hexdigest(), "allowance_total": acc["allowance"],
            "spent_total": acc["spent"], "probe_units_total": acc["probe_units"], "invest_units_total": acc["invest_units"],
            "bank_left": acc["bank"], "seconds": round(time.time() - t0, 1), "events": events,
            "rows": [rows[l] for l in db.order if l in rows]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = run(args.limit)
    json.dump(out, open(args.out, "w"), indent=0)
    n = sum(1 for r in out["rows"] if r.get("proved"))
    pursued = [ev["pursued"] for ev in out["events"] if ev.get("pursued")]
    print(f"arm E: {n} of {sum(1 for r in out['rows'] if r.get('readable'))} proved in {out['seconds']} s; spent "
          f"{out['spent_total']:.0f} of {out['allowance_total']:.0f} (probes {out['probe_units_total']:.0f}, "
          f"investments {out['invest_units_total']:.0f}); events {len(out['events'])}; pursued {pursued[:12]}")


if __name__ == "__main__":
    main()
