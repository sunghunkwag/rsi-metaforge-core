"""The relay experiment of design r (the Owner's instruction 14; registration_r.json).

    python -m rsi6.open.relay --stage meta|heldout [--ledger PATH] [--registration PATH] [--dev]

``meta``     chains of acquisitions on source categories in the registered order. In an on-policy
             chain every acquisition starts from the memory the earlier acquisitions of the chain
             left (design r rebuilds its operator prior, edit-size prior and block library from it),
             so what one acquisition discovers changes how the next generates its candidates. An
             off-policy chain makes the same acquisitions (categories, seeds) each with no memory:
             the same amount of record, made by a machinery that never changed. Retention: job shop
             and quadratic assignment acquired again, on the confirming half, with the memory of
             their own block of the chain and with the final memory.
``heldout``  on the held-out categories (role ``fresh``, unlocked here; no learner ran on them
             before), paired by chain and seed, in a registered order of priority under a CPU cap:
             relay and frozen (the primary), shuffled, o0 raised to relay's CPU, offpolicy,
             library only, frozen at four times the training budget, prior only, the memories of
             depth 8 and 4, references at the earlier processes' run budget, a0 raised to relay's
             CPU. A non-binding futility look after half of the primary.

Every chain step is recorded (``r_memory``) with the digests of the memory it started from and
left, and the memory is rebuilt from the run records' reports alone; a stopped stage replays
from its start, every measurement served from the ledger, every record checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.environments import fresh
from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles
from rsi6.kernel.environment import split
from rsi6.kernel.problem import Meter
from rsi6.kernel.run import Cache
from rsi6.learner import design_r, designs, dispatch_extra
from rsi6.open import evaluate
from rsi6.open.discovery import append_once

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration_r.json")
ORDER_STAGES = ("meta", "heldout")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def new_entries(record) -> list:
    return list(((record.get("report") or {}).get("relay") or {}).get("new_entries") or [])


def digest_of(memory) -> str:
    return ledgers.digest(memory)


# =============================================================================================
# meta
# =============================================================================================
def run_meta(reg, cache, ledger) -> None:
    M, order = reg["meta"], reg["meta"]["order"]
    J, J_off = M["chains"], M["chains_off"]
    budget = dict(reg["budgets"]["meta"])
    on = {j: [] for j in range(J)}                       # entries after each position, per chain
    off = {j: [] for j in range(J_off)}
    depth = {j: {0: None} for j in range(J)}
    for k, env in enumerate(order):
        jobs, tags = [], []
        for j in range(max(J, J_off)):
            seed = M["seed_base"] + 100 * j + k
            if j < J:
                jobs.append({"env": env, "version": reg["version"], "seed": seed, "budget": budget, "memory": design_r.mem(on[j]),
                             "purpose": f"relay-meta:on{j}:pos{k}"})
                tags.append(("on", j))
            if j < J_off:
                jobs.append({"env": env, "version": reg["version"], "seed": seed, "budget": budget, "memory": None,
                             "purpose": f"relay-meta:off{j}:pos{k}"})
                tags.append(("off", j))
        got = cache.get(jobs)
        for (policy, j), job, r in zip(tags, jobs, got):
            store = on if policy == "on" else off
            before = design_r.mem(store[j]) if policy == "on" else None
            after_entries = (store[j] if policy == "on" else []) + new_entries(r)
            append_once(ledger, {"type": "r_memory", "policy": policy, "chain": j, "position": k, "env": env, "seed": job["seed"],
                                 "run_key": r["key"], "digest_in": digest_of(before), "digest_out": digest_of(design_r.mem(after_entries)),
                                 "n_entries": len(after_entries)}, ("policy", "chain", "position"))
            if policy == "on":
                on[j] = after_entries
                depth[j][k + 1] = design_r.mem(on[j])
            else:
                off[j] = off[j] + new_entries(r)
        say(f"meta position {k} ({env}): on-policy acquired {np.mean([r['acquired'] for (p, _), r in zip(tags, got) if p == 'on']):.4f}")
    for j in range(J):
        append_once(ledger, {"type": "r_chain_done", "chain": j, "digest": digest_of(design_r.mem(on[j])), "entries": len(on[j])}, ("chain",))
    # retention, on the confirming half
    R = M["retention"]
    rb = dict(reg["budgets"]["retention"])
    jobs, labels = [], []
    for j in range(R["chains"]):
        seed = R["seed_base"] + 10 * j
        for env, depths in R["plan"].items():
            for d in depths:
                memory = None if d == 0 else depth[j][d]
                jobs.append({"env": env, "version": reg["version"], "seed": seed, "budget": rb, "memory": memory,
                             "purpose": f"relay-retention:chain{j}:{env}:depth{d}"})
                labels.append((j, env, d))
    got = cache.get(jobs)
    append_once(ledger, {"type": "r_retention", "rows": [{"chain": j, "env": e, "depth": d, "key": r["key"]} for (j, e, d), r in zip(labels, got)]},
                ("type",))


def rebuild(ledger, reg) -> dict:
    """The memories of every chain at every depth, from the ledger's run records alone."""
    by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}
    on, off = {}, {}
    for s in sorted(ledger.select(type="r_memory"), key=lambda r: (r["policy"], r["chain"], r["position"])):
        if s["policy"] == "on":
            entries = on.setdefault(s["chain"], {0: []})
            before = design_r.mem(entries[s["position"]])
            if digest_of(before) != s["digest_in"]:
                raise SystemExit(f"chain {s['chain']} position {s['position']}: the rebuilt memory differs from the recorded one")
            entries[s["position"] + 1] = entries[s["position"]] + new_entries(by_key[s["run_key"]])
            if digest_of(design_r.mem(entries[s["position"] + 1])) != s["digest_out"]:
                raise SystemExit(f"chain {s['chain']} position {s['position']}: the memory it left differs from the recorded one")
        else:
            off.setdefault(s["chain"], []).extend(new_entries(by_key[s["run_key"]]))
    return {"on": {j: {d: design_r.mem(e) for d, e in v.items()} for j, v in on.items()},
            "off": {j: design_r.mem(e) for j, e in off.items()}}


