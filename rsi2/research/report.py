"""Report procedure research and derive rules only from development confirmation."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from ..report import validate_measurement


HERE = Path(__file__).resolve().parent
CYCLE_FIELDS = ("current_performance", "failure_clusters", "bottleneck",
                "previous_attempt_insufficiency", "intervention", "mechanism",
                "verification_plan", "regression_risks", "result",
                "keep_revert_revise", "updated_rule")
OBJECTIVE = "previous_audit_valid_and_informative_productivity_proxy"
SOURCE_FIELDS = {"cycle", "arm", "seed", "selected_indices", "confirmed_indices",
                 "adopted_index", "incumbent_validation", "validation",
                 "incumbent_confirmation", "confirmation", "failure_clusters",
                 "proposal_productivity", "draw", "selection", "model", "candidates",
                 "probe_program_evaluations", "probe_example_evaluations",
                 "probe_evaluator_steps", "wall_seconds", "cpu_seconds", "decision", "memory"}


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _time(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return value


def _solved(measurement):
    return {r["name"] for r in measurement["records"] if r["solved"]}


def validate_cycle(row, seed, arm, number, config, previous=None):
    missing = SOURCE_FIELDS - row.keys()
    if missing:
        raise ValueError(f"incomplete cycle fields: {', '.join(sorted(missing))}")
    if "online_report" in row:
        missing = set(CYCLE_FIELDS) - row["online_report"].keys()
        if missing or any(row["online_report"][field] is None for field in CYCLE_FIELDS):
            raise ValueError("incomplete online cycle report fields")
    if (row["seed"], row["arm"], row["cycle"]) != (seed, arm, number):
        raise ValueError("cycle identity disagrees with its position")
    for key, tasks in (("incumbent_validation", 12), ("validation", 12),
                       ("incumbent_confirmation", 6), ("confirmation", 6)):
        validate_measurement(row[key], config["B_eval"], tasks)
    candidates = row["candidates"]
    slots = config["raw_enumeration_slots"] + config["mutation_slots"]
    if len(candidates) != slots or any(r["index"] != i for i, r in enumerate(candidates)):
        raise ValueError("raw draw slots are missing or reordered")
    selected, confirmed = row["selected_indices"], row["confirmed_indices"]
    if (len(selected) > config["screen_slots"] or len(selected) != len(set(selected))
            or any(type(i) is not int or not 0 <= i < slots for i in selected)
            or len(confirmed) > config["confirmation_slots"] or len(confirmed) != len(set(confirmed))
            or not set(confirmed) <= set(selected)):
        raise ValueError("selection or full confirmation exceeds the fixed ceilings")
    productive = fresh = 0
    probes = examples = steps = 0
    for index, candidate in enumerate(candidates):
        audit = candidate["audit"]
        if type(audit["valid"]) is not bool or type(audit["informative"]) is not bool:
            raise ValueError("semantic probes lack verified Boolean labels")
        if candidate["selected"] is not (index in selected):
            raise ValueError("candidate selection flag disagrees with selected indices")
        if index in selected:
            productive += audit["valid"] and audit["informative"]
            confirmation = candidate.get("confirmation_audit")
            if candidate["term"] is not None and confirmation is None:
                raise ValueError("selected proposal lacks its fresh-confirmation probes")
            if confirmation is not None:
                fresh += confirmation["valid"] and confirmation["informative"]
        for check in (audit, candidate.get("confirmation_audit")):
            if check is not None:
                probes += _count(check["program_evaluations"], "probe attempts")
                examples += _count(check["example_evaluations"], "probe examples")
                steps += _count(check["evaluator_steps"], "probe steps")
        for key, budget, tasks in (("screen", config["screen_budget"], config["screen_tasks"]),
                                   ("full", config["B_eval"], 12),
                                   ("confirmation", config["B_eval"], 6)):
            if candidate.get(key) is not None:
                validate_measurement(candidate[key], budget, tasks)
    productivity = row["proposal_productivity"]
    if (productivity["selected"], productivity["verified"], productivity["fresh_family_verified"]) != (len(selected), productive, fresh):
        raise ValueError("proposal productivity disagrees with verifier evidence")
    if (row["probe_program_evaluations"], row["probe_example_evaluations"], row["probe_evaluator_steps"]) != (probes, examples, steps):
        raise ValueError("probe costs omit semantic or fresh-confirmation evaluations")
    draw = row["draw"]
    if (draw["new_raw_draws"] != slots or draw["enumeration_slots"] != config["raw_enumeration_slots"]
            or draw["mutation_slots"] != config["mutation_slots"]):
        raise ValueError("raw draw ceilings differ from the protocol")
    prior = previous["model"]["trained_count"] if previous else 0
    if row["selection"]["model_trained_count"] != prior:
        raise ValueError("ranking model used labels outside preceding cycles")
    if row["model"]["objective"] != OBJECTIVE:
        raise ValueError("proposal model objective differs from verified productivity")
    if arm != "learned" and row["model"]["trained_count"] != 0:
        raise ValueError("control arm fitted a ranking model")
    if arm == "learned" and row["model"]["trained_count"] and row["model"]["training_steps"] != 80:
        raise ValueError("NumPy fitting steps differ from the protocol")
    adopted = row["adopted_index"]
    if adopted is None:
        if (row["validation"] != row["incumbent_validation"]
                or row["confirmation"] != row["incumbent_confirmation"]):
            raise ValueError("retained incumbent has changed measurements")
    else:
        if adopted not in confirmed:
            raise ValueError("adopted heuristic was not fully confirmed")
        candidate = candidates[adopted]
        if (not (candidate["audit"]["valid"] and candidate["audit"]["informative"])
                or row["validation"]["solved_fraction"] <= row["incumbent_validation"]["solved_fraction"]
                or candidate["full"] != row["validation"]
                or candidate["confirmation"] != row["confirmation"]
                or not _solved(row["incumbent_confirmation"]) <= _solved(row["confirmation"])):
            raise ValueError("adoption lacks strict task improvement or loses a confirmation task")
    for key in ("cpu_seconds", "wall_seconds"):
        _time(row[key], key)
    return row


def validate_seed(record, seed, config):
    if record.get("seed") != seed:
        raise ValueError("seed identity disagrees with filename")
    # Missing configuration remains unknown and cannot contribute a kept rule.
    if record.get("config") is not None and record["config"] != config:
        raise ValueError("seed configuration differs from the committed protocol")
    if "baseline_training" in record:
        validate_measurement(record["baseline_training"], config["B_eval"], 36)
    for arm, target in record.get("arms", {}).items():
        if arm not in config["arms"] or len(target["cycles"]) > config["cycles"]:
            raise ValueError("unexpected arm or extra cycles")
        for index, row in enumerate(target["cycles"], 1):
            validate_cycle(row, seed, arm, index, config,
                           target["cycles"][index - 2] if index > 1 else None)
        if "training" in target:
            validate_measurement(target["training"], config["B_eval"], 36)
        if "audit" in target:
            validate_measurement(target["audit"], config["B_eval"], 8)
    return record


def load_results(path, config):
    path = Path(path)
    runs = {}
    for seed in config["seeds"]:
        filename = path / f"seed{seed}.json"
        record = (json.loads(filename.read_text()) if filename.exists() else
                  {"seed": seed, "status": "missing", "arms": {}})
        runs[seed] = validate_seed(record, seed, config)
    filename = path / "summary.json"
    summary = json.loads(filename.read_text()) if filename.exists() else None
    if summary is not None and summary.get("config") is not None and summary["config"] != config:
        raise ValueError("summary configuration differs from the committed protocol")
    return runs, summary


def _complete_development(runs, config, summary):
    if (summary is None or summary.get("config") != config
            or summary.get("status") not in ("complete", "selection_frozen")
            or set(runs) != set(config["seeds"])):
        return False
    return all(run.get("config") == config
               and run.get("status") in ("complete", "selection_frozen")
               and set(run.get("arms", {})) == set(config["arms"])
               and all(len(run["arms"][arm]["cycles"]) == config["cycles"] for arm in config["arms"])
               for run in runs.values())


def derive_rules(runs, config, summary=None):
    """Audit scores are deliberately absent from every decision and evidence field."""
    complete = _complete_development(runs, config, summary)
    rules = []
    for intervention, control, type_ in (("static", "original", "loop"),
                                        ("learned", "static", "meta")):
        evidence = []
        if complete:
            for seed in config["seeds"]:
                changed = runs[seed]["arms"][intervention]["cycles"]
                baseline = runs[seed]["arms"][control]["cycles"]
                losses = [{"cycle": index, "task_names": sorted(_solved(b["confirmation"]) - _solved(a["confirmation"]))}
                          for index, (a, b) in enumerate(zip(changed, baseline), 1)
                          if not _solved(b["confirmation"]) <= _solved(a["confirmation"])]
                evidence.append({"seed": seed,
                                 "control_fresh_verified": sum(r["proposal_productivity"]["fresh_family_verified"] for r in baseline),
                                 "intervention_fresh_verified": sum(r["proposal_productivity"]["fresh_family_verified"] for r in changed),
                                 "control_selected": sum(r["proposal_productivity"]["selected"] for r in baseline),
                                 "intervention_selected": sum(r["proposal_productivity"]["selected"] for r in changed),
                                 "confirmation_task_losses": losses})
        nonregression = complete and all(e["intervention_fresh_verified"] >= e["control_fresh_verified"]
                                        and not e["confirmation_task_losses"] for e in evidence)
        strict = complete and any(e["intervention_fresh_verified"] > e["control_fresh_verified"] for e in evidence)
        decision = "UNKNOWN" if not complete else "KEEP" if nonregression and strict else "REVISE" if nonregression else "REVERT"
        rules.append({"id": f"{intervention}_versus_{control}", "type": type_,
                      "pattern": "Repeated finite proposal prefixes and verified unproductive selection" if type_ == "loop" else
                                 "Static novelty may leave a learned proposal-ranking opportunity",
                      "diagnosis": "Verified proposal productivity is the measured target; task capability is a separate outcome.",
                      "intervention": "Persistent frontier, semantic eligibility and AST novelty" if type_ == "loop" else
                                      "Prior-cycle NumPy ranking on verified executable, candidate-dependent labels",
                      "evidence": evidence, "decision": decision,
                      "threshold": "No worse fresh-confirmation verified count on every seed, some strict gain, and no solved-task loss in any corresponding confirmation cycle",
                      "scope": "Limited paired development claim about verified proposal productivity; not task fitness or RSI",
                      "next_test": "Complete the fixed paired comparison before selecting a rule" if not complete else
                                   "Use a new preregistered independent study to test downstream hidden-verified task gains" if decision == "KEEP" else
                                   "Retain raw verifier evidence; revise the candidate policy in a new preregistered study"})
    adoptions = []
    if complete:
        for seed in config["seeds"]:
            for arm in config["arms"]:
                for row in runs[seed]["arms"][arm]["cycles"]:
                    if row["adopted_index"] is not None:
                        adoptions.append({"seed": seed, "arm": arm, "cycle": row["cycle"],
                                          "validation_before": row["incumbent_validation"]["solved"],
                                          "validation_after": row["validation"]["solved"],
                                          "confirmation_solved": row["confirmation"]["solved"],
                                          "readable": row["candidates"][row["adopted_index"]]["readable"]})
    rules.append({"id": "task_heuristic_admission", "type": "object",
                  "pattern": "Proposal-proxy gains can fail to improve hidden-verified task search",
                  "diagnosis": "Executable and informative behavior is insufficient evidence of task fitness.",
                  "intervention": "Require strict full VALIDATION gain, valid informative probes and per-task confirmation nonloss",
                  "evidence": adoptions, "decision": "UNKNOWN" if not complete else "KEEP" if adoptions else "REVISE",
                  "scope": "Only individually verified adopted task heuristics; no original recursive-improvement claim",
                  "next_test": "Complete measurements" if not complete else
                               "Measure cumulative task capability in a fresh preregistered study" if adoptions else
                               "Investigate the gap between productive proposals and task-solve improvements"})
    return {"schema_version": 1, "development_complete": complete,
            "evidence_scope": "Development and fresh confirmation only; reporting audit excluded",
            "rules": rules}


def cycle_record(run, arm, index, rules):
    row = run["arms"][arm]["cycles"][index]
    if "online_report" in row:
        # These values were stored at the end of that cycle. A later paired
        # decision must not silently replace its provisional online judgment.
        online = {field: copy.deepcopy(row["online_report"][field]) for field in CYCLE_FIELDS}
        return {"seed": run["seed"], "arm": arm, "cycle": row["cycle"], **online}
    previous = run["arms"][arm]["cycles"][index - 1] if index else None
    rule = next((r for r in rules["rules"] if r["id"].startswith(arm + "_versus_")), None)
    evidence = row["failure_clusters"]
    observed = sorted(((name, item["count"]) for name, item in evidence.items()
                       if item.get("status") == "observed" and item.get("count")),
                      key=lambda item: (-item[1], item[0]))
    interventions = {"original": "Restart enumeration and retain the original four-prefix/two-mutation control selection.",
                     "static": "Retain the proposal frontier and reject unexecutable, input-constant and previously selected ASTs.",
                     "learned": "Apply the same frontier/eligibility/novelty procedure and rank with a model fitted on preceding cycles only."}
    result = {"validation_solved": row["validation"]["solved"],
              "confirmation_solved": row["confirmation"]["solved"],
              "selected": row["proposal_productivity"]["selected"],
              "verified_productive": row["proposal_productivity"]["verified"],
              "fresh_confirmation_productive": row["proposal_productivity"]["fresh_family_verified"],
              "adopted_task_heuristic": row["adopted_index"] is not None,
              "cpu_seconds": row["cpu_seconds"], "wall_seconds": row["wall_seconds"]}
    return {"seed": run["seed"], "arm": arm, "cycle": row["cycle"],
            "current_performance": {"validation": row["validation"]["solved_fraction"],
                                    "confirmation": row["confirmation"]["solved_fraction"]},
            "failure_clusters": evidence,
            "bottleneck": [{"category": name, "observed_evidence_records": count} for name, count in observed[:4]]
                          or "No observed failure cluster identifies a bottleneck; unobserved causes remain unknown.",
            "previous_attempt_insufficiency": ({"previous_cycle": previous["cycle"],
                                                 "validation_solved": previous["validation"]["solved"],
                                                 "fresh_confirmation_productive": previous["proposal_productivity"]["fresh_family_verified"],
                                                 "adopted": previous["adopted_index"] is not None,
                                                 "interpretation": "Prior proposal productivity is not proof of task-search improvement."}
                                                if previous else
                                                "One original TRAIN round supplies the fixed task learner; this cycle tests the original procedure against frontier/selection interventions."),
            "intervention": interventions[arm],
            "mechanism": "Production/AST features predict preceding-cycle verified executable and candidate-dependent behavior; the objective is not task fitness."
                         if arm == "learned" else "Verified semantic eligibility and AST novelty change which proposals reach the fixed task assessments."
                         if arm == "static" else "Fixed original indices provide the restart/failed-prefix procedure control.",
            "verification_plan": "Charge common semantic probes; verify selected productivity on six fresh confirmation-family public profiles; screen at most six on four VALIDATION tasks at 16; confirm at most two on twelve VALIDATION tasks at 64; admit only strict gain with no solved confirmation task lost.",
            "regression_risks": "The productivity proxy can improve without task capability; coarse task-name families and small hidden sets limit transfer; model labels must precede ranking; exact cache scope and replay work must remain visible.",
            "result": result,
            "keep_revert_revise": {"timing": "retrospective final-study decision",
                                   "procedure": rule["decision"] if rule else "REVISE"},
            "updated_rule": ({"timing": "retrospective final-study decision", "id": rule["id"],
                              "decision": rule["decision"], "scope": rule["scope"]}
                             if rule else {"timing": "retrospective final-study decision", "id": "original_control",
                                           "decision": "REVISE", "scope": "Measured control; no newly learned improvement rule"})}


def _table(lines, headers, rows):
    lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    lines.append("")


def _fraction(measurement):
    return "unknown" if measurement is None else f"{measurement['solved']}/{measurement['tasks']} ({measurement['solved_fraction']:.4f})"


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_report(runs, config, summary=None):
    rules = derive_rules(runs, config, summary)
    complete = rules["development_complete"]
    lines = ["# Follow-up procedure research", "",
             "This separate study preserves the original RSI-2 measurements and null result. "
             "The measured proxy is verified proposal productivity: executable, candidate-dependent "
             "heuristics selected under equal proposal and assessment ceilings. It is not solver fitness "
             "or a positive recursive self-improvement claim.", "",
             "Development comparison: **complete**." if complete else
             "Development comparison: **unknown/incomplete**. No improvement rule is kept or judged failed from partial evidence.", "",
             "Three seeds (11, 22, 33), three cycles, ORIGINAL/STATIC/LEARNED; 32 enumeration and "
             "two mutation slots, at most six screens and two full confirmations per cycle. The task "
             "learner is trained once per seed and then its grammar, library and recognizer remain fixed. "
             "Only the proposal procedure, memory/model and strictly admitted heuristic can change.", "",
             "## Paired development decisions", ""]
    _table(lines, ["Rule", "Type", "Decision", "Evidence"],
           [(r["id"], r["type"], r["decision"], _json(r["evidence"]).replace("|", "\\|")) for r in rules["rules"]])
    lines.extend(["KEEP requires no worse fresh-confirmation productive proposal count on every seed, "
                  "some strict gain, and no solved task lost in any corresponding confirmation cycle. "
                  "Ties are REVISE; regressions are REVERT. These are limited paired development decisions. "
                  "The fitted LEARNED model is not retained as a verified improvement when its comparison ties. "
                  "All raw labels and rejection history remain evidence. Audit outcomes never select these rules.", "",
                  "## Every seed, arm and cycle", ""])
    rows = []
    for seed in config["seeds"]:
        run = runs[seed]
        for arm in config["arms"]:
            for row in run.get("arms", {}).get(arm, {}).get("cycles", []):
                candidates = row["candidates"]
                valid = sum(c["audit"]["valid"] for c in candidates)
                informative = sum(c["audit"]["valid"] and c["audit"]["informative"] for c in candidates)
                audit = row.get("audit_productivity")
                rows.append((seed, arm, row["cycle"], valid, informative,
                             row["proposal_productivity"]["selected"], row["proposal_productivity"]["verified"],
                             row["proposal_productivity"]["fresh_family_verified"],
                             "unknown" if audit is None else audit["verified"],
                             _fraction(row["validation"]), _fraction(row["confirmation"]),
                             "yes" if row["adopted_index"] is not None else "no", f"{row['cpu_seconds']:.3f}"))
    _table(lines, ["Seed", "Arm", "Cycle", "Raw valid", "Raw productive", "Selected",
                   "Selected productive", "Fresh confirmation productive", "Reporting audit productive",
                   "VALIDATION", "Confirmation", "Task adoption", "CPU s"], rows)
    lines.extend(["Fresh confirmation and reporting-audit productivity count proposal programs passing "
                  "their public task-derived probe profile; they are not hidden-verified task solve counts. "
                  "A selected invalid ORIGINAL proposal remains a charged control assessment. All arms "
                  "share the semantic admission guard against invalid or candidate-constant heuristic adoption.", "",
                  "## Hidden-verified task outcomes", ""])
    rows = []
    for seed in config["seeds"]:
        run = runs[seed]
        for arm in config["arms"]:
            target = run.get("arms", {}).get(arm, {})
            cycles = target.get("cycles", [])
            rows.append((seed, arm, run.get("status", "unknown"), _fraction(run.get("baseline_training")),
                         _fraction(target.get("training")), _fraction(cycles[-1]["validation"] if cycles else None),
                         _fraction(cycles[-1]["confirmation"] if cycles else None), _fraction(target.get("audit"))))
    _table(lines, ["Seed", "Arm", "Status", "Initial TRAIN", "Final TRAIN", "Final VALIDATION",
                   "Final confirmation", "Reporting-only audit"], rows)
    lines.extend(["Final TRAIN and audit columns are measured only after selection freezes; final TRAIN is "
                  "not substituted for unmeasured intermediate-cycle performance. An audit transfer "
                  "failure limits the result's applicability but cannot revise the selected rules or another cycle.", "",
                  "## Compute, fitting and memory", ""])
    rows = []
    for seed in config["seeds"]:
        for arm in config["arms"]:
            for row in runs[seed].get("arms", {}).get(arm, {}).get("cycles", []):
                draw, model, selection = row["draw"], row["model"], row["selection"]
                memory = row["memory"]
                rows.append((seed, arm, row["cycle"], draw["new_raw_draws"], draw.get("replay_draws", 0),
                             draw.get("enumeration_frontier_pops", "unknown"),
                             row["probe_program_evaluations"], row["probe_example_evaluations"], row["probe_evaluator_steps"],
                             selection["model_trained_count"], model["trained_count"], model.get("training_steps", 0),
                             memory["cache_hits"], memory["actual_candidate_evaluations"],
                             f"{row['wall_seconds']:.3f}", f"{row['cpu_seconds']:.3f}"))
    _table(lines, ["Seed", "Arm", "Cycle", "Raw slots", "Replay enumerations", "Frontier pops",
                   "Probe programs", "Probe examples", "Probe steps", "Prior labels ranked with",
                   "Post-cycle fit labels", "NumPy steps", "Cumulative cache hits",
                   "Cumulative actual inner candidates", "Wall s", "CPU s"], rows)
    lines.extend(["The model uses 80 NumPy logistic-gradient steps, L2 0.001 and fixed production/AST "
                  "features. Labels are verified executable AND informative behavior, not task solves. "
                  "The prior-label column checks that current-cycle labels never trained its ranking model. "
                  "Cache counts and inner candidates are cumulative within each arm. Exact task/example, "
                  "grammar/library/recognizer, heuristic, budget and search-limit scope controls reuse. "
                  "Replay enumeration work and frontier pops are separate from new raw proposal attempts; "
                  "equal ceilings do not imply equal actual computation. In incomplete checkpoints, "
                  "completed-operation counters are lower bounds; an interrupted operation has no "
                  "published verifier result and may contain unrecorded work.", ""])
    raw = sum(r["draw"]["new_raw_draws"] for run in runs.values() for target in run.get("arms", {}).values() for r in target["cycles"])
    replay = sum(r["draw"].get("replay_draws", 0) for run in runs.values() for target in run.get("arms", {}).values() for r in target["cycles"])
    probes = sum(r["probe_program_evaluations"] for run in runs.values() for target in run.get("arms", {}).values() for r in target["cycles"])
    inner = sum(target.get("evaluation_memory", {}).get("actual_candidate_evaluations", 0)
                for run in runs.values() for target in run.get("arms", {}).values())
    initial = sum(run.get("initial_learning", {}).get("wake_candidate_evaluations", 0)
                  + run.get("initial_learning", {}).get("dream_candidate_evaluations", 0)
                  + run.get("baseline_training", {}).get("actual_candidate_evaluations", 0) for run in runs.values())
    lines.extend([f"Development units: {raw} raw proposal slots; {replay} replay enumerations; {probes} semantic/fresh-confirmation "
                  f"probe-program contexts; {inner} actual inner task-search candidates; {initial} "
                  "initial wake/dream/TRAIN search candidates. These conceptual units are disaggregated; "
                  "their summed counter is an accounting total, not a uniform candidate-throughput metric.", ""])
    if summary is not None:
        audit = summary.get("audit", {})
        lines.extend([f"Controller status: {summary.get('status', 'unknown')}; aggregate CPU "
                      f"{summary.get('cpu_seconds', 'unknown')} s; wall {summary.get('wall_seconds', 'unknown')} s; "
                      f"audit CPU {summary.get('audit_cpu_seconds', 'unknown')} s; summed accounting total "
                      f"{summary.get('actual_candidate_evaluations', 'unknown')}. Limit: 7,200 aggregate CPU seconds.", "",
                      "Reporting-only audit units: "
                      f"{audit.get('probe_program_evaluations', 'unknown')} probe programs; "
                      f"{audit.get('probe_example_evaluations', 'unknown')} probe examples; "
                      f"{audit.get('probe_evaluator_steps', 'unknown')} evaluator steps; "
                      f"{audit.get('memory', {}).get('actual_candidate_evaluations', 'unknown')} actual TRAIN/audit task-search candidates.", ""])
        if summary.get("stop_reason"):
            lines.extend([f"Controller stopping reason: {summary['stop_reason']}.", ""])
    lines.extend(["## Eleven evidence fields for every cycle", "",
                  "Stored online reports preserve the task-admission decision and provisional procedure "
                  "judgment made at the end of that cycle, before later-cycle or reporting-audit evidence. "
                  "Artifacts lacking an online report use an explicitly labeled retrospective final-study "
                  "decision. Final paired development rules are reported separately above.", ""])
    for seed in config["seeds"]:
        for arm in config["arms"]:
            for index, row in enumerate(runs[seed].get("arms", {}).get(arm, {}).get("cycles", [])):
                record = cycle_record(runs[seed], arm, index, rules)
                lines.extend([f"### Seed {seed}, {arm}, cycle {row['cycle']}", ""])
                for field in CYCLE_FIELDS:
                    value = record[field]
                    lines.extend([f"**{field.replace('_', ' ')}:** " + (value if isinstance(value, str) else _json(value)), ""])
    lines.extend(["## Limits and next evidence", "",
                  "No original held-out performance selects an intervention. The fresh partition uses "
                  "six confirmation and eight audit task-name families excluded from all original 60 "
                  "identities; coarse names do not prove semantic independence. Each task has ten public "
                  "examples and a small hidden set. Runtime probes test observed behavior, not universal "
                  "function equivalence. Fixed AST size 12, 20,000 expansions and 2,000 interpreter steps "
                  "bound the findings. The study isolates three improver cycles over a fixed one-round task "
                  "learner, so proxy gains alone cannot establish cumulative capability or the original "
                  "five recursive-improvement criteria. A new preregistered study is needed before any "
                  "revised policy receives additional task-capability credit.", ""])
    return "\n".join(lines), rules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rules", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads((HERE / "config.json").read_text())
        runs, summary = load_results(args.results, config)
        text, rules = render_report(runs, config, summary)
    except (KeyError, TypeError, ValueError) as exc:
        parser.error(f"invalid research artifacts: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    if args.rules is not None:
        args.rules.parent.mkdir(parents=True, exist_ok=True)
        args.rules.write_text(json.dumps(rules, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
