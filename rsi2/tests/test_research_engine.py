"""Admission and development-cycle isolation, separate from research outcomes."""
import ast
import copy
import inspect
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.learning import State
from rsi2.research import diagnostics, engine
from rsi2.research.memory import EvaluationMemory
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Int, subterms
from rsi2.types import Arrow, INT, PRIMITIVE_TYPES


def _assessment(names, solved, count=4):
    names, solved = list(names), set(solved)
    records = [{"name": name, "solved": name in solved, "candidates": count,
                "candidates_to_solution": count if name in solved else None}
               for name in names]
    return {"tasks": len(names), "solved": len(solved),
            "solved_fraction": len(solved) / len(names) if names else 0,
            "candidate_evaluations": len(names) * count, "records": records}


def _enumerated_constant(value):
    grammar = Grammar(primitives={}, constants=(Int(value),))
    return next(candidate.term for candidate in enumerate_programs(
        HEURISTIC_TYPE, grammar, max_size=5, max_expansions=20)
        if any(node.tag == "int" and node.value == value
               for _, node in subterms(candidate.term)))


def _tasks(names):
    return [Task(name, Arrow(INT, INT), (((2,), 2),), (((-3,), 3),)) for name in names]


class _RecordingMemory(EvaluationMemory):
    def __init__(self):
        super().__init__()
        self.calls = []

    def measure(self, state, tasks, heuristic, budget, searchconfig):
        tasks = list(tasks)
        report = super().measure(state, tasks, heuristic, budget, searchconfig)
        self.calls.append({"names": [task.name for task in tasks], "heuristic": heuristic,
                           "budget": budget, "search": dict(searchconfig), "report": report})
        return report


class _FixedOriginalPool:
    """A generated constant-prefix fixture for the engine's ORIGINAL control."""
    mode = "original"

    def __init__(self):
        self.terms = [_enumerated_constant(value) for value in (0, -1, 1, 0, -1, 1)]
        self.draw_report = {"new_raw_draws": 6}
        self.selection_report = {}
        self.observations = []

    def draw(self, incumbent, number, limits):
        return [{"index": index, "origin": "enumeration", "term": term,
                 "rejection": None} for index, term in enumerate(self.terms)]

    def select(self, records, audits, quota):
        self.selection_report = {"quota": quota}
        return list(range(min(len(records), quota)))

    def observe(self, records, audits):
        self.observations.append(copy.deepcopy((records, audits)))
        observed = sum(record["term"] is not None
                       for previous, _ in self.observations for record in previous)
        return {"objective": "test_fixture", "fitted_after_selection": True,
                "observed_count": observed,
                "new_training_rows": sum(record["term"] is not None for record in records)}


class ResearchAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.audit = {"valid": True, "informative": True}
        self.incumbent = _assessment(["v1", "v2", "v3"], ["v1"])
        self.improved = _assessment(["v1", "v2", "v3"], ["v1", "v2"])
        self.confirmation = _assessment(["c1", "c2", "c3"], ["c1"])

    def test_valid_informative_strict_gain_with_no_confirmation_loss_is_admissible(self):
        candidate_confirmation = _assessment(["c1", "c2", "c3"], ["c1", "c2"])
        self.assertTrue(engine.admissible(self.audit, self.incumbent, self.improved,
                                          self.confirmation, candidate_confirmation))

    def test_faster_validation_tie_and_validation_regression_are_rejected(self):
        faster_tie = _assessment(["v1", "v2", "v3"], ["v1"], count=1)
        regression = _assessment(["v1", "v2", "v3"], [])
        for candidate in (faster_tie, regression):
            with self.subTest(fraction=candidate["solved_fraction"]):
                self.assertFalse(engine.admissible(self.audit, self.incumbent, candidate,
                                                   self.confirmation, self.confirmation))

    def test_invalid_or_uninformative_candidate_cannot_receive_improvement_credit(self):
        for audit in ({"valid": False, "informative": True},
                      {"valid": True, "informative": False}, {}):
            with self.subTest(audit=audit):
                self.assertFalse(engine.admissible(audit, self.incumbent, self.improved,
                                                   self.confirmation, self.confirmation))

    def test_real_generated_nonzero_constant_cannot_be_adopted_despite_apparent_gain(self):
        constant = _enumerated_constant(-1)
        audit = diagnostics.audit_candidate(constant, {})
        self.assertTrue(audit["valid"])
        self.assertFalse(audit["informative"])
        self.assertEqual(audit["score_signatures"], [-1] * 12)
        self.assertFalse(engine.admissible(audit, self.incumbent, self.improved,
                                           self.confirmation, self.confirmation))

    def test_confirmation_task_loss_is_rejected_even_when_aggregate_count_ties(self):
        replaced = _assessment(["c1", "c2", "c3"], ["c2"])
        self.assertEqual(replaced["solved_fraction"], self.confirmation["solved_fraction"])
        self.assertFalse(engine.admissible(self.audit, self.incumbent, self.improved,
                                           self.confirmation, replaced))

    def test_more_confirmation_solves_cannot_hide_loss_of_previous_solved_task(self):
        replaced = _assessment(["c1", "c2", "c3"], ["c2", "c3"])
        self.assertGreater(replaced["solved_fraction"], self.confirmation["solved_fraction"])
        self.assertFalse(engine.admissible(self.audit, self.incumbent, self.improved,
                                           self.confirmation, replaced))


