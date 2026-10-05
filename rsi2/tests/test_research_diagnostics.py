"""Semantic diagnostics use the frozen interpreter and public-only profiles."""
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research import diagnostics
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Bool, Int, Lam, Prim, Ref, Var, apply
from rsi2.types import INT, ListOf, PRIMITIVE_TYPES


def _constant(value):
    # Constant zero is the frozen initial incumbent; negative one reproduces
    # the constant-offset artifact which admission must exclude.
    return Lam(ListOf(INT), Lam(ListOf(INT), Lam(INT, Lam(INT, Int(value)))))


def _enumerated(operation="add"):
    grammar = Grammar(primitives={operation: PRIMITIVE_TYPES[operation]}, constants=())
    return next(enumerate_programs(HEURISTIC_TYPE, grammar,
                                  max_size=6, max_expansions=500)).term


class PublicOnlyTask:
    name = "guarded-public-task"
    examples = ((([1, 2],), [[1, False], []]), (([3],), [[3, True]]))

    @property
    def hidden(self):
        raise AssertionError("diagnostics accessed private examples")

    @property
    def request_type(self):
        raise AssertionError("a public output profile does not require task types")


class ResearchDiagnosticTests(unittest.TestCase):
    def test_default_profile_has_fixed_target_crossed_feature_groups(self):
        profile = diagnostics.default_profile()
        self.assertEqual(len(profile), 12)
        self.assertEqual(len({tuple(p["target_outputs"]) for p in profile}), 2)
        for target in {tuple(p["target_outputs"]) for p in profile}:
            group = [p for p in profile if tuple(p["target_outputs"]) == target]
            self.assertEqual(len(group), 6)
            self.assertTrue(any(p["candidate_outputs"] == [] for p in group))
            self.assertGreater(len({p["size"] for p in group}), 1)
            self.assertGreater(len({p["depth"] for p in group}), 1)
        profile[0]["target_outputs"].append(99)
        self.assertNotIn(99, diagnostics.default_profile()[0]["target_outputs"])

    def test_zero_and_negative_constants_are_callable_but_uninformative(self):
        for value in (0, -1):
            report = diagnostics.audit_candidate(_constant(value), {})
            self.assertTrue(report["valid"])
            self.assertFalse(report["informative"])
            self.assertEqual(report["score_signatures"], [value] * 12)
            self.assertEqual(report["failures"], [])

    def test_target_only_score_is_not_candidate_information(self):
        target_length = Lam(ListOf(INT), Lam(ListOf(INT),
                            Lam(INT, Lam(INT, apply(Prim("length"), Var(2))))))
        report = diagnostics.audit_candidate(target_length, {})
        self.assertTrue(report["valid"])
        self.assertGreater(len(set(report["score_signatures"])), 1)
        self.assertFalse(report["informative"])
        self.assertFalse(any(g["informative"] for g in report["target_groups"]))

    def test_enumeration_derived_add_and_sub_are_informative(self):
        for operation in ("add", "sub"):
            report = diagnostics.audit_candidate(_enumerated(operation), {})
            self.assertTrue(report["valid"], report["failures"])
            self.assertTrue(report["informative"])
            self.assertTrue(all(group["informative"] for group in report["target_groups"]))
            self.assertEqual(json.loads(json.dumps(report)), report)

    def test_real_polymorphic_bottom_fails_every_probe(self):
        bottom = apply(Prim("head"), Prim("nil"))
        report = diagnostics.audit_candidate(bottom, {})
        self.assertFalse(report["valid"])
        self.assertFalse(report["informative"])
        self.assertEqual(report["example_evaluations"], 12)
        self.assertEqual(len(report["failures"]), 12)
        self.assertTrue(all("head of empty list" in f["error"] for f in report["failures"]))
        self.assertEqual(report["score_signatures"], [None] * 12)
        self.assertGreater(report["evaluator_steps"], 0)

    def test_boolean_score_and_budget_failure_are_invalid(self):
        boolean = Lam(ListOf(INT), Lam(ListOf(INT), Lam(INT, Lam(INT, Bool(True)))))
        report = diagnostics.audit_candidate(boolean, {})
        self.assertFalse(report["valid"])
        self.assertEqual({f["kind"] for f in report["failures"]}, {"non_integer_score"})
        budget = diagnostics.audit_candidate(_constant(0), {}, step_budget=3)
        self.assertFalse(budget["valid"])
        self.assertEqual({f["kind"] for f in budget["failures"]}, {"budget_exhausted"})
        self.assertEqual(budget["program_evaluations"], 1)
        self.assertEqual(budget["example_evaluations"], 12)
        self.assertEqual(budget["evaluator_steps"], 36)

    def test_frozen_queue_integer_magnitude_boundary_is_enforced(self):
        for sign in (1, -1):
            boundary = diagnostics.audit_candidate(_constant(sign * ((1 << 1023) - 1)), {})
            self.assertTrue(boundary["valid"], boundary["failures"])
            self.assertFalse(boundary["informative"])
            term = _constant(sign * (1 << 1023))
            independent = [evaluate(term, (p["candidate_outputs"], p["target_outputs"],
                                           p["size"], p["depth"]), library={})
                           for p in diagnostics.default_profile()]
            self.assertTrue(all(result.ok for result in independent))
            report = diagnostics.audit_candidate(term, {})
            self.assertFalse(report["valid"])
            self.assertFalse(report["informative"])
            self.assertEqual({failure["kind"] for failure in report["failures"]},
                             {"unusable_queue_score"})
            self.assertEqual(len(report["failures"]), 12)
            self.assertEqual(report["score_signatures"], [None] * 12)
            self.assertEqual((report["program_evaluations"], report["example_evaluations"]), (1, 12))
            self.assertEqual(report["evaluator_steps"], sum(result.steps for result in independent))

    def test_measured_attempt_and_interpreter_costs_are_exact(self):
        term = _constant(0)
        profile = diagnostics.default_profile()
        independent = [evaluate(term, (p["candidate_outputs"], p["target_outputs"],
                                       p["size"], p["depth"]), library={}) for p in profile]
        with patch.object(diagnostics, "evaluate", wraps=evaluate) as observe:
            report = diagnostics.audit_candidate(term, {})
        self.assertEqual(observe.call_count, 12)
        self.assertEqual(report["program_evaluations"], 1)
        self.assertEqual(report["example_evaluations"], 12)
        self.assertEqual(report["evaluator_steps"], sum(r.steps for r in independent))
        self.assertEqual(report["evaluator_steps"], 326)
        single = diagnostics.audit_candidate(term, {}, profile=profile[:1])
        self.assertEqual((single["program_evaluations"], single["example_evaluations"],
                          single["evaluator_steps"]), (1, 1, 25))

    def test_library_candidates_use_the_supplied_current_library(self):
        term = _enumerated()
        report = diagnostics.audit_candidate(Ref("current_fragment"),
                                             {"current_fragment": term})
        self.assertTrue(report["valid"], report["failures"])
        self.assertTrue(report["informative"])

    def test_task_profile_reads_only_public_examples_and_flattens_them(self):
        tasks = [PublicOnlyTask(), SimpleNamespace(name="empty-output", examples=(((), []),))]
        profile = diagnostics.profile_from_tasks(tasks)
        self.assertEqual(len(profile), 4)
        self.assertEqual(profile[0]["candidate_outputs"], [])
        self.assertEqual(profile[1]["candidate_outputs"], [1, 0])
        self.assertEqual(profile[0]["target_outputs"], [1, 0, 3, 1])
        self.assertEqual(profile[1]["target_outputs"], profile[0]["target_outputs"])
        self.assertEqual(profile[2]["target_outputs"], [])
        self.assertEqual([(p["size"], p["depth"]) for p in profile],
                         [(4, 2), (8, 4), (4, 2), (8, 4)])
        report = diagnostics.audit_candidate(_enumerated(), {}, profile=profile)
        self.assertTrue(report["valid"])
        self.assertTrue(report["informative"])
        self.assertEqual(report["example_evaluations"], 4)
        self.assertFalse(diagnostics.audit_candidate(_constant(0), {}, profile=profile)["informative"])

    def test_absent_or_malformed_profiles_fail_explicitly(self):
        report = diagnostics.audit_candidate(_constant(0), {}, profile=[])
        self.assertFalse(report["valid"])
        self.assertEqual(report["example_evaluations"], 0)
        self.assertEqual(report["evaluator_steps"], 0)
        with self.assertRaisesRegex(ValueError, "public example"):
            diagnostics.profile_from_tasks([SimpleNamespace(examples=())])
        bad = diagnostics.default_profile()
        bad[0]["depth"] = 99
        with self.assertRaisesRegex(ValueError, "depth"):
            diagnostics.audit_candidate(_constant(0), {}, profile=bad)

    def test_task_failure_taxonomy_preserves_observed_and_unknown_limits(self):
        assessment = {"budget": 4, "records": [
            {"name": "budget", "solved": False, "public_matched": False,
             "candidates": 4, "exhausted": False},
            {"name": "exhaustion", "solved": False, "public_matched": False,
             "candidates": 1, "exhausted": True},
            {"name": "unknown", "solved": False, "candidates": 1, "exhausted": False},
            {"name": "verifier", "solved": False, "public_matched": True,
             "candidates": 2, "exhausted": False},
            {"name": "solved", "solved": True, "public_matched": True},
        ]}
        report = diagnostics.clusters(assessment, [], [])
        limits = report["no_solution_budget_vs_exhausted"]
        self.assertEqual(limits["count"], 3)
        self.assertEqual((limits["candidate_budget"], limits["search_exhausted"],
                          limits["unknown_limit"]), (1, 1, 1))
        self.assertEqual(limits["absence_of_public_solution_confirmed"], 2)
        self.assertEqual(report["selected_hidden_verifier_failure"]["count"], 1)
        self.assertEqual(report["selected_hidden_verifier_failure"]["evidence"][0]["name"], "verifier")
        unobserved = diagnostics.clusters({"records": [{"solved": False}]}, [], [])
        self.assertEqual(unobserved["selected_hidden_verifier_failure"]["status"], "unknown")
        for key in ("planning_failure", "memory_failure", "tool_failure",
                    "environment_failure", "credit_assignment_failure"):
            self.assertEqual(report[key]["status"], "unknown")
            self.assertIsNone(report[key]["count"])

    def test_proposal_failure_and_confirmation_starvation_are_evidence_based(self):
        dead = apply(Prim("head"), Prim("nil"))
        constant = _constant(0)
        usable = _enumerated()
        proposals = [
            {"index": 7, "term": dead.to_dict(), "screen": {"solved_fraction": 0.0}, "full": {}},
            {"index": 8, "term": constant.to_dict(), "screen": {"solved_fraction": 0.0}, "full": {}},
            {"index": 9, "term": usable.to_dict(), "screen": {"solved_fraction": 0.0}},
            {"index": 10, "term": usable.to_dict(), "screen": {"solved_fraction": 0.5}},
        ]
        audits = {7: diagnostics.audit_candidate(dead, {}),
                  8: diagnostics.audit_candidate(constant, {}),
                  9: diagnostics.audit_candidate(usable, {}),
                  10: diagnostics.audit_candidate(usable, {})}
        report = diagnostics.clusters({}, proposals, audits)
        self.assertEqual(report["evaluator_failure"]["count"], 12)
        self.assertEqual(report["evaluator_failure"]["invalid_programs"], 1)
        self.assertEqual(report["constant_score"]["count"], 1)
        self.assertEqual(report["duplicate_proposals"]["count"], 1)
        starvation = report["confirmation_starvation"]
        self.assertEqual(starvation["count"], 1)
        self.assertEqual(starvation["confirmed_unusable"], 2)
        self.assertEqual(starvation["evidence"][0]["proposal_index"], 9)
        self.assertEqual(starvation["evidence"][0]["confirmed_unusable_indices"], [7, 8])
        self.assertEqual(json.loads(json.dumps(report)), report)
        self.assertTrue(any("memory failure: unknown" in s for s in diagnostics.summarize_clusters(report)))


if __name__ == "__main__":
    unittest.main()
