"""Sealing: the judge copy is byte-identical to rsi4/run-p1 at c48c820, the guard blocks
every path into it (test_guard_blocks_pool_access; the attacks route by route are in
test_guard.py), and the static half: no solver module imports J in any form, imports a
module outside a short list, or names RSI-2's sealed partition.

The guard test runs in a subprocess because an audit hook cannot be removed."""
import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

RSI5 = Path(__file__).resolve().parents[1]
REPO = RSI5.parent
JUDGE_SOURCE_COMMIT = "c48c820f14a61611ac4a7d864ad780729c1f277f"

#: Everything a solver module may import besides this package's own solver modules. The
#: routes no audit event covers (ctypes, native modules, unaudited process starts, Tcl) are
#: closed here, statically: a module that would give one is not on the list.
STANDARD_LIBRARY = frozenset({
    "__future__", "argparse", "collections", "dataclasses", "functools", "hashlib", "itertools",
    "json", "math", "multiprocessing", "os", "pathlib", "platform", "random", "re", "sys", "time",
    "typing"})
#: The read-only loaders of the exposed partitions, and the only modules that may import them.
LOADERS = {"partitions.py": ("rsi2.corpus", "rsi3.compose24", "rsi3.fresh", "rsi3.reserve"),
           "audit_p1.py": ("rsi3.compose24",)}
#: RSI-2's sealed partition: its only loader module, that module's function, its file.
SEALED_PARTITION_NAMES = ("sealed_evaluation", "load_test", "test.json")


def imported_names(source: str, package: tuple) -> list:
    """Every module ``source`` imports, as absolute dotted names. ``package`` is the dotted
    path of the package the file lives in, so ``from . import x`` and ``from .. import x``
    resolve to what they load. ``from m import n`` yields both ``m`` and ``m.n``."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = list(package[:len(package) - (node.level - 1)]) if node.level else []
            module = ".".join(base + ([node.module] if node.module else []))
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def within(name: str, module: str) -> bool:
    return name == module or name.startswith(module + ".")


def imports_judge(source: str, package: tuple) -> list:
    return [name for name in imported_names(source, package) if within(name, "rsi5.judge")]


def import_allowed(name: str, loaders: tuple = ()) -> bool:
    from rsi5 import guard
    if guard._refused_module(name):                     # J, and the modules that bypass the hook
        return False
    if within(name, "rsi5"):
        return not within(name, "rsi5.tests")           # J's audit exempts tests/: no way around it
    return name.split(".")[0] in STANDARD_LIBRARY or any(within(name, loader) for loader in loaders)


def string_constants(source: str) -> list:
    """Every string a source spells out: its constants, and constants joined with ``+``."""
    def joined(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = joined(node.left), joined(node.right)
            return None if left is None or right is None else left + right
        if isinstance(node, ast.JoinedStr):
            parts = [joined(value) for value in node.values]
            return None if None in parts else "".join(parts)
        return None
    return [text for text in map(joined, ast.walk(ast.parse(source))) if text is not None]


def names_sealed_partition(source: str) -> list:
    tree = ast.parse(source)
    spelled = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
    spelled += [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]
    spelled += [name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names for name in (alias.name, alias.asname or "")]
    spelled += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    spelled += string_constants(source)
    return sorted({sealed for sealed in SEALED_PARTITION_NAMES for text in spelled if sealed in text})


class JudgeCopy(unittest.TestCase):
    def test_manifest_intact(self):
        from rsi5.judge import registry
        self.assertEqual(registry.verify_manifest(registry.JUDGE_DIR), [])

    def test_byte_identical_to_rsi4_run_p1(self):
        """Every file under rsi5/judge equals rsi4/judge at the source commit (needs git)."""
        try:
            listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", JUDGE_SOURCE_COMMIT,
                                      "rsi4/judge", "rsi4/data/stage_train.json"],
                                     cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("source commit not available in this checkout")
        self.assertGreater(len(listing), 20)
        for path in listing:
            original = subprocess.run(["git", "show", f"{JUDGE_SOURCE_COMMIT}:{path}"], cwd=REPO,
                                      capture_output=True, check=True).stdout
            copy = RSI5 / path.replace("rsi4/", "", 1)
            self.assertEqual(copy.read_bytes(), original, path)
        copied = sorted(str(p.relative_to(RSI5 / "judge")) for p in (RSI5 / "judge").rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts)
        expected = sorted(p.replace("rsi4/judge/", "", 1) for p in listing if p.startswith("rsi4/judge/"))
        self.assertEqual(copied, expected)


class Guard(unittest.TestCase):
    def test_guard_blocks_pool_access(self):
        script = r"""
