"""Corpus-free causal, persistence and rejection checks for the grouped runner."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.evaluator import evaluate
from rsi2.research import failure_credit_run as runner
from rsi2.research.journal_checkpoint import reconstruct
from rsi2.research.population_search import PopulationResult
from rsi2.terms import Int, Lam, Var
from rsi2.types import Arrow, INT


def fixture():
    names = {}
    for number in range(100):
        name = f"synthetic_family_{number}"
        group = runner.grouping([name])["tasks"][0]["group"]
        names.setdefault(group, name)
        if len(names) == 3:
            break
    tasks = []
    for group, name in sorted(names.items()):
        inputs = (-2 + group, group, 3 + group)
        # The shadow's deliberate hidden mismatch must never reach learning.
        tasks.append(Task(name, Arrow(INT, INT), tuple(((x,), x) for x in inputs),
                          (((10 + group,), 999 if group == 0 else 10 + group),)))
    return sorted(tasks, key=lambda task: task.name)


def solver(calls=None, *, malformed=False):
    def solve(examples, request_type, budget, grammar, **kwargs):
        if calls is not None:
            calls.append((examples, request_type, budget, grammar, kwargs))
        terms = [Lam(INT, Int(0)), Lam(INT, Int(1)), Lam(INT, Var(0))]
        trials, evaluations, steps = [], 0, 0
        for number, term in enumerate(terms):
            outcomes = [evaluate(term, inputs, library=grammar.library) for inputs, _ in examples]
            evaluations += len(outcomes)
            steps += sum(result.steps for result in outcomes)
            trials.append({"id": number, "parent_id": number - 1 if number else None,
                "term": term.to_dict(), "raw_term": term.to_dict(),
                "outputs": [result.value for result in outcomes],
                "runtime_failure": None, "incomplete": False, "heuristic_incomplete": False,
                "public_match": number == 2, "source": "own-enumerator" if number == 0 else "own-edit"})
        result = PopulationResult(term=terms[-1], candidates=True if malformed else len(terms),
            evaluator_calls=evaluations, evaluation_steps=steps, expansions=4,
            normalization_steps=5, termination="public_match", seed=kwargs["seed"])
        result.trials = trials
        result.edit_mode = "arity_coordinates"
        result.neighborhood_work = {flag: kwargs[flag]
            for flag in ("arity_context", "production_priority", "eta_exposure")}
        return result
    return solve


class FailureCreditRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = fixture()
        cls.manifest = runner.grouping([task.name for task in cls.tasks])
        cls.config = {**copy.deepcopy(runner.REGISTERED_CONFIG), "train_tasks": len(cls.tasks),
                      "worker_cpu_allowance_seconds": 30}
        cls.folder = tempfile.TemporaryDirectory()
        cls.path = Path(cls.folder.name) / "probe.checkpoint.json"
        cls.calls = []
        with patch("rsi2.corpus.load_train", side_effect=AssertionError("corpus read")), \
                patch("rsi2.corpus.load_validation", side_effect=AssertionError("heldout read")):
            cls.result = runner.run_probe(cls.tasks, cls.manifest, cls.path, cls.config,
                                          kernel=solver(cls.calls))
        cls.record = reconstruct(cls.path).record
        cls.events = {(e["kind"], e["generation"], e.get("seed")): e
                      for e in cls.record["generations"]}

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_grouping_keeps_parameter_families_together_and_ignores_order(self):
        names = ["family with 2", "family with 7", "other"]
        manifest = runner.grouping(names)
        self.assertEqual(manifest, runner.grouping(reversed(names)))
        family = [r for r in manifest["tasks"] if r["family"] == "family"]
        self.assertEqual(len({r["group"] for r in family}), 1)
        with self.assertRaises(ValueError):
            runner.grouping(["same", "same"])

    def test_full_synthetic_campaign_has_fitting_only_provenance_and_hidden_veto(self):
        self.assertEqual(self.result["status"], "complete")
        self.assertTrue(runner.complete_record(self.record, self.config, self.manifest))
        self.assertFalse(self.record["rsi_success"])
        self.assertFalse(self.record["loop_improvement"])
        fitting, shadow = set(self.record["fitting_names"]), set(self.record["shadow_names"])
        for generation in range(2):
            for seed in self.config["seeds"]:
                source = self.events["fitting", generation, seed]
                model = self.events["models", generation, seed]
                report = self.events["shadow", generation, seed]
                self.assertEqual(set(model["bank"]), fitting)
                self.assertEqual(set(model["positive_names"]), fitting)
                self.assertTrue(all(r["task_name"] in fitting for r in model["memory"]["records"]))
                self.assertEqual(model["grammar"]["library"], {})
                self.assertEqual(model["dreams"], [])
                self.assertFalse(source["retained_from_admitted_update"])
                for arm in runner.ARMS:
                    self.assertEqual(report["arms"][arm]["solved_names"], [])
                    for row in report["arms"][arm]["tasks"]:
                        self.assertIn(row["name"], shadow)
                        self.assertTrue(row["public_selected"])
                        self.assertFalse(row["solved"])
                        self.assertFalse(row["verification"]["passed"])
                        self.assertEqual(row["verification"]["cost"]["hidden_example_evaluations"], 1)
                if generation == 0:
                    self.assertEqual(source["input_bank"], {})
                    self.assertIsNone(source["input_model"])
                else:
                    old = self.events["models", 0, seed]
                    self.assertEqual(source["input_model"], old["models"]["predecessor"])
                    self.assertEqual(model["new_preferences"], 0)
                    self.assertEqual(model["metrics"]["contrastive"]["steps"], 0)
                    self.assertEqual(model["metrics"]["permuted"]["steps"], 0)
                    self.assertEqual(model["memory"]["records"], old["memory"]["records"])
                    self.assertGreater(len(model["memory"]["occurrences"]), len(old["memory"]["occurrences"]))

    def test_all_arms_receive_matching_search_limits_and_root_sources(self):
        for examples, request, budget, grammar, kwargs in self.calls:
            self.assertEqual(budget, 64)
            self.assertEqual(grammar.library, {})
            self.assertFalse(kwargs["arity_context"])
            self.assertTrue(kwargs["production_priority"])
            self.assertTrue(kwargs["eta_exposure"])
            self.assertLessEqual(kwargs["max_cpu_seconds"], 10)
            for key, value in self.config["search"].items():
                self.assertEqual(kwargs[key], value)
        for generation in range(2):
            for seed in self.config["seeds"]:
                reports = self.events["shadow", generation, seed]["arms"]
                allocations = [[r["root_allocation"] for r in reports[arm]["tasks"]] for arm in runner.ARMS]
                seeds = [[r["search_seed"] for r in reports[arm]["tasks"]] for arm in runner.ARMS]
                self.assertTrue(all(item == allocations[0] for item in allocations))
                self.assertTrue(all(item == seeds[0] for item in seeds))

    def test_persisted_completion_gate_rejects_broken_causal_identity_and_proofs(self):
        def event(record, kind, generation=0, seed=11):
            return next(e for e in record["generations"]
                        if (e["kind"], e["generation"], e.get("seed")) == (kind, generation, seed))

        mutations = [
            lambda r: r["generations"].pop(),
            lambda r: event(r, "fitting", 1).update(input_model=None),
            lambda r: event(r, "shadow")["arms"].pop("positive"),
            lambda r: event(r, "shadow")["arms"]["contrastive"]["tasks"][0].update(verification=None),
            lambda r: event(r, "shadow")["arms"]["contrastive"]["tasks"][0]["search"].update(candidates=True),
            lambda r: event(r, "shadow")["arms"]["contrastive"]["tasks"][0]["search"].update(edit_mode="coordinates"),
            lambda r: event(r, "shadow")["arms"]["uniform"]["tasks"][0]["source_grammar"]["weights"].update({"lambda/1": 999}),
            lambda r: event(r, "shadow")["arms"]["contrastive"]["tasks"][0]["search"]["neighborhood_work"].update(arity_context=True),
            lambda r: event(r, "models")["models"]["predecessor"]["weights"][0][0].__setitem__(0, 999),
            lambda r: event(r, "models", 1)["models"]["oneshot"]["weights"][0][0].__setitem__(0, 999),
            lambda r: event(r, "admission", seed=None).update(admitted=True),
        ]
        for number, mutate in enumerate(mutations):
            corrupted = copy.deepcopy(self.record)
            mutate(corrupted)
            with self.subTest(number=number):
                self.assertFalse(runner.complete_record(corrupted, self.config, self.manifest))

    def test_admission_requires_every_seed_new_evidence_strict_controls_and_no_loss(self):
        def reports():
            return {str(seed): {"status": "complete", "new_preferences": 1,
                "permutation": {"status": "informative"},
                "arms": {arm: {"status": "complete", "solved_names":
                    ["old", "new"] if arm in ("contrastive", "oneshot") else ["old"]}
                    for arm in runner.ARMS}} for seed in (11, 22, 33)}

        saved = reports()
        gate = runner.admission(saved, [11, 22, 33], 0)
        self.assertTrue(gate["admitted"])
        self.assertFalse(runner.admission(saved, [11, 22, 33], 1, gate)["admitted"])
        for row in saved.values():
            row["arms"]["contrastive"]["solved_names"].append("later")
        self.assertTrue(runner.admission(saved, [11, 22, 33], 1, gate)["admitted"])
        for mutate in (
                lambda r: r["22"]["arms"]["positive"].update(solved_names=["other"]),
                lambda r: r["33"].update(new_preferences=0),
                lambda r: r["11"]["arms"]["permuted"].update(status="partial"),
                lambda r: r["11"].pop("permutation"),
                lambda r: r["11"]["arms"]["contrastive"].update(solved_names=["new", "later"])):
            corrupted = copy.deepcopy(saved)
            mutate(corrupted)
            self.assertFalse(runner.admission(corrupted, [11, 22, 33], 1, gate)["admitted"])

    def test_worker_stop_retains_lower_bound_and_reports_unrun_conditions(self):
        config = dict(self.config, worker_cpu_allowance_seconds=0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "partial.checkpoint.json"
            result = runner.run_probe(self.tasks, self.manifest, path, config, kernel=solver())
            record = reconstruct(path).record
        self.assertEqual(result["status"], "partial")
        self.assertFalse(runner.complete_record(record, config, self.manifest))
        conditions, work = runner._progress(record)
        self.assertEqual(len(conditions), 2 * 3 * 7)
        self.assertEqual(conditions[0]["status"], "partial")
        self.assertTrue(all(row["status"] == "unrun" for row in conditions[1:]))
        self.assertEqual(work["candidates"], 0)
        self.assertFalse(record["loop_improvement"])

    def test_malformed_result_preserves_raw_trials_without_granting_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.checkpoint.json"
            with self.assertRaisesRegex(ValueError, "invalid actual search counter"):
                runner.run_probe(self.tasks, self.manifest, path, self.config, kernel=solver(malformed=True))
            record = reconstruct(path).record
        self.assertEqual(record["status"], "failed")
        self.assertEqual(len(record["active"]["tasks"][0]["search"]["trials"]), 3)
        self.assertIsNone(record["active"]["tasks"][0]["solved"])
        self.assertFalse(record["loop_improvement"])

    def test_registration_is_name_only_and_requires_committed_matching_source(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest_path, registration = Path(folder) / "groups.json", Path(folder) / "registration.json"
            manifest_path.write_text(json.dumps(self.manifest))

            def git(*args):
                return "source-commit" if args == ("rev-parse", "HEAD") else ""

            with patch.object(runner, "MANIFEST", manifest_path), \
                    patch.object(runner, "training_names", return_value=[t.name for t in self.tasks]), \
                    patch.object(runner, "_git", side_effect=git), \
                    patch("rsi2.corpus.load_train", side_effect=AssertionError("corpus read")):
                saved = runner.register(registration)
                self.assertEqual(runner.validate_registration(registration), saved)
                self.assertFalse(saved["performance_read"])
                with self.assertRaises(FileExistsError):
                    runner.register(registration)
                changed = dict(saved, source_commit="different")
                registration.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "source commit"):
                    runner.validate_registration(registration)


if __name__ == "__main__":
    unittest.main()
