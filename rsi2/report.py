"""Report frozen experiment artifacts without loading tasks or changing a learner."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
STATUSES = {"unrun", "running", "complete", "failed", "partial", "missing"}
CRITERIA = {
    "a": "Final FULL exceeds BRUTE on every seed",
    "b": "Final FULL exceeds ONESHOT on every seed",
    "c": "Three consecutive strict mean increases after g1, without any seed decline",
    "d": "Final FULL exceeds NO_HEURISTIC on every seed",
    "e": "Library heuristic synthesis exceeds primitives on every seed at equal quota",
}


def _integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return value


def _equal_number(actual, expected, label):
    _number(actual, label)
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{label} disagrees with task records")


def validate_measurement(report, budget, tasks=12):
    """Recompute solved fractions, costs and means from hidden-verification records."""
    if report["tasks"] != tasks or report["budget"] != budget:
        raise ValueError("measurement task count or budget differs from the protocol")
    records = report["records"]
    if len(records) != tasks or len({r["name"] for r in records}) != tasks:
        raise ValueError("measurement has missing or duplicate task records")
    solved = []
    for record in records:
        candidates = _integer(record["candidates"], "task candidates")
        if candidates > budget or type(record["solved"]) is not bool:
            raise ValueError("task record exceeds its budget or lacks a verification outcome")
        if record["candidates_to_solution"] != (candidates if record["solved"] else None):
            raise ValueError("candidates-to-solution disagrees with hidden verification")
        if record["solved"]:
            solved.append(candidates)
    if report["solved"] != len(solved):
        raise ValueError("measurement solve count disagrees with task records")
    _equal_number(report["solved_fraction"], len(solved) / tasks, "solved fraction")
    mean = report["mean_candidates_to_solution"]
    if solved:
        _equal_number(mean, sum(solved) / len(solved), "mean candidates-to-solution")
    elif mean is not None:
        raise ValueError("zero solves must have a null candidates-to-solution mean")
    cost = sum(record["candidates"] for record in records)
    if _integer(report["candidate_evaluations"], "measurement candidates") != cost:
        raise ValueError("measurement candidate total disagrees with task records")
    return cost


def _heuristic_cost(report, config):
    quota = config["heuristics"]["N_h"] + config["heuristics"]["N_m"]
    if report["synthesis_candidate_evaluations"] != quota or len(report["candidates"]) != quota:
        raise ValueError("heuristic synthesis did not retain every proposal slot")
    inner = validate_measurement(report["incumbent_full"], config["B_eval"])
    for candidate in report["candidates"]:
        if candidate["screen"] is not None:
            inner += validate_measurement(candidate["screen"],
                                          config["B_eval"] // config["heuristics"]["screen_budget_divisor"],
                                          config["heuristics"]["screen_tasks"])
        if candidate["full"] is not None:
            inner += validate_measurement(candidate["full"], config["B_eval"])
    if (report["inner_candidate_evaluations"] != inner
            or report["candidate_evaluations"] != inner + quota):
        raise ValueError("heuristic costs omit proposal slots or inner searches")
    _number(report["best_full_fraction"], "best heuristic fraction")
    if report["best_full_fraction"] > 1:
        raise ValueError("heuristic fraction exceeds one")
    return inner + quota


def validate_run(record, config):
    """Reject inconsistent completed artifacts; preserve explicitly partial runs."""
    if record["status"] not in STATUSES or record["config"] != config:
        raise ValueError("run status or configuration differs from the protocol")
    rows = record["generations"]
    if len(rows) > config["generations"] + 1:
        raise ValueError("run has extra generations")
    complete = record["status"] == "complete"
    if complete and len(rows) != config["generations"] + 1:
        raise ValueError("completed run omits preregistered generations")
    cost = 0
    arm = record["arm"]
    budget = config["B_eval"] * (config["M"] if arm == "BRUTE" else 1)
    for generation, row in enumerate(rows):
        if row["generation"] != generation:
            raise ValueError("generations must be a contiguous prefix beginning at zero")
        val = validate_measurement(row["validation"], budget)
        test = validate_measurement(row["test"], budget)
        frozen = generation > 0 and (arm in ("BASE", "BRUTE")
                                     or (arm == "ONESHOT" and generation > 1))
        if row["reused_measurement"] is not frozen:
            raise ValueError("frozen control reuse differs from the protocol")
        if frozen:
            source = 1 if arm == "ONESHOT" else 0
            if (row.get("reuse_source_generation") != source
                    or row["validation"] != rows[source]["validation"]
                    or row["test"] != rows[source]["test"]
                    or row["learning"] is not None or row["heuristic"] is not None):
                raise ValueError("reused measurement changed a frozen control")
            continue
        cost += val + test
        if generation == 0:
            if row["learning"] is not None or row["heuristic"] is not None:
                raise ValueError("generation zero must precede learning")
            continue
        learned = row["learning"]
        if learned is None or learned["generation"] != generation:
            raise ValueError("learning generation is missing or inconsistent")
        cost += _integer(learned["wake_candidate_evaluations"], "wake candidates")
        cost += _integer(learned["dream_candidate_evaluations"], "dream candidates")
        if arm == "NO_HEURISTIC":
            if row["heuristic"] is not None:
                raise ValueError("NO_HEURISTIC contains an improver round")
        else:
            improved = row["heuristic"]
            if (improved is None or improved["generation"] != generation
                    or improved["seed"] != record["seed"]):
                raise ValueError("heuristic generation or seed is inconsistent")
            cost += _heuristic_cost(improved, config)
    comparison = record.get("comparison")
    if complete and arm == "FULL" and comparison is None:
        raise ValueError("completed FULL run lacks the library vocabulary comparison")
    # A stop after the g8 improver but before g8 TEST leaves a legitimate
    # counterfactual alongside only the completed g0..g7 measurement rows.
    # Preserve that partial artifact; no scientific criterion can use it.
    comparison_has_row = rows and rows[-1]["generation"] == config["generations"]
    if comparison is not None and (complete or comparison_has_row):
        current = rows[-1]["heuristic"]
        primitive = comparison["primitive_only"]
        if (arm != "FULL" or comparison["generation"] != config["generations"]
                or comparison["quota"] != 6 or current is None
                or primitive["synthesis_candidate_evaluations"] != 6
                or current["synthesis_candidate_evaluations"] != 6
                or primitive["incumbent"] != current["incumbent"]
                or primitive["primitive_only"] is not True
                or primitive["update_state"] is not False
                or current["primitive_only"] is not False
                or current["update_state"] is not True
                or comparison["library_best"] != current["best_full_fraction"]
                or comparison["primitives_best"] != primitive["best_full_fraction"]):
            raise ValueError("library comparison changed state, incumbent, quotas, or measured scores")
        cost += _heuristic_cost(primitive, config)
    totals = record["totals"]
    actual = _integer(totals["candidate_evaluations"], "run candidates")
    _number(totals["wall_seconds"], "run wall time")
    _number(totals["cpu_seconds"], "run CPU time")
    if complete and actual != cost:
        raise ValueError("run candidate total does not charge actual computations exactly once")
    if complete:
        state = record["final_state"]
        expected_generation = 0 if arm in ("BASE", "BRUTE") else 1 if arm == "ONESHOT" else config["generations"]
        if (state is None or state["generation"] != expected_generation
                or state["seed"] != record["seed"] or state["logical_evaluations"] != actual):
            raise ValueError("final state disagrees with the completed run")
    return record


def load_runs(results, config):
    results = Path(results)
    runs = {}
    expected = {f"{arm}_seed{seed}.json" for arm in config["arms"] for seed in config["seeds"]}
    unexpected = {p.name for p in results.glob("*.json")} - expected - {"execution_summary.json"}
    if unexpected:
        raise ValueError(f"unexpected result artifacts: {', '.join(sorted(unexpected))}")
    for arm in config["arms"]:
        for seed in config["seeds"]:
            path = results / f"{arm}_seed{seed}.json"
            if not path.exists():
                runs[arm, seed] = {"arm": arm, "seed": seed, "status": "missing",
                                   "generations": [], "final_state": None,
                                   "totals": {"candidate_evaluations": 0,
                                              "wall_seconds": 0, "cpu_seconds": 0}}
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["arm"] != arm or record["seed"] != seed:
                raise ValueError(f"artifact identity disagrees with its filename: {path.name}")
            runs[arm, seed] = validate_run(record, config)
    summary_path = results / "execution_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    if summary is not None:
        statuses = {(r["arm"], r["seed"]): r["status"] for r in summary["runs"]}
        if summary["config"] != config or statuses != {key: r["status"] for key, r in runs.items()}:
            raise ValueError("execution summary disagrees with run artifacts")
        if summary["status"] == "complete" and any(r["status"] != "complete" for r in runs.values()):
            raise ValueError("execution summary falsely labels incomplete runs complete")
    return runs, summary


def evaluate_criteria(runs, config):
    """Use integer verified-solve counts for TEST comparisons and growth windows."""
    if any(r["status"] != "complete" for r in runs.values()):
        return {key: {"passed": None, "evidence": "Incomplete study; not assessed."}
                for key in CRITERIA}
    seeds, final = config["seeds"], config["generations"]

    def solved(arm, seed, generation=final):
        return runs[arm, seed]["generations"][generation]["test"]["solved"]

    criteria = {}
    for key, control in (("a", "BRUTE"), ("b", "ONESHOT"), ("d", "NO_HEURISTIC")):
        criteria[key] = {"passed": all(solved("FULL", seed) > solved(control, seed) for seed in seeds),
                         "evidence": "; ".join(f"seed {seed}: FULL {solved('FULL', seed)}/12, "
                                               f"{control} {solved(control, seed)}/12" for seed in seeds)
                         + f"; mean FULL {sum(solved('FULL', seed) for seed in seeds) / (12 * len(seeds)):.4f}, "
                         + f"{control} {sum(solved(control, seed) for seed in seeds) / (12 * len(seeds)):.4f}"}
    windows = []
    for start in range(1, final - 2):
        transitions = range(start, start + 3)
        means_rise = all(sum(solved("FULL", seed, g + 1) for seed in seeds)
                         > sum(solved("FULL", seed, g) for seed in seeds) for g in transitions)
        seeds_do_not_drop = all(solved("FULL", seed, g + 1) >= solved("FULL", seed, g)
                                for seed in seeds for g in transitions)
        if means_rise and seeds_do_not_drop:
            windows.append((start, start + 3))
    criteria["c"] = {"passed": bool(windows), "windows": windows,
                     "evidence": ("Qualifying transitions: " + ", ".join(f"g{a}→g{b}" for a, b in windows)
                                  if windows else "No three-transition window qualifies after g1.")}
    criteria["e"] = {"passed": all(runs["FULL", seed]["comparison"]["library_best"]
                                   > runs["FULL", seed]["comparison"]["primitives_best"] for seed in seeds),
                     "evidence": "; ".join(f"seed {seed}: library {runs['FULL', seed]['comparison']['library_best']:.4f}, "
                                           f"primitives {runs['FULL', seed]['comparison']['primitives_best']:.4f} "
                                           "(6 proposal slots each)" for seed in seeds)}
    return criteria


def stopping_point(values):
    """Last generation establishing a strict all-time best, plus a final flat suffix."""
    best, last_best = values[0], 0
    for generation, value in enumerate(values[1:], 1):
        if value > best:
            best, last_best = value, generation
    flat = len(values) - 1
    while flat > 0 and values[flat - 1] == values[-1]:
        flat -= 1
    return {"last_new_best": last_best, "final_flat_start": flat if flat < len(values) - 1 else None}


def load_predictions(path=HERE / "PREDICTIONS.md"):
    curves = {arm: [] for arm in ("BASE", "BRUTE", "ONESHOT", "FULL")}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0].isdigit():
            if int(cells[0]) != len(curves["BASE"]):
                raise ValueError("prediction generations are not contiguous")
            for arm, cell in zip(curves, cells[1:]):
                value = _number(float(cell), "predicted fraction")
                if value > 1:
                    raise ValueError("predicted fraction exceeds one")
                curves[arm].append(value)
    if any(len(curve) != 9 for curve in curves.values()):
        raise ValueError("preregistered prediction curves are missing generations")
    return curves


def _fraction(measurement):
    return f"{measurement['solved']}/{measurement['tasks']} ({measurement['solved_fraction']:.4f})"


def _mean_candidates(measurement):
    value = measurement["mean_candidates_to_solution"]
    return "—" if value is None else f"{value:.2f}"


def _table(lines, columns, rows):
    lines.extend(["| " + " | ".join(columns) + " |",
                  "| " + " | ".join("---" for _ in columns) + " |"])
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    lines.append("")


def render_report(runs, config, summary=None, predictions=None):
    criteria = evaluate_criteria(runs, config)
    complete = all(r["status"] == "complete" for r in runs.values())
    count = sum(r["status"] == "complete" for r in runs.values())
    lines = ["# RSI-2 measured results", ""]
    if complete:
        failed = [key for key, result in criteria.items() if not result["passed"]]
        outcome = ("Positive recursive self-improvement was not established. "
                   f"Criteria {', '.join(f'({key})' for key in failed)} failed."
                   if failed else "All five preregistered criteria passed in this bounded study.")
        lines.extend([f"All {count} preregistered arm/seed runs completed. {outcome}", ""])
    else:
        lines.extend([f"Study incomplete: {count}/{len(runs)} arm/seed runs completed. "
                      "Scientific criteria are not assessed; missing and partial runs are not counted as failures.", ""])
    lines.extend(["The frozen study uses 60 external DreamCoder tasks: TRAIN 36, VALIDATION 12, TEST 12; "
                  "seeds 11, 22, 33; generations 0–8; B_wake = B_eval = 64; BRUTE budget 640. "
                  "Heuristic synthesis has four enumeration slots and two mutation slots per round, "
                  "with all valid proposals screened on four VALIDATION tasks at budget 16 and two "
                  "confirmed on all VALIDATION tasks at 64. Strict full-VALIDATION improvement controls adoption.", "",
                  "TEST fractions below count only solutions passing separate hidden examples. "
                  "Mean candidates-to-solution is conditional on a hidden-verified solve; — means no solves. "
                  "Frozen BASE/BRUTE and post-round ONESHOT measurements are reused explicitly. "
                  "Reused rows add no computation to run totals.", "",
                  "## Preregistered criteria", ""])
    _table(lines, ["Criterion", "Requirement", "Result", "Evidence"],
           [(f"({key})", CRITERIA[key], "NOT ASSESSED" if value["passed"] is None
             else "PASS" if value["passed"] else "FAIL", value["evidence"])
            for key, value in sorted(criteria.items())])
    lines.extend(["Criteria (d) and (e) use the preregistered conservative every-seed requirement. "
                  "Criterion (c) requires three strict mean increases on successive transitions starting "
                  "at g1 or later, with every seed nondecreasing on each transition. "
                  "Criterion (e) compares final-generation VALIDATION scores from the same pre-adoption "
                  "state and incumbent with six synthesis proposal slots in each vocabulary. "
                  "Task-search grammar/library/recognition remain shared in this counterfactual.", "",
                  "## Every arm, seed and generation", ""])
    for seed in config["seeds"]:
        lines.extend([f"### Seed {seed}", ""])
        rows = []
        for arm in config["arms"]:
            run = runs[arm, seed]
            if run["status"] != "complete":
                lines.extend([f"{arm}: **{run['status']}**"
                              + (f" — {run.get('stop_reason', run.get('error'))}" if run.get("stop_reason", run.get("error")) else ""), ""])
            for row in run["generations"]:
                rows.append((arm, row["generation"], _fraction(row["test"]),
                             _mean_candidates(row["test"]), _fraction(row["validation"]),
                             f"g{row['reuse_source_generation']}" if row["reused_measurement"] else "no"))
        _table(lines, ["Arm", "Generation", "TEST hidden solves", "Mean candidates to solution",
                       "VALIDATION hidden solves", "Reused from"], rows)
    lines.extend(["## Measured compute", "",
                  "Logical candidate counts include task-search attempts, dream attempts, heuristic "
                  "proposal slots and every inner heuristic search, including duplicates and failed candidates. "
                  "FULL also includes its primitive-only vocabulary counterfactual. "
                  "Candidates/s uses each run's wall time; CPU time is reported separately. "
                  "Per-arm summed wall time is worker duration, not parallel experiment elapsed time. "
                  "For partial or failed runs, candidate totals count completed operations only and are "
                  "lower bounds; an interrupted operation's attempts may not have been checkpointed.", ""])
    compute_rows = []
    for arm in config["arms"]:
        for seed in config["seeds"]:
            run = runs[arm, seed]
            totals = run["totals"]
            wall, cpu, candidates = totals["wall_seconds"], totals["cpu_seconds"], totals["candidate_evaluations"]
            compute_rows.append((arm, seed, run["status"], candidates, f"{wall:.3f}",
                                 f"{cpu:.3f}", f"{candidates / wall:.3f}" if wall else "—"))
    _table(lines, ["Arm", "Seed", "Status", "Logical candidates", "Wall seconds", "CPU seconds", "Candidates/s"], compute_rows)
    _table(lines, ["Arm", "Summed worker wall seconds", "Summed CPU seconds"],
           [(arm, f"{sum(runs[arm, seed]['totals']['wall_seconds'] for seed in config['seeds']):.3f}",
             f"{sum(runs[arm, seed]['totals']['cpu_seconds'] for seed in config['seeds']):.3f}")
            for arm in config["arms"]])
    if summary is not None:
        totals = summary["totals"]
        lines.extend([f"Controller elapsed wall time: {totals['wall_seconds']:.3f} s. "
                      f"Measured aggregate CPU: {totals['cpu_seconds']:.3f} s "
                      f"({totals['cpu_seconds'] / 3600:.4f} CPU-hours); limit 24 CPU-hours. "
                      f"Workers: {summary['workers']}; NumPy threads per worker: 1.", ""])
    lines.extend(["## Where improvement stopped", "",
                  "Descriptive stopping point means the last generation reaching a strictly higher "
                  "all-time best TEST solved count; it is g0 if no later generation exceeds g0. "
                  "The flat suffix is the earliest generation in the final constant-valued suffix "
                  "containing at least two observations. These descriptions did not stop or tune any run.", ""])
    if complete:
        curves = {str(seed): [row["test"]["solved"] for row in runs["FULL", seed]["generations"]]
                  for seed in config["seeds"]}
        curves["Mean FULL"] = [sum(curves[str(seed)][g] for seed in config["seeds"])
                                for g in range(config["generations"] + 1)]
        _table(lines, ["FULL curve", "Last new best", "Final flat suffix begins"],
               [(label, f"g{point['last_new_best']}",
                 "none" if point["final_flat_start"] is None else f"g{point['final_flat_start']}")
                for label, values in curves.items() for point in [stopping_point(values)]])
        mean = [sum(runs["FULL", seed]["generations"][g]["test"]["solved_fraction"]
                    for seed in config["seeds"]) / len(config["seeds"])
                for g in range(config["generations"] + 1)]
        lines.extend(["Mean FULL TEST fractions: " + ", ".join(f"g{g}={value:.4f}" for g, value in enumerate(mean)) + ".", ""])
    else:
        lines.extend(["No final stopping-point claim is made for an incomplete study.", ""])
    lines.extend(["## Learned library entries", "",
                  "All adopted entries are printed below, ordered within each run by MDL reduction. "
                  "Their source generation is the generation when first adopted.", ""])
    library_count = 0
    for (arm, seed), run in runs.items():
        history = (run.get("final_state") or {}).get("library_history", [])
        if not history:
            continue
        lines.extend([f"### {arm}, seed {seed}", ""])
        for entry in sorted(history, key=lambda item: (-item["delta"], item["generation"], item["name"])):
            lines.append(f"- g{entry['generation']} `{entry['name']}`: `{entry['readable_term']}` "
                         f"(MDL reduction {entry['delta']}; support {entry['support']}).")
            library_count += 1
        lines.append("")
    if not library_count:
        lines.extend(["No learned library entries were adopted in the recorded runs.", ""])
    lines.extend(["## Every adopted heuristic", ""])
    heuristic_count = 0
    for (arm, seed), run in runs.items():
        history = (run.get("final_state") or {}).get("heuristic_history", [])
        if not history:
            continue
        lines.extend([f"### {arm}, seed {seed}", ""])
        for entry in history:
            lines.append(f"- g{entry['generation']}: `{entry['readable']}` "
                         f"(full VALIDATION fraction {entry['validation_solved_fraction']:.4f}).")
            heuristic_count += 1
        lines.append("")
    if not heuristic_count:
        lines.extend(["No heuristic was adopted in the recorded runs; the initial four-input constant-zero heuristic remained incumbent.", ""])
    lines.extend(["Every proposed heuristic, including duplicates and rejections, remains in its arm/seed JSON generation log. "
                  "The final FULL JSON also contains the primitive-only comparison's proposal log.", "",
                  "## Predictions versus observations", ""])
    predictions = load_predictions() if predictions is None else predictions
    if complete:
        rows = []
        for generation in range(config["generations"] + 1):
            for arm, curve in predictions.items():
                observed = sum(runs[arm, seed]["generations"][generation]["test"]["solved_fraction"]
                               for seed in config["seeds"]) / len(config["seeds"])
                rows.append((generation, arm, f"{curve[generation]:.4f}", f"{observed:.4f}",
                             f"{observed - curve[generation]:+.4f}"))
        _table(lines, ["Generation", "Arm", "Preregistered mean", "Observed mean", "Observed − predicted"], rows)
    else:
        lines.extend(["Final prediction errors are not computed for an incomplete study.", ""])
    lines.extend(["Predictions were committed before final TEST measurement in [PREDICTIONS.md](PREDICTIONS.md). "
                  "Reported prediction errors do not alter the frozen protocol.", "",
                  "## Scope and limits", "",
                  "This is the resource-scaled 60-task subset of 207 eligible external tasks, with eight "
                  "learning generations, AST size at most 12 and expansion limit 20,000. Each selected "
                  "task has ten distinct search examples and only one to five hidden examples. "
                  "Named parameter variants of a routine can cross TRAIN/VALIDATION/TEST boundaries; "
                  "this limits claims about generalization to new routine families. Hidden verification "
                  "establishes agreement on those observed examples, not universal semantic equivalence. "
                  "The original primitive set, evaluator and four-input heuristic interface remain frozen. "
                  "No LLM is used by synthesis, learning or evaluation. Conclusions apply only to the "
                  "measured tasks and configured search limits.", "",
                  "Configuration: [experiment_config.json](experiment_config.json). "
                  "Corpus provenance and split: [DATASET.md](DATASET.md). "
                  "One JSON per arm/seed run is retained in [results/](results/); "
                  "execution_summary.json contains controller timing and completion status.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "results")
    parser.add_argument("--output", type=Path, default=HERE / "RESULTS.md")
    args = parser.parse_args()
    try:
        config = json.loads((HERE / "experiment_config.json").read_text(encoding="utf-8"))
        runs, summary = load_runs(args.results, config)
        report = render_report(runs, config, summary)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(f"invalid experiment artifacts: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
