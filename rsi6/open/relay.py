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


CHUNK = 16                                              # runs per submission: what a stopped stage can lose


def chunked(cache, jobs) -> list:
    """The runs of ``jobs`` in order, submitted a chunk at a time: the ledger gets a chunk's runs when
    the chunk is done, so a stopped stage repeats at most one chunk. A run does not depend on the
    chunk it is in."""
    got = []
    for k in range(0, len(jobs), CHUNK):
        got += cache.get(jobs[k:k + CHUNK])
    return got


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
        got = chunked(cache, jobs)
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
    got = chunked(cache, jobs)
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


def raise_with_memory(cache, version, want: dict, purpose, budget, memory_of=lambda pair: None) -> list:
    """``evaluate.raise_until`` with a memory per pair: the same schedule (doubled at first, then the
    factor that the measured CPU of the last two levels says is needed with a tenth to spare, at
    least 2 and at most 64 per level, 64 when the CPU did not rise, at most twelve levels counting
    the registered budget as the first). With no memory its jobs, and so its runs, are those of
    ``evaluate.raise_until``. A pair still below its CPU after the last level is not reached."""
    value = {pair: budget["train"] for pair in want}
    last, first, seen = {}, {}, {pair: [] for pair in want}
    pending = list(want)
    for _ in range(12):
        if not pending:
            break
        jobs = []
        for e, s in pending:
            job = {"env": e, "version": version, "seed": s, "budget": dict(budget, train=value[(e, s)]), "purpose": purpose}
            memory = memory_of((e, s))
            if memory is not None:
                job["memory"] = memory
            jobs.append(job)
        got = []
        for k in range(0, len(jobs), 4):                   # in small batches, so that a stopped driver loses little
            got += cache.get(jobs[k:k + 4])
        for pair, r in zip(pending, got):
            last[pair] = r
            first.setdefault(pair, r)                        # the run at the registered budget
            seen[pair].append((value[pair], evaluate.cpu(r)))
            factor = 2.0
            if len(seen[pair]) >= 2:
                (v1, c1), (v2, c2) = seen[pair][-2:]
                slope = (c2 - c1) / (v2 - v1)
                factor = 64.0 if slope <= 0 else min(64.0, max(2.0, (v2 + (1.1 * want[pair] - c2) / slope) / v2))
            value[pair] *= factor
        pending = [p for p in pending if evaluate.cpu(last[p]) < want[p]]
    return [dict(last[p], reached=evaluate.cpu(last[p]) >= want[p], levels=len(seen[p]), matched_cpu=want[p], first_key=first[p]["key"])
            for p in want]


class Counted:
    """The cache, counting the CPU of every distinct run the stage has requested so far. A replay
    makes the same requests in the same order, so it reads the same count at every step (the
    cache itself may already hold runs of an item that was stopped half way)."""

    def __init__(self, cache):
        self.cache, self.cpu = cache, {}
        self.by_key = cache.by_key

    def get(self, jobs, workers: int = 4) -> list:
        got = chunked(self.cache, jobs)
        for r in got:
            self.cpu.setdefault(r["key"], evaluate.cpu(r))
        return got

    def spent(self) -> float:
        return float(sum(self.cpu.values()))


ITEMS = [(1, "primary-a"), (2, "primary-b"), (3, "shuffled"), (4, "o0@relay"), (5, "offpolicy"), (6, "libonly"),
         (7, "frozen@ceiling"), (8, "prioronly"), (9, "depth-a"), (10, "depth-b"), (11, "references"), (12, "a0@relay")]
FUTILE = (2, 3, 5, 6, 8, 9, 10)                          # cancelled by the futility look
LATER_R0 = ("shuffled", "offpolicy", "libonly", "prioronly")   # r0 arms compared with relay: the CPU rule applies to them


def item_cost(number, c, unit, H, J, S, n_sec, R, raised=()) -> float:
    """Predicted recorded CPU of priority item ``number`` on category ``c``: runs times the CPU of a
    run (``unit``: r0 at the category's training budget, o0 and a0 at the reference budget). A
    matched item counts ``matched_levels`` runs at relay's CPU per pair; frozen at the ceiling
    budget ``ceiling_cost`` runs; on a category of ``raised`` (frozen raised to relay's CPU) the
    primary counts ``matched_levels - 1`` further runs per pair. ``n_sec`` is the number of chains
    of the secondary items."""
    r0, ref = unit["r0"][c], unit["o0@ref"][c] + unit["a0@ref"][c]
    half, lv, ceil = J // 2, H["matched_levels"], H["ceiling_cost"]
    pair = 2 * r0 + ((lv - 1) * r0 if c in raised else 0.0)
    return {1: half * S * pair, 2: (J - half) * S * pair, 3: n_sec * 2 * r0, 4: n_sec * 2 * lv * r0, 5: n_sec * 2 * r0,
            6: n_sec * 2 * r0, 7: n_sec * ceil * r0, 8: n_sec * 2 * r0, 9: n_sec * r0, 10: n_sec * r0, 11: R * ref, 12: R * lv * r0}[number]


