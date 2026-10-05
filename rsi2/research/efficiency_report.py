"""Compare completed policy prefixes under an independently verified reuse procedure.

Reporting-only audit outcomes are outside this comparison. Logical source
records remain exact; only named timing, cache and actual-work telemetry differ.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORK_METRICS = ("evaluation_steps", "heuristic_calls", "heuristic_evaluations",
                "heuristic_steps", "verification_examples", "verification_steps")
IGNORED_FIELDS = frozenset({
    "wall_seconds", "cpu_seconds", "actual_wall_seconds", "source_wall_seconds",
    "cache_hit", "source_budget", "requested_budget", "reuse_kind",
    "actual_candidate_evaluations", *(f"actual_{key}" for key in WORK_METRICS),
})
MEMORY_FIELDS = frozenset({"entries", "certificates", "cache_hits", "assessment_calls",
                           "task_cache_hits", "exact_hits", "certificate_hits",
                           "task_assessment_calls", "actual_candidate_evaluations",
                           *(f"actual_{key}" for key in WORK_METRICS)})
REQUIRED_CYCLE = frozenset({
    "seed", "arm", "cycle", "incumbent", "selected_indices", "confirmed_indices",
    "adopted_index", "incumbent_validation", "validation", "incumbent_confirmation",
    "confirmation", "failure_clusters", "proposal_productivity", "draw", "selection",
    "model", "candidates", "probe_program_evaluations", "probe_example_evaluations",
    "probe_evaluator_steps", "online_report", "decision", "memory", "cpu_seconds",
})
CYCLE_FIELDS = ("current_performance", "failure_clusters", "bottleneck",
                "previous_attempt_insufficiency", "intervention", "mechanism",
                "verification_plan", "regression_risks", "result",
                "keep_revert_revise", "updated_rule")


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return value


def _hash(value):
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def logical_record(value, path=()):
    """Remove an explicit allowlist; logical counts and unknown fields remain."""
    if isinstance(value, list):
        return [logical_record(item, path + (str(index),)) for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value
    output = {}
    for key, item in value.items():
        if key in IGNORED_FIELDS or (path and path[-1] == "memory" and key in MEMORY_FIELDS):
            continue
        # Added only by the separate, post-freeze reporting capability.
        if key == "audit_productivity" and path and path[-1] == "cycle":
            continue
        output[key] = logical_record(item, path + (key,))
    return output


def differences(baseline, effective, path="$", limit=30):
    """Return exact differing paths, including types, list order and missing keys."""
    found = []

    def visit(left, right, current):
        if len(found) >= limit:
            return
        if type(left) is not type(right):
            found.append({"path": current, "baseline": left, "effective": right, "reason": "type differs"})
        elif isinstance(left, dict):
            if current.endswith((".grammar.primitives", ".grammar.library")) and list(left) != list(right):
                found.append({"path": current, "baseline": list(left), "effective": list(right), "reason": "executable insertion order differs"})
            for key in sorted(left.keys() | right.keys()):
                if key not in left or key not in right:
                    found.append({"path": f"{current}.{key}", "reason": "field missing",
                                  "baseline_present": key in left, "effective_present": key in right})
                else:
                    visit(left[key], right[key], f"{current}.{key}")
                if len(found) >= limit:
                    break
        elif isinstance(left, list):
            if len(left) != len(right):
                found.append({"path": current, "baseline": len(left), "effective": len(right), "reason": "list length differs"})
            for index, (a, b) in enumerate(zip(left, right)):
                visit(a, b, f"{current}[{index}]")
        elif left != right:
            found.append({"path": current, "baseline": left, "effective": right, "reason": "value differs"})

    visit(baseline, effective, path)
    return found


def _cycles(seed, arm, record, config):
    rows = record.get("arms", {}).get(arm, {}).get("cycles", [])
    indexed = {}
    for row in rows:
        number = row.get("cycle")
        if (row.get("seed") != seed or row.get("arm") != arm or type(number) is not int
                or not 1 <= number <= config["cycles"] or number in indexed):
            raise ValueError("cycle identities must be unique and match their seed/arm")
        indexed[number] = row
    if list(indexed) != list(range(1, len(indexed) + 1)):
        raise ValueError("completed cycles must form an ordered prefix beginning at one")
    return indexed


def _actual_delta(rows, number):
    total = rows[number].get("memory", {}).get("actual_candidate_evaluations")
    previous = rows[number - 1].get("memory", {}).get("actual_candidate_evaluations") if number > 1 else 0
    if total is None or previous is None:
        return None
    _count(total, "cumulative actual inner candidates")
    _count(previous, "previous cumulative actual inner candidates")
    if total < previous:
        raise ValueError("cumulative actual inner candidates decreased")
    return total - previous


def _assessments(row):
    """Enumerate actual calls; selected-result aliases are not new operations."""
    assessments = [row.get("incumbent_validation"), row.get("incumbent_confirmation")]
    assessments.extend(candidate.get(key) for candidate in row.get("candidates", [])
                       for key in ("screen", "full", "confirmation") if candidate.get(key) is not None)
    return assessments


def _operation_candidates(row):
    total = 0
    for assessment in _assessments(row):
        if not isinstance(assessment, dict) or "actual_candidate_evaluations" not in assessment:
            return None
        actual = _count(assessment["actual_candidate_evaluations"], "actual assessment candidates")
        expected = 0
        for record in assessment.get("records", []):
            hit = record.get("cache_hit", assessment.get("cache_hit"))
            if type(hit) is not bool:
                return None
            count = _count(record["candidates"], "logical task candidates")
            charged = 0 if hit else count
            if "actual_candidate_evaluations" in record and record["actual_candidate_evaluations"] != charged:
                raise ValueError("actual task candidates disagree with source counts and cache evidence")
            expected += charged
        if actual != expected:
            raise ValueError("actual assessment candidates disagree with per-task cache evidence")
        total += actual
    return total


def _operation_work(row):
    """Count source assessments once; selected-result aliases are not new calls."""
    assessments = _assessments(row)
    totals = {}
    for metric in WORK_METRICS:
        total, known = 0, True
        for assessment in assessments:
            if not isinstance(assessment, dict):
                known = False
                break
            actual = f"actual_{metric}"
            if actual in assessment:
                total += _count(assessment[actual], actual)
                continue
            for record in assessment.get("records", []):
                if actual in record:
                    total += _count(record[actual], actual)
                elif record.get("cache_hit", assessment.get("cache_hit")) is True:
                    continue
                elif record.get("cache_hit", assessment.get("cache_hit")) is False and metric in record:
                    total += _count(record[metric], metric)
                else:
                    known = False
        totals[metric] = total if known else None
    return totals


def _verification(evidence):
    checks = {}
    for name in ("exact_reuse", "exhaustion_certificate"):
        proof = (evidence or {}).get(name, {})
        tests, count = proof.get("tests"), proof.get("count")
        supplied = (isinstance(tests, list) and bool(tests)
                    and all(isinstance(test, str) and bool(test.strip()) for test in tests)
                    and type(count) is int and count >= len(tests))
        status = proof.get("status") if supplied else "unknown"
        checks[name] = {"status": status if status in ("passed", "failed") else "unknown",
                        "tests": tests if supplied else [], "count": count if supplied else None}
    return checks


def compare_runs(baseline, effective, config, *, verification=None, baseline_source_commit=None):
    """Assess all completed baseline rows without crediting unmatched later work."""
    checks = _verification(verification)
    source = baseline_source_commit or (verification or {}).get("baseline_source_commit")
    failures, unknown, pairs, coverage = [], [], [], []
    reference_complete = intervention_complete = True
    for seed in config["seeds"]:
        base = baseline.get(seed, {"seed": seed, "status": "missing"})
        changed = effective.get(seed, {"seed": seed, "status": "missing"})
        reference_complete &= base.get("status") in ("complete", "selection_frozen")
        intervention_complete &= changed.get("status") in ("complete", "selection_frozen")
        if base.get("seed") != seed or changed.get("seed") != seed:
            raise ValueError("seed identity disagrees with its selected file")
        for label, run in (("baseline", base), ("effective", changed)):
            if run.get("config") is None:
                unknown.append(f"seed {seed}: {label} configuration missing")
            elif json.dumps(run["config"], sort_keys=True) != json.dumps(config, sort_keys=True):
                raise ValueError(f"seed {seed}: {label} configuration differs from the scientific protocol")
        declared = base.get("source_commit", source)
        if not _hash(declared) or not _hash(changed.get("source_commit")):
            unknown.append(f"seed {seed}: baseline/effective source attestation missing")
        elif declared != changed["source_commit"]:
            failures.append({"path": f"seed{seed}.source_commit", "baseline": declared,
                             "effective": changed["source_commit"], "reason": "frozen scientific source differs"})
        for field in ("initial_learning", "initial_state", "baseline_training"):
            if field not in base or field not in changed:
                unknown.append(f"seed {seed}: {field} unavailable")
            else:
                failures.extend(differences(logical_record(base[field], (field,)),
                                            logical_record(changed[field], (field,)), f"seed{seed}.{field}"))
        for arm in config["arms"]:
            before, after = _cycles(seed, arm, base, config), _cycles(seed, arm, changed, config)
            matched = sorted(before.keys() & after.keys())
            missing = sorted(before.keys() - after.keys())
            extra = sorted(after.keys() - before.keys())
            unseen = sorted(set(range(1, config["cycles"] + 1)) - before.keys())
            coverage.append({"seed": seed, "arm": arm, "matched_cycles": matched,
                             "baseline_completed_missing_from_effective": missing,
                             "effective_cycles_without_baseline": extra,
                             "baseline_unrun_cycles": unseen})
            reference_complete &= len(before) == config["cycles"]
            intervention_complete &= len(after) == config["cycles"]
            if missing:
                unknown.append(f"seed {seed} {arm}: completed baseline cycles lack an effective pair: {missing}")
            for number in matched:
                a, b = before[number], after[number]
                absent = (REQUIRED_CYCLE - a.keys()) | (REQUIRED_CYCLE - b.keys())
                if absent:
                    unknown.append(f"seed {seed} {arm} cycle {number}: missing core fields {sorted(absent)}")
                differences_ = differences(logical_record(a, ("cycle",)), logical_record(b, ("cycle",)),
                                           f"seed{seed}.{arm}.cycle{number}")
                failures.extend(differences_)
                actual_a, actual_b = _actual_delta(before, number), _actual_delta(after, number)
                charged_a, charged_b = _operation_candidates(a), _operation_candidates(b)
                for label, delta, calls in (("baseline", actual_a, charged_a), ("effective", actual_b, charged_b)):
                    if delta is not None and calls is not None and delta != calls:
                        raise ValueError(f"seed {seed} {arm} cycle {number}: {label} cumulative memory delta disagrees with actual assessment calls")
                    if calls is None:
                        unknown.append(f"seed {seed} {arm} cycle {number}: {label} assessment accounting unavailable")
                cpu_a, cpu_b = a.get("cpu_seconds"), b.get("cpu_seconds")
                if actual_a is None or actual_b is None or cpu_a is None or cpu_b is None:
                    unknown.append(f"seed {seed} {arm} cycle {number}: actual-work or CPU accounting incomplete")
                if cpu_a is not None:
                    _number(cpu_a, "baseline cycle CPU")
                if cpu_b is not None:
                    _number(cpu_b, "effective cycle CPU")
                secondary_a, secondary_b = _operation_work(a), _operation_work(b)
                pairs.append({"seed": seed, "arm": arm, "cycle": number,
                              "logical_equal": not differences_ and not absent,
                              "baseline_actual_inner_candidates": actual_a,
                              "effective_actual_inner_candidates": actual_b,
                              "saved_actual_inner_candidates": None if actual_a is None or actual_b is None else actual_a - actual_b,
                              "baseline_cpu_seconds": cpu_a, "effective_cpu_seconds": cpu_b,
                              "saved_cpu_seconds": None if cpu_a is None or cpu_b is None else cpu_a - cpu_b,
                              "secondary_baseline_work": secondary_a, "secondary_effective_work": secondary_b,
                              "secondary_saved_work": {key: None if secondary_a[key] is None or secondary_b[key] is None
                                                       else secondary_a[key] - secondary_b[key] for key in WORK_METRICS}})
            # A terminal state is comparable only at the same cycle boundary.
            if before and list(before) == list(after):
                target_a, target_b = base["arms"][arm], changed["arms"][arm]
                for field in ("final_state", "proposal_memory"):
                    if field not in target_a or field not in target_b:
                        unknown.append(f"seed {seed} {arm}: {field} unavailable at matching boundary")
                    else:
                        failures.extend(differences(logical_record(target_a[field], (field,)),
                                                    logical_record(target_b[field], (field,)),
                                                    f"seed{seed}.{arm}.{field}"))
    candidate_known = bool(pairs) and all(pair["saved_actual_inner_candidates"] is not None for pair in pairs)
    saved = sum(pair["saved_actual_inner_candidates"] for pair in pairs) if candidate_known else None
    cpu_known = bool(pairs) and all(pair["saved_cpu_seconds"] is not None for pair in pairs)
    cpu_saved = sum(pair["saved_cpu_seconds"] for pair in pairs) if cpu_known else None
    proof_passed = all(check["status"] == "passed" for check in checks.values())
    proof_failed = any(check["status"] == "failed" for check in checks.values())
    if not pairs:
        unknown.append("No completed cycle pairs are available")
    logical_status = "DIFFERENT" if failures else "UNKNOWN" if unknown else "EQUAL_OBSERVED_PREFIX"
    decision = ("REVERT" if failures or proof_failed else "UNKNOWN" if unknown or not proof_passed
                else "KEEP" if saved is not None and saved > 0 else "REVISE")
    full_status = ("DIFFERENT" if failures else "EQUAL" if reference_complete and intervention_complete and not unknown
                   else "UNKNOWN")
    return {"schema_version": 1, "scope": "observed_matched_prefix", "logical_status": logical_status,
            "full_study_equivalence": full_status, "decision": decision, "verification": checks,
            "baseline_source_commit": source, "matched_cycles": pairs, "coverage": coverage,
            "differences": failures, "unknown_reasons": unknown,
            "totals": {"matched_cycles": len(pairs), "saved_actual_inner_candidates": saved,
                       "baseline_actual_inner_candidates": sum(p["baseline_actual_inner_candidates"] for p in pairs) if candidate_known else None,
                       "effective_actual_inner_candidates": sum(p["effective_actual_inner_candidates"] for p in pairs) if candidate_known else None,
                       "saved_cpu_seconds": cpu_saved,
                       "baseline_cpu_seconds": sum(p["baseline_cpu_seconds"] for p in pairs) if cpu_known else None,
                       "effective_cpu_seconds": sum(p["effective_cpu_seconds"] for p in pairs) if cpu_known else None}}


def efficiency_rule(comparison):
    return {"id": "exact_evaluation_reuse", "type": "loop", "scope": "observed_matched_prefix",
            "pattern": "Completed task evidence is recomputed across overlapping exact scopes or a certified larger budget",
            "diagnosis": "Actual inner evaluation work can repeat while the scientific policy is unchanged",
            "intervention": "Share exact per-task evidence and sound early-termination certificates without changing proposals or search",
            "evidence": {"matched_cycles": comparison["totals"]["matched_cycles"],
                         "logical_status": comparison["logical_status"], "totals": comparison["totals"],
                         "verification": comparison["verification"], "coverage": comparison["coverage"]},
            "decision": comparison["decision"],
            "next_test": "Complete missing paired checks before accepting reuse" if comparison["decision"] == "UNKNOWN" else
                         "Test a newly preregistered workload for further evaluation savings; do not claim solver or RSI gains",
            "claim_limit": "Efficiency for the observed matched prefix only; full-study equivalence is " + comparison["full_study_equivalence"]}


def intervention_record(comparison):
    totals = comparison["totals"]
    return {
        "current_performance": totals,
        "failure_clusters": {"logical_differences": comparison["differences"], "unknown_checks": comparison["unknown_reasons"]},
        "bottleneck": "Redundant exact task assessments and certified early-terminated searches, rather than a changed candidate objective",
        "previous_attempt_insufficiency": "Whole-assessment caching cannot reuse overlapping task subsets or share identical task evidence across arms",
        "intervention": "Per-task exact reuse and guarded cross-budget early-termination certificates",
        "mechanism": "Reuse only completed scope-equivalent evidence; preserve source logical counts and separately charge actual work",
        "verification_plan": "Compare every completed baseline cycle recursively, including ASTs, probes, selections, fitted models, online decisions and source task/search counters; require external exact-reuse and exhaustion tests",
        "regression_risks": "Unsound budget extrapolation, changed primitive/grammar insertion order, stale recognizer or example scope, hidden-verifier failures mistaken for search exhaustion, and attributing unmatched cycles as savings",
        "result": {"logical_status": comparison["logical_status"], "full_study_equivalence": comparison["full_study_equivalence"], "totals": totals},
        "keep_revert_revise": comparison["decision"],
        "updated_rule": efficiency_rule(comparison),
    }


def _table(lines, headers, rows):
    lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    lines.append("")


def _display(value):
    return "unknown" if value is None else f"{value:.4f}" if type(value) is float else str(value)


def render_report(comparison):
    totals = comparison["totals"]
    lines = ["# Evaluation-reuse follow-up", "",
             f"Observed matched-prefix decision: **{comparison['decision']}**; logical comparison: "
             f"**{comparison['logical_status']}**. Full-study equivalence: **{comparison['full_study_equivalence']}**.", "",
             f"The comparison covers {totals['matched_cycles']} completed paired cycles. It measures "
             "saved actual inner task-search candidates and cycle CPU, preserving the original candidate "
             "policy and all logical outcomes. It does not establish better solver capability, a better "
             "proposal ranker, or recursive self-improvement. Reporting-only audit outcomes are excluded.", "",
             "## Matched-cycle costs", ""]
    _table(lines, ["Seed", "Arm", "Cycle", "Logical equal", "Baseline actual inner candidates",
                   "Reuse actual inner candidates", "Saved actual inner candidates", "Baseline CPU s", "Reuse CPU s", "Saved CPU s"],
           [(p["seed"], p["arm"], p["cycle"], p["logical_equal"],
             *(_display(p[key]) for key in ("baseline_actual_inner_candidates", "effective_actual_inner_candidates",
                                          "saved_actual_inner_candidates", "baseline_cpu_seconds", "effective_cpu_seconds", "saved_cpu_seconds")))
            for p in comparison["matched_cycles"]])
    lines.extend([f"Matched actual inner candidates: baseline {_display(totals['baseline_actual_inner_candidates'])}, "
                  f"reuse {_display(totals['effective_actual_inner_candidates'])}, saved {_display(totals['saved_actual_inner_candidates'])}. "
                  f"Matched cycle CPU saved: {_display(totals['saved_cpu_seconds'])} s. "
                  "Actual inner candidates are differences of each arm's cumulative memory counter between "
                  "successive matched cycles. Initial TRAIN/wake/dream overhead and later unmatched cycles "
                  "are excluded from these savings. Negative savings remain visible.", "",
                  "## Secondary actual workload", ""])
    _table(lines, ["Seed", "Arm", "Cycle", *WORK_METRICS],
           [(p["seed"], p["arm"], p["cycle"], *(_display(p["secondary_saved_work"][key]) for key in WORK_METRICS))
            for p in comparison["matched_cycles"]])
    lines.extend(["These columns are saved actual source assessment operations, not changed logical "
                  "search outcomes. Selected-result aliases are counted once. They expose interpreter "
                  "and heuristic work even when a capped search attempts zero complete task candidates. "
                  "Unknown source telemetry remains unknown rather than zero.", "",
                  "## Coverage", ""])
    _table(lines, ["Seed", "Arm", "Matched cycles", "Completed baseline rows without pair", "Reuse-only cycles", "Baseline unrun cycles"],
           [(c["seed"], c["arm"], c["matched_cycles"], c["baseline_completed_missing_from_effective"],
             c["effective_cycles_without_baseline"], c["baseline_unrun_cycles"]) for c in comparison["coverage"]])
    lines.extend(["A retained efficiency rule applies only to the observed matched prefix. No logical "
                  "equivalence or savings are inferred for unrun or unmatched cycles. An intervention "
                  "missing a completed baseline row leaves the narrow policy decision UNKNOWN. "
                  "A partial baseline can support a limited observed-prefix efficiency decision while "
                  "full-study equivalence remains UNKNOWN.", "",
                  "## Independent verifier evidence", ""])
    _table(lines, ["Verifier", "Status", "Count", "Test identifiers or paths"],
           [(name, check["status"], _display(check["count"]), ", ".join(check["tests"]))
            for name, check in comparison["verification"].items()])
    lines.extend(["A narrative assertion of safety is insufficient: exact-reuse and exhaustion-certificate "
                  "checks require supplied passing status, nonempty test identifiers/paths and measured counts. "
                  "The comparator ignores only the named timing/cache/actual-work telemetry allowlist. "
                  "Candidate/evaluation/heuristic/verifier logical counts, failure evidence, ASTs, order, "
                  "coefficients, policy state and online decisions remain exact.", "",
                  "## Eleven intervention fields", ""])
    record = intervention_record(comparison)
    for field in CYCLE_FIELDS:
        value = record[field]
        lines.extend([f"**{field.replace('_', ' ')}:** " + (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)), ""])
    if comparison["differences"]:
        lines.extend(["## Differing logical paths", ""])
        for difference in comparison["differences"]:
            lines.append("- " + json.dumps(difference, ensure_ascii=False, sort_keys=True))
        lines.append("")
    if comparison["unknown_reasons"]:
        lines.extend(["## Incomplete checks", ""])
        lines.extend("- " + reason for reason in comparison["unknown_reasons"])
        lines.append("")
    return "\n".join(lines)


def load_seed_files(path, seeds):
    """Load development fields only; never inspect final task/proposal audit results."""
    runs = {}
    for seed in seeds:
        file = Path(path) / f"seed{seed}.json"
        if not file.exists():
            continue
        source = json.loads(file.read_text())
        record = {key: source[key] for key in ("seed", "status", "config", "source_commit",
                                               "initial_learning", "initial_state", "baseline_training") if key in source}
        record["arms"] = {}
        for arm, target in source.get("arms", {}).items():
            selected = {key: target[key] for key in ("final_state", "proposal_memory") if key in target}
            selected["cycles"] = [{key: value for key, value in row.items() if key != "audit_productivity"}
                                  for row in target.get("cycles", [])]
            record["arms"][arm] = selected
        runs[seed] = record
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--baseline-source-commit")
    args = parser.parse_args()
    try:
        config = json.loads((HERE / "config.json").read_text())
        evidence = json.loads(args.verification.read_text()) if args.verification else None
        baseline = load_seed_files(args.baseline, config["seeds"])
        effective = load_seed_files(args.results, config["seeds"])
        comparison = compare_runs(baseline, effective, config, verification=evidence,
                                  baseline_source_commit=args.baseline_source_commit)
    except (ValueError, TypeError, KeyError) as exc:
        parser.error(f"invalid comparison artifacts: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(comparison), encoding="utf-8")
    if args.rules:
        args.rules.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "comparison": comparison, "rules": [efficiency_rule(comparison)]}
        args.rules.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    if comparison["differences"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
