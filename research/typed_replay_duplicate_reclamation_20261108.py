#!/usr/bin/env python3
"""Conservative typed replay: preserve every incumbent program and reclaim duplicates.

Frozen dependency: PR #55 at a specific immutable commit.
New independent targets for integer-list, string and directed-graph substrates.
All arms execute exactly the SAME number of valid VM programs and public probes.
The gate rejects any held-out task regression, even if the mean improves.

Research only; no production, RSI-4, sealed TEST/J, or archived experiment edits.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import types

PR55_SHA = "dbb7ba9600534e1578198d45bc58a4d99893fdf1"
PR55_PATH = "research/tri_substrate_portfolio_20261108.py"
BASE_MAIN_SHA = "c4f0a8627a1c9f37dd3aa6291b0eee0c78648210"
DOMAIN_NAMES = ("integer_list", "string", "directed_graph")
ARMS = (
    "typed_uniform",
    "reclaim_uniform",
    "reclaim_novelty",
    "reclaim_failure",
    "reclaim_hybrid",
    "reclaim_mutation",
)
SEEDS = 32
BUDGET = 48
TRAIN = 12
INDEPENDENT = 24
CPU_CAP_PER_CASE = 0.75

# These targets are disjoint from all targets in PR #55.
DEV = {
    "integer_list": (
        ("reverse", "minimum"), ("sort", "first"),
        ("positive", "sum"), ("negative", "sum"),
        ("odd", "length"), ("reverse", "sum_squares")),
    "string": (
        ("lower", "vowel_count"), ("sort", "count_a"),
        ("digits", "distinct"), ("reverse", "without_spaces", "length"),
        ("upper", "first_ord"), ("no_vowels", "first_ord")),
    "directed_graph": (
        ("reverse_edges", "sink_count"), ("dedup_edges", "edge_count"),
        ("no_loops", "source_count"), ("up_edges", "distinct_endpoints"),
        ("even_sources", "sink_count"), ("undirected", "up_edge_count")),
}
AUDIT = {
    "integer_list": (
        ("sort", "sum_squares"), ("tail", "count_nonzero"),
        ("positive", "minimum"), ("reverse", "even", "sum_squares"),
        ("dedup", "maximum"), ("negative", "last")),
    "string": (
        ("reverse", "upper", "first_ord"), ("lower", "count_e"),
        ("digits", "ascii_sum_mod"), ("sort", "distinct"),
        ("without_spaces", "count_a"), ("unique", "ascii_sum_mod")),
    "directed_graph": (
        ("last_half", "sink_count"), ("first_half", "loop_count"),
        ("odd_sources", "distinct_endpoints"), ("up_edges", "source_count"),
        ("undirected", "edge_count"), ("reverse_edges", "loop_count")),
}


def load_frozen_previous(repo):
    code = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{PR55_SHA}:{PR55_PATH}"], text=True,
    )
    module = types.ModuleType("_frozen_pr55_portfolio")
    module.__file__ = f"{PR55_SHA}:{PR55_PATH}"
    sys.modules[module.__name__] = module
    exec(compile(code, module.__file__, "exec"), module.__dict__)
    for domain in DOMAIN_NAMES:
        assert all(
            module.valid(domain, task)
            for task in DEV[domain] + AUDIT[domain]
        )
        assert set(DEV[domain]).isdisjoint(AUDIT[domain])
        assert set(DEV[domain] + AUDIT[domain]).isdisjoint(
            module.DEVELOPMENT[domain] + module.INDEPENDENT_AUDIT[domain]
        )
    return module


def typed_replay(prior, domain, index, seed):
    rng = random.Random(
        prior.stable_seed("typed-replay-v1", domain, index, seed)
    )
    return tuple(prior.typed_draw(domain, rng) for _ in range(BUDGET))


def mutation_candidate(prior, domain, rng, used, best):
    if best is None:
        return prior.typed_draw(domain, rng)
    for _ in range(36):
        candidate = list(best)
        location = rng.randrange(len(candidate))
        group = "aggregate" if location == len(candidate) - 1 else "transform"
        candidate[location] = rng.choice(prior.OPS[domain][group])
        p = tuple(candidate)
        if p not in used and prior.valid(domain, p):
            return p
    return prior.typed_draw(domain, rng)


def draw_replacement(prior, domain, rng, arm, used, archive, failed, best):
    if arm == "reclaim_mutation":
        for _ in range(12):
            p = mutation_candidate(prior, domain, rng, used, best)
            if p not in used:
                return p
    name = {
        "reclaim_uniform": "conservative_uniform",
        "reclaim_novelty": "conservative_novelty",
        "reclaim_failure": "conservative_failure",
        "reclaim_hybrid": "conservative_hybrid",
        "reclaim_mutation": "conservative_uniform",
    }[arm]
    return prior.proposed(domain, rng, name, used, archive, failed)


def evaluate(prior, domain, task, idx, seed, split, arm):
    started = time.process_time()
    train_x = prior.examples(domain, "typed-replay-" + split, idx, seed, TRAIN)
    target = tuple(prior.execute(domain, task, x) for x in train_x)
    independent_x = prior.examples(
        domain, "typed-replay-shift", idx, seed + 39991, INDEPENDENT
    )
    independent_y = tuple(
        prior.execute(domain, task, x) for x in independent_x
    )
    incumbent = typed_replay(prior, domain, idx, seed)
    included = set(incumbent)
    seen_incumbent = set()
    used = set(incumbent)
    rng = random.Random(
        prior.stable_seed("replacement-v2", domain, idx, seed, arm)
    )
    archive = Counter()
    behavior_classes = set()
    failed = Counter()
    best, best_hits = None, -1
    first_baseline_exact = None
    first_recovery_exact = None
    reclaimed = 0
    for i, initial in enumerate(incumbent):
        replacement = False
        if arm == "typed_uniform" or initial not in seen_incumbent:
            program = initial
            seen_incumbent.add(initial)
        else:
            program = draw_replacement(
                prior, domain, rng, arm, used, archive, failed, best
            )
            assert prior.valid(domain, program)
            used.add(program)
            replacement = True
            reclaimed += 1
        # Exactly TRAIN actual interpreter calls for every arm and slot.
        hits, outputs = prior.scored_program(domain, program, train_x, target)
        if hits > best_hits:
            best, best_hits = program, hits
        if outputs not in behavior_classes:
            behavior_classes.add(outputs)
            for token in program:
                archive[token] += 1
            for j in range(len(program) - 1):
                archive[program[j] + "|" + program[j + 1]] += 1
        if hits == 0:
            for token in program:
                failed[token] += 1
        if hits == TRAIN:
            if not replacement and first_baseline_exact is None:
                first_baseline_exact = program
            if replacement and first_recovery_exact is None:
                first_recovery_exact = program
    # Any incumbent exact solution wins over replacements; this preserves
    # incumbent OOD correctness, even if an earlier new program train-overfits.
    winner = first_baseline_exact or first_recovery_exact
    if arm == "typed_uniform":
        assert reclaimed == 0 and winner == first_baseline_exact
    else:
        assert included.issubset(seen_incumbent)
    ood_ok = bool(
        winner is not None
        and all(
            prior.execute(domain, winner, x) == y
            for x, y in zip(independent_x, independent_y)
        )
    )
    return {
        "domain": domain,
        "task": idx,
        "seed": seed,
        "arm": arm,
        "solved": winner is not None,
        "ood_pass": ood_ok,
        "winner": list(winner) if winner else None,
        "first_incumbent_solution": (
            list(first_baseline_exact) if first_baseline_exact else None
        ),
        "reclaimed_duplicates": reclaimed,
        "behavior_classes": len(behavior_classes),
        "candidate_evaluations": BUDGET,
        "actual_interpreter_calls": BUDGET * TRAIN,
        "charged_input_probes": BUDGET * TRAIN,
        "cpu_seconds": time.process_time() - started,
    }


def evaluate_stage(prior, tasks, split, seed_count):
    rows = []
    for domain in DOMAIN_NAMES:
        for task_index, task in enumerate(tasks[domain]):
            for seed in range(seed_count):
                for arm in ARMS:
                    rows.append(evaluate(
                        prior, domain, task, task_index, seed, split, arm
                    ))
    summary = {}
    for arm in ARMS:
        grp = [x for x in rows if x["arm"] == arm]
        summary[arm] = {
            "train_solved": sum(x["solved"] for x in grp),
            "ood_pass": sum(x["ood_pass"] for x in grp),
            "candidate_evaluations": sum(x["candidate_evaluations"] for x in grp),
            "actual_interpreter_calls": sum(x["actual_interpreter_calls"] for x in grp),
            "charged_input_probes": sum(x["charged_input_probes"] for x in grp),
            "reclaimed_duplicates": sum(x["reclaimed_duplicates"] for x in grp),
            "cpu_seconds": round(sum(x["cpu_seconds"] for x in grp), 6),
            "cpu_cap_breaches": sum(x["cpu_seconds"] > CPU_CAP_PER_CASE for x in grp),
            "by_domain": {
                d: sum(x["ood_pass"] for x in grp if x["domain"] == d)
                for d in DOMAIN_NAMES
            },
            "by_task": {
                d: [
                    sum(x["ood_pass"] for x in grp if x["domain"] == d and x["task"] == k)
                    for k in range(len(tasks[d]))
                ] for d in DOMAIN_NAMES
            },
        }
    for field in ("candidate_evaluations", "actual_interpreter_calls", "charged_input_probes"):
        assert len({summary[arm][field] for arm in ARMS}) == 1
    incumbent = {
        (x["domain"], x["task"], x["seed"]): x
        for x in rows if x["arm"] == "typed_uniform"
    }
    for x in rows:
        if x["arm"] == "typed_uniform":
            continue
        first = incumbent[(x["domain"], x["task"], x["seed"])]
        if first["solved"]:
            assert x["solved"] and x["winner"] == first["winner"]
            assert x["ood_pass"] == first["ood_pass"]
    return {"summary": summary, "rows": rows, "incumbent_inclusion_verified": True}


def select_development(summary, seed_count):
    base = summary["typed_uniform"]
    detail = {}
    eligible = []
    for arm in ARMS[1:]:
        cur = summary[arm]
        by_domain = {
            d: cur["by_domain"][d] - base["by_domain"][d]
            for d in DOMAIN_NAMES
        }
        by_task = {
            d: [x-y for x, y in zip(cur["by_task"][d], base["by_task"][d])]
            for d in DOMAIN_NAMES
        }
        budget_parity = (
            cur["candidate_evaluations"] == base["candidate_evaluations"]
            and cur["actual_interpreter_calls"] == base["actual_interpreter_calls"]
            and cur["charged_input_probes"] == base["charged_input_probes"]
        )
        accept = (
            min(by_domain.values()) >= 1
            and min(z for row in by_task.values() for z in row) >= 0
            and budget_parity
            and cur["cpu_cap_breaches"] == 0
            and base["cpu_cap_breaches"] == 0
        )
        detail[arm] = {
            "eligible": accept,
            "by_domain_ood_gain": by_domain,
            "by_task_ood_gain": by_task,
            "matched_interpreter_calls": budget_parity,
        }
        if accept:
            eligible.append(arm)
    selected = max(
        eligible,
        key=lambda name: (
            min(detail[name]["by_domain_ood_gain"].values()),
            sum(detail[name]["by_domain_ood_gain"].values()),
            -summary[name]["cpu_seconds"],
        ),
        default=None,
    )
    return {"selected": selected, "candidates": detail}


def independent_gate(summary, selected):
    if selected is None:
        return {"pass": False, "reason": "Development guard selected no candidate"}
    incumbent = summary["typed_uniform"]
    challenger = summary[selected]
    deltas = {
        d: challenger["by_domain"][d] - incumbent["by_domain"][d]
        for d in DOMAIN_NAMES
    }
    task_deltas = {
        d: [x-y for x, y in zip(challenger["by_task"][d], incumbent["by_task"][d])]
        for d in DOMAIN_NAMES
    }
    pass_all = (
        min(deltas.values()) >= 1
        and min(z for vals in task_deltas.values() for z in vals) >= 0
        and challenger["actual_interpreter_calls"] == incumbent["actual_interpreter_calls"]
        and challenger["candidate_evaluations"] == incumbent["candidate_evaluations"]
        and challenger["cpu_cap_breaches"] == 0
    )
    return {
        "pass": pass_all,
        "by_domain_ood_gain": deltas,
        "by_task_ood_gain": task_deltas,
        "actual_interpreter_calls_matched": True,
        "reason": (
            "Finite-substrate prespecified test passed; still NOT general RSI"
            if pass_all else "At least one preregistered condition failed"
        ),
    }


def self_test(prior):
    for domain in DOMAIN_NAMES:
        for task in DEV[domain] + AUDIT[domain]:
            assert prior.valid(domain, task)
            xs = prior.examples(domain, "typed-replay-smoke", 1, 17, 3)
            assert all(isinstance(prior.execute(domain, task, x), int) for x in xs)
        for seed in (0, 1, 2):
            incumbent = evaluate(prior, domain, DEV[domain][0], 0, seed, "dev", "typed_uniform")
            for arm in ARMS[1:]:
                result = evaluate(prior, domain, DEV[domain][0], 0, seed, "dev", arm)
                assert result["actual_interpreter_calls"] == incumbent["actual_interpreter_calls"]
                if incumbent["solved"]:
                    assert result["winner"] == incumbent["winner"]
                    assert result["ood_pass"] == incumbent["ood_pass"]
    print("PASS 18 invariants: three distinct substrates, immutable typed replay, "
          "same valid interpreter calls, conserved first incumbent exact solution")


def run(repo, seeds):
    prior = load_frozen_previous(repo)
    self_test(prior)
    development = evaluate_stage(prior, DEV, "dev", seeds)
    selected = select_development(development["summary"], seeds)
    # Freeze development-selected arm before evaluating new audit tasks.
    audit = evaluate_stage(prior, AUDIT, "independent", seeds)
    gate = independent_gate(audit["summary"], selected["selected"])
    return {
        "schema": "typed-incumbent-conservative-replay-v1",
        "frozen_pr55_sha": PR55_SHA,
        "baseline_main_sha": BASE_MAIN_SHA,
        "preregistered": {
            "domains": DOMAIN_NAMES,
            "development_targets": DEV,
            "independent_audit_targets": AUDIT,
            "seeds": seeds,
            "proposal_budget": BUDGET,
            "input_probes": TRAIN,
            "independent_shift_probes": INDEPENDENT,
            "guard": "positive OOD gain in each domain, no individual task regression, exactly equal interpreter and candidate budgets",
        },
        "development": development,
        "development_selection": selected,
        "independent_audit": audit,
        "independent_audit_gate": gate,
        "finite_experiment_success": gate["pass"],
        "recursive_self_improvement_proven": False,
        "production_eligible": False,
        "limitations": [
            "Type-preserving inclusion proves incumbent solution preservation only under deterministic evaluation.",
            "Identical interpreter calls and probe counts do not imply identical proposal-generation CPU.",
            "Programs are generated by a shared synthetic DSL; benchmarks do not cover all domains.",
            "Failure memory and novelty feedback are based only on public training examples.",
            "No cross-generation optimizer improvement, continual-learning forgetting or general RSI established.",
            "No sealed TEST/J, RSI-4 Phase 1, existing PR or past audit labels used for candidate selection.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--seeds", type=int, default=SEEDS)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("typed_replay_results.json"))
    args = ap.parse_args()
    if args.self_test:
        self_test(load_frozen_previous(args.repo))
        return
    assert 1 <= args.seeds <= 128
    obj = run(args.repo, args.seeds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "development": obj["development"]["summary"],
        "selected": obj["development_selection"],
        "independent_audit": obj["independent_audit"]["summary"],
        "independent_gate": obj["independent_audit_gate"],
        "finite_experiment_success": obj["finite_experiment_success"],
        "production_eligible": obj["production_eligible"],
        "raw_results": str(args.out),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
