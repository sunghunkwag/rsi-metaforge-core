"""J's pure parts: statistics, bounds, decisions, the ledger, the manifest, the metrics."""
import json
from pathlib import Path
import tempfile
import unittest

from rsi2.corpus import load_train
from rsi2.terms import Int, Lam

from rsi4.judge import adopt, ledger, metrics, pools, registry, replay, sleep_check
from rsi4.judge.evaluate import EvaluationError, JudgeVerifier, check_config
from rsi3.verifier import QueryLimitExceeded


class SignTestTests(unittest.TestCase):
    def test_directive_examples(self):
        self.assertAlmostEqual(adopt.sign_test(8, 1), 10 / 512)        # 0.020
        self.assertAlmostEqual(adopt.sign_test(7, 2), 46 / 512)        # 0.090
        self.assertLessEqual(adopt.sign_test(8, 1), 0.05)
        self.assertGreater(adopt.sign_test(7, 2), 0.05)

    def test_edges(self):
        self.assertEqual(adopt.sign_test(0, 0), 1.0)
        self.assertEqual(adopt.sign_test(0, 5), 1.0)
        self.assertAlmostEqual(adopt.sign_test(5, 0), 1 / 32)

    def test_holm(self):
        self.assertEqual(adopt.holm([0.01, 0.04]), [True, True])
        self.assertEqual(adopt.holm([0.04, 0.03]), [False, False])   # 0.03 > 0.025
        self.assertEqual(adopt.holm([0.001, 0.2, 0.02]), [True, False, True])


class BoundsTests(unittest.TestCase):
    def test_defaults_are_inside(self):
        self.assertEqual(adopt.out_of_bounds(adopt.DEFAULT_RULES), [])

    def test_outside_is_rejected(self):
        for key, value in [("C.threshold", 3.5), ("C.floor_chunks", 4), ("C.floor_chunks", 1.5),
                           ("meta.chunk", 24), ("controller.exploration", 0.05),
                           ("meta.selfplay", 1024), ("invention.concept_weight", 0.5),
                           ("dreams", 4), ("G.offer_min_solves", 0), ("dreams", True)]:
            rules = dict(adopt.DEFAULT_RULES, **{key: value})
            self.assertTrue(adopt.out_of_bounds(rules), (key, value))
        self.assertTrue(adopt.out_of_bounds(dict(adopt.DEFAULT_RULES, B_eval=128)))
        missing = dict(adopt.DEFAULT_RULES)
        del missing["dreams"]
        self.assertTrue(adopt.out_of_bounds(missing))

    def test_never_in_the_search_space(self):
        for key in ("B_wake", "B_eval", "search", "delta_sleep", "alpha", "seeds"):
            self.assertNotIn(key, adopt.RULE_BOUNDS)


class DecisionTests(unittest.TestCase):
    def test_pooled_two_of_three(self):
        per_seed = {"11": {"a": True, "b": True}, "22": {"a": True, "b": False},
                    "33": {"a": False, "b": False}}
        self.assertEqual(adopt.pooled(per_seed, ["a", "b"]), {"a": True, "b": False})

    def test_select(self):
        d = adopt.decide_select(10, [("c1", 12), ("c2", 12), ("c3", 9)])
        self.assertEqual((d["best"], d["selected"]), ("c1", "c1"))
        self.assertIsNone(adopt.decide_select(12, [("c1", 12)])["selected"])

    def test_confirm(self):
        base = {f"t{i}": False for i in range(200)}
        cand = dict(base, **{f"t{i}": True for i in range(8)})
        cand_loss = dict(cand)
        base_loss = dict(base, t199=True)
        ok = adopt.decide_confirm(adopt.pairs(base_loss, cand_loss), 200)
        self.assertTrue(ok["adopt"])                       # 8 wins, 1 loss: p = 0.020
        weak = adopt.decide_confirm(adopt.pairs(dict(base, t198=True, t199=True), cand), 200)
        self.assertFalse(weak["adopt"])                    # 8 vs 2: p = 0.055
        self.assertFalse(adopt.decide_confirm(adopt.pairs(base_loss, cand_loss), 201)["adopt"])
        many = {f"t{i}": i < 30 for i in range(200)}
        more = {f"t{i}": 6 <= i < 60 for i in range(200)}
        budget = adopt.decide_confirm(adopt.pairs(many, more), 200)
        self.assertTrue(budget["significant"])
        self.assertFalse(budget["adopt"])                  # 6 losses > 5

    def test_sleep_rule(self):
        before = {"a": True, "b": True, "c": False}
        self.assertEqual(sleep_check.decide(before, {"a": False, "b": False, "c": False})["decision"],
                         "revert")
        self.assertEqual(sleep_check.decide(before, {"a": False, "b": False, "c": True})["decision"],
                         "keep")
        self.assertEqual(sleep_check.decide(before, before)["decision"], "keep")


