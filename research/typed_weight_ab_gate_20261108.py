#!/usr/bin/env python3
"""Opt-in typed proposal search + weight-only evidence-gated A/B (historical VM).

This research module does not import sealed TEST/J pools, alter historical
verifiers, modify production search, or use audit examples to select weights.
Only the immutable root commit's first runtime kernel is executed.
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import types

ROOT_SHA = "3cfc329eca17a08e1a1565064b61a5bd4a1dd520"
ROOT_FILE = "rsi_levels_metaforge_unified.py"
DEV_TASKS = ("even_sum", "odd_sum", "even_length", "odd_length")
AUDIT_TASKS = ("tail_sum", "tail_length", "head", "max")
TRAIN_SUPPORT = ("length", "sum")
ARMS = ("legacy", "typed_uniform", "typed_null", "typed_learned")
SEEDS = (100, 132)  # half-open [100,132): 32 fixed paired seeds
PROPOSALS = 20
CPU_CEILING_PER_TASK_SEED_ARM = 0.5
MIN_DEV_DELTA = 3
MAX_TASK_REGRESSION = 1
MAX_AUDIT_TASK_REGRESSION = 1

# Type-checked, postfix productions using the original root VM op IDs.
# Excludes generalized stack operations, macros, and extensions intentionally.
LEAVES = {"i": (0, 1, 2, 3), "l": (4,)}
UNARY = {
    "i": (("l", (16, 17, 18, 29, 30)),),
    "l": (("l", (20, 21, 22, 27, 28, 31, 32)),),
}
BINARY = {
    "i": (("i", "i", (9, 10, 11, 12, 13, 14, 15)),),
    "l": (("l", "l", (23, 24, 25, 26)),),
}


def load_historical_core(repo: Path):
    source = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{ROOT_SHA}:{ROOT_FILE}"],
        text=True,
    )
    prefix = "\n".join(source.splitlines()[:2288]) + "\n"
    mod = types.ModuleType("_immutable_metaforge_root_core")
    mod.__file__ = f"{ROOT_SHA}:{ROOT_FILE}"
    sys.modules[mod.__name__] = mod
    exec(compile(prefix, mod.__file__, "exec"), mod.__dict__)
    assert mod.N_BASE_OPS == 34
    return mod


@lru_cache(None)
def enumerate_typed(result_type: str, length: int):
    """Generate exact-length postfix programs with one typed result."""
    if length < 1:
        return ()
    if length == 1:
        return tuple((token,) for token in LEAVES[result_type])
    out = []
    for input_type, ops in UNARY[result_type]:
        for child in enumerate_typed(input_type, length - 1):
            for op in ops:
                out.append(child + (op,))
    for left_type, right_type, ops in BINARY[result_type]:
        for left_len in range(1, length - 1):
            right_len = length - 1 - left_len
            for left in enumerate_typed(left_type, left_len):
                for right in enumerate_typed(right_type, right_len):
                    for op in ops:
                        out.append(left + right + (op,))
    return tuple(out)


class TypedSampler:
    def __init__(self, mod, state):
        self.programs = {}
        self.cumulative = {}
        self.totals = {}
        sigs = mod.build_type_sigs(state.macros)
        for length in (2, 3, 4):
            ps = enumerate_typed("i", length)
            assert ps
            assert all(mod.static_plausible(p, sigs) for p in ps)
            cumulative = []
            total = 0.0
            for p in ps:
                weight = math.prod(state.weight(tok) for tok in p)
                assert weight > 0 and math.isfinite(weight)
                total += weight
                cumulative.append(total)
            self.programs[length] = ps
            self.cumulative[length] = cumulative
            self.totals[length] = total

    def sample(self, rng):
        length = rng.randint(2, 4)
        pos = bisect.bisect_left(
            self.cumulative[length], rng.random() * self.totals[length]
        )
        return self.programs[length][min(pos, len(self.programs[length]) - 1)]


def task_oracle(name):
    funcs = {
        "length": lambda x: len(x),
        "sum": lambda x: sum(x),
        "even_sum": lambda x: sum(x[::2]),
        "odd_sum": lambda x: sum(x[1::2]),
        "even_length": lambda x: len(x[::2]),
        "odd_length": lambda x: len(x[1::2]),
        "tail_sum": lambda x: sum(x[1:]),
        "tail_length": lambda x: len(x[1:]),
        "head": lambda x: x[0] if x else 0,
        "max": lambda x: max(x) if x else 0,
    }
    return funcs[name]


def input_pairs(mod, name, seed):
    oracle = task_oracle(name)
    xs_set = mod.build_train_inputs(seed)
    return tuple((tuple(xs), int(oracle(xs))) for xs in xs_set)


def independent_shift_inputs():
    rng = random.Random(991733)
    return tuple(
        tuple(rng.randint(-11, 23) for _ in range(length))
        for length in (0, 5, 8, 13, 21, 34)
        for _ in range(4)
    )


def evaluate_proposal(mod, candidate, state, train_pairs):
    """Charge every candidate 20 probes, even for crashes and invalid types."""
    sigs = mod.build_type_sigs(state.macros)
    type_valid = mod.static_plausible(candidate, sigs)
    try:
        expanded = mod.expand_tokens(candidate, state.macros)
    except mod.VMCrash:
        expanded = None
    hits = 0
    for xs, target in train_pairs:
        try:
            prediction = (
                mod.run_base_program(expanded, xs) if expanded is not None
                else None
            )
            hits += int(prediction == target)
        except (mod.VMCrash, OverflowError, ValueError):
            pass
    return hits, type_valid


def transfer_ok(mod, candidate, state, task, shift):
    if candidate is None:
        return False
    oracle = task_oracle(task)
    try:
        expanded = mod.expand_tokens(candidate, state.macros)
        return all(
            mod.run_base_program(expanded, xs) == oracle(xs) for xs in shift
        )
    except (mod.VMCrash, OverflowError, ValueError):
        return False


def learn_weights(mod, support_budget=96):
    """Train only on public support examples; no gate/audit task labels."""
    uniform = mod.SearcherState()
    sampler = TypedSampler(mod, uniform)
    mined = {}
    total_probe_slots = 0
    for task_index, task in enumerate(TRAIN_SUPPORT):
        rng = random.Random(70003 + task_index)
        pairs = input_pairs(mod, task, 91)
        best = (-1, ())
        for _ in range(support_budget):
            program = sampler.sample(rng)
            hits, _ = evaluate_proposal(mod, program, uniform, pairs)
            total_probe_slots += len(pairs)
            if hits > best[0] or (hits == best[0] and len(program) < len(best[1])):
                best = (hits, program)
        mined[task] = {"hits": best[0], "tokens": list(best[1])}
    counts = Counter(token for record in mined.values() for token in record["tokens"])
    weighted = uniform.clone()
    weighted.weights = {
        token: min(6.0, 1.0 + 3.0 * counts[token])
        for token in uniform.vocab()
    }
    return weighted, {
        "support_tasks": list(TRAIN_SUPPORT),
        "support_budget_per_task": support_budget,
        "support_candidate_evaluations": support_budget * len(TRAIN_SUPPORT),
        "support_charged_probe_slots": total_probe_slots,
        "support_best": mined,
        "learned_token_weights": {
            mod.OP_NAMES[token]: weighted.weights[token]
            for token in sorted(counts)
        },
        "support_labels_used_in_gate_or_audit": False,
    }


def run_arm(mod, name, state, sampler, task, seed, examples_seed,
            shift, proposals):
    pairs = input_pairs(mod, task, examples_seed)
    rng = random.Random(1000003 * seed + 7919 * ARMS.index(name) * 0)
    # Deliberately identical RNG seed across all arms; generators differ.
    started = time.process_time()
    success = None
    best_score = 0
    type_valid = 0
    for _ in range(proposals):
        if name == "legacy":
            candidate = tuple(mod._random_tokens(rng, state, lo=2, hi=4))
        else:
            candidate = sampler.sample(rng)
        hits, valid = evaluate_proposal(mod, candidate, state, pairs)
        type_valid += int(valid)
        best_score = max(best_score, hits)
        if hits == len(pairs) and success is None:
            success = candidate
    elapsed = time.process_time() - started
    return {
        "solved": success is not None,
        "shift_pass": transfer_ok(mod, success, state, task, shift),
        "program": list(success) if success is not None else [],
        "candidate_evals": proposals,
        "charged_probe_slots": proposals * len(pairs),
        "type_valid_proposals": type_valid,
        "best_hits": best_score,
        "cpu_seconds": elapsed,
        "cpu_cap_breached": elapsed > CPU_CEILING_PER_TASK_SEED_ARM,
    }


def execute_stage(mod, tasks, arms, seeds, examples_seed, proposals):
    shift = independent_shift_inputs()
    rows = []
    for task in tasks:
        for seed in range(*seeds):
            for name, (state, sampler) in arms.items():
                row = run_arm(
                    mod, name, state, sampler, task, seed, examples_seed,
                    shift, proposals,
                )
                row.update({"task": task, "seed": seed, "arm": name})
                rows.append(row)
    summary = {}
    for name in ARMS:
        selected = [r for r in rows if r["arm"] == name]
        summary[name] = {
            "solved": sum(r["solved"] for r in selected),
            "shift_pass": sum(r["shift_pass"] for r in selected),
            "candidate_evals": sum(r["candidate_evals"] for r in selected),
            "charged_probe_slots": sum(r["charged_probe_slots"] for r in selected),
            "type_valid_proposals": sum(r["type_valid_proposals"] for r in selected),
            "total_cpu_seconds": round(sum(r["cpu_seconds"] for r in selected), 6),
            "cpu_cap_breaches": sum(r["cpu_cap_breached"] for r in selected),
            "by_task_solved": {
                task: sum(r["solved"] for r in selected if r["task"] == task)
                for task in tasks
            },
            "by_task_shift": {
                task: sum(r["shift_pass"] for r in selected if r["task"] == task)
                for task in tasks
            },
        }
    # Identical logical candidate/probe-slot budgets, deterministic uniform null.
    metrics = ("candidate_evals", "charged_probe_slots")
    assert all(
        len({summary[name][metric] for name in ARMS}) == 1
        for metric in metrics
    )
    def stripped(name):
        return [
            (r["task"], r["seed"], r["solved"], r["program"],
             r["best_hits"], r["type_valid_proposals"])
            for r in rows if r["arm"] == name
        ]
    assert stripped("typed_uniform") == stripped("typed_null")
    return {"summary": summary, "rows": rows}


def judge_gate(stage, tasks, delta_threshold=MIN_DEV_DELTA):
    stats = stage["summary"]
    incumbent = stats["typed_uniform"]
    candidate = stats["typed_learned"]
    delta = candidate["solved"] - incumbent["solved"]
    per_task_delta = {
        task: candidate["by_task_solved"][task] - incumbent["by_task_solved"][task]
        for task in tasks
    }
    same_logical_budget = (
        candidate["candidate_evals"] == incumbent["candidate_evals"]
        and candidate["charged_probe_slots"] == incumbent["charged_probe_slots"]
    )
    cpu_cap_clear = (
        incumbent["cpu_cap_breaches"] == 0
        and candidate["cpu_cap_breaches"] == 0
    )
    accept = (
        delta >= delta_threshold
        and min(per_task_delta.values()) >= -MAX_TASK_REGRESSION
        and same_logical_budget and cpu_cap_clear
    )
    return {
        "accept": accept,
        "delta_total": delta,
        "delta_per_task": per_task_delta,
        "min_delta_required": delta_threshold,
        "max_task_regression": MAX_TASK_REGRESSION,
        "same_candidate_and_probe_budget": same_logical_budget,
        "identical_cpu_ceiling_seconds_per_task_seed_arm":
            CPU_CEILING_PER_TASK_SEED_ARM,
        "cpu_ceiling_satisfied": cpu_cap_clear,
        "cpu_usage_equal": False,
        "decision_source": "synthetic development tasks only",
    }


def run(repo, seeds=SEEDS, proposals=PROPOSALS):
    mod = load_historical_core(repo)
    uniform = mod.SearcherState()
    null = uniform.clone()
    null.weights = {tok: 1.0 for tok in null.vocab()}
    learned, support = learn_weights(mod)
    arms = {
        "legacy": (uniform, None),
        "typed_uniform": (uniform, TypedSampler(mod, uniform)),
        "typed_null": (null, TypedSampler(mod, null)),
        "typed_learned": (learned, TypedSampler(mod, learned)),
    }
    assert tuple(arms) == ARMS
    development = execute_stage(
        mod, DEV_TASKS, arms, seeds, examples_seed=113, proposals=proposals,
    )
    decision = judge_gate(development, DEV_TASKS)
    # Audit is always reported but has no influence on the development gate.
    audit = execute_stage(
        mod, AUDIT_TASKS, arms, seeds, examples_seed=211, proposals=proposals,
    )
    audit_delta = (
        audit["summary"]["typed_learned"]["solved"]
        - audit["summary"]["typed_uniform"]["solved"]
    )
    audit_per_task = {
        task: (audit["summary"]["typed_learned"]["by_task_solved"][task]
               - audit["summary"]["typed_uniform"]["by_task_solved"][task])
        for task in AUDIT_TASKS
    }
    independent_replication = (
        audit_delta > 0
        and min(audit_per_task.values()) >= -MAX_AUDIT_TASK_REGRESSION
        and audit["summary"]["typed_learned"]["cpu_cap_breaches"] == 0
    )
    return {
        "schema": "typed-weight-gate-v1",
        "root_commit": ROOT_SHA,
        "scope": "synthetic grammar tasks only; no sealed TEST/J or RSI-4 Phase 1",
        "preregistered": {
            "support_tasks": TRAIN_SUPPORT,
            "development_tasks": DEV_TASKS,
            "independent_audit_tasks": AUDIT_TASKS,
            "seed_interval": seeds,
            "proposals_per_task_seed_arm": proposals,
            "cpu_ceiling_per_task_seed_arm": CPU_CEILING_PER_TASK_SEED_ARM,
            "min_dev_delta": MIN_DEV_DELTA,
            "max_regression_per_task": MAX_TASK_REGRESSION,
            "audit_requires_positive_replication": True,
        },
        "support": support,
        "development": development,
        "development_gate": decision,
        "independent_audit": audit,
        "audit_delta": audit_delta,
        "audit_per_task": audit_per_task,
        "independent_replication": independent_replication,
        "production_eligible": bool(decision["accept"] and independent_replication),
        "limitations": [
            "Synthetic publicly described task families are not general RSI.",
            "Logical proposal/probe budgets match, but CPU consumption need not.",
            "CPU ceiling is enforced as an acceptance criterion, not a scheduler cutoff.",
            "Search weights are learned once from two support tasks, not from TEST/J.",
            "The candidate grammar excludes some root VM operators and macros.",
            "No production verifier, gate, or incumbent searcher is modified.",
        ],
    }


def self_test(repo):
    mod = load_historical_core(repo)
    state = mod.SearcherState()
    sigs = mod.build_type_sigs(state.macros)
    assert all(
        mod.static_plausible(p, sigs)
        for n in (2, 3, 4) for p in enumerate_typed("i", n)
    )
    assert (4, 16) in enumerate_typed("i", 2)
    assert (4, 29) in enumerate_typed("i", 2)
    first = TypedSampler(mod, state)
    clone = state.clone()
    clone.weights = {t: 1.0 for t in clone.vocab()}
    second = TypedSampler(mod, clone)
    assert [first.sample(random.Random(s)) for s in range(100)] == [
        second.sample(random.Random(s)) for s in range(100)
    ]
    weights, support = learn_weights(mod)
    assert len(support["support_best"]) == 2
    assert all(v >= 1.0 for v in weights.weights.values())
    fake = {"summary": {
        "typed_uniform": {
            "solved": 10, "by_task_solved": {k: 3 for k in DEV_TASKS},
            "candidate_evals": 100, "charged_probe_slots": 2000,
            "cpu_cap_breaches": 0,
        },
        "typed_learned": {
            "solved": 11, "by_task_solved": {k: 3 for k in DEV_TASKS},
            "candidate_evals": 100, "charged_probe_slots": 2000,
            "cpu_cap_breaches": 0,
        },
    }}
    assert not judge_gate(fake, DEV_TASKS)["accept"]
    fake["summary"]["typed_learned"]["by_task_solved"][DEV_TASKS[0]] = 8
    fake["summary"]["typed_learned"]["solved"] = 15
    assert judge_gate(fake, DEV_TASKS)["accept"]
    fake["summary"]["typed_learned"]["cpu_cap_breaches"] = 1
    assert not judge_gate(fake, DEV_TASKS)["accept"]
    print("PASS 6 self-tests: type validity, reachable programs, uniform null, "
          "support isolation, gate threshold, CPU-ceiling rejection")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("typed_weight_ab.json"))
    parser.add_argument("--seeds", type=int, default=SEEDS[1] - SEEDS[0])
    parser.add_argument("--proposals", type=int, default=PROPOSALS)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(args.repo)
        return
    assert 1 <= args.seeds <= 128
    assert 1 <= args.proposals <= 100
    payload = run(args.repo, seeds=(SEEDS[0], SEEDS[0] + args.seeds),
                  proposals=args.proposals)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "support": payload["support"],
        "development": payload["development"]["summary"],
        "development_gate": payload["development_gate"],
        "independent_audit": payload["independent_audit"]["summary"],
        "audit_delta": payload["audit_delta"],
        "audit_per_task": payload["audit_per_task"],
        "independent_replication": payload["independent_replication"],
        "production_eligible": payload["production_eligible"],
        "artifact": str(args.out),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
