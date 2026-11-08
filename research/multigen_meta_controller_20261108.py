#!/usr/bin/env python3
"""Four-generation meta-policy experiment with held-out cross-substrate transfer.

Frozen source dependencies: PR #55 and #56 at exact immutable commit SHAs.
New substrate: rectangular integer matrices; other inputs are integer lists,
strings and directed graphs. Existing PRs, TEST/J pools, RSI-4, and sealed
verification code are never changed or queried.

A meta-controller *updates its own choice of proposal/mutation operators* after
each generation of public support tasks. Fresh transfer tasks and a final
single-use independent audit NEVER update those weights. This tests stateful
learning-to-search, not self-editing source code or general AGI/RSI.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time
import types

BASE_MAIN = "c4f0a8627a1c9f37dd3aa6291b0eee0c78648210"
PR55 = "dbb7ba9600534e1578198d45bc58a4d99893fdf1"
PR56 = "967c4d08c2e22403a5e7689796d011e6a85677b8"
DOMAINS = ("integer_list", "string", "directed_graph", "matrix")
ACTIONS = ("uniform", "mutate", "splice", "novelty", "failure")
ARMS = (
    "frozen_uniform", "frozen_mutation", "frozen_ensemble",
    "placebo_domain", "adaptive_global", "adaptive_domain", "adaptive_shrunk",
)
GENERATIONS = 4
BUDGET = 40
TRAIN_N = 12
SHIFT_N = 20
SUPPORT_SEEDS = 8
DEV_SEEDS = 12
AUDIT_SEEDS = 16
CPU_CAP = 0.75
ETA = 3.0
PROPOSAL_TRIES = 24
MATRIX_OPS = {
    "transform": (
        "transpose", "flip_rows", "flip_cols", "absolute",
        "positive", "negative", "sort_rows", "rotate_rows",
        "zero_diag", "zero_offdiag",
    ),
    "aggregate": (
        "sum", "minimum", "maximum", "nonzero", "rows",
        "cols", "trace", "anti_trace", "first_row_sum",
        "last_col_sum",
    ),
}


def seed_of(*parts):
    data = "::".join(map(str, parts)).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


def load_frozen(repo):
    def load(sha, path, name):
        body = subprocess.check_output(
            ["git", "-C", str(repo), "show", f"{sha}:{path}"],
            text=True,
        )
        mod = types.ModuleType(name)
        mod.__file__ = f"{sha}:{path}"
        sys.modules[name] = mod
        exec(compile(body, mod.__file__, "exec"), mod.__dict__)
        return mod

    prior = load(
        PR55, "research/tri_substrate_portfolio_20261108.py",
        "_frozen_tri_substrate_pr55",
    )
    previous = load(
        PR56, "research/typed_replay_duplicate_reclamation_20261108.py",
        "_frozen_typed_replay_pr56",
    )
    assert previous.PR55_SHA == PR55
    assert set(prior.DOMAINS) == set(DOMAINS[:3])
    return prior, previous


def ops(domain, prior):
    return MATRIX_OPS if domain == "matrix" else prior.OPS[domain]


def valid(domain, program, prior):
    if domain != "matrix":
        return prior.valid(domain, program)
    cfg = MATRIX_OPS
    return (
        1 <= len(program) <= 3
        and program[-1] in cfg["aggregate"]
        and all(t in cfg["transform"] for t in program[:-1])
    )


def matrix_transform(op, grid):
    g = tuple(tuple(row) for row in grid)
    r, c = len(g), (len(g[0]) if g else 0)
    if op == "transpose":
        return tuple(zip(*g)) if c else ()
    if op == "flip_rows":
        return g[::-1]
    if op == "flip_cols":
        return tuple(row[::-1] for row in g)
    if op == "absolute":
        return tuple(tuple(abs(v) for v in row) for row in g)
    if op == "positive":
        return tuple(tuple(max(0, v) for v in row) for row in g)
    if op == "negative":
        return tuple(tuple(min(0, v) for v in row) for row in g)
    if op == "sort_rows":
        return tuple(tuple(sorted(row)) for row in g)
    if op == "rotate_rows":
        return g[1:] + g[:1]
    if op == "zero_diag":
        return tuple(
            tuple(0 if i == j else v for j, v in enumerate(row))
            for i, row in enumerate(g)
        )
    if op == "zero_offdiag":
        return tuple(
            tuple(v if i == j else 0 for j, v in enumerate(row))
            for i, row in enumerate(g)
        )
    raise ValueError(op)


def matrix_aggregate(op, grid):
    g = tuple(tuple(row) for row in grid)
    flat = tuple(v for row in g for v in row)
    n, m = len(g), (len(g[0]) if g else 0)
    if op == "sum":
        return sum(flat)
    if op == "minimum":
        return min(flat, default=0)
    if op == "maximum":
        return max(flat, default=0)
    if op == "nonzero":
        return sum(v != 0 for v in flat)
    if op == "rows":
        return n
    if op == "cols":
        return m
    if op == "trace":
        return sum(g[i][i] for i in range(min(n, m)))
    if op == "anti_trace":
        return sum(g[i][m-1-i] for i in range(min(n, m)))
    if op == "first_row_sum":
        return sum(g[0]) if g else 0
    if op == "last_col_sum":
        return sum(row[-1] for row in g if row)
    raise ValueError(op)


def execute(domain, program, inp, prior):
    if not valid(domain, program, prior):
        return None
    if domain != "matrix":
        return prior.execute(domain, program, inp)
    grid = inp
    for t in program[:-1]:
        grid = matrix_transform(t, grid)
    return matrix_aggregate(program[-1], grid)


def inputs(domain, task, episode, phase, count, prior):
    seed = seed_of("new-multigen-data-v1", domain, task, episode, phase)
    if domain != "matrix":
        split = "development" if phase == "public" else "new_shift"
        return prior.examples(domain, split, seed % 100000, seed >> 14, count)
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        r = rng.randint(0, 5 if phase == "public" else 10)
        c = rng.randint(1, 5 if phase == "public" else 11)
        maxv = 7 if phase == "public" else 37
        out.append(tuple(
            tuple(rng.randint(-maxv, maxv) for _ in range(c))
            for _ in range(r)
        ))
    return tuple(out)


def build_tasks(prior, previous):
    """Fixed, disjoint algorithmic task programs; not exposed to the proposer."""
    tasks = {}
    for domain in DOMAINS:
        old = set()
        if domain != "matrix":
            old.update(prior.DEVELOPMENT[domain])
            old.update(prior.INDEPENDENT_AUDIT[domain])
            old.update(previous.DEV[domain])
            old.update(previous.AUDIT[domain])
        cfg = ops(domain, prior)
        pool = [
            (t, agg) for t in cfg["transform"] for agg in cfg["aggregate"]
            if (t, agg) not in old
        ]
        rng = random.Random(seed_of("task-split-frozen-20261108", domain))
        rng.shuffle(pool)
        assert len(pool) >= 24 and len(set(pool)) == len(pool)
        # 2 support tasks/generation; 2 distinct transfer tasks/generation;
        # 8 independent audit tasks/substrate (all untouched by selection).
        support = [pool[g*2:g*2+2] for g in range(GENERATIONS)]
        transfer = [pool[8+g*2:8+g*2+2] for g in range(GENERATIONS)]
        audit = pool[16:24]
        all_new = sum(support, []) + sum(transfer, []) + audit
        assert len(set(all_new)) == 24
        assert set(all_new).isdisjoint(old)
        assert all(valid(domain, p, prior) for p in all_new)
        tasks[domain] = {
            "support": support,
            "transfer": transfer,
            "audit": audit,
        }
    return tasks


def typed_draw(domain, rng, prior):
    if domain != "matrix":
        return prior.typed_draw(domain, rng)
    cfg = ops(domain, prior)
    k = rng.choice((0, 1, 1, 2))
    return tuple(rng.choice(cfg["transform"]) for _ in range(k)) + (
        rng.choice(cfg["aggregate"]),
    )


def baseline_stream(domain, task, episode, prior):
    rng = random.Random(seed_of("frozen-typed-incumbent-v1", domain, task, episode))
    return tuple(typed_draw(domain, rng, prior) for _ in range(BUDGET))


def novel_candidate(domain, rng, used, prior):
    for _ in range(PROPOSAL_TRIES):
        p = typed_draw(domain, rng, prior)
        if p not in used:
            return p
    return typed_draw(domain, rng, prior)


def mutate_candidate(domain, rng, used, prior, best):
    cfg = ops(domain, prior)
    if best is not None:
        for _ in range(PROPOSAL_TRIES):
            tokens = list(best)
            index = rng.randrange(len(tokens))
            kind = "aggregate" if index == len(tokens)-1 else "transform"
            tokens[index] = rng.choice(cfg[kind])
            p = tuple(tokens)
            if p not in used:
                return p
    return novel_candidate(domain, rng, used, prior)


def splice_candidate(domain, rng, used, prior, best):
    cfg = ops(domain, prior)
    if best is not None:
        for _ in range(PROPOSAL_TRIES):
            if rng.random() < 0.5:
                p = best[:-1] + (rng.choice(cfg["aggregate"]),)
            elif len(best) < 3:
                p = (rng.choice(cfg["transform"]),) + best
            else:
                p = (rng.choice(cfg["transform"]),) + best[1:]
            if p not in used:
                return p
    return novel_candidate(domain, rng, used, prior)


def choose_candidate(domain, rng, used, prior, best, action, archive, failure):
    if action == "uniform":
        return novel_candidate(domain, rng, used, prior)
    if action == "mutate":
        return mutate_candidate(domain, rng, used, prior, best)
    if action == "splice":
        return splice_candidate(domain, rng, used, prior, best)
    # These are archive heuristics using PUBLICLY observed candidate behavior
    # and failure counts. The shortlist does NOT execute extra candidate VMs.
    scored = []
    for _ in range(6):
        p = novel_candidate(domain, rng, used, prior)
        if action == "novelty":
            value = sum(1 / (1 + archive[t]) for t in p)
        else:
            value = -sum(failure[t] for t in p)
        scored.append((value, p))
    return max(scored, key=lambda v: v[0])[1]


class Controller:
    def __init__(self, arm):
        self.arm = arm
        self.weights = {
            domain: {a: 1.0 for a in ACTIONS}
            for domain in (*DOMAINS, "global")
        }
        self.rewards = defaultdict(lambda: defaultdict(float))
        self.uses = defaultdict(lambda: defaultdict(int))
        self.history = []

    def action(self, domain, rng):
        if self.arm == "frozen_uniform":
            return "uniform"
        if self.arm == "frozen_mutation":
            return "mutate"
        key = (
            "global" if self.arm in ("adaptive_global", "frozen_ensemble")
            else domain
        )
        if self.arm == "adaptive_shrunk":
            weights = {
                a: math.sqrt(self.weights["global"][a] * self.weights[domain][a])
                for a in ACTIONS
            }
        else:
            weights = self.weights[key]
        return rng.choices(ACTIONS, [weights[a] for a in ACTIONS], k=1)[0]

    def feedback(self, domain, action, reward):
        if self.arm not in ("adaptive_global", "adaptive_domain", "adaptive_shrunk"):
            return
        for key in (("global",) if self.arm == "adaptive_global"
                    else ((domain,) if self.arm == "adaptive_domain"
                          else ("global", domain))):
            self.rewards[key][action] += reward
            self.uses[key][action] += 1

    def advance(self, generation):
        if self.arm == "placebo_domain":
            for domain in DOMAINS:
                rng = random.Random(seed_of("placebo-controller", generation, domain))
                self.weights[domain] = {a: rng.uniform(0.4, 3.0) for a in ACTIONS}
        elif self.arm.startswith("adaptive_"):
            keys = (
                ["global"] if self.arm == "adaptive_global"
                else (list(DOMAINS) if self.arm == "adaptive_domain"
                      else ["global", *DOMAINS])
            )
            for key in keys:
                # A fixed weak prior prevents collapse from one lucky program.
                means = {
                    a: self.rewards[key][a] / max(1, self.uses[key][a])
                    for a in ACTIONS
                }
                avg = sum(means.values()) / len(ACTIONS)
                for a in ACTIONS:
                    update = math.exp(ETA * (means[a] - avg))
                    self.weights[key][a] = max(
                        0.35, min(3.5, self.weights[key][a] * update)
                    )
        self.history.append({
            "generation": generation,
            "weights_after_support": copy.deepcopy(self.weights),
            "reward_sum": {k: dict(v) for k, v in self.rewards.items()},
            "uses": {k: dict(v) for k, v in self.uses.items()},
        })
        self.rewards.clear()
        self.uses.clear()


def episode_run(domain, task, episode, arm, controller, prior, learn=False):
    t0 = time.process_time()
    public = inputs(domain, task, episode, "public", TRAIN_N, prior)
    target = tuple(execute(domain, task, x, prior) for x in public)
    shifted = inputs(domain, task, episode, "shift", SHIFT_N, prior)
    shift_labels = tuple(execute(domain, task, x, prior) for x in shifted)
    baseline = baseline_stream(domain, task, episode, prior)
    reserved = set(baseline)
    seen_baseline = set()
    used = set(reserved)
    rng = random.Random(seed_of("candidate-strategy-v1", domain, task, episode, arm))
    best = None
    best_hits = -1
    incumbent_hit = None
    reclaimed_hit = None
    archive = Counter()
    failure = Counter()
    behavior_seen = set()
    reclaimed_count = 0
    action_counts = Counter()
    reward_total = 0.0
    for proposal in baseline:
        replaced = proposal in seen_baseline
        if replaced:
            action = controller.action(domain, rng)
            program = choose_candidate(
                domain, rng, used, prior, best, action, archive, failure
            )
            assert valid(domain, program, prior)
            used.add(program)
            reclaimed_count += 1
            action_counts[action] += 1
        else:
            program = proposal
            seen_baseline.add(program)
            action = None
        prev_best = best_hits
        outputs = tuple(execute(domain, program, x, prior) for x in public)
        hits = sum(a == b for a, b in zip(outputs, target))
        if hits > best_hits:
            best_hits = hits
            best = program
        if outputs not in behavior_seen:
            behavior_seen.add(outputs)
            for token in program:
                archive[token] += 1
        if hits == 0:
            for token in program:
                failure[token] += 1
        if hits == TRAIN_N:
            if not replaced and incumbent_hit is None:
                incumbent_hit = program
            if replaced and reclaimed_hit is None:
                reclaimed_hit = program
        if learn and replaced:
            gain = max(0, hits-max(0, prev_best)) / TRAIN_N
            gain += 0.5 if (hits == TRAIN_N and prev_best < TRAIN_N) else 0
            reward = min(1.0, gain)
            reward_total += reward
            controller.feedback(domain, action, reward)
    assert reserved.issubset(seen_baseline)
    winner = incumbent_hit or reclaimed_hit
    ood = bool(
        winner is not None
        and all(
            execute(domain, winner, x, prior) == y
            for x, y in zip(shifted, shift_labels)
        )
    )
    return {
        "arm": arm, "domain": domain, "task": list(task),
        "episode": episode,
        "train_solved": winner is not None,
        "ood_pass": ood,
        "winner": list(winner) if winner else None,
        "incumbent_winner": list(incumbent_hit) if incumbent_hit else None,
        "candidate_evals": BUDGET,
        "candidate_training_vm_calls": BUDGET*TRAIN_N,
        "verification_vm_calls": SHIFT_N if winner is not None else 0,
        "reclaimed": reclaimed_count,
        "actions": dict(action_counts),
        "reward": round(reward_total, 6),
        "cpu_seconds": time.process_time()-t0,
    }


def batch(prior, controllers, tasks, phase, generation, seeds, learn=False):
    rows = []
    for domain in DOMAINS:
        for target_task in tasks[domain]:
            for seed in range(seeds):
                ep = seed_of("paired-meta-episode", phase, generation,
                             domain, target_task, seed)
                for arm in ARMS:
                    rows.append(episode_run(
                        domain, target_task, ep, arm, controllers[arm], prior,
                        learn=learn,
                    ))
    summaries = {}
    for arm in ARMS:
        selected = [r for r in rows if r["arm"] == arm]
        summaries[arm] = {
            "train": sum(r["train_solved"] for r in selected),
            "ood": sum(r["ood_pass"] for r in selected),
            "candidate_evals": sum(r["candidate_evals"] for r in selected),
            "training_vm_calls": sum(r["candidate_training_vm_calls"] for r in selected),
            "verification_vm_calls": sum(r["verification_vm_calls"] for r in selected),
            "reclaimed": sum(r["reclaimed"] for r in selected),
            "cpu_seconds": round(sum(r["cpu_seconds"] for r in selected), 6),
            "cpu_cap_breaches": sum(r["cpu_seconds"] > CPU_CAP for r in selected),
            "by_domain_ood": {
                d: sum(r["ood_pass"] for r in selected if r["domain"] == d)
                for d in DOMAINS
            },
            "by_task_ood": {
                d: {
                    "|".join(t): sum(
                        r["ood_pass"] for r in selected
                        if r["domain"] == d and r["task"] == list(t)
                    )
                    for t in tasks[d]
                } for d in DOMAINS
            },
        }
    for metric in ("candidate_evals", "training_vm_calls"):
        assert len({s[metric] for s in summaries.values()}) == 1
    control = {
        (r["domain"], tuple(r["task"]), r["episode"]): r
        for r in rows if r["arm"] == "frozen_uniform"
    }
    for r in rows:
        if r["arm"] == "frozen_uniform":
            continue
        orig = control[(r["domain"],tuple(r["task"]),r["episode"])]
        if orig["train_solved"]:
            assert r["train_solved"] and r["winner"] == orig["winner"]
            assert r["ood_pass"] == orig["ood_pass"]
    return {"summary": summaries, "rows": rows, "incumbent_inclusion": True}


def task_batch(tasks, key, generation):
    return {d: tasks[d][key][generation] for d in DOMAINS}


def flatten_transfer(tasks, max_generation):
    return {
        d: sum(tasks[d]["transfer"][:max_generation], [])
        for d in DOMAINS
    }


def select_candidate(development, policies):
    # Selection is based ONLY on the public transfer-development task suite,
    # never on independent audits. Compare against strongest frozen mutation.
    baseline = development["summary"]["frozen_mutation"]
    placebo = development["summary"]["placebo_domain"]
    decisions = {}
    eligible = []
    for name in ("adaptive_global", "adaptive_domain", "adaptive_shrunk"):
        challenger = development["summary"][name]
        domain_delta = {
            d: challenger["by_domain_ood"][d] - baseline["by_domain_ood"][d]
            for d in DOMAINS
        }
        task_delta = {
            d: {
                k: v-baseline["by_task_ood"][d][k]
                for k, v in challenger["by_task_ood"][d].items()
            } for d in DOMAINS
        }
        history = policies[name].history
        states = [
            tuple(round(item["weights_after_support"][d][a], 6)
                  for d in DOMAINS for a in ACTIONS)
            for item in history
        ]
        changed = len(set(states)) > 1
        passing = (
            all(v > 0 for v in domain_delta.values())
            and all(q >= 0 for m in task_delta.values() for q in m.values())
            and challenger["ood"] > placebo["ood"]
            and challenger["training_vm_calls"] == baseline["training_vm_calls"]
            and challenger["cpu_cap_breaches"] == 0
            and changed
        )
        decisions[name] = {
            "pass_development": passing,
            "domain_gain_vs_fixed_mutation": domain_delta,
            "task_gain_vs_fixed_mutation": task_delta,
            "gain_vs_placebo": challenger["ood"]-placebo["ood"],
            "policy_weights_changed": changed,
        }
        if passing:
            eligible.append(name)
    chosen = max(
        eligible,
        key=lambda k: (
            min(decisions[k]["domain_gain_vs_fixed_mutation"].values()),
            development["summary"][k]["ood"],
        ),
        default=None,
    )
    return {"selected": chosen, "decisions": decisions}


def independent_gate(audit, selection):
    name = selection["selected"]
    if name is None:
        return {"pass": False, "reason": "No evolving policy beat frozen and placebo controls on all development domains"}
    base = audit["summary"]["frozen_mutation"]
    random_control = audit["summary"]["placebo_domain"]
    cur = audit["summary"][name]
    delta = {
        d: cur["by_domain_ood"][d] - base["by_domain_ood"][d]
        for d in DOMAINS
    }
    per_task = {
        d: {k: v-base["by_task_ood"][d][k]
            for k, v in cur["by_task_ood"][d].items()}
        for d in DOMAINS
    }
    ok = (
        all(v > 0 for v in delta.values())
        and all(x >= 0 for d in per_task.values() for x in d.values())
        and cur["ood"] > random_control["ood"]
        and cur["training_vm_calls"] == base["training_vm_calls"]
        and cur["candidate_evals"] == base["candidate_evals"]
        and cur["cpu_cap_breaches"] == 0
    )
    return {
        "pass": ok,
        "domain_delta_vs_frozen_mutation": delta,
        "task_delta_vs_frozen_mutation": per_task,
        "gain_vs_placebo": cur["ood"]-random_control["ood"],
        "reason": "Independent multi-generation transfer conditions met" if ok
                  else "Independent domain or placebo criterion failed",
    }


def tests(prior, previous):
    tasks = build_tasks(prior, previous)
    assert len(tasks) == 4
    for domain in DOMAINS:
        all_p = (
            sum(tasks[domain]["support"], [])
            + sum(tasks[domain]["transfer"], [])
            + tasks[domain]["audit"]
        )
        assert len(all_p) == 24 and len(set(all_p)) == 24
        xs = inputs(domain, all_p[0], 1, "public", 4, prior)
        assert all(isinstance(execute(domain,all_p[0],x,prior),int) for x in xs)
        for arm in ARMS:
            test = episode_run(
                domain, all_p[0], 987, arm, Controller(arm), prior, learn=False
            )
            assert test["candidate_training_vm_calls"] == BUDGET*TRAIN_N
    assert Controller("frozen_mutation").action("matrix",random.Random(1)) == "mutate"
    assert Controller("frozen_uniform").action("matrix",random.Random(1)) == "uniform"
    a = Controller("adaptive_global")
    original = copy.deepcopy(a.weights)
    a.feedback("matrix", "mutate", 1.0)
    a.feedback("matrix", "uniform", 0.0)
    a.advance(0)
    assert a.weights != original and a.weights["global"]["mutate"] > a.weights["global"]["uniform"]
    before = copy.deepcopy(a.weights)
    a.advance(1)
    assert len(a.history) == 2
    print("PASS: 4 substrates, disjoint source/audit targets, invariant execution "
          "budgets, meta-weight update direction, and immutable frozen-policy controls")
    return tasks


def run(repo, support_seeds, dev_seeds, audit_seeds):
    prior, previous = load_frozen(repo)
    tasks = tests(prior, previous)
    controllers = {arm: Controller(arm) for arm in ARMS}
    generations = []
    for gen in range(GENERATIONS):
        support = batch(
            prior, controllers, task_batch(tasks,"support",gen),
            "support", gen, support_seeds, learn=True,
        )
        for controller in controllers.values():
            controller.advance(gen)
        transfer = batch(
            prior, controllers, task_batch(tasks,"transfer",gen),
            "transfer", gen, dev_seeds,
        )
        revisit = (
            batch(
                prior,controllers,flatten_transfer(tasks,gen),
                "revisit",gen,max(2,dev_seeds//2)
            ) if gen > 0 else None
        )
        generations.append({
            "generation": gen,
            "support": support,
            "fresh_transfer": transfer,
            "prior_transfer_retention": revisit,
            "policy_snapshots": {
                name: copy.deepcopy(controllers[name].history[-1])
                for name in ARMS
            },
        })
    # Development selection on all fresh-transfer tasks with new paired input
    # distributions, after all support-driven state updates are frozen.
    development = batch(
        prior, controllers, flatten_transfer(tasks,GENERATIONS),
        "development_final", GENERATIONS, dev_seeds,
    )
    selected = select_candidate(development,controllers)
    # Only now execute entirely new audit tasks; no reward updates afterward.
    audit = batch(
        prior, controllers,
        {d: tasks[d]["audit"] for d in DOMAINS},
        "single_use_independent_audit", GENERATIONS, audit_seeds,
    )
    result = independent_gate(audit,selected)
    return {
        "schema":"multigeneration-meta-controller-v1",
        "base_main_sha":BASE_MAIN,
        "frozen_pr55_sha":PR55,
        "frozen_pr56_sha":PR56,
        "preregistered":{
            "generations":GENERATIONS,
            "domains":DOMAINS,
            "support_targets_per_generation_per_domain":2,
            "fresh_transfer_targets_per_generation_per_domain":2,
            "independent_audit_targets_per_domain":8,
            "seeds_support":support_seeds,
            "seeds_transfer":dev_seeds,
            "seeds_audit":audit_seeds,
            "candidate_budget":BUDGET,
            "training_examples":TRAIN_N,
            "shift_examples":SHIFT_N,
            "CPU_ceiling_per_case":CPU_CAP,
            "eta":ETA,
            "selection":"strict positive OOD gains vs strongest frozen mutation in EVERY domain and nonnegative per task, beating placebo",
        },
        "task_program_manifest":tasks,
        "generations":generations,
        "final_development":development,
        "selection":selected,
        "independent_audit":audit,
        "independent_gate":result,
        "policy_history":{name:controllers[name].history for name in ARMS},
        "finite_meta_learning_success":result["pass"],
        "general_rsi_proven":False,
        "production_eligible":False,
        "limitations":[
            "All tasks are finite synthetic programs, with shared transform+aggregate structure.",
            "Meta-controller changes operator-choice probabilities; it does not edit its own source code.",
            "Support-task feedback only updates weights; held-out transfer/audit does not.",
            "Program inventory preservation guarantees incumbent retention, not transferable improvement.",
            "Matched candidate training VM calls do not imply matched total CPU or verifier calls.",
            "All independent audit tasks are single-use and become spent after this run.",
            "Multi-generation learning is necessary but insufficient for recursive self-improvement.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo",type=Path,default=Path("."))
    ap.add_argument("--support-seeds",type=int,default=SUPPORT_SEEDS)
    ap.add_argument("--dev-seeds",type=int,default=DEV_SEEDS)
    ap.add_argument("--audit-seeds",type=int,default=AUDIT_SEEDS)
    ap.add_argument("--out",type=Path,default=Path("multigen_meta_results.json"))
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    prior,previous=load_frozen(args.repo)
    if args.self_test:
        tests(prior,previous)
        return
    assert 1<=args.support_seeds<=32 and 1<=args.dev_seeds<=32 and 1<=args.audit_seeds<=64
    result=run(args.repo,args.support_seeds,args.dev_seeds,args.audit_seeds)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "generations":[{
            "generation":g["generation"],
            "support":{n:{"ood":r["ood"],"cpu":r["cpu_seconds"]}
                       for n,r in g["support"]["summary"].items()},
            "transfer":{n:{"ood":r["ood"],"cpu":r["cpu_seconds"]}
                        for n,r in g["fresh_transfer"]["summary"].items()},
        } for g in result["generations"]],
        "development":result["final_development"]["summary"],
        "selection":result["selection"],
        "audit":result["independent_audit"]["summary"],
        "gate":result["independent_gate"],
        "meta_learning_success":result["finite_meta_learning_success"],
        "rsi_proven":result["general_rsi_proven"],
        "production_eligible":result["production_eligible"],
        "raw_json":str(args.out),
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
