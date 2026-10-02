"""Stage-2 corpus integrity and the structural boundary around sealed tasks."""

import ast
import inspect
import json
from pathlib import Path
import random
import unittest

from rsi2 import corpus
from rsi2.sealed_evaluation import load_test
from rsi2.types import Arrow, BOOL, INT, ListOf, function_parts


PACKAGE = Path(__file__).resolve().parents[1]
DATA = PACKAGE / "data"
LEARNING_MODULES = ("learning.py", "abstraction.py", "recognition.py", "heuristics.py")
SEALED_MODULES = ("search.py", "grammar.py") + LEARNING_MODULES


def static_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = static_string(node.left), static_string(node.right)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = [static_string(value) for value in node.values]
        return "".join(parts) if all(value is not None for value in parts) else None
    return None


def seal_violations(source):
    """Inspect executable syntax, including aliases and split path literals."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        symbols = []
        if isinstance(node, ast.Import):
            symbols.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            symbols.append(node.module or "")
            symbols.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            symbols.append(node.id)
        elif isinstance(node, ast.Attribute):
            symbols.append(node.attr)
        if any(part in ("sealed_evaluation", "load_test")
               for symbol in symbols for part in symbol.split(".")):
            violations.append((node.lineno, "sealed loader or evaluation module"))
        literal = static_string(node)
        if literal is not None:
            normalized = literal.replace("\\", "/").lower()
            if ("test.json" in normalized or literal == "load_test"
                    or normalized.split(".")[-1] == "sealed_evaluation"):
                violations.append((node.lineno, "sealed task path or dynamic loader"))
    return violations


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Corpus integrity is checked before learning; this is not an evaluation
        # and does not expose held-out search performance to any learning module.
        cls.splits = {"train": corpus.load_train(),
                      "validation": corpus.load_validation(),
                      "test": load_test()}

    def assert_value_type(self, value, expected_type):
        if expected_type == INT:
            self.assertIs(type(value), int)
        elif expected_type == BOOL:
            self.assertIs(type(value), bool)
        elif expected_type.tag == "list":
            self.assertIs(type(value), list)
            for element in value:
                self.assert_value_type(element, expected_type.args[0])
        else:
            self.fail(f"corpus value has unsupported type {expected_type}")

    def test_each_external_task_has_separate_search_and_hidden_examples(self):
        for split, tasks in self.splits.items():
            for task in tasks:
                with self.subTest(split=split, task=task.name):
                    self.assertGreaterEqual(len(task.examples), 10)
                    self.assertGreater(len(task.hidden), 0)
                    search_inputs = {json.dumps(inputs, sort_keys=True) for inputs, _ in task.examples}
                    hidden_inputs = {json.dumps(inputs, sort_keys=True) for inputs, _ in task.hidden}
                    self.assertEqual(len(search_inputs), len(task.examples))
                    self.assertEqual(len(hidden_inputs), len(task.hidden))
                    self.assertFalse(search_inputs & hidden_inputs)

    def test_every_example_matches_its_declared_input_and_output_types(self):
        for tasks in self.splits.values():
            for task in tasks:
                arguments, output = function_parts(task.request_type)
                for inputs, expected in task.examples + task.hidden:
                    with self.subTest(task=task.name, inputs=inputs):
                        self.assertIsInstance(inputs, tuple)
                        self.assertEqual(len(inputs), len(arguments))
                        for value, type_ in zip(inputs, arguments):
                            self.assert_value_type(value, type_)
                        self.assert_value_type(expected, output)

    def test_sixty_selected_concepts_have_disjoint_sixty_twenty_twenty_splits(self):
        names = {split: [task.name for task in tasks] for split, tasks in self.splits.items()}
        self.assertEqual({split: len(ids) for split, ids in names.items()},
                         {"train": 36, "validation": 12, "test": 12})
        all_names = [name for ids in names.values() for name in ids]
        self.assertEqual(len(all_names), 60)
        self.assertEqual(len(set(all_names)), 60)
        self.assertFalse(set(names["train"]) & set(names["validation"]))
        self.assertFalse(set(names["train"]) & set(names["test"]))
        self.assertFalse(set(names["validation"]) & set(names["test"]))

    def test_recorded_seed_independently_reproduces_selection_and_partition(self):
        manifest = json.loads((DATA / "split_manifest.json").read_text())
        self.assertEqual(manifest["seed"], 20261002)
        eligible = manifest["eligible_names"]
        self.assertEqual(len(eligible), len(set(eligible)))
        self.assertEqual(manifest["population"], len(eligible))
        self.assertGreaterEqual(len(eligible), 60)
        ordered = sorted(eligible)
        random.Random(manifest["seed"]).shuffle(ordered)
        selected = ordered[:60]
        expected = {"train": selected[:36],
                    "validation": selected[36:48], "test": selected[48:60]}
        for split, names in expected.items():
            with self.subTest(split=split):
                self.assertEqual(manifest[split], names)
                self.assertEqual([task.name for task in self.splits[split]], names)

    def test_normalized_examples_come_directly_from_the_external_source(self):
        records = json.loads((DATA / "source_list_tasks.json").read_text())
        manifest = json.loads((DATA / "split_manifest.json").read_text())
        sources = {record["name"]: record for record in records}
        self.assertEqual(len(sources), len(records))
        types = {"int": INT, "bool": BOOL,
                 "list-of-int": ListOf(INT), "list-of-bool": ListOf(BOOL)}
        deduplicated = {}
        for record in records:
            seen = {}
            examples = []
            for example in record["examples"]:
                key = json.dumps(example["i"], sort_keys=True)
                if key in seen:
                    self.assertEqual(seen[key], example["o"], record["name"])
                else:
                    seen[key] = example["o"]
                    examples.append(((example["i"],), example["o"]))
            deduplicated[record["name"]] = examples
        eligible = {name for name, examples in deduplicated.items() if len(examples) >= 11}
        self.assertEqual(set(manifest["eligible_names"]), eligible)
        for tasks in self.splits.values():
            for task in tasks:
                with self.subTest(task=task.name):
                    self.assertIn(task.name, sources)
                    examples = deduplicated[task.name]
                    self.assertEqual(task.examples, tuple(examples[:10]))
                    self.assertEqual(task.hidden, tuple(examples[10:]))
                    declared = sources[task.name]["type"]
                    self.assertEqual(task.request_type,
                                     Arrow(types[declared["input"]], types[declared["output"]]))

    def test_training_loaders_cannot_select_the_sealed_partition(self):
        public_loaders = {name for name, value in vars(corpus).items()
                          if name.startswith("load_") and callable(value)}
        self.assertEqual(public_loaders, {"load_train", "load_validation"})
        self.assertFalse(hasattr(corpus, "load_test"))
        for loader in (corpus.load_train, corpus.load_validation):
            self.assertEqual(len(inspect.signature(loader).parameters), 0)
            with self.assertRaises(TypeError):
                loader("test")
            with self.assertRaises(TypeError):
                loader(split="test")


class StructuralSealTests(unittest.TestCase):
    def test_learning_and_search_modules_do_not_reference_sealed_tasks(self):
        if (PACKAGE / "learning.py").exists():
            for filename in LEARNING_MODULES:
                self.assertTrue((PACKAGE / filename).is_file(),
                                f"Stage 3 must include and scan {filename}")
        for filename in SEALED_MODULES:
            path = PACKAGE / filename
            if path.exists():
                self.assertEqual(seal_violations(path.read_text()), [], filename)

    def test_seal_scanner_catches_import_aliases_attributes_and_composed_paths(self):
        prohibited = (
            "import rsi2.sealed_evaluation as innocuous",
            "from rsi2 import sealed_evaluation as innocuous",
            "from .sealed_evaluation import report",
            "module.load_test()",
            "getattr(module, 'load_test')()",
            "open('data/test.json')",
            "open('data/' + 'test' + '.json')",
            "Path('data') / 'test.json'",
        )
        for source in prohibited:
            with self.subTest(source=source):
                self.assertTrue(seal_violations(source))
        self.assertEqual(seal_violations("from .corpus import load_train, load_validation"), [])


if __name__ == "__main__":
    unittest.main()
