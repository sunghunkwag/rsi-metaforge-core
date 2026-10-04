"""Metadata-only checks for the family-disjoint follow-up research corpus."""

import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.research import transfer
from rsi2.research.sealed_audit import load_audit
from rsi2.types import Arrow, BOOL, INT, ListOf


PACKAGE = Path(__file__).resolve().parents[1]
ORIGINAL_DATA = PACKAGE / "data"
SEED = 20261004
DECLARED_TYPES = {"int": INT, "bool": BOOL,
                  "list-of-int": ListOf(INT), "list-of-bool": ListOf(BOOL)}


def canonical(value):
    """JSON equality preserves the distinction between booleans and integers."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def unique_examples(record):
    seen = set()
    result = []
    for example in record["examples"]:
        key = canonical(example["i"])
        if key not in seen:
            seen.add(key)
            result.append({"inputs": [example["i"]], "output": example["o"]})
    return result


def synthetic_record(input_type="int", output_type="int", examples=None):
    if examples is None:
        examples = [{"i": i, "o": i * 2} for i in range(11)]
    return {"name": "synthetic with k=1",
            "type": {"input": input_type, "output": output_type},
            "examples": examples}


class NormalizationTests(unittest.TestCase):
    def test_family_uses_the_first_parameter_delimiter(self):
        for name, expected in (("reverse", "reverse"),
                               ("add-k with k=4", "add-k"),
                               ("slice-k-n with k=2 and n=5", "slice-k-n"),
                               ("custom with a=1 with b=2", "custom")):
            with self.subTest(name=name):
                self.assertEqual(transfer.family(name), expected)

    def test_normalization_deduplicates_in_source_order_and_preserves_values(self):
        order = [5, 1, 9, 2, 8, 0, 4, 7, 6, 3, 10, 11]
        examples = [{"i": [i, -i], "o": [i * 2, 0]} for i in order]
        examples.insert(3, deepcopy(examples[0]))
        examples.append(deepcopy(examples[10]))
        source = synthetic_record("list-of-int", "list-of-int", examples)
        before = deepcopy(source)
        normalized = transfer.normalize_record(source)
        expected = [{"inputs": [[i, -i]], "output": [i * 2, 0]} for i in order]
        self.assertEqual(normalized["name"], source["name"])
        self.assertEqual(normalized["examples"], expected[:10])
        self.assertEqual(normalized["hidden"], expected[10:])
        self.assertEqual(source, before)

    def test_declared_types_are_mapped_without_rewriting_json_values(self):
        cases = (
            ("int", "list-of-int", [{"i": i, "o": [i, -i]} for i in range(11)]),
            ("list-of-int", "bool", [{"i": [i], "o": i % 2 == 0} for i in range(11)]),
            ("list-of-int", "list-of-bool",
             [{"i": [i], "o": [i % 2 == 0, False]} for i in range(11)]),
            ("list-of-bool", "int", [{"i": [False] * i, "o": i} for i in range(11)]),
        )
        for input_type, output_type, examples in cases:
            with self.subTest(input_type=input_type, output_type=output_type):
                normalized = transfer.normalize_record(
                    synthetic_record(input_type, output_type, examples))
                declared = Arrow(DECLARED_TYPES[input_type], DECLARED_TYPES[output_type])
                self.assertEqual(normalized["request_type"], declared.to_dict())
                expected = [{"inputs": [e["i"]], "output": e["o"]} for e in examples]
                self.assertEqual(canonical(normalized["examples"] + normalized["hidden"]),
                                 canonical(expected))

    def test_eligibility_counts_distinct_inputs_and_requires_eleven(self):
        ten = [{"i": i, "o": i * 2} for i in range(10)]
        self.assertIsNone(transfer.normalize_record(synthetic_record(examples=ten * 3)))
        normalized = transfer.normalize_record(synthetic_record())
        self.assertEqual(len(normalized["examples"]), 10)
        self.assertEqual(len(normalized["hidden"]), 1)

    def test_duplicate_inputs_with_the_same_label_are_accepted(self):
        source = synthetic_record()
        expected = transfer.normalize_record(source)
        source["examples"].insert(2, deepcopy(source["examples"][0]))
        source["examples"].append(deepcopy(source["examples"][-1]))
        self.assertEqual(transfer.normalize_record(source), expected)

    def test_conflicting_duplicate_labels_include_boolean_integer_distinctions(self):
        for output_type, first, conflict in (("int", 1, 2), ("int", 1, True),
                                             ("list-of-int", [1], [True])):
            with self.subTest(first=first, conflict=conflict):
                examples = [{"i": i, "o": first} for i in range(11)]
                examples.append({"i": 0, "o": conflict})
                with self.assertRaises(ValueError):
                    transfer.normalize_record(synthetic_record("int", output_type, examples))


class TransferIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Source examples are copied as data; no search, evaluation, or original
        # outcome files are accessed by this follow-up integrity suite.
        cls.sources = json.loads((ORIGINAL_DATA / "source_list_tasks.json").read_text())
        cls.original_manifest = json.loads((ORIGINAL_DATA / "split_manifest.json").read_text())
        cls.original_names = [name for split in ("train", "validation", "test")
                              for name in cls.original_manifest[split]]
        cls.manifest, cls.confirmation, cls.audit = transfer.build_transfer(
            cls.sources, cls.original_names, seed=SEED)
        cls.source_by_name = {record["name"]: record for record in cls.sources}
        cls.eligible = sorted(record["name"] for record in cls.sources
                              if len(unique_examples(record)) >= 11)
        cls.excluded_families = {name.split(" with ", 1)[0] for name in cls.original_names}
        cls.remaining = [name for name in cls.eligible
                         if name.split(" with ", 1)[0] not in cls.excluded_families]
        cls.families = {}
        for name in cls.remaining:
            cls.families.setdefault(name.split(" with ", 1)[0], []).append(name)

    def test_manifest_accounts_for_the_source_and_family_exclusions(self):
        self.assertEqual(len(self.sources), 217)
        self.assertEqual(len(self.eligible), 207)
        self.assertEqual(len(self.original_names), 60)
        self.assertEqual(len(set(self.original_names)), 60)
        self.assertEqual(len(self.remaining), 47)
        self.assertEqual(len(self.families), 26)
        self.assertEqual(self.manifest["seed"], SEED)
        self.assertEqual(self.manifest["source_records"], 217)
        self.assertEqual(self.manifest["eligible_records"], 207)
        self.assertEqual(set(self.manifest["original_selected_names"]), set(self.original_names))
        self.assertEqual(self.manifest["excluded_families"], sorted(self.excluded_families))
        excluded_names = sorted(set(self.eligible) - set(self.remaining))
        self.assertEqual(self.manifest["excluded_eligible_names"], excluded_names)
        self.assertEqual(self.manifest["remaining_names"], self.remaining)
        self.assertEqual(self.manifest["remaining_families"], self.families)
        ineligible = self.manifest["ineligible_records"]
        self.assertEqual(len(ineligible), 10)
        self.assertEqual({record["name"] for record in ineligible},
                         set(self.source_by_name) - set(self.eligible))
        for record in ineligible:
            self.assertEqual(record["distinct_inputs"],
                             len(unique_examples(self.source_by_name[record["name"]])))
            self.assertLess(record["distinct_inputs"], 11)
            self.assertTrue(record["reason"])

    def test_partition_ids_and_all_original_families_are_disjoint(self):
        confirmation = {record["name"] for record in self.confirmation}
        audit = {record["name"] for record in self.audit}
        confirmation_families = {name.split(" with ", 1)[0] for name in confirmation}
        audit_families = {name.split(" with ", 1)[0] for name in audit}
        self.assertEqual(len(self.confirmation), 6)
        self.assertEqual(len(self.audit), 8)
        self.assertEqual(len(confirmation_families), 6)
        self.assertEqual(len(audit_families), 8)
        self.assertFalse(confirmation & audit)
        self.assertFalse(confirmation_families & audit_families)
        self.assertFalse((confirmation | audit) & set(self.original_names))
        self.assertFalse((confirmation_families | audit_families) & self.excluded_families)
        self.assertEqual(self.manifest["confirmation"], [r["name"] for r in self.confirmation])
        self.assertEqual(self.manifest["audit"], [r["name"] for r in self.audit])
        self.assertEqual(self.manifest["sample_counts"], {"confirmation": 6, "audit": 8})

    def test_fixed_seed_independently_reproduces_families_and_members(self):
        rng = random.Random(SEED)
        families = sorted(self.families)
        rng.shuffle(families)
        confirmation_families, audit_families = families[:6], families[6:14]
        selected = [rng.choice(sorted(self.families[family])) for family in families[:14]]
        self.assertEqual(self.manifest["shuffled_families"], families)
        self.assertEqual(self.manifest["confirmation_families"], confirmation_families)
        self.assertEqual(self.manifest["audit_families"], audit_families)
        self.assertEqual(self.manifest["unused_families"], families[14:])
        self.assertEqual(self.manifest["confirmation"], selected[:6])
        self.assertEqual(self.manifest["audit"], selected[6:])
        reordered = transfer.build_transfer(list(reversed(self.sources)),
                                            list(reversed(self.original_names)), seed=SEED)
        self.assertEqual(reordered, (self.manifest, self.confirmation, self.audit))

    def test_selected_records_retain_original_examples_and_declared_types(self):
        for record in self.confirmation + self.audit:
            with self.subTest(name=record["name"]):
                source = self.source_by_name[record["name"]]
                expected = unique_examples(source)
                self.assertEqual(canonical(record["examples"]), canonical(expected[:10]))
                self.assertEqual(canonical(record["hidden"]), canonical(expected[10:]))
                declared = source["type"]
                request = Arrow(DECLARED_TYPES[declared["input"]],
                                DECLARED_TYPES[declared["output"]])
                self.assertEqual(record["request_type"], request.to_dict())
                public_inputs = {canonical(e["inputs"]) for e in record["examples"]}
                hidden_inputs = {canonical(e["inputs"]) for e in record["hidden"]}
                self.assertEqual(len(public_inputs), 10)
                self.assertEqual(len(hidden_inputs), len(record["hidden"]))
                self.assertFalse(public_inputs & hidden_inputs)

    def test_preparation_is_deterministic_and_writes_only_the_requested_directory(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.json"
            original_path = root / "original_manifest.json"
            source_path.write_text(json.dumps(self.sources))
            original_path.write_text(json.dumps(self.original_manifest))
            original_bytes = (source_path.read_bytes(), original_path.read_bytes())
            expected_manifest = {**self.manifest,
                                 "source_repository": self.original_manifest["source_repository"],
                                 "source_commit": self.original_manifest["source_commit"]}
            outputs = [root / "first", root / "second"]
            for directory in outputs:
                manifest = transfer.prepare(directory, source_path, original_path)
                self.assertEqual(manifest, expected_manifest)
                self.assertEqual({p.name for p in directory.iterdir()},
                                 {"manifest.json", "confirmation.json", "audit.json"})
                self.assertEqual(json.loads((directory / "confirmation.json").read_text()),
                                 self.confirmation)
                self.assertEqual(json.loads((directory / "audit.json").read_text()), self.audit)
                self.assertEqual(json.loads((directory / "manifest.json").read_text()),
                                 expected_manifest)
            first = {p.name: p.read_bytes() for p in outputs[0].iterdir()}
            second = {p.name: p.read_bytes() for p in outputs[1].iterdir()}
            self.assertEqual(first, second)
            transfer.prepare(outputs[0], source_path, original_path)
            self.assertEqual(first, {p.name: p.read_bytes() for p in outputs[0].iterdir()})
            self.assertEqual(original_bytes, (source_path.read_bytes(), original_path.read_bytes()))
            self.assertEqual({p.name for p in root.iterdir()},
                             {"source.json", "original_manifest.json", "first", "second"})

    def test_loaders_open_only_their_partition_and_leave_files_unchanged(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "confirmation.json").write_text(json.dumps(self.confirmation))
            (directory / "audit.json").write_text(json.dumps(self.audit))
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
            original_read = Path.read_text
            for loader, filename, expected in (
                (transfer.load_confirmation, "confirmation.json", self.confirmation),
                (load_audit, "audit.json", self.audit),
            ):
                reads = []

                def partition_read(path, *args, **kwargs):
                    reads.append(path)
                    self.assertEqual(path, directory / filename)
                    return original_read(path, *args, **kwargs)

                with self.subTest(filename=filename), patch.object(Path, "read_text", partition_read):
                    tasks = loader(directory)
                    self.assertEqual(reads, [directory / filename])
                    self.assertTrue(all(isinstance(task, Task) for task in tasks))
                    self.assertEqual([task.name for task in tasks], [r["name"] for r in expected])
                    for task, record in zip(tasks, expected):
                        self.assertEqual(task.examples,
                                         tuple((tuple(e["inputs"]), e["output"])
                                               for e in record["examples"]))
                        self.assertEqual(task.hidden,
                                         tuple((tuple(e["inputs"]), e["output"])
                                               for e in record["hidden"]))
            after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
            self.assertEqual(after, before)

    def test_default_loaders_use_the_new_research_data_directory(self):
        directory = PACKAGE / "research" / "data"
        for loader, filename, records in (
            (transfer.load_confirmation, "confirmation.json", self.confirmation),
            (load_audit, "audit.json", self.audit),
        ):
            reads = []

            def partition_read(path, *args, **kwargs):
                reads.append(path)
                self.assertEqual(path, directory / filename)
                return json.dumps(records)

            with self.subTest(filename=filename), patch.object(Path, "read_text", partition_read):
                self.assertEqual([task.name for task in loader()], [r["name"] for r in records])
                self.assertEqual(reads, [directory / filename])

    def test_public_transfer_module_does_not_import_or_expose_the_audit_loader(self):
        public_loaders = {name for name, value in vars(transfer).items()
                          if name.startswith("load_") and callable(value)}
        self.assertEqual(public_loaders, {"load_confirmation"})
        self.assertFalse(hasattr(transfer, "load_audit"))
        source = ast.parse(inspect.getsource(transfer))
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
                self.assertFalse({"sealed_audit", "load_audit"} & set(symbol.split(".")), symbol)


if __name__ == "__main__":
    unittest.main()
