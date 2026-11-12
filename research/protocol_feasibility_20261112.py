"""Pure arithmetic feasibility check; no benchmark or learner is imported."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

SOURCE_PINS = {
    "main": "c4f0a8627a1c9f37dd3aa6291b0eee0c78648210",
    "reviewed_pr58_head": "355fc090d390c29933e481777d8d2a2353cf5ff4",
    "protocol_blob": "7949aa76dd0b8c821c0389bb8d14301508273c65",
    "work_order_blob": "4fc6770e136278eb7f5cb652bbc7ed49556c258c",
    "owner_directive_blob": "1f478f2db1c52d57bd7d47db390ade6bef0ec9c5",
    "constitution_blob": "1257eb27993d0489311354690132d1e6e62bf674",
}


def rounds_for(n, sources=2, adoption_per_round=2, targets=3, reserves=1):
    if min(n, sources, adoption_per_round, targets, reserves) < 0 or adoption_per_round == 0:
        raise ValueError("counts must be nonnegative and adoption_per_round positive")
    return max(0, (n - sources - targets - reserves) // adoption_per_round)


def assess():
    start = time.process_time()
    n, required_rounds = 7, 2
    sources, adoption_per_round, targets, reserves = 2, 2, 3, 1
    minimum = sources + targets + reserves + required_rounds * adoption_per_round
    rows = [{"categories": i, "rounds": rounds_for(i)} for i in range(7, 13)]
    predictions = {
        "P1_seven_categories_zero_rounds": rounds_for(7) == 0,
        "P2_eight_nine_one_ten_two": [rounds_for(i) for i in (8, 9, 10)] == [1, 1, 2],
        "P3_minimum_ten_deficit_three": minimum == 10 and minimum - n == 3,
        "P4_seed_ceiling_shortfall_thirty": 40 - 10 == 30,
        "P5_inference_not_applicable": True,
    }
    cpu = time.process_time() - start
    if cpu > 2.0:
        raise RuntimeError("preregistered 2-second CPU cap exceeded")
    return {
        "study": "static_protocol_feasibility_20261112",
        "classification": "non_audit_non_performance_static_review",
        "source_pins": SOURCE_PINS,
        "inputs": {"named_candidate_categories": n, "source_categories": sources,
                   "adoption_categories_per_round": adoption_per_round,
                   "target_categories": targets, "minimum_reserve_categories": reserves,
                   "required_rounds": required_rounds,
                   "draft_pilot_seed_ceiling": 10, "requested_paired_seed_trajectories": 40},
        "rows": rows,
        "minimum_categories_for_two_rounds": minimum,
        "additional_categories_required": minimum - n,
        "pilot_seed_ceiling_shortfall": 30,
        "predictions": predictions,
        "preregistered_checks_passed": all(predictions.values()),
        "inference": "not_applicable_exact_arithmetic_not_a_statistical_test",
        "candidate_evaluations": 0,
        "interpreter_calls": 0,
        "audit_tasks_read": 0,
        "measured_process_cpu_seconds": cpu,
        "cpu_cap_seconds": 2.0,
        "rsi_success_claim": False,
        "work_order_approved": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = assess()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["preregistered_checks_passed"],
                      "minimum_categories": report["minimum_categories_for_two_rounds"],
                      "shortfall": report["additional_categories_required"]}, sort_keys=True))


if __name__ == "__main__":
    main()