import json, os, sys
sys.path.insert(0, %r)
from rsi5 import guard
assert guard.install()
out = {}
judge = os.path.join(%r, "judge")
for label, action in [
    ("open_pool", lambda: open(os.path.join(judge, "pools", "probe.json"))),
    ("open_seed", lambda: open(os.path.join(judge, "seed.json"))),
    ("open_assembled", lambda: open(os.path.join(judge, "po" + "ols", "stage_eval_S1.json"))),
    ("listdir", lambda: os.listdir(os.path.join(judge, "pools"))),
    ("scandir", lambda: list(os.scandir(judge))),
    ("source_file", lambda: open(os.path.join(%r, "list_tasks2.json"), "w")),
    ("import", lambda: __import__("rsi5.judge.registry")),
    ("import_pools", lambda: __import__("rsi5.judge.pools")),
]:
    try:
        action()
        out[label] = "allowed"
    except (PermissionError, ImportError) as exc:
        out[label] = type(exc).__name__
# ordinary files stay readable
with open(os.path.join(%r, "probes.py")) as handle:
    out["probes_py"] = "allowed" if handle.read(1) else "empty"
print(json.dumps(out))
""" % (str(REPO), str(RSI5), str(RSI5 / "data"), str(RSI5))
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                   cwd=REPO)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        out = json.loads(completed.stdout.strip().splitlines()[-1])
        for label in ("open_pool", "open_seed", "open_assembled", "listdir", "scandir", "source_file"):
            self.assertEqual(out[label], "PermissionError", label)
        self.assertEqual(out["import"], "ImportError")
        self.assertEqual(out["import_pools"], "ImportError")
        self.assertEqual(out["probes_py"], "allowed")


class StaticAudit(unittest.TestCase):
    """J's own static audit over rsi5/, plus the rsi5-specific import check."""

    def _solver_modules(self):
        for path in sorted(RSI5.rglob("*.py")):
            parts = path.relative_to(RSI5).parts
            if parts[0] in ("judge", "tests") or "__pycache__" in parts:
                continue
            yield path

    def _package(self, path) -> tuple:
        return ("rsi5",) + path.relative_to(RSI5).parts[:-1]

    def test_no_solver_module_imports_judge(self):
        for path in self._solver_modules():
            found = imports_judge(path.read_text(encoding="utf-8"), self._package(path))
            self.assertEqual(found, [], f"{path.relative_to(REPO)} imports {found}")

    def test_judge_import_check_catches_every_form(self):
        """The attacks: each way a solver module could import J, relative forms included
        (the copied audit flags no rsi5 import at all)."""
        top, engine = ("rsi5",), ("rsi5", "engine")
        attacks = [("import rsi5.judge", top), ("import rsi5.judge.pools as p", top),
                   ("from rsi5 import judge", top), ("from rsi5.judge import registry", top),
                   ("from rsi5.judge.pools import load", top),
                   ("from . import judge", top), ("from . import guard, judge as j", top),
                   ("from .judge import registry", top), ("from .judge.pools import load", top),
                   ("from .. import judge", engine), ("from ..judge import registry", engine),
                   ("from ..judge.pools import load", engine),
                   ("def f():\n    from . import judge\n    return judge", top)]
        for source, package in attacks:
            self.assertNotEqual(imports_judge(source, package), [], source)
        innocent = [("from . import guard as judge", top), ("from .dsl import terms", top),
                    ("from . import judge", engine),            # that would be rsi5.engine.judge
                    ("import rsi5.judgement", top), ("from .. import guard", engine)]
        for source, package in innocent:
            self.assertEqual(imports_judge(source, package), [], source)

    def test_solver_modules_import_only_the_listed_modules(self):
        for path in self._solver_modules():
            loaders = LOADERS.get(path.relative_to(RSI5).as_posix(), ())
            for name in imported_names(path.read_text(encoding="utf-8"), self._package(path)):
                self.assertTrue(import_allowed(name, loaders), f"{path.relative_to(REPO)} imports {name}")

    def test_import_list_refuses_the_unaudited_routes(self):
        """The attacks: modules that read a file or start a program with no audit event, the
        dynamic importers, J, the loaders outside the two modules that may use them, and the
        tests directory that J's audit exempts."""
        top = ("rsi5",)
        attacks = ["import ctypes", "from ctypes import CDLL", "import _ctypes", "import subprocess",
                   "import _posixsubprocess", "from multiprocessing import popen_spawn_posix",
                   "import multiprocessing.popen_forkserver", "import readline", "import mmap",
                   "import tkinter", "import socket", "import importlib", "from importlib import util",
                   "import runpy", "import pickle", "import numpy", "from . import judge",
                   "from .tests import guard_attacks", "import rsi5.tests.test_throughput",
                   "import rsi2.corpus", "from rsi3.compose24 import load_frozen_tasks",
                   "from rsi2 import sealed_evaluation", "import rsi4.judge"]
        for source in attacks:
            names = imported_names(source, top)
            self.assertFalse(all(import_allowed(name) for name in names), source)
        for source in ["import os", "import multiprocessing", "from pathlib import Path",
                       "from . import guard, partitions, probes", "from .dsl.types import Type"]:
            self.assertTrue(all(import_allowed(name) for name in imported_names(source, top)), source)
        self.assertTrue(all(import_allowed(name, LOADERS["partitions.py"])
                            for name in imported_names("from rsi3.fresh import load_fresh", top)))
        self.assertFalse(all(import_allowed(name, LOADERS["partitions.py"])
                             for name in imported_names("from rsi2 import sealed_evaluation", top)))

    def test_no_solver_module_names_the_sealed_partition(self):
        """RSI-2's sealed partition has one loader module, one loader function and one file;
        no solver module spells any of them. (The guard seals the file at run time, however
        its name is built: test_guard.py.)"""
        for path in self._solver_modules():
            found = names_sealed_partition(path.read_text(encoding="utf-8"))
            self.assertEqual(found, [], f"{path.relative_to(REPO)} names {found}")
        attacks = ["from rsi2.sealed_evaluation import load_test", "import rsi2.sealed_evaluation as s",
                   "from rsi2 import sealed_evaluation", "tasks = corpus.load_test()",
                   "open('rsi2/data/test.json')", "open('data/' + 'test' + '.json')",
                   "name = 'test'\nopen(f'rsi2/data/test.json')", "x = getattr(m, 'load_' + 'test')"]
        for source in attacks:
            self.assertNotEqual(names_sealed_partition(source), [], source)
        for source in ["from rsi2.corpus import load_train, load_validation",
                       "open('rsi2/data/train.json')", "latest = 1"]:
            self.assertEqual(names_sealed_partition(source), [], source)

    def test_judge_audit_findings_are_the_declared_ones(self):
        """J's audit (unchanged) over rsi5/: the only findings are the frozen verifier's
        reads of hidden examples, which is the module that exists to read them."""
        from rsi5.judge.audit import problems
        found = problems(RSI5)
        unexpected = [f for f in found if not f.startswith("verifier.py:")]
        self.assertEqual(unexpected, [])
        self.assertTrue(all("hidden" in f for f in found), found)


if __name__ == "__main__":
    unittest.main()
