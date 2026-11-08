"""Synthetic, preregistered finite-probe collision experiment for RSI-3.

Uses real typed RSI-2 ASTs, grammar derivations, interpreter, integrator,
receipt memory and frozen verifier. Never imports a benchmark split or RSI-4 J.
No claim about naturally occurring collision rates or external transfer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from rsi2.corpus import Task
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.terms import Int, Lam, Prim, Var, apply
from rsi2.types import Arrow, INT
from rsi3.integrator import BindingIntegrator
from rsi3.memory import EpisodicMemory
from rsi3.verifier import FrozenVerifier, public_view, term_digest


TRIGGERS = (-1, 0, 1, 2)
SEEDS = (11, 22, 33)
MODES = ("signature", "exact", "none")
STEP_BUDGET = 2000
MAX_AST_SIZE = 12
CPU_CAP_SECONDS = 2.0
PREREGISTRATION_COMMIT = "b40784d5a2e203ad2998c05a7021e6a9eeecfb3f"


def make_task(seed: int, trigger: int) -> Task:
    """Construct development-only public and independent synthetic oracle cases."""
    public_values = list(range(10, 20))
    random.Random(seed * 1009 + 17).shuffle(public_values)
    # This second generator does not inspect candidates or public samples.
    oracle_values = list(range(-3, 4))
    oracle_values.extend(random.Random(seed * 10007 + 431).sample(range(30, 50), 5))
    return Task(
        f"synthetic_identity_seed{seed}_trigger{trigger}",
        Arrow(INT, INT),
        tuple(((x,), x) for x in public_values),
        tuple(((x,), x) for x in oracle_values),
    )


def candidate_pair(trigger: int):
    """Both ASTs use only the existing default grammar's productions."""
    replacement = 0 if trigger == -1 else -1
    good = Lam(INT, Var(0))
    bad = Lam(
        INT,
        apply(
            Prim("if"),
            apply(Prim("eq"), Var(0), Int(trigger)),
            Int(replacement),
            Var(0),
        ),
    )
    return bad, good


def matches(term, examples) -> bool:
    for inputs, expected in examples:
        result = evaluate(term, inputs, library={}, step_budget=STEP_BUDGET)
        if not result.ok or result.value != expected:
            return False
    return True


def witness(seed: int, trigger: int):
    """Verify actual (not mocked) signatures and independent oracle disagreement."""
    task = make_task(seed, trigger)
    bad, good = candidate_pair(trigger)
    grammar = Grammar()
    derivations = {
        "rejected": grammar.log_probability(bad, task.request_type),
        "correct": grammar.log_probability(good, task.request_type),
    }
    if max(bad.size, good.size) > MAX_AST_SIZE:
        raise AssertionError("AST exceeds the registered size ceiling")
    if term_digest(bad) == term_digest(good):
        raise AssertionError("distinct ASTs must have distinct digests")
    if not matches(bad, task.examples) or not matches(good, task.examples):
        raise AssertionError("candidate does not match all public examples")
    integrator = BindingIntegrator([public_view(task)], step_budget=STEP_BUDGET)
    sig_bad = integrator.signature(task.name, bad, {})
    sig_good = integrator.signature(task.name, good, {})
    if sig_bad != sig_good:
        raise AssertionError("unmocked finite-probe collision was not found")
    if matches(bad, task.hidden) or not matches(good, task.hidden):
        raise AssertionError("independent oracle did not distinguish candidates")
    probe_values = {p[0] for p in integrator.probes[task.name]}
    public_values = {p[0][0] for p in task.examples}
    hidden_values = {p[0][0] for p in task.hidden}
    if hidden_values & (public_values | probe_values):
        raise AssertionError("independent oracle cases overlap public/probe inputs")
    return task, bad, good, {
        "seed": seed,
        "trigger": trigger,
        "bad_ast_size": bad.size,
        "good_ast_size": good.size,
        "bad_digest": term_digest(bad),
        "good_digest": term_digest(good),
        "bad_log_probability": derivations["rejected"],
        "good_log_probability": derivations["correct"],
        "probe_count": len(integrator.probes[task.name]),
        "probe_signature_sha256": hashlib.sha256(sig_bad.encode("utf-8")).hexdigest(),
        "public_count": len(task.examples),
        "independent_oracle_count": len(task.hidden),
    }


