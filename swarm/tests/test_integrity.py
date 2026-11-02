"""Integrity invariants (OWNER_DIRECTIVE.md §9) that concern the kernel and the package layout."""
import ast
import json
from pathlib import Path
import subprocess
import unittest

from swarm.kernel import hashes

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parent
KERNEL = PACKAGE / "kernel"
PROTECTED = ("rsi2", "rsi3", "docs", "rsi_levels_metaforge_unified.py", "EVIDENCE.md",
             "OUTER_LOOP_CONSTITUTION.md", ".github")
VAULT_SYMBOLS = ("vault", "sealed_")


def python_files(directory: Path, exclude=()):
    return sorted(p for p in directory.rglob("*.py")
                  if "__pycache__" not in p.parts and not any(x in p.parts for x in exclude))


def identifiers(path: Path) -> set:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found.add(node.name)
    return found


class IntegrityTests(unittest.TestCase):
    def test_kernel_is_hash_pinned(self):
        pins = hashes.verify()
        self.assertEqual(set(pins), set(hashes.KERNEL_FILES) | set(hashes.PINNED_MUTABLE))
        self.assertEqual(pins, hashes.pinned())

    def test_tampering_with_a_kernel_file_aborts_import(self):
        code = ("import sys; sys.path.insert(0, %r)\n"
                "from pathlib import Path\n"
                "p = Path(%r) / 'budget.py'; original = p.read_bytes()\n"
                "p.write_bytes(original + b'\\n# tampered\\n')\n"
                "try:\n"
                "    import swarm.kernel\n"
                "    print('imported')\n"
                "except Exception as exc:\n"
                "    print(type(exc).__name__)\n"
                "finally:\n"
                "    p.write_bytes(original)\n") % (str(ROOT), str(KERNEL))
        out = subprocess.run(["python3", "-c", code], capture_output=True, text=True, cwd=ROOT)
        self.assertIn("KernelTampered", out.stdout + out.stderr)

    def test_vault_symbols_appear_only_in_the_kernel(self):
        for path in python_files(PACKAGE, exclude=("kernel", "tests")):
            names = {n.lower() for n in identifiers(path)}
            for symbol in VAULT_SYMBOLS:
                self.assertFalse(any(symbol in n for n in names), f"{path} references {symbol}")
            self.assertNotIn("swarm.kernel.vault", path.read_text(encoding="utf-8"), str(path))

    def test_meter_is_the_sole_cost_counter(self):
        """Only the kernel charges the meter; the Builder's counts come from the pinned evaluator."""
        for path in python_files(PACKAGE, exclude=("kernel", "tests")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self.assertNotEqual(node.name, "charge", f"{path} defines charge")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(node.func.attr, "charge", f"{path} charges a meter")
        evaluator = PACKAGE / "builder" / "mutable" / "evaluator.py"
        self.assertIn("builder/mutable/evaluator.py", hashes.pinned())
        self.assertEqual(hashes.sha256_of(evaluator), hashes.pinned()["builder/mutable/evaluator.py"])

    def test_no_benchmark_is_read(self):
        for path in [*python_files(PACKAGE, exclude=("tests",)), *PACKAGE.glob("*.md"),
                     *PACKAGE.glob("*.json")]:
            text = path.read_text(encoding="utf-8")
            for token in ("load_test", "load_train", "load_validation", "test.json", "train.json",
                          "validation.json", "sealed_evaluation", "fresh_tasks"):
                self.assertNotIn(token, text, f"{path} references {token}")

    def test_protected_files_untouched_and_not_imported(self):
        try:
            result = subprocess.run(["git", "diff", "--stat", "main", "--", *PROTECTED], cwd=ROOT,
                                    capture_output=True, text=True, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            self.skipTest(f"git unavailable: {exc}")
        self.assertEqual(result.stdout.strip(), "", result.stdout)
        # Provenance comments may name the original core; no module imports it or rsi2/rsi3.
        for path in python_files(PACKAGE, exclude=("tests",)):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                for name in names:
                    root = name.split(".")[0]
                    self.assertNotIn(root, ("rsi_levels_metaforge_unified", "rsi2", "rsi3"),
                                     f"{path} imports protected code ({name})")

    def test_mutable_tree_is_self_contained(self):
        tree = PACKAGE / "builder" / "mutable"
        for path in python_files(tree):
            text = path.read_text(encoding="utf-8")
            for module in ("import rsi2", "from rsi2", "import rsi3", "from rsi3"):
                self.assertNotIn(module, text, f"{path} imports a protected package")
        for name in ("forged.json", "library.json", "params.json"):
            json.loads((tree / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
