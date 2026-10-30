"""Structural audits: hidden examples, sealed partitions, and protected code."""
import ast
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SOURCES = sorted(p for p in PACKAGE.glob("*.py"))
# Runners load the splits to drive and measure runs; nothing they load is
# passed to a learning component except TRAIN public views.
RUNNERS = ("experiment.py", "longrun.py", "reserve.py", "reserve_eval.py", "fresh.py")
LEARNING = [p for p in SOURCES if p.name not in (*RUNNERS, "verifier.py", "__init__.py")]


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _attributes(tree):
    return {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def _names(tree):
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


class SealingTests(unittest.TestCase):
    def test_only_the_verifier_reads_hidden_examples(self):
        for path in SOURCES:
            if path.name == "verifier.py":
                continue
            self.assertNotIn("hidden", _attributes(_tree(path)), path.name)

    def test_test_partition_is_never_opened(self):
        for path in SOURCES:
            names = _names(_tree(path))
            self.assertNotIn("load_test", names, path.name)
            self.assertFalse(any("sealed_evaluation" in name for name in names), path.name)
            self.assertNotIn("test.json", path.read_text(encoding="utf-8"), path.name)

    def test_learning_modules_load_no_partition(self):
        for path in LEARNING:
            names = _names(_tree(path))
            for forbidden in ("load_train", "load_validation", "assess"):
                self.assertNotIn(forbidden, names, f"{path.name} references {forbidden}")

    def test_legacy_runtime_is_not_imported(self):
        for path in [*SOURCES, *PACKAGE.glob("studies/*.py")]:
            self.assertNotIn("rsi_levels_metaforge_unified", path.read_text(encoding="utf-8"),
                             path.name)

    def test_rsi2_package_is_imported_not_modified(self):
        """RSI-3 depends on RSI-2 read-only; no module writes into rsi2."""
        for path in SOURCES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("rsi2/", text.replace("rsi2/data", ""), path.name)


if __name__ == "__main__":
    unittest.main()