# =============================================================================================
# held-out
# =============================================================================================
def units(env) -> dict:
    """Construction units of the training and the fresh problems (problems built with a dummy
    meter: no learner, no score)."""
    train_ids, fresh_ids = split(env, 16, 24)
    ut = sum(env.problem(i, Meter(0.0), 1, True)[0].construction_units() for i in train_ids)
    uf = sum(env.problem(i, Meter(0.0), 1, False)[0].construction_units() for i in fresh_ids)
    starts = all(env.problem(i, Meter(0.0), 1, False)[0].start_answer is not None for i in fresh_ids)
    return {"train": float(ut), "test": float(uf), "all_fresh_have_start_answers": bool(starts)}


def predicted_cpu(model, T, u) -> float:
    return float(model["a"] + model["b"] * T * u["train"] + model["d"] * u["test"])


def chain_means(arm, base, chains_of, held):
    b = {(r["env"], r["seed"]): r["acquired"] for r in base}
    by = {}
    for r in arm:
        if (r["env"], r["seed"]) in b:
            by.setdefault(chains_of(r["seed"]), {}).setdefault(r["env"], []).append(r["acquired"] - b[(r["env"], r["seed"])])
    return {j: float(np.mean([np.mean(v) for v in ev.values()])) for j, ev in by.items()}


