"""Raw-only reports must preserve costs, failures and evidence boundaries."""
import ast
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.research import bootstrap_report as report


IDENTITY = {"tag": "lam", "value": {"tag": "int", "args": []},
            "children": [{"tag": "var", "value": 0, "children": []}]}


def artifact(method="enumeration", budget=64, seed=11, solved=(0,), search=None):
    rows = []
    for index in range(36):
        data = {"candidates": budget, "evaluation_steps": 20,
                "evaluator_calls": 2, "expansions": 10, "cpu_seconds": 0.25,
                "wall_seconds": 0.5, "term": IDENTITY if index in solved else None}
        if search is not None:
            data = {**search, "term": IDENTITY if index in solved else None}
        rows.append({"name": f"task{index:02d}", "verified": index in solved,
                     "search": data, "verification_calls": 1 if index in solved else 0,
                     "verification_steps": 7 if index in solved else 0,
                     "verification_failure": None})
    return {"method": method, "budget": budget, "seed": seed, "source": "TRAIN only",
            "status": "complete", "tasks": rows, "cpu_seconds": 17.0, "wall_seconds": 20.0,
            "solutions": {r["name"]: IDENTITY for r in rows if r["verified"]},
            "verified_solved": len(solved), "compression": {"records": [], "library": {}}}


class BootstrapReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def save(self, raw, name, namespace="frozen", compressed=False):
        path = self.root / "bootstrap_results" / namespace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(raw)
        if compressed:
            path = path.with_suffix(path.suffix + ".gz")
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write(text)
        else:
            path.write_text(text)
        return path

    def test_observational_complete_plus_auxiliary_and_verifier_cost_are_preserved(self):
        source = artifact("observational", search={"complete_candidates": 43,
            "auxiliary_candidates": 21, "evaluator_calls": 100, "evaluation_steps": 1000,
            "expansions": 200, "termination": "evaluation_budget", "cpu_seconds": 0.2,
            "language_complete": False})
        cycle = report.build_report([self.save(source, "observational.json")])["cycles"][0]
        totals = cycle["totals"]
        self.assertEqual(totals["logical_program_attempts"]["value"], 36 * 64)
        self.assertEqual(totals["complete_program_attempts"]["value"], 36 * 43)
        self.assertEqual(totals["auxiliary_program_attempts"]["value"], 36 * 21)
        self.assertEqual(totals["total_interpreter_calls"]["value"], 3601)
        self.assertEqual(totals["total_interpreter_steps"]["value"], 36007)
        self.assertEqual(cycle["run_cpu_seconds"], 17.0)
        self.assertAlmostEqual(totals["search_cpu_seconds"]["value"], 7.2)
        self.assertFalse(cycle["tasks"][0]["language_complete"])

    def test_decomposition_helpers_are_not_reported_as_full_roots(self):
        source = artifact("decomposition", search={"candidates": 6, "helper_attempts": 5,
            "head_attempts": 1, "component_attempts": 4, "root_attempts": 1,
            "example_evaluations": 9, "evaluator_steps": 70, "expansions": 10,
            "termination": "candidate_budget"})
        totals = report.build_report([self.save(source, "decomposition.json")])["cycles"][0]["totals"]
        self.assertEqual(totals["logical_program_attempts"]["value"], 216)
        self.assertEqual(totals["complete_program_attempts"]["value"], 36)
        self.assertEqual(totals["auxiliary_program_attempts"]["value"], 180)
        self.assertEqual(totals["search_interpreter_calls"]["value"], 324)
        self.assertEqual(totals["search_interpreter_steps"]["value"], 2520)

    def test_missing_old_instrumentation_remains_unknown_with_known_only_subtotal(self):
        source = artifact(search={"candidates": 64, "evaluation_steps": 20, "exhausted": False})
        source["tasks"][0]["search"]["evaluator_calls"] = 3
        cycle = report.build_report([self.save(source, "old.json", namespace="")])["cycles"][0]
        calls = cycle["totals"]["search_interpreter_calls"]
        self.assertIsNone(calls["value"])
        self.assertEqual(calls["known_subtotal"], 3)
        self.assertEqual(calls["missing_rows"], 35)
        self.assertIsNone(cycle["totals"]["expansions"]["value"])
        self.assertIsNone(cycle["totals"]["search_cpu_seconds"]["value"])
        self.assertIsNone(cycle["totals"]["auxiliary_program_attempts"]["value"])

    def test_gzip_reader_and_writer_emit_replayable_json_and_all_eleven_fields(self):
        result = report.build_report([self.save(artifact(), "baseline.json", compressed=True)])
        paths = report.write_report(result, self.root / "output")
        self.assertEqual(json.loads(paths[0].read_text()), result)
        text = paths[1].read_text()
        self.assertIn("Original criteria a–e remain **FAIL**", text)
        self.assertEqual(set(result["cycles"][0]["eleven_fields"]), set(report.FIELDS))
        for field in report.FIELDS:
            self.assertIn(f"**{field}**", text)
        self.assertFalse(result["rsi_claim"])

    def test_invalid_observational_pilot_is_never_promoted_by_complete_counters(self):
        pilot = self.save(artifact("observational"), "old_observation.json", namespace="")
        current = self.save(artifact("observational"), "new_observation.json")
        cycles = report.build_report([pilot, current])["cycles"]
        indexed = {r["classification"]: r for r in cycles}
        self.assertFalse(indexed["invalid_pre_scope_fix_pilot"]["eligible"])
        self.assertEqual(indexed["invalid_pre_scope_fix_pilot"]["eleven_fields"]["keep_revert_revise"],
                         "EXCLUDE_INVALID_PILOT")
        self.assertTrue(indexed["frozen_development"]["eligible"])

    def test_pilot_baseline_is_not_borrowed_for_missing_frozen_budget(self):
        baseline = self.save(artifact(), "baseline.json", namespace="instrumented")
        alternative = self.save(artifact("stratified", solved=(0, 1)), "alternative.json")
        cycles = report.build_report([baseline, alternative])["cycles"]
        candidate = next(c for c in cycles if c["method"] == "stratified")
        self.assertEqual(candidate["baseline_comparison"]["status"], "unavailable")
        self.assertEqual(candidate["eleven_fields"]["keep_revert_revise"], "UNKNOWN_NO_PAIRED_BASELINE")

    def test_same_count_task_swap_is_a_regression_and_never_an_activated_rule(self):
        paths = [self.save(artifact(solved=(0, 1)), "baseline.json"),
                 self.save(artifact("stratified", solved=(0, 2)), "candidate.json")]
        result = report.build_report(paths)
        cycle = next(r for r in result["cycles"] if r["method"] == "stratified")
        self.assertEqual(cycle["baseline_comparison"]["new_verified_tasks"], ["task02"])
        self.assertEqual(cycle["baseline_comparison"]["lost_verified_tasks"], ["task01"])
        self.assertEqual(cycle["eleven_fields"]["keep_revert_revise"], "REVISE_REGRESSION")
        self.assertEqual(result["activated_rules"], [])

    def test_hidden_failure_partial_run_and_cap_violation_are_retained(self):
        source = artifact()
        source["tasks"][1]["search"].update(term=IDENTITY, candidates=65)
        source["tasks"][1]["verification_failure"] = {"error": "mismatch"}
        source["tasks"][2]["search"].update(termination="cpu_budget", cpu_seconds=10.1)
        source["status"] = "partial_cpu_cap"
        cycle = report.build_report([self.save(source, "partial.json")])["cycles"][0]
        self.assertFalse(cycle["eligible"])
        failures = cycle["eleven_fields"]["failure_clusters"]
        self.assertEqual(failures["selected_verifier_failures"], 1)
        self.assertEqual(failures["reported_search_cpu_above_nominal_cap"], 1)
        self.assertIn("task task01: logical candidate cap exceeded", cycle["alerts"])
        self.assertEqual(cycle["termination_counts"]["cpu_budget"], 1)

    def test_exhausted_is_bounded_stream_end_not_full_space_exhaustion(self):
        source = artifact(search={"candidates": 3, "evaluation_steps": 7, "exhausted": True})
        cycle = report.build_report([self.save(source, "bounded.json")])["cycles"][0]
        self.assertEqual(cycle["tasks"][1]["termination"],
                         "bounded_stream_end_unknown_heap_or_expansion_cap")

    def test_tiny_identity_and_positive_mdl_never_establish_library_or_rsi_gain(self):
        source = artifact()
        source["compression"] = {"records": [{"term_dict": IDENTITY, "delta": 1}],
                                 "library": {"own_identity": IDENTITY}}
        result = report.build_report([self.save(source, "identity.json")])
        compression = result["cycles"][0]["compression"]
        self.assertEqual(compression["identity_macros"], 1)
        self.assertEqual(compression["mdl_delta"], 1)
        self.assertIn("unmeasured", compression["downstream_library_benefit"])
        self.assertEqual(set(result["original_criteria"].values()), {"FAIL"})

    def test_exact_verified_program_support_is_explicit_syntactic_evidence(self):
        source = artifact(solved=(0, 1, 2))
        cycle = report.build_report([self.save(source, "support.json")])["cycles"][0]
        evidence = cycle["verified_program_evidence"]
        self.assertEqual(evidence["unique_exact_ast_count"], 1)
        self.assertEqual(evidence["total_solution_nodes"], 6)
        self.assertEqual(evidence["exact_ast_support"][0]["task_names"], ["task00", "task01", "task02"])
        self.assertTrue(evidence["exact_ast_support"][0]["identity"])
        self.assertIn("Syntactic support only", evidence["scope"])

    def test_explicit_scratch_diagnostics_preserve_novelty_and_scalar_input_bias(self):
        prefix = self.root / "prefix.json"
        prefix.write_text(json.dumps({"failed_request_types": {"list[int] -> int": 6},
            "tasks": [{"name": "one", "first32_unique_signatures": 11,
                       "continued32_new_signatures": 5, "public_matches": 0}]}))
        scalar = self.root / "scalar.json"
        scalar.write_text(json.dumps({"measurements": [{"name": "two", "budget": 640,
            "trials": [{"stage": "component", "term": IDENTITY},
                       {"stage": "component", "term": {"tag": "prim", "value": "neg", "children": []}}]}]}))
        result = report.build_report([], [prefix, scalar])
        self.assertEqual(result["diagnostics"][0]["facts"][0]["continued32_new_signatures"], 5)
        evidence = result["diagnostics"][1]["facts"][0]["component_structural_evidence"]
        self.assertEqual(evidence, {"recorded_components": 2, "lambda_roots": 1, "contains_bound_variable": 1})
        self.assertFalse(result["diagnostics"][0]["scientifically_eligible"])

    def test_ambiguous_baselines_and_conflicting_counter_aliases_fail_closed(self):
        source = artifact("stratified")
        source["tasks"][1]["search"]["logical_evaluations"] = 1
        paths = [self.save(artifact(), "base1.json"), self.save(artifact(), "base2.json"),
                 self.save(source, "bad_counter.json")]
        cycles = report.build_report(paths)["cycles"]
        candidate = next(c for c in cycles if c["method"] == "stratified")
        self.assertFalse(candidate["eligible"])
        self.assertIsNone(candidate["totals"]["logical_program_attempts"]["value"])
        self.assertEqual(candidate["baseline_comparison"]["status"], "unavailable")

    def test_nonbootstrap_input_rejected_before_read_and_module_has_no_task_loader(self):
        with patch.object(report, "_read", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "bootstrap_results"):
                report.build_report([self.root / "data" / "train.json"])
        source = ast.parse(Path(report.__file__).read_text())
        imports = [node.module for node in ast.walk(source) if isinstance(node, ast.ImportFrom)]
        self.assertTrue(all(not name or not any(token in name for token in
            ("corpus", "sealed", "evaluator", "learning", "search")) for name in imports))

    def test_missing_verifier_evidence_prevents_frozen_eligibility(self):
        source = artifact()
        source["tasks"][1].pop("verified")
        source["tasks"][2]["search"].pop("term")
        cycle = report.build_report([self.save(source, "missing_evidence.json")])["cycles"][0]
        self.assertFalse(cycle["eligible"])
        self.assertEqual(cycle["eleven_fields"]["failure_clusters"]["unknown_verifier_rows"], 1)
        self.assertIn("task task02: missing selected-term telemetry", cycle["alerts"])
        self.assertEqual(cycle["guard_evidence"]["search_cpu_observed_rows"], 36)

    def test_nested_scalar_costs_are_preserved_without_double_counting(self):
        source = artifact("stratified_decomposition", search={"candidates": 3,
            "helper_attempts": 2, "head_attempts": 1, "component_attempts": 1,
            "root_attempts": 1, "example_evaluations": 6, "evaluator_steps": 49,
            "scalar_search": {"baseline_attempts": 1, "stratum_attempts": 0, "cpu_seconds": 0.01}})
        cycle = report.build_report([self.save(source, "nested.json")])["cycles"][0]
        self.assertEqual(cycle["tasks"][0]["scalar_search"]["baseline_attempts"], 1)
        self.assertEqual(cycle["totals"]["search_interpreter_calls"]["value"], 36 * 6)
        self.assertEqual(cycle["totals"]["logical_program_attempts"]["value"], 36 * 3)

    def test_missing_trial_and_compression_logs_are_unknown_not_zero(self):
        source = artifact()
        source.pop("compression")
        cycle = report.build_report([self.save(source, "missing_logs.json")])["cycles"][0]
        self.assertIsNone(cycle["tasks"][0]["trials_recorded"])
        self.assertIsNone(cycle["tasks"][0]["trial_failure_evidence"])
        self.assertIsNone(cycle["tasks"][0]["seed_size_evidence"])
        self.assertIsNone(cycle["compression"]["adoptions"])
        self.assertIsNone(cycle["compression"]["identity_macros"])
        self.assertIsNone(cycle["compression"]["mdl_delta"])
        self.assertEqual(cycle["eleven_fields"]["failure_clusters"]["tasks_without_trial_logs"], 36)

    def test_method_budget_summary_requires_all_registered_seeds_and_still_no_activation(self):
        paths = []
        for seed in (11, 22, 33):
            paths += [self.save(artifact(seed=seed), f"baseline{seed}.json"),
                      self.save(artifact("stratified", seed=seed, solved=(0, 1)), f"candidate{seed}.json")]
        partial = report.build_report(paths[:2])
        summary = next(r for r in partial["method_budget_summaries"] if r["method"] == "stratified")
        self.assertEqual(summary["status"], "PENDING_MISSING_REGISTERED_SEEDS")
        complete = report.build_report(paths)
        summary = next(r for r in complete["method_budget_summaries"] if r["method"] == "stratified")
        self.assertEqual(summary["status"], "KEEP_FOR_CAUSAL_TEST_ONLY")
        self.assertEqual(summary["eligible_seeds"], [11, 22, 33])
        self.assertFalse(summary["activated"])
        self.assertEqual(complete["activated_rules"], [])

    def test_pre_live_cap_source_versions_are_quarantined_and_never_a_paired_baseline(self):
        old_baseline = self.save(artifact(budget=640), "old_baseline.json", namespace="pre_live_cap")
        old_bytes = old_baseline.read_bytes()
        candidate = artifact("stratified", budget=640, solved=(0, 1))
        for task in candidate["tasks"]:
            task["search"]["expansion_accounting"] = "live_shared_global_cap_v2"
        new_candidate = self.save(candidate, "corrected_candidate.json")
        result = report.build_report([old_baseline, new_candidate])
        old = next(c for c in result["cycles"] if c["method"] == "enumeration")
        current = next(c for c in result["cycles"] if c["method"] == "stratified")
        self.assertEqual(old["classification"], "invalid_pre_live_cap_pilot")
        self.assertEqual(old["eleven_fields"]["keep_revert_revise"], "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT")
        self.assertFalse(old["eligible"])
        self.assertTrue(old["accounting_provenance"]["quarantined_pre_live_cap"])
        self.assertEqual(old["accounting_provenance"]["version_unknown_rows"], 36)
        self.assertEqual(old_baseline.read_bytes(), old_bytes)
        self.assertTrue(current["eligible"])
        self.assertEqual(current["accounting_provenance"]["reported_expansion_versions"],
                         {"live_shared_global_cap_v2": 36})
        self.assertEqual(current["baseline_comparison"]["status"], "unavailable")
        corrected_baseline = artifact(budget=640)
        for task in corrected_baseline["tasks"]:
            task["search"]["expansion_accounting"] = "live_shared_global_cap_v2"
        new_baseline = self.save(corrected_baseline, "corrected_baseline.json")
        updated = report.build_report([old_baseline, new_candidate, new_baseline])
        current = next(c for c in updated["cycles"] if c["method"] == "stratified")
        self.assertEqual(current["baseline_comparison"]["baseline_path"], str(new_baseline))

    def test_pre_live_cap_quarantine_applies_to_both_stratified_variants_even_with_v2_label(self):
        paths = []
        for method in ("stratified", "stratified_decomposition"):
            raw = artifact(method)
            for task in raw["tasks"]:
                task["search"]["expansion_accounting"] = "live_shared_global_cap_v2"
            paths.append(self.save(raw, f"{method}.json", namespace="pre_live_cap"))
        result = report.build_report(paths)
        for cycle in result["cycles"]:
            self.assertFalse(cycle["eligible"])
            self.assertEqual(cycle["classification"], "invalid_pre_live_cap_pilot")
            self.assertEqual(cycle["eleven_fields"]["updated_rule"]["status"],
                             "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT")


if __name__ == "__main__":
    unittest.main()