class LedgerTests(unittest.TestCase):
    def test_chain_detects_alteration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge_log.jsonl"
            for k in range(3):
                ledger.append(path, {"op": "x", "k": k})
            self.assertEqual(len(ledger.verify(path)), 3)
            lines = path.read_text().splitlines()
            lines[1] = lines[1].replace('"k":1', '"k":7')
            path.write_text("\n".join(lines) + "\n")
            with self.assertRaises(ledger.LedgerError):
                ledger.verify(path)

    def test_chain_detects_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge_log.jsonl"
            for k in range(3):
                ledger.append(path, {"op": "x", "k": k})
            lines = path.read_text().splitlines()
            path.write_text("\n".join([lines[0], lines[2]]) + "\n")
            with self.assertRaises(ledger.LedgerError):
                ledger.verify(path)


def _summary(pool, outcomes):
    return {"pool": pool, "complete": True,
            "pooled": {"solved": sum(outcomes.values()), "tasks": outcomes},
            "per_seed": {s: {"verdicts": outcomes} for s in ("11", "22", "33")}}


class ReplayTests(unittest.TestCase):
    def test_logged_decisions_replay_and_a_forged_one_is_found(self):
        before = {"a": True, "b": True, "c": False}
        after = {"a": False, "b": False, "c": False}
        sleep = {"before": _summary("probe", before), "after": _summary("probe", after),
                 **sleep_check.decide(before, after)}
        inc = _summary("selection_r1", {"a": True, "b": False})
        c1 = _summary("selection_r1", {"a": True, "b": True})
        select = {"candidate_order": ["c1"], "incumbent": inc, "candidates": {"c1": c1},
                  **adopt.decide_select(1, [("c1", 2)])}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge_log.jsonl"
            ledger.append(path, {"op": "sleep_check", "result": sleep})
            ledger.append(path, {"op": "select", "result": select})
            self.assertEqual(replay.replay(path)["mismatches"], [])
            forged = dict(sleep, decision="keep")
            ledger.append(path, {"op": "sleep_check", "result": forged})
            found = replay.replay(path)["mismatches"]
            self.assertEqual(found, ["line 2 (sleep_check): decision"])


class MetricsTests(unittest.TestCase):
    def test_definitions(self):
        names = [f"t{k}" for k in range(10)]

        def solved(n):
            return {name: index < n for index, name in enumerate(names)}

        R = {0: {1: 2, 2: 3, 3: 1}, 1: {1: 6, 2: 4, 3: 2}, 2: {1: 5, 2: 7, 3: 3},
             3: {1: 4, 2: 6, 3: 8}}
        outcomes = {(i, j): solved(R[i][j]) for i in R for j in R[i]}
        result = metrics.compute(outcomes)
        self.assertAlmostEqual(result["point"]["ACC"], (4 + 6 + 8) / 3)
        self.assertAlmostEqual(result["point"]["BWT"], ((4 - 6) + (6 - 7)) / 2)
        self.assertAlmostEqual(result["point"]["FGT"], (max(6, 5) - 4 + (7 - 6)) / 2)
        self.assertAlmostEqual(result["point"]["FWT"], ((4 - 3) + (3 - 1)) / 2)
        low, high = result["ci95"]["ACC"]
        self.assertLessEqual(low, result["point"]["ACC"])
        self.assertGreaterEqual(high, result["point"]["ACC"])
        self.assertEqual(result, metrics.compute(outcomes))   # fixed resampling seed


class VerifierTests(unittest.TestCase):
    def test_public_and_hidden_one_query(self):
        task = load_train()[0]
        verifier = JudgeVerifier([task], 2000)
        wrong = Lam(task.request_type.args[0], Int(0))
        self.assertFalse(verifier.verify(task.name, wrong, {}, 1).verdict)
        with self.assertRaises(QueryLimitExceeded):
            verifier.verify(task.name, wrong, {}, 1)

    def test_registered_budget_and_limits(self):
        config = json.loads((registry.REPO_DIR / "rsi3" / "experiment_config_honest.json")
                            .read_text())
        check_config(config)
        with self.assertRaises(EvaluationError):
            check_config(dict(config, B_eval=128))
        with self.assertRaises(EvaluationError):
            check_config(dict(config, search=dict(config["search"], max_size=14)))


class ManifestTests(unittest.TestCase):
    def test_live_tree_matches_manifest(self):
        self.assertEqual(registry.verify_manifest(), [])

    def test_pool_uses(self):
        self.assertEqual(pools.use_of("probe"), "sleep_check")
        self.assertEqual(pools.use_of("confirmation_r2"), "confirm")
        self.assertEqual(pools.use_of("final_test_3"), "final_test")
        self.assertEqual(pools.use_of("stage_eval_S1"), "evaluate")


if __name__ == "__main__":
    unittest.main()
