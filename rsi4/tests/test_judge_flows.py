"""J's decision operations end to end, on a judge copy whose pools are TRAIN-derived.

Every loop-4 and gate operation runs here through ``service.handle`` before J
is frozen: select (with an out-of-bounds candidate rejected), the one-use
rules, confirm and its burn, the final test, compare with Holm, the metrics,
and a replay of both ledgers. The real pools are never read: the copy's
pools hold TRAIN tasks in DreamCoder's record format (8 public examples, the
rest hidden), and its manifest is rewritten for them.
"""
import json
from pathlib import Path
import tempfile
import unittest

from rsi2.corpus import load_train

from rsi4.judge import adopt, ledger, pools, registry, replay, service
from rsi4.tests import fixtures

TYPES = {"list[int]": "list-of-int", "list[bool]": "list-of-bool", "int": "int", "bool": "bool"}
SOLVED = ["prepend-k with k=4", "has-k with k=3", "caesar-cipher-k-modulo-n with k=1 and n=2",
          "caesar-cipher-k-modulo-n with k=5 and n=5", "caesar-cipher-k-modulo-n with k=2 and n=2",
          "modulo-k with k=2", "bool-identify-k with k=1", "prepend-index-k with k=2",
          "caesar-cipher-k-modulo-n with k=0 and n=3", "prepend-k with k=0",
          "replace-all-with-index-k with k=1"]


def nothing(runtime, model, tasks, config, verifier, generation, **_):
    """The weakest solver: submits nothing."""
    return {"solved": 0, "tasks": [{"name": t.name, "solved": False, "spent": {}} for t in tasks]}


def _record(task):
    out = TYPES[str(task.request_type).split(" -> ")[1]]
    return {"name": task.name, "type": {"input": "list-of-int", "output": out},
            "examples": [{"i": list(x[0]), "o": y} for x, y in task.examples + task.hidden]}


class JudgeFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        train = {t.name: t for t in load_train()}
        solved = [_record(train[n]) for n in SOLVED]
        unsolved = [_record(t) for n, t in sorted(train.items()) if n not in SOLVED][:4]
        layout = {"selection_r1": solved[:3] + unsolved[:2],
                  "confirmation_r1": solved[3:] + unsolved[2:],
                  "final_test_2": solved[:6], "final_test_3": solved[6:],
                  "stage_eval_S1": solved[:2] + unsolved[:1],
                  "stage_eval_S2": solved[2:4] + unsolved[1:2],
                  "stage_eval_S3": solved[4:6] + unsolved[2:3]}
        cls.judge = fixtures.judge_copy()
        for pool, records in layout.items():
            (cls.judge / "pools" / f"{pool}.json").write_text(json.dumps(
                {"pool": pool, "use": pools.use_of(pool), "records": records}))
        registry.write_manifest(cls.judge)
        cls.dir = Path(tempfile.mkdtemp(dir=fixtures.scratch()))
        cls.canonical = cls.dir / "canonical.jsonl"
        cls.checkpoint = str(fixtures.tiny_checkpoint())
        cls.solvers = {"nothing": nothing}

    def ask(self, request):
        request = dict({"config": str(fixtures.CONFIG), "run_dir": str(self.dir / "run")},
                       **request)
        return service.handle(request, judge_dir=self.judge, canonical_ledger=self.canonical,
                              solvers=self.solvers)

    def spec(self, cid, solver, rules=None):
        return {"id": cid, "checkpoint": self.checkpoint, "solver": solver, "rules": rules}

    def test_flow(self):
        incumbent = self.spec("incumbent", "nothing")
        bad = dict(adopt.DEFAULT_RULES, **{"C.threshold": 9.0})
        # 1. Selection: the out-of-bounds candidate is rejected, the real solver moves on.
        sel = self.ask({"op": "select", "round": 1, "incumbent": incumbent,
                        "candidates": [self.spec("weak", "nothing"),
                                       self.spec("out", "nothing", bad),
                                       self.spec("real", "rsi3")]})
        self.assertTrue(sel["ok"], sel.get("refused") or sel.get("error"))
        result = sel["result"]
        self.assertIn("out", result["rejected"])
        self.assertEqual(result["selected"], "real")
        self.assertEqual(result["candidate_order"], ["weak", "real"])
        # 2. A selection pool is used once.
        self.assertFalse(self.ask({"op": "select", "round": 1, "incumbent": incumbent,
                                   "candidates": [self.spec("real", "rsi3")]})["ok"])
        # 3. Only the selected candidate may be confirmed.
        wrong = self.ask({"op": "confirm", "round": 1, "incumbent": incumbent,
                          "candidate": self.spec("weak", "nothing")})
        self.assertFalse(wrong["ok"])
        conf = self.ask({"op": "confirm", "round": 1, "incumbent": incumbent,
                         "candidate": self.spec("real", "rsi3")})
        self.assertTrue(conf["ok"], conf.get("refused") or conf.get("error"))
        pairs = conf["result"]["pairs"]
        self.assertEqual(pairs["losses"], 0)
        self.assertEqual(conf["result"]["adopt"], pairs["wins"] >= 5)
        self.assertTrue(conf["result"]["complete"])
        # 4. Burned: the confirmation pool is refused, and the round is closed.
        again = self.ask({"op": "confirm", "round": 1, "incumbent": incumbent,
                          "candidate": self.spec("real", "rsi3")})
        self.assertFalse(again["ok"])
        self.assertIn("burned", again["refused"])
        self.assertFalse(self.ask({"op": "select", "round": 1, "incumbent": incumbent,
                                   "candidates": []})["ok"])
        self.assertFalse(self.ask({"op": "confirm", "round": 2, "incumbent": incumbent,
                                   "candidate": self.spec("real", "rsi3")})["ok"])
        ops = [e["op"] for e in ledger.entries(self.canonical)]
        self.assertEqual(ops.count("burn"), 1)
        # 5. The final test runs once.
        final = self.ask({"op": "final_test", "theta_star": self.spec("star", "rsi3"),
                          "theta_0": self.spec("zero", "nothing")})
        self.assertTrue(final["ok"], final.get("refused") or final.get("error"))
        self.assertEqual(final["result"]["pairs"]["tasks"], len(SOLVED))
        self.assertFalse(self.ask({"op": "final_test", "theta_star": self.spec("star", "rsi3"),
                                   "theta_0": self.spec("zero", "nothing")})["ok"])
        # 6. Stage-eval evaluations, the score matrix and a Holm-corrected comparison.
        refs, weak = {}, []
        run_ledger = self.dir / "run" / "judge_log.jsonl"
        for j in (1, 2, 3):
            for i in (0, 1, 2, 3):
                spec = self.spec(f"R{i}{j}", "rsi3" if i else "nothing")
                out = self.ask({"op": "evaluate", "pool": f"stage_eval_S{j}",
                                "checkpoint": spec["checkpoint"], "solver": spec["solver"],
                                "label": f"R[{i}][{j}]"})
                self.assertTrue(out["ok"], out.get("refused") or out.get("error"))
                refs[f"{i},{j}"] = [str(run_ledger), len(ledger.verify(run_ledger)) - 1]
            weak.append(refs[f"0,{j}"])
        m = self.ask({"op": "metrics", "R": refs, "label": "flow"})
        self.assertTrue(m["ok"], m.get("refused") or m.get("error"))
        self.assertEqual(m["result"]["point"]["FGT"], 0.0)
        self.assertGreater(m["result"]["point"]["FWT"], 0.0)       # nothing at i = 0
        strong = [refs[f"3,{j}"] for j in (1, 2, 3)]
        cmp_ = self.ask({"op": "compare", "label": "flow",
                         "family": [{"name": "R3 vs R0", "candidate": strong, "baseline": weak}]})
        self.assertTrue(cmp_["ok"], cmp_.get("refused") or cmp_.get("error"))
        self.assertEqual(cmp_["result"]["comparisons"][0]["pairs"]["losses"], 0)
        # 7. Probe misuse is refused; both ledgers replay without a mismatch.
        self.assertFalse(self.ask({"op": "evaluate", "pool": "selection_r2",
                                   "checkpoint": self.checkpoint})["ok"])
        for path in (self.canonical, run_ledger):
            self.assertEqual(replay.replay(path, self.judge)["mismatches"], [], path)


if __name__ == "__main__":
    unittest.main()
