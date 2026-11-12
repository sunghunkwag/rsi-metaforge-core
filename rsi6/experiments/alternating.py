"""Process c (amendment 3): several techniques of self-modification, tried in turn, generation
after generation, each judged on categories its search did not see.

    python -m rsi6.experiments.alternating [--generations N] [--ledger PATH]

The three rounds before this adopted nothing: what an improver found by following its
measurements on the pool lost on new categories. Here every generation sets aside three
categories of the pool, one of each kind in rotation: one of the four light categories on which
generation 0 learns, one of the two heavy ones, and one of the three on which generation 0
gains nothing (they stay in the gate as a check that nothing is harmed). It searches on the
other three light categories and the other heavy one. Four techniques each name a nominee:

  single     every single-field change of the current version is measured on the three light
             categories; the twelve best are measured on the heavy one too; the best one over
             the four categories
  remeasure  the five best of those are measured again with two more seeds; the best over all
             four seeds
  combine    single-field changes that helped a category and harmed none are added one at a
             time, best first, and an addition is kept only if the measured value goes up
  climb      the learner's own search over versions, as in the earlier rounds, on the three
             light categories

Every nominee goes through the registered gate on the categories that were set aside (deciding
half of their fresh instances) and through the confirmation (other half, other seeds). A
nominee is adopted if it passes the gate and its confirmation is positive; of several, the one
with the largest value at the gate. The next generation starts from the adopted version, with
another set of categories set aside.

What this is and is not. The categories set aside are pool categories: over the generations
each of them is searched on and set aside in turn. Adoptions here are therefore provisional.
Whether the process improved the learner is decided once, afterwards, on the reserve
categories and the sealed targets, which this process never touches.

The run writes to a working copy of the ledger (``ledger/live.jsonl``, started from
``main.jsonl`` and extending its chain); checkpoints are copied to ``main.jsonl``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.meta import rounds, space

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration_c.json")
MAIN = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
LIVE = os.path.join(os.path.dirname(HERE), "ledger", "live.jsonl")
TECHNIQUES = ("single", "remeasure", "combine", "climb")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def split_of(g: int, reg: dict) -> tuple:
    """``(light categories searched on, heavy category searched on, categories set aside)`` of generation ``g``."""
    order = lambda names: sorted(names, key=lambda c: hashlib.sha256(f"rsi6 process c|{c}".encode()).hexdigest())
    light, heavy, still = order(reg["light"]), order(reg["heavy"]), order(reg["still"])
    aside = [light[(g - 1) % len(light)], heavy[(g - 1) % len(heavy)], still[(g - 1) % len(still)]]
    return sorted(c for c in light if c not in aside), [c for c in heavy if c not in aside][0], sorted(aside)


def neighbours(version: dict) -> list:
    """Every version that differs from this one in exactly one field, on the grid of its design."""
    fields, grids, _ = space.layout_of(version)
    here = space.encode(version)
    out = []
    for k, name in enumerate(fields):
        for j in range(len(grids[k])):
            if j != here[k]:
                answer = here.copy()
                answer[k] = j
                out.append((name, grids[k][j], space.decode(answer, version)))
    return out


def per_category(base, records) -> dict:
    envs = sorted({r["env"] for r in base})
    return {e: float(np.mean([o["acquired"] - b["acquired"] for b, o in zip(base, records) if b["env"] == e])) for e in envs}


def measured(version, base, envs, seeds, budget, cache, tag) -> dict:
    records = cache.get(rounds.jobs_for(version, envs, seeds, budget, tag))
    change = per_category(base, records)
    cpu = rounds.cpu_of(records)
    return {"version": version, "digest": designs.digest(version), "breadth": rounds.breadth(base, records),
            "mean": rounds.improvement(base, records), "change": change, "cpu": cpu,
            "cpu_ok": bool(cpu <= rounds.RULES["search_cpu_ratio"] * rounds.cpu_of(base)),
            "helped": int(sum(v > 0.005 for v in change.values())), "harmed": int(sum(v < -0.005 for v in change.values()))}


def nominees(current, light, heavy, g, reg, cache, ledger, limit=None) -> dict:
    """The nominee of every technique for this generation (``None`` where a technique has none)."""
    budget = reg["budgets"]["search"]
    seeds = [1000 + 10 * g + 1, 1000 + 10 * g + 2]
    more = [1000 + 10 * g + 3, 1000 + 10 * g + 4]
    tag = f"search:c{g}"
    envs = light + [heavy]
    base_light = cache.get(rounds.jobs_for(current, light, seeds, budget, tag + ":start"))
    # ---- stage 1: every single-field change, two seeds, on the light categories
    todo = neighbours(current)[:limit]
    for k in range(0, len(todo), 8):                    # in batches, so that an interrupted run keeps what it measured
        cache.get([job for _, _, version in todo[k:k + 8] for job in rounds.jobs_for(version, light, seeds, budget, tag + ":single")])
    first = [dict(measured(version, base_light, light, seeds, budget, cache, tag + ":single"), field=name, value=value)
             for name, value, version in todo]
    ahead = sorted((r for r in first if r["cpu_ok"] and r["breadth"] > 0), key=lambda r: -r["breadth"])[:reg["stage_two"]]
    # ---- stage 2: the best of them on the heavy category too; the value over all four categories decides
    base = cache.get(rounds.jobs_for(current, envs, seeds, budget, tag + ":start"))
    cache.get([job for r in ahead for job in rounds.jobs_for(r["version"], [heavy], seeds, budget, tag + ":single")])
    table = [dict(measured(r["version"], base, envs, seeds, budget, cache, tag + ":single"), field=r["field"], value=r["value"])
             for r in ahead]
    usable = sorted((r for r in table if r["cpu_ok"]), key=lambda r: -r["breadth"])
    if find(ledger, type="c_screen", generation=g) is None:
        ledger.append({"type": "c_screen", "process": "c", "generation": g, "light": light, "heavy": heavy, "seeds": seeds,
                       "candidates": len(first), "positive_on_light": int(sum(r["breadth"] > 0 for r in first)),
                       "stage_one": [{"field": r["field"], "value": r["value"], "digest": r["digest"], "breadth": r["breadth"],
                                      "change": r["change"], "cpu_ok": r["cpu_ok"]} for r in first],
                       "stage_two": [{"field": r["field"], "value": r["value"], "digest": r["digest"], "breadth": r["breadth"],
                                      "mean": r["mean"], "change": r["change"], "cpu_ok": r["cpu_ok"]} for r in table]})
    say(f"  screening: {len(first)} single-field changes, {sum(r['breadth'] > 0 for r in first)} positive on the light categories,",
        f"{len(table)} measured on {heavy} too; best", [(r["field"], r["value"], round(r["breadth"], 4)) for r in usable[:3]])
    out = {}
    # single
    out["single"] = usable[0]["version"] if usable and usable[0]["breadth"] > 0 else None
    # remeasure: the five best again, with two more seeds; the best over all four
    top = [r for r in usable[:5] if r["breadth"] > 0]
    if top:
        base4 = cache.get(rounds.jobs_for(current, envs, seeds + more, budget, tag + ":start"))
        cache.get([job for r in top for job in rounds.jobs_for(r["version"], envs, seeds + more, budget, tag + ":remeasure")])
        again = [measured(r["version"], base4, envs, seeds + more, budget, cache, tag + ":remeasure") for r in top]
        best = max(again, key=lambda r: r["breadth"])
        out["remeasure"] = best["version"] if best["breadth"] > 0 and best["cpu_ok"] else None
    else:
        out["remeasure"] = None
    # combine: consistent single changes added one at a time, kept only if the measured value goes up
    consistent = [r for r in usable if r["breadth"] > 0 and r["harmed"] == 0 and r["helped"] >= 1]
    version, value, fields = current, 0.0, []
    for r in consistent[:8]:
        if r["field"] in fields:
            continue
        trial = designs.validate(dict(version, **{r["field"]: r["value"]}))
        got = measured(trial, base, envs, seeds, budget, cache, tag + ":combine")
        if got["cpu_ok"] and got["breadth"] > value + 0.001:
            version, value, fields = trial, got["breadth"], fields + [r["field"]]
    out["combine"] = version if fields else None
    # climb: the learner's own search over versions, on the light categories
    record = find(ledger, type="search", tag=tag + ":climb")
    if record is None:
        record = rounds.search("learner", current, current, light, seeds, budget, reg["climb_cpu_limit"], cache, tag + ":climb",
                               seed=3000 + g, objective=rounds.breadth)
        record = ledger.append(dict(record, round=f"c{g}", name="climb", process="c", objective="breadth"))
    out["climb"] = record["nominee_version"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=None)
    parser.add_argument("--ledger", default=LIVE)
    parser.add_argument("--registration", default=REGISTRATION)
    parser.add_argument("--dev", type=int, default=None, help="development only: measure this many single-field changes; needs a scratch ledger")
    args = parser.parse_args()
    if args.dev and os.path.abspath(args.ledger) in (os.path.abspath(LIVE), os.path.abspath(MAIN)):
        raise SystemExit("--dev needs a scratch ledger")
    reg = json.load(open(args.registration))
    if not os.path.exists(args.ledger):
        shutil.copy(MAIN, args.ledger)
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    cache = Cache(ledger)
    if find(ledger, type="registration_c") is None:
        ledger.append({"type": "registration_c", "digest": ledgers.digest(reg), "registration": reg})
    if find(ledger, type="registration_c")["digest"] != ledgers.digest(reg):
        raise SystemExit("the registration file of process c differs from the one recorded in the ledger")
    rounds.RULES.update(reg["rules"])
    current = designs.default(reg["design"])
    for record in ledger.select(type="adopt", process="c"):
        current = record["version"]
    last = args.generations or reg["generations_planned"]
    for g in range(1, last + 1):
        if find(ledger, type="c_generation_done", generation=g):
            continue
        light, heavy, aside = split_of(g, reg)
        envs = light + [heavy]
        say(f"generation {g}: from {designs.digest(current)[:12]}; searched on {light} and {heavy}; set aside {aside}")
        found = nominees(current, light, heavy, g, reg, cache, ledger, args.dev)
        gate_seeds = [2000 + 10 * g + k for k in range(1, 7)]
        confirm_seeds = [3000 + 10 * g + k for k in range(1, 7)]
        passed = []
        for technique in TECHNIQUES:
            nominee = found[technique]
            tag = f"c{g}:{technique}"
            if find(ledger, type="c_nominee", tag=tag) is None:
                ledger.append({"type": "c_nominee", "process": "c", "generation": g, "technique": technique, "tag": tag,
                               "nominee": None if nominee is None else designs.digest(nominee), "version": nominee,
                               "changes": None if nominee is None else designs.differences(current, nominee)})
            if nominee is None:
                say(f"  {technique}: no nominee")
                continue
            decision = find(ledger, type="gate", tag=f"gate:{tag}")
            if decision is None:
                decision = ledger.append(dict(rounds.gate(current, nominee, aside, gate_seeds, reg["budgets"]["run"], cache,
                                                          f"gate:{tag}", seed=200 + g), round=f"c{g}", name=technique, process="c"))
            check = find(ledger, type="confirm", tag=f"confirm:{tag}")
            if check is None:
                check = ledger.append(dict(rounds.confirm(current, nominee, aside, confirm_seeds, reg["budgets"]["run"], cache,
                                                          f"confirm:{tag}"), round=f"c{g}", name=technique, process="c"))
            ok = bool(decision["adopted"] and check["mean_min"] > 0.0)
            say(f"  {technique}: changes {sorted(designs.differences(current, nominee))} | gate {decision['mean_min']:+.4f}",
                f"(lower bound {decision['gain_lower_bound']:+.4f}, cpu x{decision['cpu_ratio']:.2f}, passes {decision['adopted']})",
                f"| confirmation {check['mean_min']:+.4f} | adopted by rule: {ok}")
            if ok:
                passed.append((decision["mean_min"], technique, nominee))
        adopted = None
        if passed:
            _, technique, nominee = max(passed, key=lambda t: t[0])
            ledger.append({"type": "adopt", "process": "c", "round": g, "lineage": "c", "technique": technique, "version": nominee,
                           "digest": designs.digest(nominee), "changes": designs.differences(current, nominee),
                           "provisional": "adopted on categories of the pool that this generation's search did not see"})
            current, adopted = nominee, technique
        ledger.append({"type": "c_generation_done", "process": "c", "generation": g, "searched": envs, "set_aside": aside,
                       "adopted_by": adopted, "version": designs.digest(current)})
        say(f"generation {g} done: adopted by {adopted}; version {designs.digest(current)[:12]}")
    say("process c at", designs.digest(current)[:12], "after", len(ledger.select(type="adopt", process="c")), "adoptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