def run_heldout(reg, cache, ledger, mem, args) -> None:
    H = reg["heldout"]
    base_seed = H["seed_base"]
    chain_of = lambda seed: (seed - base_seed) // 10
    cats = H["categories"] if not args.dev else reg["dev_heldout"]
    if not args.dev:
        on_them = [r for r in ledger.records if r.get("type") == "run" and r.get("env") in cats]
        if on_them and not find(ledger, type="r_plan"):
            raise SystemExit(f"the ledger already holds {len(on_them)} runs on the held-out categories")
        if not ledger.select(type="unlock", role=H["role"]):
            ledger.append({"type": "unlock", "role": H["role"], "why": "the held-out stage of design r (registration_r.json)"})
    U = {c: units(environments.load(c)) for c in cats}
    cats = [c for c in cats if not U[c]["all_fresh_have_start_answers"]]
    if len(cats) < 3 and not args.dev:
        raise SystemExit(f"fewer than three held-out categories can be changed by a capability: {cats}")
    model = H["cpu_model"]
    grid = H["train_grid"]
    T = {}
    for c in cats:
        ok = [t for t in grid if predicted_cpu(model["o0"], t, U[c]) <= H["max_cpu_per_run"]]
        T[c] = max(ok) if ok else min(grid)
    held_budget = lambda c, factor=1.0: dict(reg["budgets"]["heldout"], train=float(T[c]) * factor)
    J, S, J2 = reg["meta"]["chains"], H["seeds"], H["secondary_chains"]
    r0, o0, a0 = reg["version"], designs.default("o"), designs.default("a")
    plan = {"categories": cats, "units": U, "train": T}
    append_once(ledger, dict({"type": "r_plan"}, **plan), ("type",))
    say(f"held-out plan: {plan['train']}")

    def jobs(name, version, memory_of, chains, seeds, factor=1.0, budget_of=None):
        out = []
        for j in chains:
            for c in cats:
                for s in range(seeds):
                    out.append({"env": c, "version": version, "seed": base_seed + 10 * j + s,
                                "budget": budget_of(c) if budget_of else held_budget(c, factor),
                                "memory": memory_of(j), "purpose": f"relay-heldout:{name}:chain{j}"})
        return out

    arms, cancelled, matched_frozen = {}, set(), {}
    spent = lambda: sum(evaluate.cpu(r) for rows in arms.values() for r in rows)
    cap = H["cpu_cap"]

    def add(name, rows):
        arms[name] = arms.get(name, []) + rows
        say(f"held-out {name}: {len(rows)} runs, acquired {np.mean([r['acquired'] for r in rows]):.4f}; spent {spent():.0f}")

    def matched(name, version, rows_ref, budget_of):
        out = []
        for c in cats:
            want = {(r["env"], r["seed"]): evaluate.cpu(r) for r in rows_ref if r["env"] == c}
            if want:
                out += evaluate.raise_until(cache, version, want, f"relay-heldout:{name}", budget_of(c))
        append_once(ledger, {"type": "r_matched", "arm": name, "keys": [r["key"] for r in out], "reached": [bool(r["reached"]) for r in out],
                             "levels": [r["levels"] for r in out], "budgets": [r["budget"]["train"] for r in out]}, ("arm",))
        return out

    half = list(range(J // 2))
    sec = list(range(J2))
    D1, D2 = H["depths"]                                         # the shallower memories measured besides the final one
    refs = list(range(min(H["reference_chains"], J2)))
    # 1. primary-a
    add("relay", cache.get(jobs("relay", r0, lambda j: mem["on"][j][len(reg["meta"]["order"])], half, S)))
    add("frozen", cache.get(jobs("frozen", r0, lambda j: None, half, S)))
    cm = chain_means(arms["relay"], arms["frozen"], chain_of, cats)
    x = np.array([cm[j] for j in sorted(cm)])
    t = float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))) if len(x) > 1 and x.std(ddof=1) > 0 else 0.0
    append_once(ledger, {"type": "r_futility", "chains": len(x), "mean": float(x.mean()), "t": t, "stop": bool(t < H["futility_t"])}, ("type",))
    if t < H["futility_t"]:
        cancelled = {2, 3, 5, 6, 8, 9, 10}
    ratios = {}
    for c in cats:
        cells = {(r["env"], r["seed"]) for r in arms["frozen"] if r["env"] == c}
        ratios[c] = sum(evaluate.cpu(r) for r in arms["relay"] if (r["env"], r["seed"]) in cells) / max(
            sum(evaluate.cpu(r) for r in arms["frozen"] if r["env"] == c), 1e-9)
    over = [c for c, v in ratios.items() if v > H["cpu_tolerance"]]
    append_once(ledger, {"type": "r_cpu_rule", "ratios": ratios, "matched_categories": over}, ("type",))
    if over:
        rows = matched("frozen@relay", r0, [r for r in arms["relay"] if r["env"] in over], held_budget)
        add("frozen@relay", rows)

    items = [
        (2, "primary-b", lambda: (add("relay", cache.get(jobs("relay", r0, lambda j: mem["on"][j][len(reg["meta"]["order"])], range(J // 2, J), S))),
                                  add("frozen", cache.get(jobs("frozen", r0, lambda j: None, range(J // 2, J), S))))),
        (3, "shuffled", lambda: add("shuffled", cache.get(jobs("shuffled", r0, lambda j: design_r.shuffled(mem["on"][j][len(reg["meta"]["order"])], j), sec, 2)))),
        (4, "o0@relay", lambda: add("o0@relay", matched("o0@relay", o0, [r for r in arms["relay"] if chain_of(r["seed"]) < J2 and (r["seed"] - base_seed) % 10 < 2], held_budget))),
        (5, "offpolicy", lambda: add("offpolicy", cache.get(jobs("offpolicy", r0, lambda j: mem["off"][j], sec, 2)))),
        (6, "libonly", lambda: add("libonly", cache.get(jobs("libonly", r0, lambda j: design_r.without(mem["on"][j][len(reg["meta"]["order"])], design_r.KIND_STATS), sec, 2)))),
        (7, "frozen@ceiling", lambda: add("frozen@ceiling", cache.get(jobs("frozen@ceiling", r0, lambda j: None, sec, 1, H["ceiling_factor"])))),
        (8, "prioronly", lambda: add("prioronly", cache.get(jobs("prioronly", r0, lambda j: design_r.without(mem["on"][j][len(reg["meta"]["order"])], design_r.KIND_LIB), sec, 2)))),
        (9, f"depth{D1}", lambda: add(f"depth{D1}", cache.get(jobs(f"depth{D1}", r0, lambda j: mem["on"][j][D1], sec, 1)))),
        (10, f"depth{D2}", lambda: add(f"depth{D2}", cache.get(jobs(f"depth{D2}", r0, lambda j: mem["on"][j][D2], sec, 1)))),
        (11, "references", lambda: (add("o0@ref", cache.get(jobs("o0@ref", o0, lambda j: None, refs, 1, budget_of=lambda c: dict(evaluate.RUN_BUDGET)))),
                                    add("a0@ref", cache.get(jobs("a0@ref", a0, lambda j: None, refs, 1, budget_of=lambda c: dict(evaluate.RUN_BUDGET)))))),
        (12, "a0@relay", lambda: add("a0@relay", matched("a0@relay", a0, [r for r in arms["relay"] if chain_of(r["seed"]) in refs and (r["seed"] - base_seed) % 10 == 0], held_budget))),
    ]
    for number, name, run in items:
        if number in cancelled:
            append_once(ledger, {"type": "r_item", "item": number, "name": name, "done": False, "why": "cancelled by the futility look"}, ("type", "item"))
            continue
        if spent() > cap:
            append_once(ledger, {"type": "r_cap", "item": number, "name": name, "spent": spent(), "cap": cap}, ("type",))
            break
        run()
        append_once(ledger, {"type": "r_item", "item": number, "name": name, "done": True}, ("type", "item"))
    ledger.append({"type": "r_stage_done", "stage": "heldout", "categories": cats, "train": T,
                   "arms": {name: [r["key"] for r in rows] for name, rows in arms.items()}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=guard.LIVE)
    parser.add_argument("--stage", choices=ORDER_STAGES, required=True)
    parser.add_argument("--registration", default=REGISTRATION)
    parser.add_argument("--dev", action="store_true", help="development: a scratch ledger, source categories only")
    args = parser.parse_args()
    dispatch_extra.install()
    if args.dev == guard.is_registered(args.ledger):
        raise SystemExit("the registered experiment writes the working ledger; --dev writes a scratch ledger")
    reg = json.load(open(args.registration))
    if not args.dev:
        if os.path.realpath(args.registration) != os.path.realpath(REGISTRATION):
            raise SystemExit("the registered experiment reads registry/registration_r.json and no other file")
        root = os.path.dirname(os.path.dirname(HERE))
        wrong = [f for f, sha in reg["files"].items() if hashlib.sha256(open(os.path.join(root, f), "rb").read()).hexdigest() != sha]
        if wrong or designs.digest(reg["version"]) != reg["version_digest"] or designs.digest(design_r.default()) != reg["version_digest"]:
            raise SystemExit(f"the files or the version differ from the registration: {wrong or 'version digest'}")
    guard.same_history(args.ledger)
    guard.single_writer(args.ledger)
    installed = fresh.install()
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    if not args.dev:
        recorded = find(ledger, type="registration_r")
        if recorded is None:
            guard.amendment(ledger, reg["amendment"], reg["what"])
            recorded = ledger.append({"type": "registration_r", "digest": ledgers.digest(reg), "registration": reg})
        if recorded["digest"] != ledgers.digest(reg):
            raise SystemExit("registration_r.json differs from the file recorded in the ledger")
    for e in reg["meta"]["order"]:
        if roles.effective_role(environments.load(e).category, ledger) != "source":
            raise SystemExit(f"{e} is not in the source pool")
    held = reg["heldout"]["categories"] if not args.dev else reg["dev_heldout"]
    for e in held:
        if e not in environments.REGISTRY:
            raise SystemExit(f"{e} has no admitted adapter (installed: {installed})")
        role = roles.effective_role(environments.load(e).category, ledger)
        if args.dev and role != "source":
            raise SystemExit(f"development touches source categories only: {e}")
        if not args.dev and role != reg["heldout"]["role"]:
            raise SystemExit(f"{e} has role {role!r}, not {reg['heldout']['role']!r}")
    cache = Cache(ledger)
    stage = args.stage
    if find(ledger, type="r_stage_done", stage=stage):
        say(f"the stage {stage} is recorded")
        return 0
    if stage == "meta":
        run_meta(reg, cache, ledger)
        ledger.append({"type": "r_stage_done", "stage": "meta"})
        return 0
    if not find(ledger, type="r_stage_done", stage="meta"):
        raise SystemExit("the stage heldout follows meta")
    run_heldout(reg, cache, ledger, rebuild(ledger, reg), args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
