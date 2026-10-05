"""Dream logs preserve sampled syntax, failed calls, and unchanged learning data."""
import copy
import json
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research import recursive_bootstrap as rb
from rsi2.sampling import sample_program
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES


class DreamProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.request = Arrow(ListOf(INT), INT)
        self.grammar = Grammar(
            primitives={n: PRIMITIVE_TYPES[n] for n in ("head", "length")}, constants=())
        self.task = Task("synthetic-public-inputs", self.request,
                         ((([],), 999), (([1, 2],), 999)), ((([3],), 999),))
        self.config = copy.deepcopy(rb.REGISTERED_CONFIG)
        self.config.update(dreams=1, dream_attempts=3)
        self.state = rb.RecursiveState(11, "FULL", generation=1, grammar=self.grammar)
        emitted = [c.term for c in enumerate_programs(
            self.request, self.grammar, max_size=3, max_expansions=100)]
        self.failed = next(t for t in emitted if not evaluate(t, ([],)).ok)
        self.success = next(t for t in emitted
                            if evaluate(t, ([],)).value == 0
                            and evaluate(t, ([1, 2],)).value == 2)

    def test_every_sampling_and_interpreter_cost_reconciles_from_trial_records(self):
        work, trials, actual = rb._work(), [], []

        def recorded(term, inputs, **options):
            result = evaluate(term, inputs, **options)
            actual.append(result)
            return result

        with patch.object(rb, "sample_program", side_effect=[None, self.failed, self.success]), \
                patch.object(rb, "evaluate", side_effect=recorded):
            pairs = rb._dreams(self.state, [self.task], self.config,
                               rb.CpuGuard(60), work, trials)
        self.assertEqual(work["dream_sampling_calls"], len(trials))
        self.assertEqual(work["dream_programs"], sum(t["sampled"] for t in trials))
        self.assertEqual(work["dream_examples"], sum(len(t["evaluations"]) for t in trials))
        self.assertEqual(work["dream_steps"], sum(e["steps"] for t in trials for e in t["evaluations"]))
        self.assertEqual(work["dream_steps"], sum(r.steps for r in actual))
        self.assertEqual([t["reason"] for t in trials],
                         ["sampler_returned_none", "public_runtime_failure", "accepted"])
        self.assertEqual([t["sampler_index"] for t in trials], [0, 1, 2])
        self.assertTrue(all(t["rng_seed"] == 11000034 for t in trials))
        self.assertIsNone(trials[0]["term"])
        self.assertFalse(trials[1]["evaluations"][0]["ok"])
        self.assertIsNotNone(trials[1]["evaluations"][0]["error"])
        self.assertEqual(trials[2]["evaluations"][1]["inputs"], ([1, 2],))
        self.assertEqual(pairs, [(Task("dream_2", self.request,
                                      ((([],), 0), (([1, 2],), 2)), ()), self.success)])
        # Dream labels contain only evaluated public inputs, never source hidden cases.
        self.assertEqual(pairs[0][0].hidden, ())

    def test_logging_preserves_real_sampler_rng_draws_evaluator_calls_and_learning_pairs(self):
        config = copy.deepcopy(self.config)
        config.update(dreams=3, dream_attempts=40)
        observations = []
        results = []
        for logged in (False, True):
            states, calls, work = [], [], rb._work()

            def sampled(request, grammar, rng, **options):
                states.append(rng.getstate())
                return sample_program(request, grammar, rng, **options)

            def evaluated(term, inputs, **options):
                result = evaluate(term, inputs, **options)
                calls.append((term, inputs, result))
                return result

            with patch.object(rb, "sample_program", side_effect=sampled), \
                    patch.object(rb, "evaluate", side_effect=evaluated):
                pairs = rb._dreams(self.state, [self.task], config, rb.CpuGuard(60),
                                   work, [] if logged else None)
            results.append(pairs)
            observations.append((states, calls, work))
        self.assertEqual(results[0], results[1])
        self.assertEqual(observations[0], observations[1])

    def test_learning_report_keeps_dream_count_and_complete_serializable_trial_provenance(self):
        config = copy.deepcopy(self.config)
        self.state.arm = "NO_LIBRARY"
        work = rb._work()
        with patch.object(rb, "sample_program", side_effect=[None, self.failed, self.success]):
            report = rb._learn(self.state, [self.task], config, rb.CpuGuard(60), work)
        self.assertEqual(report["dreams"], 1)
        self.assertEqual(report["dream_rng_seed"], 11000034)
        self.assertEqual(len(report["dream_trials"]), 3)
        encoded = json.loads(json.dumps(rb.jsonable(report), allow_nan=False))
        self.assertEqual(encoded["dream_trials"][2]["term"], self.success.to_dict())
        self.assertTrue(report["dreams_never_compression_or_verified_bank_labels"])
        self.assertEqual(self.state.raw_solutions, {})


if __name__ == "__main__":
    unittest.main()
