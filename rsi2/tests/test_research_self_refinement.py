"""Live synthetic checks of diagnosis, counterfactual admission and self-application."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.learning import State
from rsi2.research import memory, self_refinement as refinement
from rsi2.research.efficient_memory import EfficientEvaluationMemory
from rsi2.types import Arrow, INT, PRIMITIVE_TYPES


SEARCH = {"max_size": 1, "max_expansions": 20, "step_budget": 2000}


def _state(seed, only_negative=False):
    names = ("neg",) if only_negative else ("neg", "abs")
    return State(seed, grammar=Grammar(primitives={n: PRIMITIVE_TYPES[n] for n in names},
                                      constants=()), heuristic=zero_heuristic())


def _task(name):
    return Task(name, Arrow(INT, INT), (((2,), 2),), (((-3,), 3),))


def _proof(certificates=True):
    proof = {"status": "passed", "count": 1,
             "tests": ["rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_live_multitask_decomposition_equals_original_assessment"]}
    result = {"exact_reuse": proof}
    if certificates:
        result["exhaustion_certificate"] = {"status": "passed", "count": 1,
            "tests": ["rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_completed_failed_space_certificate_equals_direct_higher_budget"]}
    return result


def _fixture(only_negative=False):
    states = {seed: _state(seed, only_negative) for seed in refinement.SEEDS}
    tasks = [_task("first"), _task("second")]
    history, cases = [], {}
    for seed, state in states.items():
        cases[seed] = []
        for group in (tasks[:1], tasks):
            report = memory.assess(group, state.grammar, state.heuristic, 2, SEARCH)
            history.append({"seed": seed, "scope": memory.scope(state, group, state.heuristic, 2, SEARCH),
                            "measurement": report})
            cases[seed].append({"state": state, "tasks": group, "heuristic": state.heuristic,
                                "budget": 2, "searchconfig": SEARCH})
    return history, cases


class SelfRefinementTests(unittest.TestCase):
    def test_observed_overlap_drives_proposal_and_skips_aliases_and_hits(self):
        history, _ = _fixture()
        alias = {**copy.deepcopy(history[0]), "alias": True}
        hit = copy.deepcopy(history[0])
        hit["measurement"]["cache_hit"] = True
        coordinator = refinement.Coordinator(history + [alias, hit], _proof())
        diagnosis = coordinator.diagnose()
        self.assertEqual(diagnosis["actual_group_calls"], 6)
        self.assertEqual(diagnosis["repeated_per_task_scopes"], 3)
        self.assertEqual(len(diagnosis["repeated_evidence"]), 3)
        self.assertTrue(coordinator.propose()["available"])
        self.assertFalse(coordinator.active)

    def test_missing_proofs_or_missing_history_never_activate(self):
        history, cases = _fixture()
        for supplied in ({}, {"exact_reuse": {"status": "passed", "count": 1, "tests": []}}):
            coordinator = refinement.Coordinator(history, supplied)
            coordinator.propose()
            with patch.object(memory.EvaluationMemory, "measure", side_effect=AssertionError("missing proof must not execute")):
                result = coordinator.verify(cases)
            self.assertEqual(result["decision"], "UNKNOWN")
            coordinator.preserve()
            self.assertIsInstance(coordinator.nextmemory(11), memory.EvaluationMemory)
        empty = refinement.Coordinator([], _proof())
        self.assertFalse(empty.propose()["available"])
        self.assertEqual(empty.verify(cases)["decision"], "UNKNOWN")

    def test_live_all_seed_verification_then_preservation_changes_next_factory(self):
        history, cases = _fixture()
        coordinator = refinement.Coordinator(history, _proof())
        coordinator.propose()
        progress = []
        result = coordinator.verify(cases, progress=lambda row: progress.append(row))
        self.assertEqual([len(row["paired_seeds"]) for row in progress], [1, 2, 3])
        self.assertTrue(all(row["decision"] == "UNKNOWN" for row in progress))
        self.assertEqual(result["decision"], "KEEP")
        self.assertIsInstance(coordinator.nextmemory(11), memory.EvaluationMemory)
        cycle = coordinator.preserve(1)
        self.assertTrue(coordinator.active)
        self.assertTrue(set(refinement.FIELDS) <= cycle.keys())
        self.assertFalse(coordinator.certificates)
        first, second = coordinator.nextmemory(11), coordinator.nextmemory(11)
        self.assertIsInstance(first, EfficientEvaluationMemory)
        state = cases[11][0]["state"]
        a = first.measure(state, [_task("fresh")], state.heuristic, 2, SEARCH)
        b = second.measure(state, [_task("fresh")], state.heuristic, 2, SEARCH)
        self.assertEqual(a["actual_candidate_evaluations"], 2)
        self.assertEqual(b["actual_candidate_evaluations"], 0)
        self.assertTrue(b["cache_hit"])
        for pair in result["paired_seeds"]:
            self.assertTrue(pair["scientific_equal"])
            self.assertTrue(pair["no_work_increase"])
            self.assertTrue(pair["strict_work_saving"])
            self.assertEqual(pair["actual_work"]["original"]["candidate_evaluations"], 6)
            self.assertEqual(pair["actual_work"]["candidate"]["candidate_evaluations"], 4)

    def test_all_seed_presence_and_actual_seed_binding_are_required(self):
        history, cases = _fixture()
        coordinator = refinement.Coordinator(history, _proof())
        coordinator.propose()
        missing = {seed: case for seed, case in cases.items() if seed != 33}
        self.assertEqual(coordinator.verify(missing)["decision"], "UNKNOWN")
        mismatched = copy.deepcopy(cases)
        mismatched[33][0]["state"].seed = 11
        with patch.object(memory.EvaluationMemory, "measure", side_effect=AssertionError("bad seed must not run")):
            result = coordinator.verify(mismatched)
        self.assertEqual(result["decision"], "UNKNOWN")
        coordinator.preserve()
        self.assertFalse(coordinator.active)

    def test_zero_saving_or_one_seed_without_saving_does_not_activate(self):
        history, cases = _fixture()
        for all_seeds in (False, True):
            adjusted = copy.deepcopy(cases)
            for seed in refinement.SEEDS if all_seeds else (33,):
                adjusted[seed][1]["tasks"] = [_task("disjoint")]
            coordinator = refinement.Coordinator(history, _proof())
            coordinator.propose()
            result = coordinator.verify(adjusted)
            self.assertEqual(result["decision"], "REVISE")
            coordinator.preserve()
            self.assertFalse(coordinator.active)

    def test_scientific_difference_and_work_regression_reject_even_with_savings(self):
        history, cases = _fixture()
        real = EfficientEvaluationMemory.measure
        for corruption in ("scientific", "work"):
            def altered(backend, *args, **kwargs):
                result = real(backend, *args, **kwargs)
                if corruption == "scientific":
                    result["records"][0]["evaluation_steps"] += 1
                else:
                    result["actual_heuristic_steps"] += 1
                return result
            coordinator = refinement.Coordinator(history, _proof())
            coordinator.propose()
            with patch.object(EfficientEvaluationMemory, "measure", altered):
                result = coordinator.verify(cases)
            self.assertEqual(result["decision"], "REVERT")
            coordinator.preserve()
            self.assertIsInstance(coordinator.nextmemory(11), memory.EvaluationMemory)

    def test_next_cycle_applies_rule_and_reverts_on_transfer_difference(self):
        history, cases = _fixture()
        coordinator = refinement.Coordinator(history, _proof())
        coordinator.propose()
        coordinator.verify(cases)
        first = coordinator.preserve(1)
        frozen_first = copy.deepcopy(first)
        real = EfficientEvaluationMemory.measure
        def different(backend, *args, **kwargs):
            report = real(backend, *args, **kwargs)
            report["records"][0]["verification_steps"] += 1
            return report
        with patch.object(EfficientEvaluationMemory, "measure", different):
            result = coordinator.verify(cases, next_cycle=True)
        self.assertEqual(result["active_backend_during_cycle"], "shared_per_task")
        self.assertTrue(all(pair["backend"] == "EfficientEvaluationMemory" for pair in result["paired_seeds"]))
        self.assertEqual(result["decision"], "REVERT")
        coordinator.preserve(2)
        self.assertFalse(coordinator.active)
        self.assertEqual(coordinator.cycles[0], frozen_first)
        self.assertIsInstance(coordinator.nextmemory(11), memory.EvaluationMemory)

    def test_certificate_requires_patterns_proof_and_actual_task_specific_reuse(self):
        history, cases = _fixture(only_negative=True)
        for seed in refinement.SEEDS:
            cases[seed][1] = {**cases[seed][0], "budget": 9}
        coordinator = refinement.Coordinator(history, _proof())
        proposal = coordinator.propose()
        self.assertTrue(proposal["certificate_hypothesis"])
        self.assertGreater(proposal["diagnosis"]["early_termination_patterns"], 0)
        result = coordinator.verify(cases)
        self.assertEqual(result["decision"], "KEEP")
        self.assertTrue(result["certificate_verified"])
        coordinator.preserve()
        self.assertTrue(coordinator.certificates)
        without = refinement.Coordinator(history, _proof(certificates=False))
        self.assertFalse(without.propose()["certificate_hypothesis"])
        self.assertEqual(without.verify(cases)["decision"], "REVISE")

    def test_factored_contexts_are_copy_isolated_and_conflicting_refs_rejected(self):
        history, cases = _fixture()
        coordinator = refinement.Coordinator(history, _proof())
        compact = coordinator.to_dict()
        self.assertTrue(compact["contexts"])
        self.assertTrue(all("grammar" not in call["scope"] for call in compact["history"]))
        compact["contexts"][next(iter(compact["contexts"]))]["grammar"]["weights"]["abs"] = 999
        coordinator.propose()
        self.assertEqual(coordinator.verify(cases)["decision"], "KEEP")
        altered = copy.deepcopy(history[:2])
        for call in altered:
            call["scope"]["state_ref"] = "same"
        altered[1]["scope"]["grammar"]["weights"]["abs"] = 999
        with self.assertRaisesRegex(ValueError, "different frozen context"):
            refinement.Coordinator(altered, _proof())

    def test_scientific_comparator_does_not_ignore_unknown_or_type_fields(self):
        sample = {"records": [{"solved": True, "evaluation_steps": 3}], "tasks": 1}
        changed = copy.deepcopy(sample)
        changed["records"][0]["evaluation_steps"] = 3.0
        self.assertNotEqual(refinement._key(refinement.scientific(sample)),
                            refinement._key(refinement.scientific(changed)))
        changed = {**sample, "actual_unregistered_claim": 99}
        self.assertIn("actual_unregistered_claim", refinement.scientific(changed))

    def test_registered_loop_durably_admits_before_next_partition_and_self_applies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "new"
            source.mkdir()
            proof_path = root / "proof.json"
            proof_path.write_text(json.dumps(_proof()))
            limits = {"max_size": 12, "max_expansions": 20000, "step_budget": 2000}
            validation = [_task(f"v{i:02}") for i in range(12)]
            confirmation = [_task(f"c{i:02}") for i in range(6)]
            before = {}
            for seed in refinement.SEEDS:
                state = _state(seed)
                initial = memory.snapshot(state)
                measured = memory.assess(validation, state.grammar, state.heuristic, 64, limits)
                row = {"cycle": 1, "incumbent": state.heuristic.to_dict(),
                       "incumbent_validation": measured, "candidates": []}
                artifact = {"initial_state": initial, "config": {"search": limits}, "arms": {
                    arm: {"cycles": [row], "final_state": initial} for arm in ("original", "static")}}
                path = source / f"seed{seed}.json"
                before[path] = json.dumps(artifact)
                path.write_text(before[path])
            protocol = {"schema_version": 1, "id": "autonomous_evaluation_refinement",
                        "seeds": list(refinement.SEEDS), "B_eval": 64, "search": limits,
                        "cpu_limit_seconds": 300, "source_results": str(source),
                        "verification": str(proof_path), "cycles": [
                            {"cycle": 1, "partition": "validation", "prefix_tasks": 4, "full_tasks": 12},
                            {"cycle": 2, "partition": "confirmation", "prefix_tasks": 3, "full_tasks": 6}]}
            def after_admission():
                saved = json.loads((output / "self_refinement.json").read_text())
                self.assertEqual(saved["status"], "admission_saved")
                self.assertTrue(saved["coordinator"]["active"])
                self.assertEqual(len(saved["coordinator"]["cycles"]), 1)
                return confirmation
            with patch.object(refinement, "load_validation", return_value=validation), \
                 patch.object(refinement, "load_confirmation", side_effect=after_admission):
                result = refinement.run(protocol, output)
            self.assertEqual(result["status"], "complete")
            cycles = result["coordinator"]["cycles"]
            self.assertEqual(len(cycles), 2)
            self.assertEqual([cycle["keep_revert_revise"] for cycle in cycles], ["KEEP", "KEEP"])
            self.assertEqual(cycles[1]["result"]["active_backend_during_cycle"], "shared_per_task")
            self.assertTrue(all(set(refinement.FIELDS) <= cycle.keys() for cycle in cycles))
            self.assertNotIn("contexts", result["coordinator"])
            self.assertEqual(result["coordinator"]["context_registry"], "initial_states")
            refs = set(result["initial_states"])
            self.assertEqual(refs, set(result["coordinator"]["context_refs"]))
            for cycle in cycles:
                for pair in cycle["result"]["paired_seeds"]:
                    for call in pair["calls"]:
                        self.assertIn(call["scope"]["state_ref"], refs)
                        self.assertNotIn("grammar", call["scope"])
                        self.assertNotIn("recognition", call["scope"])
            self.assertTrue(all(call["scope"]["state_ref"] in refs
                                for call in result["coordinator"]["history"]))
            for path, original in before.items():
                self.assertEqual(path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