def run_arm(task: Task, bad, good, mode: str):
    """Fixed candidate stream with equal candidate and CPU ceilings."""
    started = time.process_time()
    verifier = FrozenVerifier([task], step_budget=STEP_BUDGET)
    memory = EpisodicMemory(verifier)
    integrator = BindingIntegrator(
        [public_view(task)],
        step_budget=STEP_BUDGET,
        skip_mode="signature" if mode == "none" else mode,
    )
    logical_evaluations = 0
    false_suppressions = 0
    accepted_correct = 0
    receipt_verdicts = []
    for generation, term in enumerate((bad, good), 1):
        # The public evaluation is charged before a candidate can be suppressed.
        logical_evaluations += 1
        if not matches(term, task.examples):
            raise AssertionError("candidate stream no longer matches public examples")
        skip = None if mode == "none" else integrator.skip_callback(task.name, {}, memory)
        if skip is not None and skip(term):
            false_suppressions += int(term == good)
            continue
        receipt = verifier.verify(task.name, term, {}, generation=generation)
        if not verifier.is_authentic(receipt):
            raise AssertionError("verifier returned a non-authentic receipt")
        receipt_verdicts.append(receipt.verdict)
        if receipt.verdict:
            accepted_correct += int(term == good)
        else:
            integrator.bind_rejected(task.name, term, {}, receipt, memory)
    elapsed = time.process_time() - started
    if elapsed > CPU_CAP_SECONDS:
        raise AssertionError("CPU ceiling exceeded")
    if logical_evaluations != 2 or verifier.queries > 2:
        raise AssertionError("logical or verifier budget violated")
    return {
        "mode": mode,
        "logical_evaluations": logical_evaluations,
        "verifier_queries": verifier.queries,
        "false_suppressions": false_suppressions,
        "accepted_correct": accepted_correct,
        "negative_receipts": sum(not x for x in receipt_verdicts),
        "positive_receipts": sum(x for x in receipt_verdicts),
        "probe_interpreter_calls": integrator.probe_evaluations,
        "cpu_seconds": round(elapsed, 6),
        "cpu_ceiling_seconds": CPU_CAP_SECONDS,
    }


def study():
    rows = []
    for trigger in TRIGGERS:
        for seed in SEEDS:
            task, bad, good, witness_data = witness(seed, trigger)
            arms = {mode: run_arm(task, bad, good, mode) for mode in MODES}
            if not (
                arms["signature"]["false_suppressions"] == 1
                and arms["signature"]["accepted_correct"] == 0
                and arms["signature"]["verifier_queries"] == 1
                and all(
                    arms[mode]["false_suppressions"] == 0
                    and arms[mode]["accepted_correct"] == 1
                    and arms[mode]["verifier_queries"] == 2
                    for mode in ("exact", "none")
                )
            ):
                raise AssertionError("registered control prediction failed")
            rows.append(dict(witness_data, arms=arms))
    return {
        "status": "synthetic_development_only",
        "pre_registration_commit": PREREGISTRATION_COMMIT,
        "triggers": list(TRIGGERS),
        "seeds": list(SEEDS),
        "modes": list(MODES),
        "step_budget": STEP_BUDGET,
        "max_ast_size": MAX_AST_SIZE,
        "cpu_cap_seconds_per_arm_task": CPU_CAP_SECONDS,
        "case_count": len(rows),
        "summary": {
            mode: {
                "false_suppressions": sum(r["arms"][mode]["false_suppressions"] for r in rows),
                "accepted_correct": sum(r["arms"][mode]["accepted_correct"] for r in rows),
                "verifier_queries": sum(r["arms"][mode]["verifier_queries"] for r in rows),
                "logical_evaluations": sum(r["arms"][mode]["logical_evaluations"] for r in rows),
                "probe_interpreter_calls": sum(r["arms"][mode]["probe_interpreter_calls"] for r in rows),
                "cpu_seconds": round(sum(r["arms"][mode]["cpu_seconds"] for r in rows), 6),
            }
            for mode in MODES
        },
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = study()
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))


if __name__ == "__main__":
    main()
