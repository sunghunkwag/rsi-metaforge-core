"""The relay experiment of design r (the Owner's instruction 14): does the learner's own record
of its discoveries, carried from one category to the next, make its later discovery better?

    python -m rsi6.open.relay --stage meta|heldout [--ledger PATH] [--registration PATH] [--dev]

``meta``     chains of acquisitions on source categories, in the registered order. In an
             on-policy chain every acquisition starts from the memory of the acquisitions
             before it in the chain, so the discovery machinery that generates its candidates
             (operator prior, composite operators, block library: ``learner/design_r.py``) was
             rebuilt from what the chain itself discovered, and what it discovers rebuilds the
             machinery of the next one. An off-policy chain makes the same acquisitions (same
             categories, same seeds) each with an empty memory: the same amount of record,
             produced by a machinery that never changed. At the end of every on-policy chain
             its first category is acquired once more with the chain's final memory (retention).
``heldout``  on the held-out categories, which no process used before this stage (role
             ``fresh``, unlocked here), for every chain and seed, paired: design r with the
             chain's final memory (relay), with no memory (frozen: design q exactly), with the
             memory's operator labels deranged and its library replaced by blocks that were not
             kept (shuffled), with the off-policy chain's memory (offpolicy), with only the
             operator record (prior) and with only the library (blocks); generation 0 of the open
             design with its training budget raised pair by pair to relay's CPU (o0@relay); and
             frozen at four times the training budget on a subset (ceiling).

A chain is rebuilt from the ledger: the memory an acquisition passes on is the one its run
record's report holds (``report.relay``), and every step is recorded (``r_chain``) with the
digest of the memory it started from. A stopped stage is resumed by starting the driver again:
every measurement is served from the ledger and every record is checked against the recorded
one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
from rsi6.kernel.run import Cache
from rsi6.learner import design_r, designs, dispatch_extra
from rsi6.open import evaluate
from rsi6.open.discovery import append_once

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration_r.json")
ORDER = ("meta", "heldout")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def entry_of(record) -> dict | None:
    rep = record.get("report") or {}
    return rep.get("relay")


def chain_jobs(reg, budget, j, k, memory, purpose):
    env = reg["meta"]["order"][k]
    seed = reg["seeds"]["meta_base"] + 100 * j + k
    return {"env": env, "version": reg["version"], "seed": seed, "budget": budget, "memory": memory, "purpose": purpose}


def run_meta(reg, cache, ledger, budget) -> dict:
    n, order = reg["meta"]["chains"], reg["meta"]["order"]
    memories = {j: {"entries": []} for j in range(n)}
    for k in range(len(order)):
        jobs = [chain_jobs(reg, budget, j, k, memories[j], f"relay-meta:chain{j}:pos{k}") for j in range(n)]
        got = cache.get(jobs)
        for j, (job, r) in enumerate(zip(jobs, got)):
            append_once(ledger, {"type": "r_chain", "kind": "on", "chain": j, "position": k, "env": job["env"], "seed": job["seed"],
                                 "key": r["key"], "memory_in": ledgers.digest(job["memory"]), "entries_in": len(job["memory"]["entries"])},
                        ("kind", "chain", "position"))
            e = entry_of(r)
            if e is not None:
                memories[j] = {"entries": job["memory"]["entries"] + [e]}
        say(f"meta position {k} ({order[k]}): acquired {np.mean([r['acquired'] for r in got]):.4f}, "
            f"switches {np.mean([(r['report'] or {}).get('switches', 0) for r in got]):.2f}")
    # off-policy: the same acquisitions, each from an empty memory
    off = {j: {"entries": []} for j in range(n)}
    jobs = [chain_jobs(reg, budget, j, k, {"entries": []}, f"relay-meta:off{j}:pos{k}") for j in range(n) for k in range(len(order))]
    got = cache.get(jobs)
    for job, r in zip(jobs, got):
        j = (job["seed"] - reg["seeds"]["meta_base"]) // 100
        k = (job["seed"] - reg["seeds"]["meta_base"]) % 100
        append_once(ledger, {"type": "r_chain", "kind": "off", "chain": j, "position": k, "env": job["env"], "seed": job["seed"],
                             "key": r["key"], "memory_in": ledgers.digest(job["memory"]), "entries_in": 0}, ("kind", "chain", "position"))
    for j in range(n):
        for k in range(len(order)):
            r = got[j * len(order) + k]
            e = entry_of(r)
            if e is not None:
                off[j] = {"entries": off[j]["entries"] + [e]}
    # retention: the chain's first category again, with the final memory and a new seed
    jobs = [{"env": order[0], "version": reg["version"], "seed": reg["seeds"]["retention_base"] + j, "budget": budget,
             "memory": memories[j], "purpose": f"relay-meta:retention{j}"} for j in range(n)]
    jobs += [{"env": order[0], "version": reg["version"], "seed": reg["seeds"]["retention_base"] + j, "budget": budget,
              "memory": {"entries": []}, "purpose": f"relay-meta:retention-empty{j}"} for j in range(n)]
    got = cache.get(jobs)
    for j in range(n):
        append_once(ledger, {"type": "r_chain", "kind": "retention", "chain": j, "position": len(order), "env": order[0],
                             "key": got[j]["key"], "key_empty": got[n + j]["key"], "memory_in": ledgers.digest(memories[j])},
                    ("kind", "chain", "position"))
    return {"on": memories, "off": off}


def rebuild(ledger, reg) -> dict:
    """The final memories of the chains, from the ledger's run records."""
    by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}
    out = {"on": {}, "off": {}}
    for kind in ("on", "off"):
        steps = sorted((r for r in ledger.select(type="r_chain", kind=kind)), key=lambda r: (r["chain"], r["position"]))
        for s in steps:
            mem = out[kind].setdefault(s["chain"], {"entries": []})
            if kind == "on" and ledgers.digest(mem) != s["memory_in"]:
                raise SystemExit(f"chain {s['chain']} position {s['position']}: the memory rebuilt from the ledger differs from the recorded one")
            e = entry_of(by_key[s["key"]])
            if e is not None:
                mem["entries"] = mem["entries"] + [e]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=guard.LIVE)
    parser.add_argument("--stage", choices=ORDER, required=True)
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
        if wrong or designs.digest(reg["version"]) != reg["version_digest"]:
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
    budget = dict(reg["budget"])
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
    if stage == "heldout" and not find(ledger, type="r_stage_done", stage="meta"):
        raise SystemExit("the stage heldout follows meta")
    if stage == "meta":
        run_meta(reg, cache, ledger, budget)
        ledger.append({"type": "r_stage_done", "stage": "meta"})
        return 0
    mem = rebuild(ledger, reg)
    if not args.dev and not ledger.select(type="unlock", role=reg["heldout"]["role"]):
        ledger.append({"type": "unlock", "role": reg["heldout"]["role"], "why": "the held-out stage of design r (registration_r.json)"})
    H, S = reg["heldout"], reg["seeds"]
    n = reg["meta"]["chains"]
    o0 = designs.default("o")
    arms = {}

    def jobs_for(name, version, memory_of, seeds_per_chain, chains, budget_of=lambda j: budget):
        out = []
        for j in chains:
            for e in held:
                for s in range(seeds_per_chain):
                    out.append({"env": e, "version": version, "seed": S["heldout_base"] + 10 * j + s, "budget": budget_of(j),
                                "memory": memory_of(j), "purpose": f"relay-heldout:{name}:chain{j}"})
        return out

    full, sub = H["seeds_full"], H["seeds_sub"]
    chains = list(range(n))
    plan = [("relay", lambda j: mem["on"][j], full), ("frozen", lambda j: {"entries": []}, full),
            ("shuffled", lambda j: design_r.shuffled(mem["on"][j], S["permutation"] + j), sub),
            ("offpolicy", lambda j: mem["off"][j], sub),
            ("prior", lambda j: design_r.ablated(mem["on"][j], "prior"), sub),
            ("blocks", lambda j: design_r.ablated(mem["on"][j], "blocks"), sub)]
    for name, memory_of, k in plan:
        jobs = jobs_for(name, reg["version"], memory_of, k, chains)
        arms[name] = cache.get(jobs)
        say(f"held-out {name}: acquired {np.mean([r['acquired'] for r in arms[name]]):.4f} over {len(jobs)} runs")
    want = {(r["env"], r["seed"]): evaluate.cpu(r) for r in arms["relay"] if (r["seed"] - S["heldout_base"]) % 10 < sub}
    rows = evaluate.raise_until(cache, o0, want, "relay-heldout:o0@relay", budget)
    arms["o0@relay"] = rows
    append_once(ledger, {"type": "r_matched", "arm": "o0@relay", "keys": [r["key"] for r in rows],
                         "reached": [bool(r["reached"]) for r in rows], "levels": [r["levels"] for r in rows],
                         "budgets": [r["budget"]["train"] for r in rows]}, ("arm",))
    ceiling = dict(budget, train=budget["train"] * H["ceiling_factor"])
    arms["frozen@ceiling"] = cache.get(jobs_for("frozen@ceiling", reg["version"], lambda j: {"entries": []}, H["seeds_ceiling"],
                                                chains, lambda j: ceiling))
    ledger.append({"type": "r_stage_done", "stage": "heldout", "envs": held,
                   "arms": {name: [r["key"] for r in rows] for name, rows in arms.items()}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
