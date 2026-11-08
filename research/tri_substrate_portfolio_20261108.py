#!/usr/bin/env python3
"""Cross-substrate conservative proposal portfolios with multiple exploration policies.

Research-only: uses wholly synthetic task-generating DSLs for integer lists,
strings, and directed graphs. Never reads or modifies sealed TEST/J,
historical verifier, RSI-4 Phase 1, or PRs #48-54.

A structural inclusion invariant guarantees that every distinct type-valid
incumbent candidate is evaluated by each conservative arm under the SAME
number of candidate-evaluation slots. Invalid and duplicate slots are
reclaimed for typed-uniform, behavioral-archive novelty, local failure memory,
or their hybrid. No extra candidate is evaluated for lookahead.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

BASE_SHA = "c4f0a8627a1c9f37dd3aa6291b0eee0c78648210"
DOMAINS = ("integer_list", "string", "directed_graph")
ARMS = (
    "legacy", "typed_uniform", "conservative_uniform",
    "conservative_novelty", "conservative_failure", "conservative_hybrid",
)
BUDGET = 48
SEEDS = 24
TRAIN_EXAMPLES = 12
SHIFT_EXAMPLES = 24
CPU_CEILING_PER_CASE = 0.75
NOVELTY_POOL = 6
RECLAIM_MAX_DRAW_ATTEMPTS = 48

OPS = {
    "integer_list": {
        "transform": ("reverse", "tail", "even", "odd", "sort",
                      "positive", "negative", "dedup"),
        "aggregate": ("length", "sum", "minimum", "maximum",
                      "first", "last", "sum_squares", "count_nonzero"),
    },
    "string": {
        "transform": ("reverse", "lower", "upper", "letters",
                      "digits", "no_vowels", "vowels_only",
                      "without_spaces", "unique", "sort"),
        "aggregate": ("length", "count_a", "count_e", "vowel_count",
                      "digit_count", "distinct", "first_ord", "ascii_sum_mod"),
    },
    "directed_graph": {
        "transform": ("reverse_edges", "undirected", "no_loops",
                      "even_sources", "odd_sources", "up_edges",
                      "down_edges", "dedup_edges", "first_half", "last_half"),
        "aggregate": ("edge_count", "vertex_count", "loop_count",
                      "distinct_endpoints", "source_count", "sink_count",
                      "up_edge_count", "even_source_count"),
    },
}
# New, non-overlapping benchmark targets, fixed before running any audit.
# Their programs are private to the task constructor, not supplied to search.
DEVELOPMENT = {
    "integer_list": (
        ("tail", "sum"), ("even", "maximum"), ("sort", "last"),
        ("reverse", "first"), ("positive", "length"), ("odd", "sum")),
    "string": (
        ("lower", "count_a"), ("reverse", "first_ord"),
        ("digits", "length"), ("no_vowels", "length"),
        ("unique", "length"), ("reverse", "count_e")),
    "directed_graph": (
        ("reverse_edges", "up_edge_count"), ("no_loops", "edge_count"),
        ("even_sources", "edge_count"), ("undirected", "loop_count"),
        ("reverse_edges", "even_source_count"),
        ("dedup_edges", "distinct_endpoints")),
}
INDEPENDENT_AUDIT = {
    "integer_list": (
        ("reverse", "tail", "sum"), ("even", "sum"),
        ("negative", "length"), ("tail", "sort", "first"),
        ("dedup", "length"), ("reverse", "odd", "sum")),
    "string": (
        ("upper", "count_e"), ("without_spaces", "length"),
        ("lower", "unique", "length"), ("letters", "distinct"),
        ("vowels_only", "length"), ("reverse", "digits", "length")),
    "directed_graph": (
        ("no_loops", "reverse_edges", "up_edge_count"),
        ("odd_sources", "edge_count"), ("even_sources", "loop_count"),
        ("first_half", "edge_count"),
        ("reverse_edges", "source_count"),
        ("down_edges", "edge_count")),
}
assert all(
    set(DEVELOPMENT[d]).isdisjoint(INDEPENDENT_AUDIT[d])
    for d in DOMAINS
)


def stable_seed(*parts):
    raw = "|".join(str(x) for x in parts)
    return int.from_bytes(hashlib.sha256(raw.encode()).digest()[:8], "big")


def unique(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return tuple(out)


def transform(domain, name, value):
    if domain == "integer_list":
        xs = tuple(value)
        functions = {
            "reverse": lambda: xs[::-1],
            "tail": lambda: xs[1:],
            "even": lambda: xs[::2],
            "odd": lambda: xs[1::2],
            "sort": lambda: tuple(sorted(xs)),
            "positive": lambda: tuple(x for x in xs if x > 0),
            "negative": lambda: tuple(x for x in xs if x < 0),
            "dedup": lambda: unique(xs),
        }
        return functions[name]()
    if domain == "string":
        s = value
        functions = {
            "reverse": lambda: s[::-1],
            "lower": lambda: s.lower(),
            "upper": lambda: s.upper(),
            "letters": lambda: "".join(c for c in s if c.isalpha()),
            "digits": lambda: "".join(c for c in s if c.isdigit()),
            "no_vowels": lambda: "".join(c for c in s if c.lower() not in "aeiou"),
            "vowels_only": lambda: "".join(c for c in s if c.lower() in "aeiou"),
            "without_spaces": lambda: s.replace(" ", ""),
            "unique": lambda: "".join(unique(s)),
            "sort": lambda: "".join(sorted(s)),
        }
        return functions[name]()
    n, edges = value
    edges = tuple(edges)
    functions = {
        "reverse_edges": lambda: tuple((b, a) for a, b in edges),
        "undirected": lambda: edges + tuple((b, a) for a, b in edges),
        "no_loops": lambda: tuple((a, b) for a, b in edges if a != b),
        "even_sources": lambda: tuple((a, b) for a, b in edges if a % 2 == 0),
        "odd_sources": lambda: tuple((a, b) for a, b in edges if a % 2),
        "up_edges": lambda: tuple((a, b) for a, b in edges if a < b),
        "down_edges": lambda: tuple((a, b) for a, b in edges if a > b),
        "dedup_edges": lambda: unique(edges),
        "first_half": lambda: edges[:len(edges) // 2],
        "last_half": lambda: edges[len(edges) // 2:],
    }
    return n, functions[name]()


def aggregate(domain, name, value):
    if domain == "integer_list":
        x = tuple(value)
        functions = {
            "length": lambda: len(x),
            "sum": lambda: sum(x),
            "minimum": lambda: min(x, default=0),
            "maximum": lambda: max(x, default=0),
            "first": lambda: x[0] if x else 0,
            "last": lambda: x[-1] if x else 0,
            "sum_squares": lambda: sum(y * y for y in x),
            "count_nonzero": lambda: sum(y != 0 for y in x),
        }
        return functions[name]()
    if domain == "string":
        s = value
        functions = {
            "length": lambda: len(s),
            "count_a": lambda: s.count("a"),
            "count_e": lambda: s.count("e"),
            "vowel_count": lambda: sum(c.lower() in "aeiou" for c in s),
            "digit_count": lambda: sum(c.isdigit() for c in s),
            "distinct": lambda: len(set(s)),
            "first_ord": lambda: ord(s[0]) if s else 0,
            "ascii_sum_mod": lambda: sum(map(ord, s)) % 97,
        }
        return functions[name]()
    n, edges = value
    functions = {
        "edge_count": lambda: len(edges),
        "vertex_count": lambda: n,
        "loop_count": lambda: sum(a == b for a, b in edges),
        "distinct_endpoints": lambda: len({v for edge in edges for v in edge}),
        "source_count": lambda: len({a for a, _ in edges}),
        "sink_count": lambda: len({b for _, b in edges}),
        "up_edge_count": lambda: sum(a < b for a, b in edges),
        "even_source_count": lambda: sum(a % 2 == 0 for a, b in edges),
    }
    return functions[name]()


def valid(domain, program):
    ops = OPS[domain]
    return (
        1 <= len(program) <= 3
        and program[-1] in ops["aggregate"]
        and all(op in ops["transform"] for op in program[:-1])
    )


def execute(domain, program, xs):
    if not valid(domain, program):
        return None
    value = xs
    for token in program[:-1]:
        value = transform(domain, token, value)
    return aggregate(domain, program[-1], value)


def examples(domain, split, task_index, seed, count):
    rng = random.Random(stable_seed("input-v1", domain, split, task_index, seed))
    out = []
    for index in range(count):
        if domain == "integer_list":
            n = rng.randint(0, 7 if split == "development" else 16)
            valmax = 7 if split == "development" else 31
            xs = tuple(rng.randint(-valmax, valmax) for _ in range(n))
        elif domain == "string":
            n = rng.randint(0, 10 if split == "development" else 25)
            alphabet = "aAeEiIoOuUbcdfXYZ 01359" if split == "development" else "aAeEiIoOuUbcdfGhJXYZ 013579"
            xs = "".join(rng.choice(alphabet) for _ in range(n))
        else:
            n = rng.randint(2, 7 if split == "development" else 12)
            e = rng.randint(0, 12 if split == "development" else 32)
            xs = (n, tuple((rng.randrange(n), rng.randrange(n)) for _ in range(e)))
        out.append(xs)
    return tuple(out)


def scored_program(domain, p, train_x, train_y):
    # Every candidate is charged the same public train-example slots.
    outputs = tuple(execute(domain, p, x) for x in train_x)
    hits = sum(a == b for a, b in zip(outputs, train_y))
    return hits, outputs


def legacy_draws(domain, task_index, seed):
    rng = random.Random(stable_seed("legacy-v1", domain, task_index, seed))
    vocab = OPS[domain]["transform"] + OPS[domain]["aggregate"]
    return tuple(
        tuple(rng.choice(vocab) for _ in range(rng.randint(1, 3)))
        for _ in range(BUDGET)
    )


def typed_draw(domain, rng):
    ops = OPS[domain]
    length_transforms = rng.choice((0, 1, 1, 2))
    return tuple(rng.choice(ops["transform"]) for _ in range(length_transforms)) + (
        rng.choice(ops["aggregate"]),)


def proposed(domain, rng, mode, used, behavior_archive, failed):
    choices = []
    for _ in range(NOVELTY_POOL if mode != "conservative_uniform" else 1):
        for _retry in range(RECLAIM_MAX_DRAW_ATTEMPTS):
            p = typed_draw(domain, rng)
            if p not in used:
                break
        if p in used:
            continue
        novelty = sum(1.0 / (1.0 + behavior_archive[t]) for t in p)
        if len(p) > 1:
            novelty += 0.3 * sum(
                1.0 / (1.0 + behavior_archive[p[i] + "|" + p[i+1]])
                for i in range(len(p) - 1))
        failure_penalty = sum(failed[t] for t in p)
        if mode == "conservative_novelty":
            priority = novelty
        elif mode == "conservative_failure":
            priority = -failure_penalty
        elif mode == "conservative_hybrid":
            priority = novelty - 0.25 * failure_penalty
        else:
            priority = 0.0
        choices.append((priority, p))
    if not choices:
        # Exhaustion is rare in the finite DSL. Existing valid program is
        # still evaluated and charged, with no extra oracle execution.
        return typed_draw(domain, rng)
    top = max(priority for priority, _ in choices)
    return next(p for priority, p in choices if priority == top)


def run_arm(domain, task_index, task, seed, split, arm):
    t0 = time.process_time()
    train_x = examples(domain, split, task_index, seed, TRAIN_EXAMPLES)
    train_y = tuple(execute(domain, task, x) for x in train_x)
    shift_x = examples(domain, "independent_shift", task_index, seed+7000, SHIFT_EXAMPLES)
    shift_y = tuple(execute(domain, task, x) for x in shift_x)
    raw = legacy_draws(domain, task_index, seed)
    base_set = {p for p in raw if valid(domain, p)}
    baseline_first, recovered_first = None, None
    seen_baseline = set()
    seen_all = set(base_set)
    behavioral_outputs = set()
    behavior_archive = Counter()
    failed = Counter()
    rng = random.Random(stable_seed("replacement-v1", domain, task_index, seed, arm))
    valid_count = 0
    reclaimed = 0
    actual_vm_calls = 0
    alt_first = None
    for i in range(BUDGET):
        is_baseline_slot = arm != "typed_uniform"
        raw_p = raw[i]
        replaced = False
        if arm == "typed_uniform":
            p = typed_draw(domain, rng)
        elif arm == "legacy":
            p = raw_p
        elif valid(domain, raw_p) and raw_p not in seen_baseline:
            p = raw_p
            seen_baseline.add(raw_p)
        else:
            p = proposed(domain, rng, arm, seen_all, behavior_archive, failed)
            seen_all.add(p)
            reclaimed += 1
            replaced = True
        val = valid(domain, p)
        valid_count += int(val)
        actual_vm_calls += TRAIN_EXAMPLES * int(val)
        hits, outputs = scored_program(domain, p, train_x, train_y)
        if val:
            signature = outputs
            if signature not in behavioral_outputs:
                behavioral_outputs.add(signature)
                for token in p:
                    behavior_archive[token] += 1
                for j in range(len(p)-1):
                    behavior_archive[p[j] + "|" + p[j+1]] += 1
            if hits == 0:
                for token in p:
                    failed[token] += 1
        if hits == TRAIN_EXAMPLES:
            if arm == "legacy" and baseline_first is None:
                baseline_first = p
            elif arm == "typed_uniform" and recovered_first is None:
                recovered_first = p
            elif arm not in ("typed_uniform", "legacy"):
                if replaced and recovered_first is None:
                    recovered_first = p
                elif not replaced and baseline_first is None:
                    baseline_first = p
    winner = baseline_first or recovered_first
    if arm == "typed_uniform":
        winner = recovered_first
    assert sum(1 for _ in raw) == BUDGET
    if arm.startswith("conservative_"):
        assert base_set.issubset(
            {p for p in raw if valid(domain, p) and p in seen_baseline})
    shift_pass = (
        winner is not None
        and all(execute(domain, winner, x) == y
                for x, y in zip(shift_x, shift_y))
    )
    return {
        "domain": domain,
        "task_index": task_index,
        "seed": seed,
        "arm": arm,
        "solved": winner is not None,
        "shift_pass": bool(shift_pass),
        "winner": list(winner) if winner else None,
        "baseline_winner": list(baseline_first) if baseline_first else None,
        "candidate_evaluations": BUDGET,
        "charged_public_probe_slots": BUDGET * TRAIN_EXAMPLES,
        "actual_training_vm_calls": actual_vm_calls,
        "valid_proposals": valid_count,
        "reclaimed_slots": reclaimed,
        "observed_behavior_classes": len(behavioral_outputs),
        "cpu_seconds": time.process_time() - t0,
    }


def stage(tasks_by_domain, split, seeds):
    data = []
    for domain in DOMAINS:
        for task_index, task in enumerate(tasks_by_domain[domain]):
            for seed in range(seeds):
                for arm in ARMS:
                    data.append(run_arm(domain, task_index, task, seed, split, arm))
    summary = {}
    for arm in ARMS:
        group = [r for r in data if r["arm"] == arm]
        summary[arm] = {
            "solved": sum(x["solved"] for x in group),
            "shift_pass": sum(x["shift_pass"] for x in group),
            "candidate_evaluations": sum(x["candidate_evaluations"] for x in group),
            "charged_public_probe_slots": sum(x["charged_public_probe_slots"] for x in group),
            "actual_training_vm_calls": sum(x["actual_training_vm_calls"] for x in group),
            "valid_proposals": sum(x["valid_proposals"] for x in group),
            "reclaimed_slots": sum(x["reclaimed_slots"] for x in group),
            "cpu_seconds": round(sum(x["cpu_seconds"] for x in group), 6),
            "cpu_cap_breaches": sum(x["cpu_seconds"] > CPU_CEILING_PER_CASE for x in group),
            "domain_solved": {
                d: sum(x["solved"] for x in group if x["domain"] == d)
                for d in DOMAINS},
            "domain_shift": {
                d: sum(x["shift_pass"] for x in group if x["domain"] == d)
                for d in DOMAINS},
            "task_solved": {
                d: [sum(x["solved"] for x in group if x["domain"] == d and x["task_index"] == k)
                    for k in range(len(tasks_by_domain[d]))]
                for d in DOMAINS},
            "task_shift": {
                d: [sum(x["shift_pass"] for x in group if x["domain"] == d and x["task_index"] == k)
                    for k in range(len(tasks_by_domain[d]))]
                for d in DOMAINS},
        }
    for metric in ("candidate_evaluations", "charged_public_probe_slots"):
        assert len({summary[a][metric] for a in ARMS}) == 1, metric
    raw_index = {
        (r["domain"], r["task_index"], r["seed"]):r
        for r in data if r["arm"] == "legacy"
    }
    for r in data:
        if not r["arm"].startswith("conservative_"):
            continue
        baseline = raw_index[(r["domain"], r["task_index"], r["seed"])]
        if baseline["solved"]:
            assert r["solved"] and r["winner"] == baseline["winner"]
            assert r["shift_pass"] == baseline["shift_pass"]
    return {"summary": summary, "rows": data, "inclusion_proof_checks_passed": True}


def choose_development(summary):
    incumbent = summary["legacy"]
    typed = summary["typed_uniform"]
    decision = {}
    candidates = []
    for arm in ARMS:
        if not arm.startswith("conservative_"):
            continue
        cur = summary[arm]
        deltas = {
            d: cur["domain_shift"][d] - incumbent["domain_shift"][d]
            for d in DOMAINS
        }
        task_deltas = {
            d: [a-b for a,b in zip(cur["task_shift"][d],incumbent["task_shift"][d])]
            for d in DOMAINS
        }
        pass_gate = (
            min(deltas.values()) > 0
            and min(v for vals in task_deltas.values() for v in vals) >= 0
            and cur["candidate_evaluations"] == incumbent["candidate_evaluations"]
            and cur["charged_public_probe_slots"] == incumbent["charged_public_probe_slots"]
            and cur["cpu_cap_breaches"] == 0
            and cur["shift_pass"] > typed["shift_pass"]
        )
        decision[arm] = {
            "passes_development": pass_gate,
            "domain_ood_gain_vs_legacy": deltas,
            "task_ood_gain_vs_legacy": task_deltas,
            "ood_gain_vs_typed_uniform": cur["shift_pass"]-typed["shift_pass"],
        }
        if pass_gate:
            candidates.append(arm)
    selection = max(
        candidates,
        key=lambda a: (
            min(decision[a]["domain_ood_gain_vs_legacy"].values()),
            summary[a]["shift_pass"],
            -summary[a]["cpu_seconds"],
        ),
        default=None,
    )
    return {"selected": selection, "candidate_decisions": decision}


def audit_gate(summary, selected):
    if selected is None:
        return {"pass": False, "reason": "No development candidate met the original and typed controls"}
    baseline = summary["legacy"]
    typed = summary["typed_uniform"]
    candidate = summary[selected]
    by_domain = {
        d: candidate["domain_shift"][d]-baseline["domain_shift"][d]
        for d in DOMAINS
    }
    by_task = {
        d: [a-b for a,b in zip(candidate["task_shift"][d],baseline["task_shift"][d])]
        for d in DOMAINS
    }
    ok = (
        min(by_domain.values()) > 0
        and min(z for v in by_task.values() for z in v) >= 0
        and candidate["shift_pass"] > typed["shift_pass"]
        and candidate["cpu_cap_breaches"] == 0
        and candidate["candidate_evaluations"] == baseline["candidate_evaluations"]
        and candidate["charged_public_probe_slots"] == baseline["charged_public_probe_slots"]
    )
    return {
        "pass": ok,
        "by_domain_ood_gain_vs_legacy": by_domain,
        "by_task_ood_gain_vs_legacy": by_task,
        "ood_gain_vs_typed_uniform": candidate["shift_pass"]-typed["shift_pass"],
        "reason": "All preregistered finite-domain criteria met" if ok else "Independent criteria failed",
    }


def self_test():
    for domain in DOMAINS:
        programs = DEVELOPMENT[domain] + INDEPENDENT_AUDIT[domain]
        assert len(programs) == 12 and len(set(programs)) == 12
        assert all(valid(domain,p) for p in programs)
        for p in programs:
            for xs in examples(domain,"development",0,3,5):
                assert isinstance(execute(domain,p,xs),int)
        for seed in range(3):
            legacy = run_arm(domain,0,DEVELOPMENT[domain][0],seed,"development","legacy")
            for mode in ARMS[2:]:
                cur=run_arm(domain,0,DEVELOPMENT[domain][0],seed,"development",mode)
                assert cur["candidate_evaluations"]==legacy["candidate_evaluations"]
                if legacy["solved"]:
                    assert cur["winner"]==legacy["winner"]
                    assert cur["shift_pass"]==legacy["shift_pass"]
    print("PASS: all DSLs type-valid, no task collisions, and incumbent-preservation "
          "invariance across three substrates and four alternatives")


def run(seeds):
    self_test()
    dev = stage(DEVELOPMENT,"development",seeds)
    selection = choose_development(dev["summary"])
    # Freeze development selection before this independent evaluation.
    audit = stage(INDEPENDENT_AUDIT,"independent_audit",seeds)
    decision = audit_gate(audit["summary"],selection["selected"])
    return {
        "schema":"conservative-cross-substrate-v1",
        "main_baseline_sha":BASE_SHA,
        "preregistration":{
            "seeds":seeds,"candidate_slots_per_case":BUDGET,
            "public_train_examples":TRAIN_EXAMPLES,
            "shift_examples":SHIFT_EXAMPLES,"domains":DOMAINS,
            "development_tasks_per_domain":6,"audit_tasks_per_domain":6,
            "policies":ARMS,
            "gate_dev":"strictly positive per-domain OOD gain vs legacy, no per-task loss, strictly exceed typed-uniform overall, identical charged slots",
            "gate_audit":"same frozen criteria on independent task programs and input distributions",
        },
        "development":dev,
        "development_selection":selection,
        "independent_audit":audit,
        "independent_audit_gate":decision,
        "research_criteria_met":decision["pass"],
        "general_rsi_proven":False,
        "production_eligible":False,
        "limitations":[
            "The task families are DSL-generated, not arbitrary real-world domains.",
            "Incumbent preservation is conditional on deterministic evaluation and exact-solution priority.",
            "Structural inclusion does not guarantee a new exact candidate on unseen tasks.",
            "Behavior-novelty scoring uses only previously observed public training behavior.",
            "All arms have equal scored proposal slots, but distinct VM instruction counts and CPU.",
            "Typing and generator rejection sampling are CPU overhead, measured but not budget matched.",
            "This is one generation of within-task search, NOT recursive improvement across generations.",
            "No existing sealed TEST/J or RSI-4 Phase 1 used for tuning.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",type=int,default=SEEDS)
    parser.add_argument("--out",type=Path,default=Path("portfolio_results.json"))
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        self_test()
        return
    assert 1 <= args.seeds <= 128
    result=run(args.seeds)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "development":result["development"]["summary"],
        "selection":result["development_selection"],
        "independent_audit":result["independent_audit"]["summary"],
        "gate":result["independent_audit_gate"],
        "research_criteria_met":result["research_criteria_met"],
        "production_eligible":result["production_eligible"],
        "result_file":str(args.out),
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
