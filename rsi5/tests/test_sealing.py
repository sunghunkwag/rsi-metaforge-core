"""Sealing: the judge copy is byte-identical to rsi4/run-p1 at c48c820, the guard blocks
every path into it (test_guard_blocks_pool_access), and no solver module imports J.

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

    def test_no_solver_module_imports_judge(self):
        for path in self._solver_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
                    if node.level and "judge" in names[0]:
                        names.append("rsi5.judge")
                for name in names:
                    self.assertFalse(name == "rsi5.judge" or name.startswith("rsi5.judge."),
                                     f"{path.relative_to(REPO)} imports {name}")

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