def plan_of(H, cats, U, J, S, J2, R, h_cap):
    """The plan made before any held-out run (registration_r.json, heldout.plan_rule)."""
    model, grid = H["cpu_model"], sorted(H["train_grid"], reverse=True)
    T = {}
    for c in cats:
        ok = [t for t in grid if predicted_cpu(model["o0"], t, U[c]) <= H["max_cpu_per_run"]]
        T[c] = max(ok) if ok else min(grid)
    factor = H["machine_factor"]
    while True:
        unit = {"r0": {c: predicted_cpu(model["o0"], T[c], U[c]) * model["r0_over_o0"] for c in cats},
                "o0@ref": {c: predicted_cpu(model["o0"], evaluate.RUN_BUDGET["train"], U[c]) for c in cats},
                "a0@ref": {c: predicted_cpu(model["o0"], evaluate.RUN_BUDGET["train"], U[c]) for c in cats}}
        raised = tuple(cats) if H.get("frozen_matched_everywhere") else ()
        cost = {n: sum(item_cost(n, c, unit, H, J, S, J2, R, raised) for c in cats) for n, _ in ITEMS}
        lower = [c for c in cats if T[c] > min(grid)]
        if factor * (cost[1] + cost[2]) <= h_cap or not lower:
            break
        worst = max(lower, key=lambda c: item_cost(1, c, unit, H, J, S, J2, R, raised) + item_cost(2, c, unit, H, J, S, J2, R, raised))
        T[worst] = max(t for t in grid if t < T[worst])
    kept = [n for n, name in ITEMS if name not in H.get("dropped_arms", [])]
    while len(kept) > 2 and factor * sum(cost[n] for n in kept) > h_cap:
        kept.pop()
    return {"train": T, "unit": unit, "cost": {str(n): cost[n] for n in cost}, "kept": kept,
            "projection": factor * sum(cost[n] for n in kept), "h_cap": h_cap}


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
    J, S, J2 = reg["meta"]["chains"], H["seeds"], H["secondary_chains"]
    R = min(H["reference_chains"], J2)
    stage_cpu = lambda prefixes: sum(evaluate.cpu(r) for r in cache.by_key.values() if r.get("purpose", "").startswith(prefixes))
    meta_cpu = stage_cpu(("relay-meta:", "relay-retention:"))
    factor = H["machine_factor"]
    h_cap = H["cpu_total"] - factor * (H["cpu_development"] + meta_cpu) - H["cpu_reserve"]
    plan = plan_of(H, cats, U, J, S, J2, R, h_cap)
    T = plan["train"]
    append_once(ledger, {"type": "r_plan", "categories": cats, "units": U, "train": T, "meta_cpu": meta_cpu, **{k: plan[k] for k in
                         ("unit", "cost", "kept", "projection", "h_cap")}}, ("type",))
    say(f"held-out plan: train {T}, items {plan['kept']}, projection {plan['projection']:.0f} of {h_cap:.0f}")
    held_budget = lambda c, factor=1.0: dict(reg["budgets"]["heldout"], train=float(T[c]) * factor)
    r0, o0, a0 = reg["version"], designs.default("o"), designs.default("a")
    final = lambda j: mem["on"][j][len(reg["meta"]["order"])]
    memories = {"relay": final, "frozen": lambda j: None, "shuffled": lambda j: design_r.shuffled(final(j), j),
                "offpolicy": lambda j: mem["off"][j], "libonly": lambda j: design_r.without(final(j), design_r.KIND_STATS),
                "prioronly": lambda j: design_r.without(final(j), design_r.KIND_LIB)}

    def jobs(name, version, memory_of, chains, seeds, factor=1.0, budget_of=None):
        out = []
        for j in chains:
            for c in cats:
                for s in range(seeds):
                    out.append({"env": c, "version": version, "seed": base_seed + 10 * j + s,
                                "budget": budget_of(c) if budget_of else held_budget(c, factor),
                                "memory": memory_of(j), "purpose": f"relay-heldout:{name}:chain{j}"})
        return out

    arms = {}
    cache = Counted(cache)
    spent = cache.spent
    versions = {"o0@ref": o0, "a0@ref": a0}

    def add(name, rows):
        arms[name] = arms.get(name, []) + rows
        say(f"held-out {name}: {len(rows)} runs, acquired {np.mean([r['acquired'] for r in rows]):.4f}; spent {spent():.0f}")

    def run_arms(names, chains, seeds, factor=1.0, budget_of=None):
        """The arms ``names`` on the same chains, categories and seeds, as one batch interleaved pair by
        pair (compared arms are measured side by side in time); every arm's rows keep the order
        chain, category, seed."""
        lists = [jobs(name, versions.get(name, r0), memories.get(name, lambda j: None), chains, seeds, factor, budget_of) for name in names]
        got = cache.get([job for group in zip(*lists) for job in group])
        for k, name in enumerate(names):
            add(name, got[k::len(names)])

    def matched(name, version, rows_ref, memory_of=lambda j: None, part=None):
        out = []
        for c in cats:
            want = {(r["env"], r["seed"]): evaluate.cpu(r) for r in rows_ref if r["env"] == c}
            if want:
                out += raise_with_memory(cache, version, want, f"relay-heldout:{name}", held_budget(c), lambda pair: memory_of(chain_of(pair[1])))
        append_once(ledger, {"type": "r_matched", "arm": name, "part": part, "keys": [r["key"] for r in out],
                             "first_keys": [r["first_key"] for r in out], "reached": [bool(r["reached"]) for r in out],
                             "levels": [r["levels"] for r in out], "budgets": [r["budget"]["train"] for r in out]}, ("type", "arm", "part"))
        return out

    raise_cpu = {}                                                # CPU of every level of frozen's raise, by part

    def cpu_rule(name, rows, part=None):
        """The registered CPU rule: on a category where relay's CPU over the arm's exceeds the
        tolerance over the arm's pairs, the arm is raised pair by pair to relay's CPU."""
        pairs = {(r["env"], r["seed"]) for r in rows}
        ratios = {}
        for c in cats:
            mine = [r for r in rows if r["env"] == c]
            theirs = [r for r in arms["relay"] if r["env"] == c and (r["env"], r["seed"]) in pairs]
            ratios[c] = sum(evaluate.cpu(r) for r in theirs) / max(sum(evaluate.cpu(r) for r in mine), 1e-9) if mine else None
        over = [c for c, v in ratios.items() if v is not None and v > H["cpu_tolerance"]]
        if name == "frozen" and H.get("frozen_matched_everywhere"):          # development rule (f)
            over = list(cats)
        append_once(ledger, {"type": "r_cpu_rule", "arm": name, "part": part, "ratios": ratios, "matched_categories": over},
                    ("type", "arm", "part"))
        if over:
            before = spent()
            ref = [r for r in arms["relay"] if r["env"] in over and (r["env"], r["seed"]) in pairs]
            add(f"{name}@relay", matched(f"{name}@relay", r0, ref, memories[name], part))
            raise_cpu[(name, part)] = spent() - before

    half = list(range(J // 2))
    DA, DB = H["depths"]                                         # the shallower memories measured besides the final one
    kept = list(plan["kept"])
    memories[f"depth{DA}"] = lambda j: mem["on"][j][DA]
    memories[f"depth{DB}"] = lambda j: mem["on"][j][DB]
    memories["frozen@ceiling"] = lambda j: None

    def primary(chains, part):
        n = len(arms.get("relay", []))
        run_arms(["relay", "frozen"], chains, S)
        relay_rows, frozen_rows = arms["relay"][n:], arms["frozen"][n:]
        if part == "a":                                          # the categories are decided over item 1
            cpu_rule("frozen", frozen_rows, "a")
            return
        over = find(ledger, type="r_cpu_rule", arm="frozen", part="a")["matched_categories"]
        if over:                                                 # primary-b follows them
            before = spent()
            add("frozen@relay", matched("frozen@relay", r0, [r for r in relay_rows if r["env"] in over], memories["frozen"], "b"))
            raise_cpu[("frozen", "b")] = spent() - before

    def later(name):
        n = len(arms.get(name, []))
        run_arms([name], sec, 2)
        cpu_rule(name, arms[name][n:])

    def raised_to_relay(name, version, rows_ref):
        """o0 or a0 raised pair by pair to relay's CPU; its runs at the registered budget (the first
        level of every raise) are kept as the arm ``name`` without the suffix."""
        rows = matched(name, version, rows_ref)
        add(name, rows)
        add(name.split("@")[0], [cache.by_key[r["first_key"]] for r in rows])

    relay_rows = lambda chains, seeds: [r for r in arms["relay"] if chain_of(r["seed"]) in chains and (r["seed"] - base_seed) % 10 < seeds]
    run_item = {
        2: lambda: primary(range(J // 2, J), "b"),
        3: lambda: later("shuffled"),
        4: lambda: raised_to_relay("o0@relay", o0, relay_rows(sec, 2)),
        5: lambda: later("offpolicy"),
        6: lambda: later("libonly"),
        7: lambda: run_arms(["frozen@ceiling"], sec, 1, H["ceiling_factor"]),
        8: lambda: later("prioronly"),
        9: lambda: run_arms([f"depth{DA}"], sec, 1),
        10: lambda: run_arms([f"depth{DB}"], sec, 1),
        11: lambda: run_arms(["o0@ref", "a0@ref"], refs, 1, budget_of=lambda c: dict(evaluate.RUN_BUDGET)),
        12: lambda: raised_to_relay("a0@relay", a0, relay_rows(refs, 1)),
    }
    # 1. primary-a, then the futility look and the CPU rule
    primary(half, "a")
    cm = chain_means(arms["relay"], arms["frozen"], chain_of, cats)
    x = np.array([cm[j] for j in sorted(cm)])
    t = float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))) if len(x) > 1 and x.std(ddof=1) > 0 else 0.0
    stop = bool(t < H["futility_t"])
    append_once(ledger, {"type": "r_futility", "chains": len(x), "mean": float(x.mean()), "t": t, "stop": stop}, ("type",))
    append_once(ledger, {"type": "r_item", "item": 1, "name": "primary-a", "done": True}, ("type", "item"))
    # after a futility stop the primary holds chains below J/2 only: the items that still run cover those chains
    measured = J // 2 if stop else J
    sec = list(range(min(J2, measured)))
    refs = list(range(min(R, measured)))
    raised_a = find(ledger, type="r_cpu_rule", arm="frozen", part="a")["matched_categories"]
    for number, name in ITEMS[1:]:
        if stop and number in FUTILE:
            append_once(ledger, {"type": "r_item", "item": number, "name": name, "done": False, "why": "cancelled by the futility look"},
                        ("type", "item"))
            continue
        if name in H.get("dropped_arms", []):                                # development rule (b)
            append_once(ledger, {"type": "r_item", "item": number, "name": name, "done": False, "why": "dropped by a development rule"},
                        ("type", "item"))
            continue
        if number not in kept:
            append_once(ledger, {"type": "r_item", "item": number, "name": name, "done": False, "why": "dropped by the CPU plan"},
                        ("type", "item"))
            continue
        # re-project with the measured CPU per run of r0 on each category; primary-b's raise of frozen is projected
        # from the measured CPU of primary-a's raise
        done_r0 = [r for a in ("relay", "frozen") for r in arms.get(a, [])]
        unit = {"r0": {c: float(np.mean([evaluate.cpu(r) for r in done_r0 if r["env"] == c])) for c in cats},
                "o0@ref": plan["unit"]["o0@ref"], "a0@ref": plan["unit"]["a0@ref"]}
        todo = [n for n in kept if n >= number and not (stop and n in FUTILE) and ITEMS[n - 1][1] not in H.get("dropped_arms", [])]
        raise_b = raise_cpu.get(("frozen", "a"), 0.0) * (J - J // 2) / (J // 2)
        cost = lambda ns: (sum(item_cost(n, c, unit, H, J, S, len(sec), len(refs)) for n in ns for c in cats)
                           + (raise_b if 2 in ns and raised_a else 0.0))
        dropped = []
        while len(todo) > 1 and factor * (spent() + cost(todo)) > h_cap:
            dropped.append(todo.pop())
        if dropped:
            kept = [n for n in kept if n not in dropped]
            append_once(ledger, {"type": "r_drop", "before_item": number, "dropped": dropped, "spent": spent(),
                                 "projection": factor * (spent() + cost(todo)), "h_cap": h_cap}, ("type", "before_item"))
        if factor * (spent() + cost(todo)) > h_cap:
            append_once(ledger, {"type": "r_cap", "item": number, "name": name, "spent": spent(),
                                 "projection": factor * (spent() + cost(todo)), "h_cap": h_cap}, ("type",))
            break
        run_item[number]()
        append_once(ledger, {"type": "r_item", "item": number, "name": name, "done": True}, ("type", "item"))
    ledger.append({"type": "r_stage_done", "stage": "heldout", "categories": cats, "train": T,
                   "arms": {name: [r["key"] for r in rows] for name, rows in arms.items()}})


_WAIT = []


def wait_for_registered_drivers() -> None:
    """Development measures nothing while a registered driver runs: it waits for the registered
    ledgers' writer lock and holds it shared (a registered driver then refuses to start until the
    development run has ended), so that neither perturbs the other's CPU-seconds."""
    import fcntl
    handle = open(os.path.join(os.path.dirname(guard.MAIN), ".writer.lock"), "a")
    fcntl.flock(handle, fcntl.LOCK_SH)
    _WAIT.append(handle)


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
    if os.path.exists(args.ledger) and guard.torn(args.ledger):
        raise SystemExit(f"{args.ledger}: the last line is incomplete (a driver was stopped while writing it). Remove that line, "
                         "note it in the record, and start again: the stage replays from its start")
    guard.same_history(args.ledger)
    guard.single_writer(args.ledger)
    if args.dev:
        wait_for_registered_drivers()
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