class ResearchCycleIsolationTests(unittest.TestCase):
    def _live_cycle(self):
        grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "abs")},
                          constants=())
        state = State(11, grammar=grammar, heuristic=zero_heuristic())
        validation = _tasks(["zeta", "beta", "epsilon", "alpha", "gamma", "delta"])
        confirmation = _tasks(["fresh-family-1", "fresh-family-2"])
        pool, memory = _FixedOriginalPool(), _RecordingMemory()
        config = engine.load_config()
        before = copy.deepcopy(state.heuristic)
        with patch.object(engine, "load_train", side_effect=AssertionError("unexpected TRAIN load")):
            with patch.object(engine, "load_validation", side_effect=AssertionError("unexpected load")):
                with patch.object(engine, "load_confirmation", side_effect=AssertionError("unexpected load")):
                    report = engine.cycle(state, pool, memory, validation, confirmation, 1, config)
        return state, before, validation, confirmation, pool, memory, config, report

    def test_live_cycle_uses_fixed_screen_and_full_budgets_on_separate_partitions(self):
        state, before, validation, confirmation, pool, memory, config, report = self._live_cycle()
        self.assertEqual(config["screen_slots"], 6)
        self.assertEqual(config["confirmation_slots"], 2)
        self.assertEqual(config["screen_tasks"], 4)
        self.assertEqual(config["screen_budget"], 16)
        self.assertEqual(config["B_eval"], 64)
        self.assertEqual(len(memory.calls), 10)  # Two incumbents, six screens, two full candidates.
        self.assertEqual(memory.calls[0]["names"], [task.name for task in validation])
        self.assertEqual(memory.calls[1]["names"], [task.name for task in confirmation])
        self.assertFalse(memory.calls[0]["report"]["cache_hit"])
        self.assertFalse(memory.calls[1]["report"]["cache_hit"])
        screens = [call for call in memory.calls if call["budget"] == 16]
        self.assertEqual(len(screens), 6)
        self.assertTrue(all(call["names"] == ["alpha", "beta", "delta", "epsilon"]
                            for call in screens))
        self.assertEqual([call["heuristic"] for call in screens], pool.terms)
        self.assertTrue(all(call["search"] == config["search"] for call in memory.calls))
        self.assertTrue(all(call["budget"] == 64 for call in memory.calls[:2] + memory.calls[-2:]))
        self.assertEqual(report["selected_indices"], list(range(6)))
        self.assertEqual(report["confirmed_indices"], [0, 1])
        self.assertIsNone(report["adopted_index"])
        self.assertEqual(state.heuristic, before)
        self.assertEqual(report["proposal_productivity"], {"selected": 6, "verified": 0,
                                                           "fresh_family_verified": 0})
        self.assertTrue(all(not record["adopted"] for record in report["candidates"]))
        self.assertEqual(report["probe_program_evaluations"], 12)
        self.assertEqual(report["probe_example_evaluations"], 6 * 12 + 6 * 4)
        # These are real search costs, including only misses in the exact cache.
        self.assertEqual(report["memory"]["actual_candidate_evaluations"],
                         sum(call["report"]["actual_candidate_evaluations"] for call in memory.calls))
        self.assertGreater(report["memory"]["actual_candidate_evaluations"], 0)
        self.assertLess(report["memory"]["actual_candidate_evaluations"],
                        sum(call["report"]["candidate_evaluations"] for call in memory.calls))

    def test_replayed_cycle_hits_cache_without_new_work_or_improvement_credit(self):
        state, before, validation, confirmation, pool, memory, config, first = self._live_cycle()
        original_cost = memory.actual_candidate_evaluations
        second = engine.cycle(state, pool, memory, validation, confirmation, 2, config)
        self.assertEqual(memory.actual_candidate_evaluations, original_cost)
        self.assertTrue(all(call["report"]["cache_hit"] for call in memory.calls[10:]))
        self.assertIsNone(second["adopted_index"])
        self.assertEqual(second["validation"]["solved"], first["validation"]["solved"])
        self.assertEqual(state.heuristic, before)
        self.assertEqual(len(pool.observations), 2)
        self.assertTrue(all("screen" not in record for record in pool.observations[0][0]))
        self.assertEqual(first["model"]["observed_count"], 6)
        self.assertEqual(second["model"]["observed_count"], 12)

    def _assert_online_report(self, report):
        online = report["online_report"]
        self.assertEqual(set(online), {
            "current_performance", "failure_clusters", "bottleneck",
            "previous_attempt_insufficiency", "intervention", "mechanism",
            "verification_plan", "regression_risks", "result", "keep_revert_revise",
            "updated_rule",
        })
        self.assertEqual(online["current_performance"], {
            "validation": report["validation"]["solved_fraction"],
            "confirmation": report["confirmation"]["solved_fraction"],
        })
        self.assertEqual(online["failure_clusters"], report["failure_clusters"])
        self.assertEqual(online["result"], {
            **report["proposal_productivity"],
            "task_heuristic_adopted": report["adopted_index"] is not None,
        })
        self.assertIn("procedure comparison remains provisional", online["keep_revert_revise"])
        self.assertEqual(online["updated_rule"]["status"],
                         "measured history; unaccepted procedure hypothesis")
        self.assertEqual(online["updated_rule"]["verified_training_rows"],
                         report["model"]["observed_count"])
        return online

    def test_online_report_is_current_evidence_with_provisional_procedure_rejection(self):
        state, before, _, _, _, _, _, report = self._live_cycle()
        online = self._assert_online_report(report)
        self.assertIsNone(report["adopted_index"])
        self.assertEqual(state.heuristic, before)
        self.assertFalse(online["result"]["task_heuristic_adopted"])
        self.assertTrue(online["keep_revert_revise"].startswith(
            "reject task candidates; retain incumbent;"))
        self.assertEqual(online["updated_rule"]["verified_training_rows"], 6)

    def test_online_report_tracks_actual_object_adoption_without_accepting_procedure(self):
        grammar = Grammar(primitives={"add": PRIMITIVE_TYPES["add"]}, constants=())
        term = next(enumerate_programs(HEURISTIC_TYPE, grammar,
                                       max_size=6, max_expansions=100)).term
        state = State(11, grammar=grammar, heuristic=zero_heuristic())
        validation, confirmation = _tasks(["v1", "v2"]), _tasks(["fresh-c1", "fresh-c2"])
        pool = _FixedOriginalPool()
        pool.terms = [term] * 6

        class ControlledGateMemory:
            def measure(self, state, tasks, heuristic, budget, searchconfig):
                names = [task.name for task in tasks]
                # The actual gate sees a strict validation gain and preservation
                # of both previously solved confirmation identities.
                solved = names if heuristic == term or names[0].startswith("fresh-") else []
                return _assessment(names, solved)

            def summary(self):
                return {"fixture": "strict validation gain with confirmation nonloss"}

        report = engine.cycle(state, pool, ControlledGateMemory(), validation,
                              confirmation, 1, engine.load_config())
        online = self._assert_online_report(report)
        self.assertEqual(report["adopted_index"], 0)
        self.assertEqual(state.heuristic, term)
        self.assertTrue(report["candidates"][0]["adopted"])
        self.assertTrue(online["result"]["task_heuristic_adopted"])
        self.assertTrue(online["keep_revert_revise"].startswith("keep verified task heuristic;"))
        self.assertGreater(online["current_performance"]["validation"],
                           report["incumbent_validation"]["solved_fraction"])

    def test_tied_screens_preserve_selected_proposal_rank_through_confirmation(self):
        grammar = Grammar(primitives={"add": PRIMITIVE_TYPES["add"]}, constants=())
        term = next(enumerate_programs(HEURISTIC_TYPE, grammar,
                                       max_size=6, max_expansions=100)).term
        audit = diagnostics.audit_candidate(term, {})
        self.assertTrue(audit["valid"])
        self.assertTrue(audit["informative"])
        validation = _tasks(["zeta", "beta", "epsilon", "alpha", "gamma", "delta"])
        confirmation = _tasks(["fresh-family-1", "fresh-family-2"])

        class TiedMemory:
            def measure(self, state, tasks, heuristic, budget, searchconfig):
                names = [task.name for task in tasks]
                return _assessment(names, names)

            def summary(self):
                return {"fixture": "equal observed screen fractions"}

        orders = {"learned": [3, 2, 5, 4, 1, 0],
                  "original": list(range(6)), "static": list(range(6))}
        for mode, selected in orders.items():
            with self.subTest(mode=mode):
                state = State(11, grammar=grammar, heuristic=zero_heuristic())
                pool = _FixedOriginalPool()
                pool.mode, pool.terms = mode, [term] * 6
                with patch.object(pool, "select", return_value=selected):
                    report = engine.cycle(state, pool, TiedMemory(), validation,
                                          confirmation, 1, engine.load_config())
                self.assertEqual(report["selected_indices"], selected)
                self.assertEqual(report["confirmed_indices"], selected[:2])
                self.assertEqual({record["index"] for record in report["candidates"]
                                  if record["full"] is not None}, set(selected[:2]))
                self.assertTrue(all(record["audit"]["valid"] and record["audit"]["informative"]
                                    for record in report["candidates"]))
                self.assertIsNone(report["adopted_index"])

    def test_engine_has_no_original_test_or_reporting_audit_capability(self):
        for name in ("load_test", "load_audit", "sealed_audit"):
            self.assertFalse(hasattr(engine, name))
        source = ast.parse(inspect.getsource(engine))
        forbidden = {"sealed_audit", "load_audit", "load_test"}
        for node in ast.walk(source):
            symbols = []
            if isinstance(node, ast.Import):
                symbols = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                symbols = [node.module or ""] + [alias.name for alias in node.names]
            elif isinstance(node, ast.Attribute):
                symbols = [node.attr]
            elif isinstance(node, ast.Name):
                symbols = [node.id]
            for symbol in symbols:
                self.assertFalse(forbidden & set(symbol.split(".")), symbol)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn("audit.json", node.value)
                self.assertNotIn("test.json", node.value)


if __name__ == "__main__":
    unittest.main()
