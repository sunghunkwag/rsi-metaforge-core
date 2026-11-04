"""Held-out tables and the reproduction check are arithmetic over evaluation and run files."""
import unittest

from rsi3.heldout_report import family, render, reproduction, summary


def _eval(arm, seeds):
    return {"arm": arm, "partition": "near", "generation": 16, "tasks": 3,
            "seeds": {str(s): {"solved": sum(v for _, v in rows), "solved_names": [n for n, v in rows if v],
                               "tasks": [{"name": n, "solved": v, "spent": {"prior": 4, "behave:map": 2},
                                          **({"analogy_from": ["src", "replace[0]"]} if v and n.startswith("add") else {})}
                                         for n, v in rows]}
                      for s, rows in seeds.items()}}


class HeldoutReportTests(unittest.TestCase):
    def test_family_names(self):
        self.assertEqual(family("near", "add-k with k=3"), "add-k")
        self.assertEqual(family("compose24", "fresh20261031::trim-and-increment::p2"), "trim-and-increment")
        self.assertEqual(family("fresh2", "((add-k (dyn . 0) (static . 3)) (reverse (dyn . 1)))"),
                         "add-k then reverse")
        self.assertEqual(family("fresh1", "((uniq (dyn . 0)))"), "uniq")

    def test_summary_and_render(self):
        rows = [("add-k with k=1", True), ("add-k with k=2", False), ("sum", True)]
        s = summary(_eval("ARM", {11: rows, 22: rows}))
        self.assertEqual(s["solved"], {"11": 2, "22": 2})
        self.assertEqual(s["by_family"]["11"], {"add-k": [1, 2], "sum": [1, 1]})
        self.assertEqual(s["spent"]["11"], {"prior": 12, "behave:map": 6})
        self.assertEqual(s["via"]["11"], [("add-k with k=1", "analogy", ["src", "replace[0]"])])
        text = render([s])
        self.assertIn("| ARM | 2 | 2 |", text)
        self.assertIn("| add-k | 1/2 |", text)
        self.assertIn("add-k with k=1: analogy from ['src', 'replace[0]']", text)

    def test_reproduction_check(self):
        def run(train, names):
            return {"generations": [{"train_solved": t, "validation": {"solved": 1},
                                     "validation_agent": {"solved": 2}} for t in train],
                    "final": {"solutions": names, "library": {"a": "x"}}}
        same = reproduction(run([1, 2], ["p", "q"]), run([1, 2], ["p", "q"]))
        self.assertTrue(all(c["match"] for c in same.values()))
        other = reproduction(run([1, 3], ["p", "q"]), run([1, 2], ["p", "q"]))
        self.assertFalse(other["train"]["match"])
        self.assertTrue(other["solutions"]["match"])
        text = render([summary(_eval("ARM", {11: [("sum", True)]}))], {("ARM", 11): other})
        self.assertIn("| ARM | 11 | **differs** | match | match | match | match |", text)


if __name__ == "__main__":
    unittest.main()
