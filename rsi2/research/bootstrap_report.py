"""Report explicitly supplied TRAIN bootstrap artifacts without loading tasks.

The ``bootstrap_results/frozen`` namespace is the registered evidence boundary.
Older root/instrumented files remain pilots; pre-fix observational pilots are
invalid. Missing instrumentation is unknown, including a missing numeric zero.
This reporter performs no search, verification, compression or model fitting.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path


FIELDS = ("current_performance", "failure_clusters", "bottleneck",
          "previous_attempt_insufficiency", "intervention", "mechanism",
          "verification_plan", "regression_risks", "result",
          "keep_revert_revise", "updated_rule")
LIMITS = {"candidate_budgets": [64, 640], "max_size": 12,
          "max_expansions": 20000, "step_budget": 2000,
          "max_cpu_seconds_per_task": 10, "total_cpu_seconds": 1800}
ROOT_METHODS = {"enumeration", "sampling", "adaptive", "repair",
                "repair_normalized", "stratified"}
ALIASES = {
    "logical_program_attempts": ("logical_evaluations", "candidates"),
    "complete_program_attempts": ("complete_candidates", "root_attempts"),
    "auxiliary_program_attempts": ("auxiliary_candidates", "helper_attempts"),
    "search_interpreter_calls": ("evaluator_calls", "example_evaluations"),
    "search_interpreter_steps": ("evaluation_steps", "evaluator_steps"),
    "expansions": ("expansions",), "search_cpu_seconds": ("cpu_seconds",),
    "search_wall_seconds": ("wall_seconds",),
    **{name: (name,) for name in (
        "draws", "duplicate_draws", "failed_draws", "updates", "seed_candidates",
        "repair_candidates", "generated_full_candidates", "duplicate_candidates",
        "invalid_repairs", "filtered_wrappers", "incompatible_accepted_seeds",
        "emitted_enumerator_terms", "cached_replacement_terms", "normalization_steps",
        "beta_reductions", "constructed_terms", "semantic_pruned", "runtime_failures",
        "retained_components", "head_attempts", "component_attempts", "root_attempts",
        "baseline_attempts", "stratum_attempts", "generated_wrappers",
        "rejected_compositions", "heuristic_calls", "heuristic_evaluations",
        "heuristic_steps")},
}
MECHANISMS = {
    "enumeration": "Frozen typed probability-order queue, with a fresh frontier per task",
    "sampling": "Current-prior typed stochastic draws",
    "adaptive": "Alternating prior and public near-miss count-fitted sampling",
    "repair": "Grammar-generated seeds and typed single-subtree replacement",
    "repair_normalized": "Typed subtree replacement with charged beta normalization",
    "observational": "Size-based typed composition and scope-specific public observational equivalence",
    "decomposition": "Public pointwise relation, enumerated head and scalar component, verified full root",
    "stratified_decomposition": "Public pointwise relation with charged head, stratified scalar search and full-root verification",
    "stratified": "Charged prefix followed by round-robin input-binder argument roles",
}
EXPANSION_MEANINGS = {
    "enumeration": "frontier pops", "sampling": "typed production requests during draws",
    "adaptive": "typed production requests during draws", "repair": "all enumerator frontier pops",
    "repair_normalized": "all enumerator frontier pops; normalization visits counted separately",
    "observational": "bottom-up construction ticks", "decomposition": "combined head/component frontier pops",
    "stratified_decomposition": "head frontier pops plus scalar prefix/argument pops and structural queries",
    "stratified": "prefix/argument frontier pops plus structural production queries",
}


def _read(path):
    path = Path(path)
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("only explicit JSON or JSON.gzip artifacts are supported")


def _number(value):
    return ((type(value) is int and value >= 0) or
            (type(value) is float and math.isfinite(value) and value >= 0))


def _size(term):
    return 1 + sum(_size(child) for child in term.get("children", ()))


def _contains(term, tag):
    return term.get("tag") == tag or any(_contains(c, tag) for c in term.get("children", ()))


def _identity(term):
    children = term.get("children", ())
    return (term.get("tag") == "lam" and len(children) == 1 and
            children[0].get("tag") == "var" and children[0].get("value") == 0)


def _metric(search, names, alerts):
    supplied = [(name, search[name]) for name in names if name in search]
    time_metric = all(name.endswith("seconds") for name in names)
    if any(not _number(value) or (not time_metric and type(value) is not int)
           for _, value in supplied):
        alerts.append(f"invalid numeric field among {list(names)}")
        return None, [name for name, _ in supplied]
    if supplied and any(value != supplied[0][1] for _, value in supplied):
        alerts.append(f"conflicting aliases {list(names)}")
        return None, [name for name, _ in supplied]
    return (supplied[0][1] if supplied else None), [name for name, _ in supplied]


def _task(row, index, method, budget):
    search, alerts = row.get("search", {}), []
    counters, sources = {}, {}
    for field, aliases in ALIASES.items():
        counters[field], sources[field] = _metric(search, aliases, alerts)
    complete, auxiliary = counters["complete_program_attempts"], counters["auxiliary_program_attempts"]
    if complete is not None and auxiliary is not None:
        combined = complete + auxiliary
        if counters["logical_program_attempts"] is None:
            counters["logical_program_attempts"] = combined
            sources["logical_program_attempts"] = ["complete + auxiliary (derived)"]
        elif counters["logical_program_attempts"] != combined:
            alerts.append("logical count differs from complete + auxiliary")
    if method in ROOT_METHODS and complete is None and counters["logical_program_attempts"] is not None:
        counters["complete_program_attempts"] = counters["logical_program_attempts"]
        sources["complete_program_attempts"] = ["candidates (documented root-only contract)"]
    for field, name in (("verification_interpreter_calls", "verification_calls"),
                        ("verification_interpreter_steps", "verification_steps")):
        counters[field], sources[field] = _metric(row, (name,), alerts)
    for target, left, right in (
        ("total_interpreter_calls", "search_interpreter_calls", "verification_interpreter_calls"),
        ("total_interpreter_steps", "search_interpreter_steps", "verification_interpreter_steps")):
        counters[target] = (counters[left] + counters[right]
                            if counters[left] is not None and counters[right] is not None else None)
        sources[target] = [f"{left} + {right} (derived)"] if counters[target] is not None else []
    logical = counters["logical_program_attempts"]
    if logical is not None and logical > budget:
        alerts.append("logical candidate cap exceeded")
    if counters["expansions"] is not None and counters["expansions"] > LIMITS["max_expansions"]:
        alerts.append("expansion cap exceeded")
    term = search.get("term")
    public_match = term is not None if "term" in search else None
    verified = row.get("verified") if type(row.get("verified")) is bool else None
    if verified is None:
        alerts.append("missing or invalid verifier verdict")
    if public_match is None:
        alerts.append("missing selected-term telemetry")
    if verified and public_match is not True:
        alerts.append("verified row lacks selected public term")
    if term is not None and _size(term) > LIMITS["max_size"]:
        alerts.append("selected AST size cap exceeded")
    reason = search.get("termination", search.get("stop_reason"))
    reason_source = "explicit" if reason is not None else "derived"
    if reason is None:
        if public_match:
            reason = "selected_public_match"
        elif search.get("exhausted") is True:
            reason = "bounded_stream_end_unknown_heap_or_expansion_cap"
        elif logical is not None and logical >= budget:
            reason = "candidate_budget"
        else:
            reason, reason_source = "unknown", "missing"
    cpu = counters["search_cpu_seconds"]
    trials = search.get("trials", [])
    trial_evidence = Counter()
    for trial in trials:
        failure = trial.get("failure", trial.get("runtime_failure"))
        if failure is not None:
            trial_evidence[str(failure)] += 1
        if trial.get("valid") is False:
            trial_evidence["sampled_program_runtime_invalid"] += 1
        if trial.get("incomplete") is True or trial.get("complete") is False:
            trial_evidence["incomplete_trial"] += 1
    seeds = search.get("seed_records", [])
    return {"name": row.get("name"), "raw_task_index": index, "verified": verified,
            "public_match": public_match, "verification_failure": row.get("verification_failure"),
            "termination": reason, "termination_source": reason_source,
            "counters": counters, "counter_sources": sources, "alerts": alerts,
            "reported_cpu_above_nominal_cap": cpu > 10 if cpu is not None else None,
            "trial_failure_evidence": dict(trial_evidence), "trials_recorded": len(trials),
            "seed_size_evidence": dict(Counter(_size(s["term"]) for s in seeds if "term" in s)),
            "expansion_components": search.get("expansion_counts"),
            "decomposition": search.get("decomposition"),
            "language_complete": search.get("language_complete"),
            "extra_search_scalars": {k: v for k, v in search.items()
                                     if type(v) in (int, float, str, bool) or v is None}}


def _totals(tasks):
    fields = set().union(*(t["counters"] for t in tasks)) if tasks else set(ALIASES)
    result = {}
    for field in sorted(fields):
        values = [t["counters"].get(field) for t in tasks]
        known = [value for value in values if value is not None]
        result[field] = {"value": sum(known) if values and len(known) == len(values) else None,
                         "known_subtotal": sum(known) if known else None,
                         "known_rows": len(known), "missing_rows": len(values) - len(known)}
    return result


def _cycle(path, raw):
    path = Path(path)
    if "bootstrap_results" not in path.parts or raw.get("source") != "TRAIN only":
        raise ValueError("bootstrap inputs must be TRAIN-only bootstrap_results artifacts")
    method, budget, seed = raw.get("method"), raw.get("budget"), raw.get("seed")
    if (method not in MECHANISMS or type(budget) is not int or budget not in (64, 640)
            or type(seed) is not int or seed not in (11, 22, 33)):
        raise ValueError("unregistered method, budget or seed")
    namespace = path.parts[path.parts.index("bootstrap_results") + 1:-1]
    frozen = namespace == ("frozen",)
    classification = "frozen_development" if frozen else "pilot"
    if method == "observational" and not frozen:
        classification = "invalid_pre_scope_fix_pilot"
    tasks = [_task(row, index, method, budget) for index, row in enumerate(raw.get("tasks", []))]
    alerts = [f"task {t['name']}: {alert}" for t in tasks for alert in t["alerts"]]
    names = [t["name"] for t in tasks]
    if any(type(name) is not str for name in names) or len(names) != len(set(names)):
        alerts.append("missing or duplicate task identity")
    verified = sorted(t["name"] for t in tasks if t["verified"] is True and type(t["name"]) is str)
    if "verified_solved" in raw and (type(raw["verified_solved"]) is not int or
                                     raw["verified_solved"] != len(verified)):
        alerts.append("top-level verified count differs from raw task rows")
    if "solutions" in raw and sorted(raw["solutions"]) != verified:
        alerts.append("top-level solutions differ from raw verifier rows")
    compression = raw.get("compression", {})
    records = compression.get("records", [])
    entries = compression.get("library")
    identity_records = sum(_identity(r.get("term_dict", {})) for r in records)
    totals = _totals(tasks)
    termination = Counter(t["termination"] for t in tasks)
    complete = raw.get("status") == "complete" and len(tasks) == 36
    run_cpu = raw.get("cpu_seconds") if _number(raw.get("cpu_seconds")) else None
    return {"source_path": str(path), "classification": classification,
            "eligible": frozen and complete and not alerts, "complete": complete,
            "status": raw.get("status", "unknown"), "method": method, "budget": budget,
            "seed": seed, "tasks_observed": len(tasks), "expected_tasks": 36,
            "verified_solved": len(verified), "verified_task_names": verified,
            "verified_fraction_observed": len(verified) / len(tasks) if tasks else None,
            "run_cpu_seconds": run_cpu,
            "run_wall_seconds": raw.get("wall_seconds") if _number(raw.get("wall_seconds")) else None,
            "cpu_scope": "Run CPU includes verification, serialization and compression; search CPU is separate",
            "totals": totals, "termination_counts": dict(termination), "alerts": alerts,
            "guard_evidence": {"unobserved_tasks": max(0, 36 - len(tasks)),
                "cpu_budget_terminations": termination.get("cpu_budget", 0),
                "expansion_budget_terminations": termination.get("expansion_budget", 0),
                "candidate_budget_terminations": sum(termination.get(name, 0)
                    for name in ("candidate_budget", "evaluation_budget")),
                "search_cpu_observed_rows": totals["search_cpu_seconds"]["known_rows"],
                "run_cpu_above_nominal_total_cap": run_cpu > 1800 if run_cpu is not None else None,
                "enforcement_claim": "Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},
            "tasks": tasks, "expansion_definition": EXPANSION_MEANINGS[method],
            "compression": {"adoptions": len(records), "records": records,
                            "entries": len(entries) if isinstance(entries, dict) else None,
                            "identity_macros": identity_records,
                            "mdl_delta": sum(r["delta"] for r in records)
                                         if all(_number(r.get("delta")) for r in records) else None,
                            "downstream_library_benefit": "unmeasured; tiny identity compression is insufficient"}}


def _compare(cycle, cycles):
    baselines = [r for r in cycles if r["eligible"] and r["method"] == "enumeration"
                 and r["seed"] == cycle["seed"] and r["budget"] == cycle["budget"]]
    if not cycle["eligible"] or len(baselines) != 1:
        return {"status": "unavailable", "reason": "requires one eligible frozen same-seed/same-budget baseline"}
    baseline = baselines[0]
    if [t["name"] for t in baseline["tasks"]] != [t["name"] for t in cycle["tasks"]]:
        return {"status": "unavailable", "reason": "task identities/order differ"}
    old, new = set(baseline["verified_task_names"]), set(cycle["verified_task_names"])
    work = {}
    for field in ("logical_program_attempts", "total_interpreter_calls", "total_interpreter_steps"):
        before, after = baseline["totals"][field]["value"], cycle["totals"][field]["value"]
        work[field] = {"baseline": before, "candidate": after,
                       "difference": after - before if before is not None and after is not None else None}
    return {"status": "descriptive_paired_development", "baseline_path": baseline["source_path"],
            "new_verified_tasks": sorted(new - old), "lost_verified_tasks": sorted(old - new),
            "same_verified_set": new == old, "logical_work": work,
            "equal_total_work_claim": False,
            "note": "Shared caps do not equalize interpreter work or differently defined expansions"}


def _fields(cycle):
    comparison = cycle["baseline_comparison"]
    if cycle["classification"] == "invalid_pre_scope_fix_pilot":
        decision = "EXCLUDE_INVALID_PILOT"
    elif cycle["classification"] == "pilot":
        decision = "PILOT_ONLY"
    elif not cycle["eligible"]:
        decision = "UNKNOWN_PARTIAL_OR_INVALID"
    elif cycle["method"] == "enumeration":
        decision = "BASELINE_ONLY"
    elif comparison["status"] == "unavailable":
        decision = "UNKNOWN_NO_PAIRED_BASELINE"
    elif comparison["lost_verified_tasks"]:
        decision = "REVISE_REGRESSION"
    elif comparison["new_verified_tasks"]:
        decision = "KEEP_FOR_CAUSAL_TEST_ONLY"
    else:
        decision = "REVISE_NO_VERIFIED_CAPABILITY_GAIN"
    failures = {"search_termination": cycle["termination_counts"],
                "selected_verifier_failures": sum(t["public_match"] is True and t["verified"] is False
                                                  for t in cycle["tasks"]),
                "unknown_verifier_rows": sum(t["verified"] is None for t in cycle["tasks"]),
                "reported_search_cpu_above_nominal_cap": sum(t["reported_cpu_above_nominal_cap"] is True
                                                            for t in cycle["tasks"]),
                "planning": "unknown", "tool": "unknown", "model": "unknown"}
    return dict(zip(FIELDS, (
        {"verified_solved": cycle["verified_solved"], "tasks_observed": cycle["tasks_observed"],
         "verified_fraction_observed": cycle["verified_fraction_observed"],
         "run_cpu_seconds": cycle["run_cpu_seconds"], "known_counters": cycle["totals"]},
        failures,
        "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient",
        "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures",
        {"method": cycle["method"], "candidate_budget": cycle["budget"], "nominal_protocol_limits": LIMITS},
        MECHANISMS[cycle["method"]],
        {"raw_source": cycle["source_path"], "classification": cycle["classification"],
         "public_search_then_separate_verifier": True, "reporter_executes_tasks": False},
        ["Finite coverage and public observational equivalence", "CPU/candidate/expansion limits",
         "Helper accounting differs; all recorded helper work remains charged",
         "No causal learned-library or synthesized-heuristic comparison"],
        {"complete": cycle["complete"], "eligible": cycle["eligible"], "baseline_comparison": comparison,
         "compression": cycle["compression"], "guard_evidence": cycle["guard_evidence"],
         "original_criteria": "FAIL; preserved"},
        decision,
        {"status": decision, "activated": False,
         "lesson": "Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests",
         "required_next": "All registered seeds, common-kernel controls, real compression support and learned-score ablations"},
    )))


def _diagnostic(path):
    raw, path = _read(path), str(path)
    if "measurements" in raw:
        kind, rows = "pointwise_scalar_search", raw["measurements"]
    elif "tasks" in raw and "failed_request_types" in raw:
        kind, rows = "prefix_continuation", raw["tasks"]
    elif "records" in raw:
        kind, rows = "typed_repair_pilot", raw["records"]
    else:
        raise ValueError("unrecognized explicitly supplied scratch diagnostic")
    facts = []
    for index, row in enumerate(rows):
        fact = {"name": row.get("name"), "raw_row_index": index}
        if kind == "prefix_continuation":
            fact.update({k: row.get(k) for k in (
                "task_program_attempts", "example_evaluations", "evaluator_steps", "public_matches",
                "total_on_public_examples", "unique_behavior_signatures", "first32_unique_signatures",
                "continued32_new_signatures")})
        elif kind == "pointwise_scalar_search":
            components = [t for t in row.get("trials", []) if t.get("stage") == "component"]
            fact.update({k: row.get(k) for k in ("budget", "candidates", "head_attempts", "component_attempts",
                "root_attempts", "example_evaluations", "evaluator_steps", "expansions", "termination")})
            fact["component_structural_evidence"] = {
                "recorded_components": len(components),
                "lambda_roots": sum(t["term"].get("tag") == "lam" for t in components),
                "contains_bound_variable": sum(_contains(t["term"], "var") for t in components)}
        else:
            repair = row.get("repair", {})
            fact.update({k: row.get(k) for k in ("baseline_candidates", "baseline_steps",
                "baseline_public_match", "baseline_hidden_verified", "repair_public_match", "repair_hidden_verified")})
            fact["repair_counters"] = {k: repair.get(k) for k in ("candidates", "evaluation_steps",
                "evaluator_calls", "seed_candidates", "repair_candidates", "invalid_repairs",
                "duplicate_candidates", "expansions", "cpu_seconds")}
            fact["seed_sizes"] = dict(Counter(_size(s["term"]) for s in repair.get("seed_records", []) if "term" in s))
            fact["additional_interpreter_steps"] = (repair["evaluation_steps"] - row["baseline_steps"]
                if _number(repair.get("evaluation_steps")) and _number(row.get("baseline_steps")) else None)
        fact["existing_eleven_fields"] = {field: row[field] for field in FIELDS if field in row}
        facts.append(fact)
    return {"source_path": path, "classification": "explicit_scratch_pilot", "kind": kind,
            "cpu_seconds": raw.get("cpu_seconds"), "status": raw.get("status", "unspecified"),
            "facts": facts, "population": raw.get("failed_request_types"),
            "eligible_tasks": raw.get("eligible"), "scientifically_eligible": False}


def build_report(paths, scratch_paths=()):
    """Read only supplied artifacts; partial and superseded evidence stays visible."""
    paths = [Path(path) for path in paths]
    if any("bootstrap_results" not in path.parts for path in paths):
        raise ValueError("only explicit bootstrap_results input paths are permitted")
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("duplicate input artifact")
    cycles = [_cycle(path, _read(path)) for path in sorted(paths, key=str)]
    for cycle in cycles:
        cycle["baseline_comparison"] = _compare(cycle, cycles)
        cycle["eleven_fields"] = _fields(cycle)
    return {"schema_version": 1, "scope": "TRAIN development bootstrap; raw artifact aggregation only",
            "original_criteria": {letter: "FAIL" for letter in "abcde"},
            "original_result_preserved": True, "rsi_claim": False, "activated_rules": [],
            "nominal_protocol_limits": LIMITS, "registered_seeds": [11, 22, 33],
            "eligible_observed_seeds": sorted({r["seed"] for r in cycles if r["eligible"]}),
            "cycles": cycles, "diagnostics": [_diagnostic(path) for path in scratch_paths],
            "limitations": ["Earlier root/instrumented records are pilots",
                "Pre-scope-fix observational pilots are invalid",
                "Missing counters are unknown, never zero-filled",
                "Bounded enumeration exhaustion does not identify heap versus expansion-cap termination",
                "Different expansion definitions prevent an equal-compute inference",
                "Only supplied completed frozen records can support descriptive same-seed/budget comparisons",
                "Tiny identity MDL reductions establish no downstream library benefit",
                "These human-designed kernels do not satisfy original RSI criteria a–e"]}


def _show(value):
    if value is None:
        return "unknown"
    return f"{value:.3f}" if type(value) is float else str(value)


def markdown(report):
    lines = ["# TRAIN bootstrap search results", "",
        "Original criteria a–e remain **FAIL**. These development kernels establish no RSI claim. "
        "All results below come from supplied raw artifacts; the reporter runs no tasks.", "",
        "| Method | B | Seed | Evidence | Complete | Verified/observed | All attempts | Helper attempts | Search calls | Search steps | Run CPU s | Rule |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in report["cycles"]:
        totals = row["totals"]
        values = [row["method"], row["budget"], row["seed"], row["classification"], row["complete"],
                  f"{row['verified_solved']}/{row['tasks_observed']}"]
        values += [totals[field]["value"] for field in ("logical_program_attempts", "auxiliary_program_attempts",
                                                       "search_interpreter_calls", "search_interpreter_steps")]
        values += [row["run_cpu_seconds"], row["eleven_fields"]["keep_revert_revise"]]
        lines.append("| " + " | ".join(_show(value) for value in values) + " |")
    lines += ["", "Run CPU includes verification, serialization and compression overhead. "
              "Search calls/steps exclude the separately reported verifier. "
              "Unknown counters have known-only subtotals in JSON. Shared caps do not equalize work.", ""]
    for row in report["cycles"]:
        lines += [f"## {row['method']} B{row['budget']} seed {row['seed']} ({row['classification']})", "",
                  f"Raw evidence: `{row['source_path']}`. Expansion meaning: {row['expansion_definition']}.", ""]
        for field in FIELDS:
            lines += [f"- **{field}**: " + json.dumps(row["eleven_fields"][field], ensure_ascii=False, separators=(",", ":"))]
        lines.append("")
    if report["diagnostics"]:
        lines += ["## Explicit scratch diagnostics", ""]
        for diagnostic in report["diagnostics"]:
            lines += [f"`{diagnostic['source_path']}` ({diagnostic['kind']}; pilot):", "",
                      "```json", json.dumps(diagnostic["facts"], ensure_ascii=False, indent=2), "```", ""]
    lines += ["## Limits", ""] + [f"- {limit}." for limit in report["limitations"]]
    return "\n".join(lines) + "\n"


def write_report(report, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = output_dir / "BOOTSTRAP_RESULTS.json", output_dir / "BOOTSTRAP_RESULTS.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, help="Explicit bootstrap result JSON(.gz)")
    parser.add_argument("--diagnostic", action="append", default=[], help="Explicit scratch diagnostic JSON(.gz)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = write_report(build_report(args.input, args.diagnostic), args.output)
    print(json.dumps({"json": str(paths[0]), "markdown": str(paths[1])}))


if __name__ == "__main__":
    main()
