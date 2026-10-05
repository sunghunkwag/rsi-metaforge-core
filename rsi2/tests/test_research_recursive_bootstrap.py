import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.research import recursive_bootstrap as rb
from rsi2.research.diagnostics import audit_candidate
from rsi2.research.heuristic_proposals import HeuristicProposalProvider
from rsi2.types import Arrow, INT


def config():
    result = copy.deepcopy(rb.REGISTERED_CONFIG)
    result.update(dreams=0)
    return result


def tasks(known=3):
    result = []
    for index in range(4):
        shift = 0 if index < known else 1
        result.append(Task(f"task{index}", Arrow(INT, INT),
                           (((index,), index + shift), ((index + 2,), index + 2 + shift)),
                           (((index + 7,), index + 7 + shift),)))
    return result


class Provider:
    def __init__(self, terms):
        self.terms, self.calls, self.last_report = list(terms), [], {}

    def draw(self, state, supplied):
        self.calls.append((state.arm, state.generation))
        self.last_report = {"work": {"frontier_pops": 10, "generated_full_candidates": 7,
                                     "replayed_ast_draws": 3, "normalization_steps": 5,
                                     "beta_reductions": 2}}
        return [{"index": index, "term": self.terms[index] if index < len(self.terms) else None,
                 "origin": "enumeration" if index < 4 else "mutation",
                 "mutation_path": None, "rejection": None if index < len(self.terms) else "unavailable"}
                for index in range(6)]


class PublicKernelFactory:
    """A synthetic public-only kernel for controller causality/accounting tests.

    All returned programs and the guide are emitted by existing own-language
    enumeration. Its deliberately tiny scheduler isolates controller wiring;
    the real population kernel's causal search tests live in its own suite.
    """
    def __init__(self, identity, successor, guide, *, loss=False, extra_guides=()):
        self.identity, self.successor, self.guide = identity, successor, guide
        self.loss, self.extra_guides = loss, tuple(extra_guides)
        self.calls, self.instances = [], 0

    def __call__(self):
        self.instances += 1
        instance = self.instances

        def solve(examples, request_type, budget, grammar, *, bank, heuristic, seed, limits):
            self.calls.append({"instance": instance, "examples": examples, "budget": budget,
                               "library": dict(grammar.library), "weights": dict(grammar.weights),
                               "contexts": copy.deepcopy(grammar.context_weights), "bank": bank,
                               "heuristic": heuristic, "seed": seed, "limits": limits})
            known = all(arguments[0] == expected for arguments, expected in examples)
            guided = heuristic == self.guide or heuristic in self.extra_guides
            term = self.identity if known and not (guided and self.loss) else (
                self.successor if not known and guided else None)
            calls = steps = 0
            if term is not None:
                for arguments, _ in examples:
                    result = evaluate(term, arguments, library=grammar.library,
                                      step_budget=limits["step_budget"])
                    calls += 1
                    steps += result.steps
            return {"term": term, "candidates": 1, "log_probability": 0.0,
                    "evaluator_calls": calls, "evaluation_steps": steps,
                    "expansions": 2, "heuristic_calls": 0, "heuristic_evaluations": 0,
                    "heuristic_steps": 0, "termination": "synthetic_public_search"}
        return solve


class RecursiveBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        iterator = enumerate_programs(Arrow(INT, INT), Grammar(), max_size=12, max_expansions=20000)
        cls.identity = next(c.term for c in iterator
                            if all(evaluate(c.term, (x,)).value == x for x in (-3, 0, 5)))
        iterator = enumerate_programs(Arrow(INT, INT), Grammar(), max_size=12, max_expansions=20000)
        cls.successor = next(c.term for c in iterator
                             if all(evaluate(c.term, (x,)).value == x + 1 for x in (-3, 0, 5)))
        records = HeuristicProposalProvider().draw(rb.RecursiveState(11, "FULL"), config())
        cls.guide = next(r["term"] for r in records if r["term"] is not None
                         and audit_candidate(r["term"], {})["valid"]
                         and audit_candidate(r["term"], {})["informative"])
        cls.invalid = next(r["term"] for r in records if r["term"] is not None
                           and not audit_candidate(r["term"], {})["valid"])

    def factory(self, **kwargs):
        return PublicKernelFactory(self.identity, self.successor, self.guide, **kwargs)

    def test_verified_scorer_is_automatically_used_in_next_wake(self):
        factory, provider = self.factory(), Provider([self.guide])
        record = rb.run_arm(tasks(), 11, "FULL", config(), kernel_factory=factory,
                            proposal_provider=provider, through_generation=2)
        self.assertEqual(record["status"], "partial")
        initial, first, second = record["generations"]
        self.assertEqual(first["wake"]["solved"], 3)
        self.assertTrue(first["heuristic"]["adopted"])
        self.assertEqual(second["wake"]["solved"], 4)
        self.assertEqual(second["same_state_zero"]["solved"], 3)
        self.assertEqual(second["wake"]["heuristic"], self.guide)
        self.assertEqual(record["final_state"]["heuristic"], self.guide)
        self.assertEqual(len(initial["state"]["raw_solutions"]), 3)
        self.assertEqual(len(first["state"]["raw_solutions"]), 3)
        self.assertEqual(len(second["state"]["raw_solutions"]), 4)
        self.assertEqual(len(second["bank_records"]), 3)
        self.assertEqual(factory.instances, len(factory.calls))
        self.assertEqual(record["original_a_e"], "NOT ASSESSED")

    def test_all_previous_labels_have_proof_and_within_wake_bank_is_fixed(self):
        record = rb.run_arm(tasks(), 11, "NO_HEURISTIC", config(), kernel_factory=self.factory(),
                            proposal_provider=Provider([]), through_generation=1)
        first = record["generations"][1]
        self.assertEqual(len(first["bank_records"]), 3)
        self.assertTrue(all("g0:" in name for name in first["bank_records"]))
        self.assertEqual(first["wake"]["bank_records"], first["bank_records"])
        for evidence in first["state"]["acceptance_records"].values():
            self.assertTrue(evidence["verification"]["passed"])
        self.assertTrue(first["learning"]["dreams_never_compression_or_verified_bank_labels"])
        self.assertEqual(record["final_state"]["raw_solutions"], record["generations"][0]["state"]["raw_solutions"])

    def test_more_solved_tasks_cannot_hide_loss_of_an_incumbent_task(self):
        state = rb.RecursiveState(11, "FULL", generation=1)
        report = rb.improve(state, tasks(known=1), config(), self.factory(loss=True),
                            Provider([self.guide]), rb.CpuGuard(600), rb._work())
        self.assertEqual(report["incumbent_full"]["solved"], 1)
        self.assertEqual(report["candidates"][0]["full"]["solved"], 3)
        self.assertFalse(report["adopted"])
        self.assertEqual(state.heuristic, zero_heuristic())

    def test_invalid_proposals_are_screened_but_do_not_starve_confirmation(self):
        state = rb.RecursiveState(11, "FULL", generation=1)
        factory = self.factory(extra_guides=(self.invalid,))
        report = rb.improve(state, tasks(), config(), factory,
                            Provider([self.invalid, self.guide]), rb.CpuGuard(600), rb._work())
        invalid, valid = report["candidates"][:2]
        self.assertIsNotNone(invalid["screen"])
        self.assertIsNone(invalid["full"])
        self.assertEqual(invalid["rejection"], "invalid_or_uninformative")
        self.assertTrue(valid["adopted"])
        self.assertEqual(report["adopted_index"], 1)

    def test_constant_proxy_gain_never_adopts_a_scorer(self):
        state = rb.RecursiveState(11, "FULL", generation=1)
        factory = self.factory(extra_guides=(zero_heuristic(),))
        report = rb.improve(state, tasks(), config(), factory,
                            Provider([zero_heuristic()]), rb.CpuGuard(600), rb._work())
        self.assertFalse(report["adopted"])
        candidate = report["candidates"][0]
        self.assertEqual(candidate["screen"]["solved"], 4)
        self.assertFalse(candidate["semantic_probe"]["informative"])
        self.assertIsNone(candidate["full"])

    def test_oneshot_reuses_postlearning_measurement_and_freezes_learning(self):
        provider = Provider([self.guide])
        record = rb.run_arm(tasks(), 11, "ONESHOT", config(), kernel_factory=self.factory(),
                            proposal_provider=provider, through_generation=3)
        rows = record["generations"]
        self.assertEqual(rows[1]["wake"]["solved"], 3)
        self.assertEqual(rows[1]["heuristic"]["best_full"]["solved"], 4)
        self.assertEqual(rows[2]["wake"]["solved"], 4)
        self.assertEqual(rows[2]["wake"], rows[1]["heuristic"]["best_full"])
        self.assertEqual(rows[2]["reuse_source_phase"], "heuristic.best_full")
        self.assertTrue(rows[3]["reused_measurement"])
        self.assertEqual(rows[2]["work"], rb._work())
        self.assertEqual(provider.calls, [("ONESHOT", 1)])
        self.assertEqual(rows[1]["state"]["raw_solutions"], rows[3]["state"]["raw_solutions"])

    def test_ablation_state_is_independent_and_disabled_component_is_absent(self):
        for arm in ("NO_LIBRARY", "NO_RECOGNITION", "NO_HEURISTIC"):
            with self.subTest(arm=arm):
                provider = Provider([self.guide])
                record = rb.run_arm(tasks(), 11, arm, config(), kernel_factory=self.factory(),
                                    proposal_provider=provider, through_generation=1)
                state = record["final_state"]
                if arm == "NO_LIBRARY":
                    self.assertEqual(state["library"], {})
                    self.assertIsNone(record["generations"][1]["learning"]["compression"])
                elif arm == "NO_RECOGNITION":
                    self.assertIsNone(state["recognition"])
                    self.assertIsNone(record["generations"][1]["learning"]["recognition"])
                else:
                    self.assertEqual(state["heuristic"], zero_heuristic())
                    self.assertEqual(provider.calls, [])

    def test_base_and_brute_freeze_initial_state_and_charge_actual_work_once(self):
        for arm, budget in (("BASE", 64), ("BRUTE640", 640)):
            with self.subTest(arm=arm):
                factory, provider = self.factory(), Provider([self.guide])
                record = rb.run_arm(tasks(), 11, arm, config(), kernel_factory=factory,
                                    proposal_provider=provider, through_generation=8)
                self.assertEqual(record["status"], "complete")
                self.assertEqual(len(record["generations"]), 9)
                self.assertEqual(len(factory.calls), 4)
                self.assertTrue(all(c["budget"] == budget and c["bank"] == () for c in factory.calls))
                self.assertEqual(record["work"]["task_candidates"], 4)
                self.assertEqual(provider.calls, [])
                self.assertEqual(record["final_state"]["grammar_weights"], {})
                self.assertIsNone(record["final_state"]["recognition"])

    def test_provider_telemetry_and_all_completed_work_reconcile(self):
        record = rb.run_arm(tasks(), 11, "FULL", config(), kernel_factory=self.factory(),
                            proposal_provider=Provider([self.guide]), through_generation=2)
        work = record["work"]
        self.assertEqual(work["proposal_frontier_pops"], 20)
        self.assertEqual(work["proposal_raw_terms"], 14)
        self.assertEqual(work["proposal_replayed_terms"], 6)
        self.assertEqual(work["proposal_normalization_steps"], 10)
        self.assertEqual(work["proposal_beta_reductions"], 4)
        self.assertEqual(work["proposal_slots"], 12)
        for field in rb.WORK_FIELDS:
            self.assertEqual(work[field], sum(row["work"][field] for row in record["generations"]))
        for row in record["generations"]:
            self.assertEqual(len(row["online_report"]), 11)

    def test_history_snapshots_do_not_change_with_future_state(self):
        state = rb.RecursiveState(11, "FULL")
        state.raw_solutions["a"] = self.identity
        state.acceptance_records["a"] = {"id": "TRAIN:a:g0", "nested": [1]}
        snapshot = rb.state_record(state)
        state.raw_solutions["b"] = self.successor
        state.acceptance_records["a"]["nested"].append(2)
        state.heuristic_history.append({"generation": 1})
        self.assertEqual(set(snapshot["raw_solutions"]), {"a"})
        self.assertEqual(snapshot["acceptance_records"]["a"]["nested"], [1])
        self.assertEqual(snapshot["heuristic_history"], [])

    def test_cpu_stop_between_search_and_proof_preserves_truthful_checkpoint(self):
        class Guard:
            def __init__(self):
                self.calls = 0

            def remaining(self):
                return 600

            def check(self):
                self.calls += 1
                if self.calls >= 3:
                    raise rb.CpuStop()

        snapshots = []
        record = rb.run_arm(tasks(), 11, "FULL", config(), kernel_factory=self.factory(),
                            proposal_provider=Provider([self.guide]), through_generation=1,
                            guard=Guard(), checkpoint=lambda r: snapshots.append(copy.deepcopy(rb.jsonable(r))))
        self.assertEqual(record["status"], "partial")
        self.assertEqual(record["generations"], [])
        self.assertEqual(record["work"]["task_candidates"], 1)
        self.assertEqual(record["work"]["verification_programs"], 0)
        pending = record["in_progress"]["wake"]
        self.assertEqual(pending["tasks_completed"], 0)
        self.assertIsNone(pending["records"][0]["solved"])
        self.assertEqual(pending["in_progress"]["stage"], "independent_verification")
        self.assertEqual(record["final_state"]["raw_solutions"], {})
        self.assertEqual(record["candidate_evaluations_scope"], "completed_operations_lower_bound")
        self.assertGreater(len(snapshots), 2)

    def test_hidden_failure_never_becomes_a_bank_or_learning_label(self):
        supplied = tasks()
        original = supplied[0]
        supplied[0] = Task(original.name, original.request_type, original.examples, (((7,), 999),))
        record = rb.run_arm(supplied, 11, "NO_HEURISTIC", config(), kernel_factory=self.factory(),
                            proposal_provider=Provider([]), through_generation=1)
        self.assertNotIn(original.name, record["final_state"]["raw_solutions"])
        self.assertNotIn(original.name, record["generations"][1]["learning"]["real_learning_labels"])
        self.assertFalse(record["generations"][0]["wake"]["records"][0]["solved"])

    def test_no_partition_loader_is_used_by_controller_api(self):
        with patch("rsi2.corpus.load_train", side_effect=AssertionError("loader forbidden")), \
                patch("rsi2.corpus.load_validation", side_effect=AssertionError("loader forbidden")):
            record = rb.run_arm(tasks(), 11, "BASE", config(), kernel_factory=self.factory(),
                                proposal_provider=Provider([]), through_generation=0)
        self.assertEqual(record["status"], "partial")
        self.assertFalse(record["evaluation_partitions_opened"])

    def test_atomic_checkpoint_keeps_all_fields_and_actual_ast_serialization(self):
        record = rb.run_arm(tasks(), 11, "BASE", config(), kernel_factory=self.factory(),
                            proposal_provider=Provider([]), through_generation=0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.json"
            rb.atomic_write(path, record)
            restored = json.loads(path.read_text())
            self.assertEqual(restored, rb.jsonable(record))
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_real_population_and_provider_contract_write_synthetic_checkpoints(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.json"
            record = rb.run_arm(tasks(known=4), 11, "BASE", config(), through_generation=0,
                                checkpoint=lambda r: rb.atomic_write(path, r))
            self.assertEqual(json.loads(path.read_text()), rb.jsonable(record))
        self.assertEqual(record["generations"][0]["wake"]["status"], "complete")
        self.assertEqual(record["generations"][0]["wake"]["solved"], 4)
        self.assertGreater(record["work"]["task_candidates"], 0)
        self.assertGreater(record["work"]["verification_examples"], 0)
        reported = sum(row["search"]["heuristic_evaluations"]
                       for row in record["generations"][0]["wake"]["records"])
        self.assertEqual(record["work"]["heuristic_evaluations"], reported)
        self.assertEqual(record["final_state"]["heuristic"], zero_heuristic())

    def test_rejects_changed_budget_and_invalid_kernel_accounting(self):
        changed = config()
        changed["B_wake"] = 65
        with self.assertRaisesRegex(ValueError, "frozen"):
            rb.run_arm(tasks(), 11, "FULL", changed, proposal_provider=Provider([]))

        def factory():
            return lambda *args, **kwargs: SimpleNamespace(term=None, candidates=65)

        with self.assertRaisesRegex(ValueError, "candidate budget"):
            rb.run_arm(tasks(), 11, "BASE", config(), kernel_factory=factory,
                       proposal_provider=Provider([]), through_generation=0)


if __name__ == "__main__":
    unittest.main()
