#!/usr/bin/env python3
"""Worst-domain guarded transfer experiment on NEW synthetic task families.

Frozen dependencies:
- Initial MetaForge runtime at immutable root commit.
- Research-only typed sampling implementation at immutable PR #53 commit.

This code NEVER reads sealed TEST/J pools, previous PR #53 independent audit
labels, or RSI-4 Phase 1. It does not patch the production runtime.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import types

ROOT_SHA = "3cfc329eca17a08e1a1565064b61a5bd4a1dd520"
PR53_SHA = "1d0a54d408378fa26b462ffa3bad66c8e98c0ea6"
PR53_PATH = "research/typed_weight_ab_gate_20261108.py"

SUPPORT_TASKS = ("minimum", "prefix_max_sum", "sum_squares")
DEVELOPMENT_TASKS = (
    "second_smallest", "second_from_end", "trim_two_count",
    "sorted_trim_sum", "sum_of_prefix_sums", "maximum_prefix_sum",
)
AUDIT_TASKS = (
    "sum_after_two_drops", "reverse_odd_sum", "reverse_even_sum",
    "minimum_after_drop", "maximum_after_drop", "sum_prefix_max_after_drop",
    "sum_prefix_sorted", "minimum_prefix_sum",
)
ARMS = (
    "typed_uniform", "typed_uniform_null", "typed_learned",
    "uniform_floor_75", "uniform_floor_50", "uniform_floor_25",
)
SEED_START = 401
SEEDS = 64
PROPOSALS_PER_SEED_TASK = 20
SUPPORT_BUDGET_PER_TASK = 768
MIN_TOTAL_GAIN = 4
MAX_PER_DOMAIN_REGRESSION = 0
MAX_CPU_SECONDS_PER_TASK_SEED_ARM = 0.5


def load_prior_research(repo: Path):
    source = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{PR53_SHA}:{PR53_PATH}"],
        text=True,
    )
    module = types.ModuleType("_frozen_prior_typed_sampler")
    module.__file__ = f"{PR53_SHA}:{PR53_PATH}"
    sys.modules[module.__name__] = module
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    assert module.ROOT_SHA == ROOT_SHA
    return module


def _prefixes(xs, mode):
    result = []
    acc = 0
    for x in xs:
        if mode == "sum":
            acc += x
        else:
            acc = x if not result else max(acc, x)
        result.append(acc)
    return result


def oracle(name):
    """All targets are grammar-reachable in <=4 original VM base opcodes."""
    functions = {
        # Fresh support tasks, with no use of the spent PR #53 audit families.
        "minimum": lambda xs: sorted(xs)[0] if xs else 0,
        "prefix_max_sum": lambda xs: sum(_prefixes(xs, "max")),
        "sum_squares": lambda xs: sum(x * x for x in xs),
        # Development task families (selection permitted here only).
        "second_smallest": lambda xs: sorted(xs)[1] if len(xs) > 1 else 0,
        "second_from_end": lambda xs: xs[-2] if len(xs) > 1 else 0,
        "trim_two_count": lambda xs: max(0, len(xs) - 2),
        "sorted_trim_sum": lambda xs: sum(sorted(xs)[1:]),
        "sum_of_prefix_sums": lambda xs: sum(_prefixes(xs, "sum")),
        "maximum_prefix_sum": lambda xs: max(_prefixes(xs, "sum"), default=0),
        # New independent audit families; selection and hyperparameters freeze
        # before these are called. Never reuse as next iteration's tuning set.
        "sum_after_two_drops": lambda xs: sum(xs[2:]),
        "reverse_odd_sum": lambda xs: sum(list(reversed(xs))[1::2]),
        "reverse_even_sum": lambda xs: sum(list(reversed(xs))[0::2]),
        "minimum_after_drop": lambda xs: min(xs[1:]) if xs[1:] else 0,
        "maximum_after_drop": lambda xs: max(xs[1:]) if xs[1:] else 0,
        "sum_prefix_max_after_drop": lambda xs: sum(_prefixes(xs, "max")[1:]),
        "sum_prefix_sorted": lambda xs: sum(_prefixes(sorted(xs), "sum")),
        "minimum_prefix_sum": lambda xs: min(_prefixes(xs, "sum"), default=0),
    }
    return functions[name]


def train_support(prior, vm, budget=SUPPORT_BUDGET_PER_TASK):
    """Credit only fully verified support matches, not best partial programs."""
    uniform = vm.SearcherState()
    sampler = prior.TypedSampler(vm, uniform)
    counts = Counter()
    records = {}
    for index, task in enumerate(SUPPORT_TASKS):
        rng = random.Random(87381 + index)
        pairs = prior.input_pairs(vm, task, 317)
        winner = None
        matched = 0
        for _ in range(budget):
            tokens = sampler.sample(rng)
            hits, valid = prior.evaluate_proposal(vm, tokens, uniform, pairs)
            if valid and hits == len(pairs):
                winner = tokens
                matched += 1
                # Deduplicate the same verified idea in credit assignment:
                # one credited program per support domain, not per replay.
                break
        if winner:
            counts.update(winner)
        records[task] = {
            "verified_support_solution": list(winner) if winner else None,
            "matched": bool(winner),
            "charged_candidate_budget": budget,
            "matched_at_or_before_budget": matched > 0,
        }
    weights = uniform.clone()
    weights.weights = {
        tok: min(6.0, 1.0 + 1.5 * counts[tok])
        for tok in weights.vocab()
    }
    return weights, {
        "support_task_records": records,
        "support_tasks": list(SUPPORT_TASKS),
        "candidate_budget_per_support_domain": budget,
        "max_charged_support_evaluations": budget * len(SUPPORT_TASKS),
        "weight_credit_from_verified_support_only": True,
        "learned_weights_nonunit": {
            vm.OP_NAMES[t]: weights.weights[t]
            for t in sorted(weights.weights)
            if weights.weights[t] != 1.0
        },
    }


class Schedule:
    """A deterministic uniform quota, not a fragile stochastic beta switch."""
    def __init__(self, uniform_sampler, learned_sampler, learned_every):
        self.uniform = uniform_sampler
        self.learned = learned_sampler
        self.learned_every = learned_every

    def draw(self, rng, proposal_index):
        if self.learned_every is None:
            return self.uniform.sample(rng)
        if self.learned_every == 1:
            return self.learned.sample(rng)
        if self.learned_every == 0:  # 75% learned, 25% guaranteed uniform
            return self.uniform.sample(rng) if proposal_index % 4 == 0 else self.learned.sample(rng)
        if (proposal_index + 1) % self.learned_every == 0:
            return self.learned.sample(rng)
        return self.uniform.sample(rng)


def make_arms(prior, vm, learned_weights):
    base = vm.SearcherState()
    explicit_null = base.clone()
    explicit_null.weights = {t: 1.0 for t in base.vocab()}
    uniform = prior.TypedSampler(vm, base)
    null = prior.TypedSampler(vm, explicit_null)
    learned = prior.TypedSampler(vm, learned_weights)
    return {
        "typed_uniform": (base, Schedule(uniform, learned, None)),
        "typed_uniform_null": (
            explicit_null, Schedule(null, learned, None)),
        "typed_learned": (
            learned_weights, Schedule(uniform, learned, 1)),
        "uniform_floor_75": (
            learned_weights, Schedule(uniform, learned, 4)),
        "uniform_floor_50": (
            learned_weights, Schedule(uniform, learned, 2)),
        "uniform_floor_25": (
            learned_weights, Schedule(uniform, learned, 0)),
    }


def make_input_pairs(prior, vm, task, seed):
    return prior.input_pairs(vm, task, seed)


def search_task(prior, vm, state, schedule, task, seed, train_seed, shift):
    rng = random.Random(1000003 * seed + 31337)
    pairs = make_input_pairs(prior, vm, task, train_seed)
    solution = None
    first_hit = None
    valid_count = 0
    start = time.process_time()
    for proposal_index in range(PROPOSALS_PER_SEED_TASK):
        candidate = schedule.draw(rng, proposal_index)
        hits, valid = prior.evaluate_proposal(vm, candidate, state, pairs)
        valid_count += int(valid)
        if hits == len(pairs) and solution is None:
            solution = candidate
            first_hit = proposal_index + 1
    cpu = time.process_time() - start
    return {
        "solved": solution is not None,
        "ood_pass": prior.transfer_ok(vm, solution, state, task, shift),
        "tokens": list(solution) if solution else [],
        "first_hit": first_hit,
        "valid_proposals": valid_count,
        "candidate_evals": PROPOSALS_PER_SEED_TASK,
        "charged_probe_slots": PROPOSALS_PER_SEED_TASK * len(pairs),
        "cpu_seconds": cpu,
        "cpu_limit_breached": cpu > MAX_CPU_SECONDS_PER_TASK_SEED_ARM,
    }


def evaluate_stage(prior, vm, arms, tasks, train_seed, seeds, shift):
    rows = []
    for task in tasks:
        for seed in range(SEED_START, SEED_START + seeds):
            for arm in ARMS:
                state, schedule = arms[arm]
                row = search_task(
                    prior, vm, state, schedule, task, seed, train_seed, shift
                )
                row.update({"arm": arm, "task": task, "seed": seed})
                rows.append(row)
    summary = {}
    for arm in ARMS:
        group = [row for row in rows if row["arm"] == arm]
        summary[arm] = {
            "solved": sum(x["solved"] for x in group),
            "ood_pass": sum(x["ood_pass"] for x in group),
            "candidate_evals": sum(x["candidate_evals"] for x in group),
            "charged_probe_slots": sum(x["charged_probe_slots"] for x in group),
            "cpu_seconds": round(sum(x["cpu_seconds"] for x in group), 6),
            "cpu_cap_breaches": sum(x["cpu_limit_breached"] for x in group),
            "valid_proposals": sum(x["valid_proposals"] for x in group),
            "by_task": {
                task: sum(x["solved"] for x in group if x["task"] == task)
                for task in tasks
            },
            "by_task_ood": {
                task: sum(x["ood_pass"] for x in group if x["task"] == task)
                for task in tasks
            },
        }
    for metric in ("candidate_evals", "charged_probe_slots"):
        assert len({v[metric] for v in summary.values()}) == 1, metric
    # Uniform and explicit-uniform produce exactly the same token proposals.
    def strip(arm):
        return [
            (r["task"], r["seed"], r["tokens"], r["first_hit"],
             r["valid_proposals"], r["ood_pass"])
            for r in rows if r["arm"] == arm
        ]
    assert strip("typed_uniform") == strip("typed_uniform_null")
    return {"summary": summary, "rows": rows}


def select_on_development(stage, tasks):
    base = stage["summary"]["typed_uniform"]
    accepted = []
    detail = {}
    # Selection happens before independent audit. Do not tune on audit.
    for arm in ARMS:
        if arm in ("typed_uniform", "typed_uniform_null"):
            continue
        s = stage["summary"][arm]
        deltas = {t: s["by_task"][t] - base["by_task"][t] for t in tasks}
        ood_deltas = {
            t: s["by_task_ood"][t] - base["by_task_ood"][t] for t in tasks
        }
        logical_parity = (
            s["candidate_evals"] == base["candidate_evals"]
            and s["charged_probe_slots"] == base["charged_probe_slots"]
        )
        eligible = (
            sum(deltas.values()) >= MIN_TOTAL_GAIN
            and min(deltas.values()) >= -MAX_PER_DOMAIN_REGRESSION
            and min(ood_deltas.values()) >= -MAX_PER_DOMAIN_REGRESSION
            and logical_parity
            and s["cpu_cap_breaches"] == 0
            and base["cpu_cap_breaches"] == 0
        )
        detail[arm] = {
            "eligible_dev": eligible,
            "total_delta": sum(deltas.values()),
            "by_task_delta": deltas,
            "by_task_ood_delta": ood_deltas,
            "equal_logical_budget": logical_parity,
        }
        if eligible:
            accepted.append(arm)
    # Maximize minimum group gain, then total gain, then simplest more-uniform
    # policy. This tie breaker is fixed BEFORE audit results are inspected.
    order = {
        "uniform_floor_75": 0, "uniform_floor_50": 1,
        "uniform_floor_25": 2, "typed_learned": 3,
    }
    selected = max(
        accepted,
        key=lambda name: (
            min(detail[name]["by_task_delta"].values()),
            detail[name]["total_delta"],
            -order[name],
        ),
        default=None,
    )
    return {"selected": selected, "development_decisions": detail}


def audit_candidate(stage, selected, support_stage):
    if selected is None:
        return {
            "pass": False,
            "reason": "No candidate passed the preregistered development guard",
        }
    s = stage["summary"][selected]
    base = stage["summary"]["typed_uniform"]
    support_s = support_stage["summary"][selected]
    support_b = support_stage["summary"]["typed_uniform"]
    audit_deltas = {
        k: s["by_task"][k] - base["by_task"][k]
        for k in AUDIT_TASKS
    }
    audit_ood_deltas = {
        k: s["by_task_ood"][k] - base["by_task_ood"][k]
        for k in AUDIT_TASKS
    }
    support_deltas = {
        k: support_s["by_task"][k] - support_b["by_task"][k]
        for k in SUPPORT_TASKS
    }
    accepts = (
        min(audit_deltas.values()) >= 0
        and min(audit_ood_deltas.values()) >= 0
        and sum(audit_deltas.values()) > 0
        and min(support_deltas.values()) >= 0
        and s["cpu_cap_breaches"] == 0
        and s["candidate_evals"] == base["candidate_evals"]
        and s["charged_probe_slots"] == base["charged_probe_slots"]
    )
    return {
        "pass": accepts,
        "audit_delta": sum(audit_deltas.values()),
        "audit_by_task_delta": audit_deltas,
        "audit_by_task_ood_delta": audit_ood_deltas,
        "support_retention_delta": support_deltas,
        "reason": (
            "All predefined finite-group criteria met"
            if accepts else "A preregistered independent/retention criterion failed"
        ),
    }


def run(repo, seeds, support_budget):
    prior = load_prior_research(repo)
    vm = prior.load_historical_core(repo)
    assert tuple(prior.TRAIN_SUPPORT) == ("length", "sum")
    assert not set(SUPPORT_TASKS + DEVELOPMENT_TASKS + AUDIT_TASKS).intersection(
        set(prior.TRAIN_SUPPORT + prior.DEV_TASKS + prior.AUDIT_TASKS)
    )
    # This assigns only a local *isolated historical research module* function,
    # not a production oracle or sealed verifier.
    prior.task_oracle = oracle
    learned, support_weights = train_support(prior, vm, support_budget)
    arms = make_arms(prior, vm, learned)
    assert tuple(arms) == ARMS
    shift_rng = random.Random(848211)
    shift = tuple(
        tuple(shift_rng.randint(-19, 31) for _ in range(L))
        for L in (0, 1, 2, 5, 8, 13, 21, 34)
        for _ in range(3)
    )
    # Freeze selection on *development* before the audit is executed.
    development = evaluate_stage(
        prior, vm, arms, DEVELOPMENT_TASKS, 707, seeds, shift
    )
    decision = select_on_development(development, DEVELOPMENT_TASKS)
    support_retention = evaluate_stage(
        prior, vm, arms, SUPPORT_TASKS, 317, seeds, shift
    )
    audit = evaluate_stage(
        prior, vm, arms, AUDIT_TASKS, 909, seeds, shift
    )
    audit_gate = audit_candidate(
        audit, decision["selected"], support_retention
    )
    return {
        "schema": "worst-domain-transfer-v1",
        "root_sha": ROOT_SHA,
        "frozen_prior_research_sha": PR53_SHA,
        "preregistration": {
            "support_tasks": SUPPORT_TASKS,
            "development_tasks": DEVELOPMENT_TASKS,
            "independent_audit_tasks": AUDIT_TASKS,
            "seed_start": SEED_START,
            "seed_count": seeds,
            "proposals_per_task_seed_arm": PROPOSALS_PER_SEED_TASK,
            "support_budget_per_domain": support_budget,
            "development_min_total_gain": MIN_TOTAL_GAIN,
            "max_domain_regression": MAX_PER_DOMAIN_REGRESSION,
            "cpu_seconds_ceiling_per_task_seed_arm":
                MAX_CPU_SECONDS_PER_TASK_SEED_ARM,
            "independent_audit_required": True,
        },
        "support_weights": support_weights,
        "development": development,
        "development_selection": decision,
        "support_retention": support_retention,
        "independent_audit": audit,
        "independent_audit_gate": audit_gate,
        "production_eligible": False,
        "decision": (
            "Research-only: independent conditions passed, still requires "
            "external validation on other substrates"
            if audit_gate["pass"] else
            "Research-only: finite-group guard rejected or no development winner"
        ),
        "limitations": [
            "All tasks remain in one fixed list-of-integers VM, not all domains.",
            "No Free Lunch prohibits strict universal improvement without assumptions.",
            "Logical evaluations and probe opportunities match, CPU cycles do not.",
            "A CPU ceiling is checked after every run, not used for exact scheduling.",
            "Support training cost is extra and reported separately.",
            "Independent audit is single-use, and is never candidate-selection data.",
            "No sealed TEST/J, frozen verifier, RSI-4, or existing PR modified.",
        ],
    }


def self_test(repo):
    prior = load_prior_research(repo)
    vm = prior.load_historical_core(repo)
    prior.task_oracle = oracle
    assert len(set(SUPPORT_TASKS + DEVELOPMENT_TASKS + AUDIT_TASKS)) == 17
    assert len(prior.enumerate_typed("i", 4)) > 0
    learned, meta = train_support(prior, vm, budget=40)
    assert all(weight >= 1.0 for weight in learned.weights.values())
    arms = make_arms(prior, vm, learned)
    rng = random.Random(12)
    for name in ARMS:
        schedule = arms[name][1]
        for k in range(20):
            tokens = schedule.draw(rng, k)
            assert vm.static_plausible(tokens, vm.build_type_sigs({}))
    for name in ("minimum", "prefix_max_sum", "sum_squares"):
        assert name in meta["support_task_records"]
    print("PASS 5 research checks: isolated source, task disjointness, "
          "reachable grammar, fixed mixture policy, support credit")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("worst_domain_results.json"))
    parser.add_argument("--seeds", type=int, default=SEEDS)
    parser.add_argument("--support-budget", type=int, default=SUPPORT_BUDGET_PER_TASK)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(args.repo)
        return
    assert 1 <= args.seeds <= 128
    assert 1 <= args.support_budget <= 4096
    result = run(args.repo, args.seeds, args.support_budget)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "support": result["support_weights"],
        "development": result["development"]["summary"],
        "selected": result["development_selection"],
        "retention": result["support_retention"]["summary"],
        "audit": result["independent_audit"]["summary"],
        "audit_gate": result["independent_audit_gate"],
        "production_eligible": result["production_eligible"],
        "raw_data_file": str(args.out),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
