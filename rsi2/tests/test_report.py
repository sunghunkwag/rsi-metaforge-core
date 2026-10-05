"""Scientific reporting checks using synthetic artifacts, never the TEST corpus."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from rsi2 import report


CONFIG = json.loads((Path(report.__file__).parent / "experiment_config.json").read_text())


def measurement(solved=2, budget=64, tasks=12):
    solved = min(solved, tasks)
    records = [{"name": f"task_{index}", "solved": index < solved,
                "candidates": 2 if index < solved else budget,
                "candidates_to_solution": 2 if index < solved else None}
               for index in range(tasks)]
    return {"tasks": tasks, "solved": solved, "solved_fraction": solved / tasks,
            "mean_candidates_to_solution": 2.0 if solved else None,
            "candidate_evaluations": sum(r["candidates"] for r in records),
            "budget": budget, "wall_seconds": 0.5, "cpu_seconds": 0.4,
            "records": records}


def heuristic(generation, seed, primitive=False, best=2):
    candidates = [{"index": index, "screen": measurement(2, 16, 4),
                   "full": measurement(best) if index < 2 else None,
                   "origin": "enumeration" if index < 4 else "mutation"}
                  for index in range(6)]
    incumbent = measurement()
    inner = incumbent["candidate_evaluations"] + sum(
        candidate["screen"]["candidate_evaluations"]
        + (candidate["full"]["candidate_evaluations"] if candidate["full"] else 0)
        for candidate in candidates)
    return {"generation": generation, "seed": seed,
            "primitive_only": primitive, "update_state": not primitive,
            "incumbent": {"tag": "int", "value": 0}, "incumbent_full": incumbent,
            "best_full_fraction": best / 12,
            "synthesis_candidate_evaluations": 6,
            "inner_candidate_evaluations": inner, "candidate_evaluations": inner + 6,
            "candidates": candidates}


def make_runs(full_curves=None, library_better=False):
    runs = {}
    for arm in CONFIG["arms"]:
        for seed in CONFIG["seeds"]:
            rows, cost = [], 0
            budget = 640 if arm == "BRUTE" else 64
            for generation in range(9):
                frozen = generation > 0 and (arm in ("BASE", "BRUTE")
                                             or (arm == "ONESHOT" and generation > 1))
                if frozen:
                    source = 1 if arm == "ONESHOT" else 0
                    row = {"generation": generation,
                           "validation": copy.deepcopy(rows[source]["validation"]),
                           "test": copy.deepcopy(rows[source]["test"]),
                           "reused_measurement": True, "reuse_source_generation": source,
                           "learning": None, "heuristic": None}
                else:
                    count = (full_curves[seed][generation] if arm == "FULL" and full_curves
                             else 3 if arm == "BRUTE" else 2)
                    learned = improved = None
                    if generation:
                        learned = {"generation": generation, "wake_candidate_evaluations": 36 * 64,
                                   "dream_candidate_evaluations": 0 if arm == "NO_RECOGNITION" else 16}
                        cost += learned["wake_candidate_evaluations"] + learned["dream_candidate_evaluations"]
                        if arm != "NO_HEURISTIC":
                            improved = heuristic(generation, seed,
                                                 best=3 if arm == "FULL" and generation == 8 and library_better else 2)
                            cost += improved["candidate_evaluations"]
                    row = {"generation": generation, "validation": measurement(2, budget),
                           "test": measurement(count, budget), "reused_measurement": False,
                           "learning": learned, "heuristic": improved}
                    cost += row["validation"]["candidate_evaluations"] + row["test"]["candidate_evaluations"]
                rows.append(row)
            run = {"arm": arm, "seed": seed, "status": "complete", "config": copy.deepcopy(CONFIG),
                   "generations": rows,
                   "final_state": {"generation": 0 if arm in ("BASE", "BRUTE") else 1 if arm == "ONESHOT" else 8,
                                   "seed": seed, "library_history": [], "heuristic_history": []},
                   "totals": {"candidate_evaluations": cost, "wall_seconds": 10.0, "cpu_seconds": 9.0}}
            if arm == "FULL":
                primitive = heuristic(8, seed, primitive=True)
                run["comparison"] = {"generation": 8, "primary": "validation_solved_fraction",
                                     "library_best": rows[8]["heuristic"]["best_full_fraction"],
                                     "primitives_best": primitive["best_full_fraction"],
                                     "quota": 6, "primitive_only": primitive}
                run["totals"]["candidate_evaluations"] += primitive["candidate_evaluations"]
            run["final_state"]["logical_evaluations"] = run["totals"]["candidate_evaluations"]
            runs[arm, seed] = run
    return runs


class ReportTests(unittest.TestCase):
    def test_complete_runs_account_for_reuse_and_counterfactual(self):
        runs = make_runs()
        for run in runs.values():
            report.validate_run(run, CONFIG)
        base = runs["BASE", 11]
        actual = base["generations"][0]["test"]["candidate_evaluations"] * 2
        self.assertEqual(base["totals"]["candidate_evaluations"], actual)
        self.assertTrue(all(row["reused_measurement"] for row in base["generations"][1:]))
        bad = copy.deepcopy(runs["FULL", 11])
        bad["totals"]["candidate_evaluations"] -= bad["comparison"]["primitive_only"]["candidate_evaluations"]
        with self.assertRaisesRegex(ValueError, "exactly once"):
            report.validate_run(bad, CONFIG)

    def test_positive_claim_requires_all_five_criteria(self):
        curves = {seed: [2, 2, 3, 4, 5, 5, 5, 5, 5] for seed in CONFIG["seeds"]}
        runs = make_runs(curves, library_better=True)
        criteria = report.evaluate_criteria(runs, CONFIG)
        self.assertTrue(all(value["passed"] for value in criteria.values()))
        self.assertEqual(criteria["c"]["windows"], [(1, 4)])
        for run in runs.values():
            report.validate_run(run, CONFIG)
        text = report.render_report(runs, CONFIG)
        self.assertIn("All five preregistered criteria passed", text)

    def test_mean_growth_does_not_hide_individual_seed_decline(self):
        curves = {11: [2, 2, 1, 2, 3, 3, 3, 3, 3],
                  22: [2, 2, 4, 5, 6, 6, 6, 6, 6],
                  33: [2, 2, 3, 4, 5, 5, 5, 5, 5]}
        result = report.evaluate_criteria(make_runs(curves), CONFIG)
        self.assertFalse(result["c"]["passed"])
        curves[11] = [2, 2, 2, 2, 2, 2, 2, 2, 2]
        result = report.evaluate_criteria(make_runs(curves), CONFIG)
        self.assertTrue(result["c"]["passed"])

    def test_every_seed_comparisons_are_strict(self):
        curves = {seed: [2, 2, 3, 4, 5, 5, 5, 5, 5] for seed in CONFIG["seeds"]}
        runs = make_runs(curves, library_better=True)
        runs["FULL", 33]["generations"][8]["test"] = measurement(3)
        runs["FULL", 22]["comparison"]["library_best"] = 2 / 12
        criteria = report.evaluate_criteria(runs, CONFIG)
        self.assertFalse(criteria["a"]["passed"])
        self.assertFalse(criteria["e"]["passed"])
        runs["FULL", 11]["generations"][8]["test"] = measurement(2)
        criteria = report.evaluate_criteria(runs, CONFIG)
        self.assertFalse(criteria["b"]["passed"])
        self.assertFalse(criteria["d"]["passed"])

    def test_partial_study_is_not_a_scientific_failure(self):
        runs = make_runs()
        runs["FULL", 33]["status"] = "partial"
        runs["FULL", 33]["stop_reason"] = "aggregate CPU limit reached"
        criteria = report.evaluate_criteria(runs, CONFIG)
        self.assertTrue(all(value["passed"] is None for value in criteria.values()))
        text = report.render_report(runs, CONFIG)
        self.assertIn("Study incomplete: 20/21", text)
        self.assertIn("NOT ASSESSED", text)
        self.assertNotIn("Criteria (a)", text)
        self.assertNotIn("All 21 preregistered", text)
        self.assertIn("No final stopping-point claim", text)

    def test_final_comparison_can_precede_partial_generation_checkpoint(self):
        run = make_runs()["FULL", 11]
        run["status"] = "partial"
        run["generations"].pop()
        # The completed g8 counterfactual is retained even though g8 TEST
        # never finished and therefore has no report row.
        report.validate_run(run, CONFIG)
        runs = make_runs()
        runs["FULL", 11] = run
        self.assertTrue(all(value["passed"] is None
                            for value in report.evaluate_criteria(runs, CONFIG).values()))

    def test_task_metrics_reject_hidden_failure_and_zero_solve_confounds(self):
        zero = measurement(0)
        report.validate_measurement(zero, 64)
        self.assertEqual(report._mean_candidates(zero), "—")
        bad = copy.deepcopy(zero)
        bad["mean_candidates_to_solution"] = 64
        with self.assertRaisesRegex(ValueError, "zero solves"):
            report.validate_measurement(bad, 64)
        bad = measurement()
        bad["records"][0]["solved"] = False
        with self.assertRaisesRegex(ValueError, "hidden verification"):
            report.validate_measurement(bad, 64)
        bad = measurement()
        bad["candidate_evaluations"] += 1
        with self.assertRaisesRegex(ValueError, "candidate total"):
            report.validate_measurement(bad, 64)

    def test_protocol_and_false_completion_are_rejected(self):
        run = make_runs()["ONESHOT", 11]
        run["generations"][2]["test"]["wall_seconds"] += 1
        with self.assertRaisesRegex(ValueError, "frozen control"):
            report.validate_run(run, CONFIG)
        run = make_runs()["FULL", 11]
        run["comparison"]["quota"] = 5
        with self.assertRaisesRegex(ValueError, "library comparison"):
            report.validate_run(run, CONFIG)
        run = make_runs()["BASE", 11]
        run["generations"].pop()
        with self.assertRaisesRegex(ValueError, "omits"):
            report.validate_run(run, CONFIG)

    def test_missing_artifacts_are_explicit_and_filename_identity_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs, summary = report.load_runs(temporary, CONFIG)
            self.assertIsNone(summary)
            self.assertTrue(all(run["status"] == "missing" for run in runs.values()))
            self.assertIn("Study incomplete: 0/21", report.render_report(runs, CONFIG))
            path = Path(temporary) / "BASE_seed11.json"
            bad = make_runs()["BASE", 11]
            bad["seed"] = 22
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, "filename"):
                report.load_runs(temporary, CONFIG)

    def test_readable_terms_predictions_and_descriptive_stopping_points(self):
        runs = make_runs()
        state = runs["FULL", 11]["final_state"]
        state["library_history"] = [{"name": "lib_1", "generation": 2, "delta": 4,
                                      "support": 3, "readable_term": "λx. add x 1"}]
        state["heuristic_history"] = [{"generation": 3, "readable": "λa. λb. λc. λd. c",
                                       "validation_solved_fraction": 3 / 12}]
        predictions = report.load_predictions()
        self.assertEqual(predictions["FULL"][3], 0.1667)
        text = report.render_report(runs, CONFIG, predictions=predictions)
        self.assertIn("g2 `lib_1`: `λx. add x 1`", text)
        self.assertIn("g3: `λa. λb. λc. λd. c`", text)
        self.assertIn("Observed − predicted", text)
        self.assertEqual(report.stopping_point([2, 1, 3, 2, 2]),
                         {"last_new_best": 2, "final_flat_start": 3})
        self.assertEqual(report.stopping_point([2, 2, 2]),
                         {"last_new_best": 0, "final_flat_start": 0})
        self.assertEqual(report.stopping_point([2, 1, 2, 1]),
                         {"last_new_best": 0, "final_flat_start": None})


if __name__ == "__main__":
    unittest.main()
