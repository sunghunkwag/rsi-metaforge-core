"""Matched scientific comparisons and actual-work accounting on synthetic data."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from rsi2.research import efficiency_report as report
from rsi2.tests.test_research_report import CONFIG, fixture


SOURCE = "2562f564cb995fd9b6863d1fa4ef3de1d0d27a31"
VERIFICATION = {"baseline_source_commit": SOURCE,
                "exact_reuse": {"status": "passed", "tests": ["tests/test_exact_reuse.py"], "count": 5},
                "exhaustion_certificate": {"status": "passed", "tests": ["tests/test_exhaustion.py"], "count": 4}}


def measurements(value):
    if isinstance(value, dict):
        if "records" in value and "candidate_evaluations" in value and "budget" in value:
            yield value
        else:
            for child in value.values():
                yield from measurements(child)
    elif isinstance(value, list):
        for child in value:
            yield from measurements(child)


def charge(assessment, reuse):
    assessment["cache_hit"] = reuse
    assessment["actual_candidate_evaluations"] = 0 if reuse else assessment["candidate_evaluations"]
    assessment["wall_seconds"] = 0.02 if reuse else 1.0
    for record in assessment["records"]:
        record["wall_seconds"] = 0.01 if reuse else 0.5
        for index, metric in enumerate(report.WORK_METRICS, 1):
            record[metric] = index * 10
        if reuse:
            record.update({"cache_hit": True, "source_budget": assessment["budget"],
                           "requested_budget": assessment["budget"], "reuse_kind": "exact",
                           "source_wall_seconds": 0.5, "actual_wall_seconds": 0.01,
                           "actual_candidate_evaluations": 0})
            for metric in report.WORK_METRICS:
                record[f"actual_{metric}"] = 0
    if reuse:
        for metric in report.WORK_METRICS:
            assessment[f"actual_{metric}"] = 0


def paired_fixture():
    baseline, _ = fixture()
    for seed, run in baseline.items():
        run["status"] = "selection_frozen"
        run["initial_state"] = {"seed": seed, "grammar": {"primitives": {"add": 1, "sub": 2}, "library": {}},
                                "recognition": {"coefficients": [0.25, -0.5]}}
        for assessment in measurements(run):
            charge(assessment, False)
        for arm, target in run["arms"].items():
            cumulative = 0
            for row in target["cycles"]:
                row["incumbent"] = {"tag": "int", "value": 0}
                row["model"]["coefficients"] = [0.25, -0.5, row["cycle"]]
                row["online_report"] = {"decision": "retain incumbent; provisional policy", "prior_labels": row["selection"]["model_trained_count"]}
                row["cpu_seconds"], row["wall_seconds"] = 10.0, 12.0
                cumulative += sum(a["actual_candidate_evaluations"] for a in report._assessments(row))
                row["memory"]["actual_candidate_evaluations"] = cumulative
            target["final_state"] = copy.deepcopy(run["initial_state"])
            target["proposal_memory"] = {"offset": 96, "selected_terms": [{"tag": "int", "value": 1}],
                                         "model": copy.deepcopy(target["cycles"][-1]["model"])}
    effective = copy.deepcopy(baseline)
    for run in effective.values():
        run["source_commit"] = SOURCE
        for assessment in measurements(run):
            charge(assessment, True)
        for target in run["arms"].values():
            for row in target["cycles"]:
                row["cpu_seconds"], row["wall_seconds"] = 2.0, 3.0
                row["memory"].update({"actual_candidate_evaluations": 0, "task_cache_hits": 20,
                                      "entries": 100, "certificates": 10, "exact_hits": 5})
                for metric in report.WORK_METRICS:
                    row["memory"][f"actual_{metric}"] = 0
    return baseline, effective


def compare(baseline, effective, **kwargs):
    kwargs.setdefault("verification", VERIFICATION)
    return report.compare_runs(baseline, effective, CONFIG, **kwargs)


class EfficiencyReportTests(unittest.TestCase):
    def test_only_telemetry_differs_and_all_completed_cycles_match(self):
        baseline, effective = paired_fixture()
        comparison = compare(baseline, effective)
        self.assertEqual(comparison["decision"], "KEEP")
        self.assertEqual(comparison["full_study_equivalence"], "EQUAL")
        self.assertEqual(comparison["totals"]["matched_cycles"], 27)
        self.assertEqual(comparison["totals"]["saved_cpu_seconds"], 27 * 8)
        self.assertGreater(comparison["totals"]["saved_actual_inner_candidates"], 0)
        self.assertTrue(all(p["secondary_saved_work"]["heuristic_calls"] > 0
                            for p in comparison["matched_cycles"]))
        self.assertFalse(comparison["differences"])

    def test_candidate_ast_selection_coefficients_and_logical_counts_are_protected(self):
        changes = (("ast", lambda r: r["candidates"][0]["term"].update(value=99), ".term.value"),
                   ("selection", lambda r: r["selected_indices"].reverse(), ".selected_indices"),
                   ("coefficient", lambda r: r["model"]["coefficients"].append(0.0), ".coefficients"),
                   ("logical_evaluator", lambda r: r["candidates"][0]["audit"].update(evaluator_steps=999), ".audit.evaluator_steps"),
                   ("source_heuristic", lambda r: r["incumbent_validation"]["records"][0].update(heuristic_calls=999), ".heuristic_calls"),
                   ("decision", lambda r: r["online_report"].update(decision="adopt"), ".online_report.decision"),
                   ("unknown_field", lambda r: r.update(actual_logical_result="changed"), ".actual_logical_result"))
        for label, mutate, path in changes:
            with self.subTest(label=label):
                baseline, effective = paired_fixture()
                mutate(effective[11]["arms"]["learned"]["cycles"][0])
                comparison = compare(baseline, effective)
                self.assertEqual(comparison["decision"], "REVERT")
                self.assertTrue(any(path in d["path"] for d in comparison["differences"]))

    def test_partial_baseline_supports_only_observed_prefix(self):
        baseline, effective = paired_fixture()
        expected = 0
        for run in baseline.values():
            run["status"] = "partial"
            for target in run["arms"].values():
                target["cycles"] = target["cycles"][:1]
                expected += target["cycles"][0]["memory"]["actual_candidate_evaluations"]
        comparison = compare(baseline, effective)
        self.assertEqual(comparison["decision"], "KEEP")
        self.assertEqual(comparison["scope"], "observed_matched_prefix")
        self.assertEqual(comparison["full_study_equivalence"], "UNKNOWN")
        self.assertEqual(comparison["totals"]["matched_cycles"], 9)
        self.assertEqual(comparison["totals"]["saved_actual_inner_candidates"], expected)
        self.assertEqual(comparison["totals"]["saved_cpu_seconds"], 9 * 8)
        self.assertTrue(all(c["effective_cycles_without_baseline"] == [2, 3] for c in comparison["coverage"]))
        self.assertIn("full-study equivalence remains UNKNOWN", report.render_report(comparison))

    def test_missing_completed_pairs_or_safety_evidence_are_unknown(self):
        baseline, effective = paired_fixture()
        effective[11]["arms"]["static"]["cycles"].pop()
        comparison = compare(baseline, effective)
        self.assertEqual(comparison["decision"], "UNKNOWN")
        self.assertTrue(any("lack an effective pair" in reason for reason in comparison["unknown_reasons"]))
        baseline, effective = paired_fixture()
        for evidence in (None, {}, {"exact_reuse": {"status": "passed"}, "exhaustion_certificate": {"status": "passed"}}):
            with self.subTest(evidence=evidence):
                comparison = compare(baseline, effective, verification=evidence, baseline_source_commit=SOURCE)
                self.assertEqual(comparison["decision"], "UNKNOWN")
        evidence = copy.deepcopy(VERIFICATION)
        evidence["exhaustion_certificate"]["status"] = "failed"
        self.assertEqual(compare(baseline, effective, verification=evidence)["decision"], "REVERT")

    def test_malformed_actual_counter_cannot_manufacture_a_saved_work_claim(self):
        baseline, effective = paired_fixture()
        baseline[11]["arms"]["original"]["cycles"][0]["memory"]["actual_candidate_evaluations"] += 100
        with self.assertRaisesRegex(ValueError, "cumulative memory delta disagrees"):
            compare(baseline, effective)
        baseline, effective = paired_fixture()
        effective[11]["arms"]["static"]["cycles"][0]["incumbent_validation"]["actual_candidate_evaluations"] = 100
        with self.assertRaisesRegex(ValueError, "per-task cache evidence"):
            compare(baseline, effective)

    def test_config_and_duplicate_cycle_identities_are_rejected(self):
        baseline, effective = paired_fixture()
        effective[11]["config"] = copy.deepcopy(CONFIG)
        effective[11]["config"]["search"]["max_size"] = 13
        with self.assertRaisesRegex(ValueError, "scientific protocol"):
            compare(baseline, effective)
        baseline, effective = paired_fixture()
        effective[11]["arms"]["static"]["cycles"][1]["cycle"] = 1
        with self.assertRaisesRegex(ValueError, "unique"):
            compare(baseline, effective)

    def test_source_attestation_and_terminal_state_changes_are_detected(self):
        baseline, effective = paired_fixture()
        self.assertEqual(compare(baseline, effective, verification=None)["decision"], "UNKNOWN")
        effective[11]["source_commit"] = "0" * 40
        comparison = compare(baseline, effective)
        self.assertEqual(comparison["decision"], "REVERT")
        baseline, effective = paired_fixture()
        effective[22]["arms"]["learned"]["proposal_memory"]["model"]["coefficients"][0] = 9.0
        self.assertEqual(compare(baseline, effective)["decision"], "REVERT")
        baseline, effective = paired_fixture()
        primitives = effective[33]["initial_state"]["grammar"]["primitives"]
        effective[33]["initial_state"]["grammar"]["primitives"] = dict(reversed(list(primitives.items())))
        self.assertTrue(any(d["reason"] == "executable insertion order differs"
                            for d in compare(baseline, effective)["differences"]))

    def test_no_saved_work_is_revise_and_zero_candidate_heuristic_work_is_visible(self):
        baseline, effective = paired_fixture()
        effective = copy.deepcopy(baseline)
        for run in effective.values():
            run["source_commit"] = SOURCE
        comparison = compare(baseline, effective)
        self.assertEqual(comparison["decision"], "REVISE")
        self.assertEqual(comparison["totals"]["saved_actual_inner_candidates"], 0)
        row = baseline[11]["arms"]["original"]["cycles"][0]
        for assessment in report._assessments(row):
            assessment["candidate_evaluations"] = assessment["actual_candidate_evaluations"] = 0
            for record in assessment["records"]:
                record["candidates"] = 0
        self.assertEqual(report._operation_candidates(row), 0)
        self.assertGreater(report._operation_work(row)["heuristic_calls"], 0)

    def test_audit_is_outside_comparison_and_all_eleven_intervention_fields_exist(self):
        baseline, effective = paired_fixture()
        before = compare(baseline, effective)
        for run in effective.values():
            for target in run["arms"].values():
                target["audit"] = {"sensitive_reporting_only_outcome": "not read"}
                target["training"] = {"post_freeze_outcome": "not read"}
                for row in target["cycles"]:
                    row["audit_productivity"] = {"sensitive_reporting_only_outcome": "not read"}
        after = compare(baseline, effective)
        self.assertEqual(before, after)
        record = report.intervention_record(after)
        self.assertEqual(set(record), set(report.CYCLE_FIELDS))
        self.assertIn("not establish better solver capability", report.render_report(after))

    def test_loader_excludes_reporting_outcomes_and_whitelist_is_explicit(self):
        baseline, _ = paired_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "seed11.json").write_text(json.dumps(baseline[11]))
            loaded = report.load_seed_files(temporary, CONFIG["seeds"])
            target = loaded[11]["arms"]["original"]
            self.assertNotIn("audit", target)
            self.assertNotIn("training", target)
            self.assertNotIn("audit_productivity", target["cycles"][0])
        value = {"actual_candidate_evaluations": 10, "actual_unrecognized_science": 4,
                 "candidate_evaluations": 10, "evaluation_steps": 50, "heuristic_steps": 30}
        logical = report.logical_record(value)
        self.assertNotIn("actual_candidate_evaluations", logical)
        self.assertEqual(logical["actual_unrecognized_science"], 4)
        self.assertEqual(logical["candidate_evaluations"], 10)
        self.assertEqual(logical["evaluation_steps"], 50)


if __name__ == "__main__":
    unittest.main()
