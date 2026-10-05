"""Procedure reporting and development-only rules from synthetic verifier evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from rsi2.research import report


CONFIG = json.loads((Path(report.__file__).parent / "config.json").read_text())


def measurement(solved=1, tasks=12, budget=64, identities=None):
    names = set(range(solved)) if identities is None else set(identities)
    rows = [{"name": f"task_{index}", "solved": index in names,
             "candidates": 2 if index in names else budget,
             "candidates_to_solution": 2 if index in names else None}
            for index in range(tasks)]
    return {"tasks": tasks, "budget": budget, "solved": len(names),
            "solved_fraction": len(names) / tasks,
            "mean_candidates_to_solution": 2.0 if names else None,
            "candidate_evaluations": sum(r["candidates"] for r in rows),
            "actual_candidate_evaluations": sum(r["candidates"] for r in rows),
            "cache_hit": False, "records": rows}


def probe(informative=True):
    return {"valid": True, "informative": informative, "program_evaluations": 1,
            "example_evaluations": 12, "evaluator_steps": 10, "failures": []}


def cycle(seed, arm, number, productive):
    selected = [0, 1, 2, 3, 32, 33] if arm == "original" else list(range(6))
    records = []
    for index in range(34):
        chosen = index in selected
        position = selected.index(index) if chosen else None
        records.append({"index": index, "term": {"tag": "int", "value": index},
                        "readable": f"proposal_{index}", "selected": chosen,
                        "audit": probe(chosen),
                        "confirmation_audit": probe(position < productive) if chosen else None,
                        "screen": measurement(0, 4, 16) if chosen else None,
                        "full": measurement(1) if index in selected[:2] else None,
                        "confirmation": None, "adopted": False})
    return {"seed": seed, "arm": arm, "cycle": number,
            "selected_indices": selected, "confirmed_indices": selected[:2], "adopted_index": None,
            "incumbent_validation": measurement(), "validation": measurement(),
            "incumbent_confirmation": measurement(tasks=6), "confirmation": measurement(tasks=6),
            "failure_clusters": {"constant_score": {"status": "observed", "count": 28, "evidence": []},
                                 "environment_failure": {"status": "unknown", "count": None, "evidence": []}},
            "proposal_productivity": {"selected": 6, "verified": 6, "fresh_family_verified": productive},
            "draw": {"new_raw_draws": 34, "enumeration_slots": 32, "mutation_slots": 2,
                     "replay_draws": 0, "enumeration_frontier_pops": 40},
            "selection": {"model_trained_count": (number - 1) * 34 if arm == "learned" else 0},
            "model": {"objective": report.OBJECTIVE, "trained_count": number * 34 if arm == "learned" else 0,
                      "observed_count": number * 34, "training_steps": 80 if arm == "learned" else 0},
            "candidates": records, "probe_program_evaluations": 40,
            "probe_example_evaluations": 480, "probe_evaluator_steps": 400,
            "cpu_seconds": 1.0, "wall_seconds": 1.1, "decision": "retain incumbent",
            "memory": {"cache_hits": number, "actual_candidate_evaluations": number * 500},
            "audit_productivity": {"selected": 6, "attempted": 6, "verified": productive,
                                   "program_evaluations": 6, "example_evaluations": 96, "evaluator_steps": 60}}


def fixture(productivity=None):
    productivity = productivity or {"original": 0, "static": 3, "learned": 3}
    runs = {}
    for seed in CONFIG["seeds"]:
        arms = {}
        for arm in CONFIG["arms"]:
            arms[arm] = {"cycles": [cycle(seed, arm, number, productivity[arm]) for number in range(1, 4)],
                         "audit": measurement(tasks=8), "training": measurement(tasks=36),
                         "evaluation_memory": {"actual_candidate_evaluations": 1500}}
        runs[seed] = {"seed": seed, "config": copy.deepcopy(CONFIG), "status": "complete", "arms": arms,
                      "initial_learning": {"wake_candidate_evaluations": 36 * 64, "dream_candidate_evaluations": 16},
                      "baseline_training": measurement(tasks=36)}
    summary = {"config": copy.deepcopy(CONFIG), "status": "complete", "cpu_seconds": 30.0,
               "wall_seconds": 10.0, "audit_cpu_seconds": 3.0, "actual_candidate_evaluations": 40000,
               "audit": {"probe_program_evaluations": 162, "probe_example_evaluations": 2592,
                         "probe_evaluator_steps": 1620, "memory": {"actual_candidate_evaluations": 5000}}}
    return runs, summary


def decisions(rules):
    return {rule["id"]: rule["decision"] for rule in rules["rules"]}


class ResearchReportTests(unittest.TestCase):
    def test_measured_loop_gain_and_learned_tie_have_different_rules(self):
        runs, summary = fixture()
        for seed, run in runs.items():
            report.validate_seed(run, seed, CONFIG)
        rules = report.derive_rules(runs, CONFIG, summary)
        self.assertEqual(decisions(rules), {"static_versus_original": "KEEP",
                                           "learned_versus_static": "REVISE",
                                           "task_heuristic_admission": "REVISE"})
        self.assertEqual({r["type"] for r in rules["rules"]}, {"loop", "meta", "object"})
        self.assertIn("not task fitness or RSI", rules["rules"][0]["scope"])

    def test_partial_or_missing_configuration_cannot_keep_or_fail_rules(self):
        for alteration in ("partial_run", "partial_summary", "missing_seed_config", "missing_summary"):
            with self.subTest(alteration=alteration):
                runs, summary = fixture()
                if alteration == "partial_run":
                    runs[33]["status"] = "partial"
                elif alteration == "partial_summary":
                    summary["status"] = "partial"
                elif alteration == "missing_seed_config":
                    del runs[22]["config"]
                else:
                    summary = None
                rules = report.derive_rules(runs, CONFIG, summary)
                self.assertFalse(rules["development_complete"])
                self.assertTrue(all(r["decision"] == "UNKNOWN" for r in rules["rules"]))

    def test_audit_outcomes_never_select_development_rules(self):
        runs, summary = fixture()
        before = report.derive_rules(runs, CONFIG, summary)
        for run in runs.values():
            for arm, target in run["arms"].items():
                target["audit"] = measurement(8 if arm == "learned" else 0, tasks=8)
                target["training"] = measurement(36 if arm == "original" else 0, tasks=36)
                for row in target["cycles"]:
                    row["audit_productivity"]["verified"] = 6 if arm == "learned" else 0
        summary["audit"]["probe_evaluator_steps"] = 999999
        after = report.derive_rules(runs, CONFIG, summary)
        self.assertEqual(before, after)
        self.assertNotIn("audit_productivity", json.dumps(after))

    def test_every_seed_nonregression_and_some_strict_gain_are_required(self):
        runs, summary = fixture({"original": 2, "static": 2, "learned": 3})
        self.assertEqual(decisions(report.derive_rules(runs, CONFIG, summary))["static_versus_original"], "REVISE")
        self.assertEqual(decisions(report.derive_rules(runs, CONFIG, summary))["learned_versus_static"], "KEEP")
        # Two strong gains cannot offset a regression in the third seed.
        for row in runs[33]["arms"]["learned"]["cycles"]:
            row["proposal_productivity"]["fresh_family_verified"] = 1
        self.assertEqual(decisions(report.derive_rules(runs, CONFIG, summary))["learned_versus_static"], "REVERT")

    def test_task_identity_loss_blocks_keep_despite_equal_solved_fraction(self):
        runs, summary = fixture()
        row = runs[11]["arms"]["static"]["cycles"][1]
        row["confirmation"] = measurement(tasks=6, identities={1})
        row["incumbent_confirmation"] = copy.deepcopy(row["confirmation"])
        report.validate_seed(runs[11], 11, CONFIG)
        rules = report.derive_rules(runs, CONFIG, summary)
        self.assertEqual(decisions(rules)["static_versus_original"], "REVERT")
        self.assertEqual(rules["rules"][0]["evidence"][0]["confirmation_task_losses"],
                         [{"cycle": 2, "task_names": ["task_0"]}])

    def test_missing_cycle_fields_and_current_cycle_label_training_rejected(self):
        runs, _ = fixture()
        bad = copy.deepcopy(runs[11])
        del bad["arms"]["static"]["cycles"][0]["failure_clusters"]
        with self.assertRaisesRegex(ValueError, "incomplete cycle fields"):
            report.validate_seed(bad, 11, CONFIG)
        bad = copy.deepcopy(runs[11])
        bad["arms"]["learned"]["cycles"][0]["selection"]["model_trained_count"] = 34
        with self.assertRaisesRegex(ValueError, "preceding cycles"):
            report.validate_seed(bad, 11, CONFIG)
        bad = copy.deepcopy(runs[11])
        bad["arms"]["static"]["cycles"][0]["proposal_productivity"]["verified"] -= 1
        with self.assertRaisesRegex(ValueError, "verifier evidence"):
            report.validate_seed(bad, 11, CONFIG)

    def test_object_rule_requires_a_verified_task_adoption(self):
        runs, summary = fixture()
        row = runs[11]["arms"]["static"]["cycles"][0]
        row["adopted_index"] = row["confirmed_indices"][0]
        row["validation"] = measurement(2)
        candidate = row["candidates"][row["adopted_index"]]
        candidate["full"] = copy.deepcopy(row["validation"])
        candidate["confirmation"] = copy.deepcopy(row["confirmation"])
        candidate["adopted"] = True
        report.validate_seed(runs[11], 11, CONFIG)
        rules = report.derive_rules(runs, CONFIG, summary)
        self.assertEqual(decisions(rules)["task_heuristic_admission"], "KEEP")
        self.assertEqual(rules["rules"][2]["evidence"][0]["validation_after"], 2)
        candidate["audit"]["informative"] = False
        row["proposal_productivity"]["verified"] -= 1
        with self.assertRaisesRegex(ValueError, "adoption lacks"):
            report.validate_seed(runs[11], 11, CONFIG)

    def test_each_cycle_has_all_eleven_fields_and_no_audit_in_rules(self):
        runs, summary = fixture()
        rules = report.derive_rules(runs, CONFIG, summary)
        for run in runs.values():
            for arm in CONFIG["arms"]:
                for index in range(3):
                    cycle_record = report.cycle_record(run, arm, index, rules)
                    self.assertEqual(set(report.CYCLE_FIELDS), set(cycle_record) - {"seed", "arm", "cycle"})
                    self.assertTrue(all(cycle_record[key] is not None for key in report.CYCLE_FIELDS))
                    self.assertNotIn("audit_productivity", json.dumps(cycle_record))
        text, rendered_rules = report.render_report(runs, CONFIG, summary)
        self.assertEqual(rules, rendered_rules)
        self.assertEqual(text.count("**current performance:**"), 27)
        self.assertIn("not solver fitness", text)
        self.assertIn("Prior labels ranked with", text)
        self.assertIn("conceptual units are disaggregated", text)
        self.assertIn("Initial TRAIN", text)

    def test_online_cycle_decision_does_not_use_future_study_evidence(self):
        runs, summary = fixture()
        initial_rules = report.derive_rules(runs, CONFIG, summary)
        stored = report.cycle_record(runs[11], "static", 0, initial_rules)
        online = {field: copy.deepcopy(stored[field]) for field in report.CYCLE_FIELDS}
        online["keep_revert_revise"] = {"task_heuristic": "revert", "procedure": "provisional"}
        online["updated_rule"] = {"status": "provisional", "next_cycle_prior_labels": 34}
        runs[11]["arms"]["static"]["cycles"][0]["online_report"] = online
        before = report.cycle_record(runs[11], "static", 0, initial_rules)
        report.validate_seed(runs[11], 11, CONFIG)
        # Later control productivity reverses the final paired judgment.
        for row in runs[11]["arms"]["original"]["cycles"][1:]:
            row["proposal_productivity"]["fresh_family_verified"] = 6
            for index in row["selected_indices"]:
                row["candidates"][index]["confirmation_audit"]["informative"] = True
        report.validate_seed(runs[11], 11, CONFIG)
        later_rules = report.derive_rules(runs, CONFIG, summary)
        self.assertNotEqual(decisions(initial_rules), decisions(later_rules))
        after = report.cycle_record(runs[11], "static", 0, later_rules)
        self.assertEqual(before, after)
        self.assertEqual(after["keep_revert_revise"], online["keep_revert_revise"])

    def test_fallback_is_retrospective_and_incomplete_online_report_rejected(self):
        runs, summary = fixture()
        rules = report.derive_rules(runs, CONFIG, summary)
        cycle_record = report.cycle_record(runs[11], "static", 0, rules)
        self.assertEqual(cycle_record["keep_revert_revise"]["timing"], "retrospective final-study decision")
        self.assertEqual(cycle_record["updated_rule"]["timing"], "retrospective final-study decision")
        runs[11]["arms"]["static"]["cycles"][0]["online_report"] = {"result": {}}
        with self.assertRaisesRegex(ValueError, "incomplete online"):
            report.validate_seed(runs[11], 11, CONFIG)

    def test_missing_results_remain_unknown_and_configuration_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs, summary = report.load_results(temporary, CONFIG)
            self.assertTrue(all(r["status"] == "missing" for r in runs.values()))
            text, rules = report.render_report(runs, CONFIG, summary)
            self.assertIn("unknown/incomplete", text)
            self.assertTrue(all(r["decision"] == "UNKNOWN" for r in rules["rules"]))
            run = fixture()[0][11]
            run["config"]["cycles"] = 4
            (Path(temporary) / "seed11.json").write_text(json.dumps(run))
            with self.assertRaisesRegex(ValueError, "committed protocol"):
                report.load_results(temporary, CONFIG)


if __name__ == "__main__":
    unittest.main()
