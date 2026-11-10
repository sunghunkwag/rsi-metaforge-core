"""The guard under attack (``rsi5/guard.py``) and the run driver's process layout.

Every route into a sealed path that the Phase 1 review and its follow-up found is
constructed here and must be refused: descriptors, ``dir_fd``, the working directory, links,
renames, child programs, every import form, a worker that could load or inherits tasks.

Each scenario runs ``guard_attacks.py`` in a fresh interpreter, because an audit hook cannot
be removed. The attacks target a decoy tree built in a temporary directory: a package with a
sealed sub-package that holds a secret file and a ``pools`` directory. Nothing in this module
opens, lists or imports J.
"""
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import unittest

from rsi5 import guard, partitions

RSI5 = Path(__file__).resolve().parents[1]
REPO = RSI5.parent
ATTACKS = Path(__file__).with_name("guard_attacks.py")

DECOY = {
    "decoypkg/__init__.py": "",
    "decoypkg/relative_dot.py": "from . import sealed\n",
    "decoypkg/relative_module.py": "from .sealed import inner\n",
    "decoypkg/sub/__init__.py": "",
    "decoypkg/sub/relative_dotdot.py": "from .. import sealed as s\n",
    "decoypkg/sealed/__init__.py": "VALUE = 'decoy-secret'\n",
    "decoypkg/sealed/inner.py": "VALUE = 'decoy-inner'\n",
    "decoypkg/sealed/secret.txt": "decoy-secret\n",
    "decoypkg/sealed/pools/a.json": "{}\n",
    "open/readme.txt": "readable\n",
    "open/spare.txt": "spare\n",
    "open/list_tasks2.json": "[]\n",
    "corpus/kept.json": "{\"kept\": true}\n",
    "corpus/other.json": "{\"other\": true}\n",
}
#: The task counts of the exposed partitions (``RESULTS_P1.md``).
PARTITION_SIZES = {"fresh1": 33, "fresh2": 100, "near": 100, "far2": 21, "compose24": 24,
                   "validation": 12, "far": 12, "train": 36}


def snapshot(root: Path) -> dict:
    """Relative path -> content for every file, and None for every directory, below ``root``."""
    tree = {}
    for path in sorted(root.rglob("*")):
        if "__pycache__" not in path.parts:
            tree[path.relative_to(root).as_posix()] = None if path.is_dir() else path.read_text()
    return tree


class Attack(unittest.TestCase):
    maxDiff = None

    def attack(self, mode: str, start: str = "") -> tuple:
        """Run one mode on a fresh decoy tree; return (outcomes, tree before, tree after)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name, text in DECOY.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text, encoding="utf-8")
            before = snapshot(root)
            completed = subprocess.run([sys.executable, "-B", str(ATTACKS), mode, str(root)],
                                       capture_output=True, text=True, cwd=root / start, timeout=900)
            self.assertEqual(completed.returncode, 0, completed.stderr[-4000:])
            lines = completed.stdout.strip().splitlines()
            self.assertEqual(len(lines), 1, completed.stdout[-2000:])      # nothing else was printed
            return json.loads(lines[0]), before, snapshot(root)


class Paths(Attack):
    def test_every_path_into_a_sealed_directory_is_refused(self):
        out, before, after = self.attack("paths")
        # os.walk and glob swallow the refusal of their directory scan and yield nothing.
        empty = {"walk": "allowed:[]", "glob": "allowed:[]"}
        # Pinned, not closed: a descriptor opened before install() stays readable (os.read raises
        # no audit event). guard.py and RESULTS_P1.md list it among the routes not stopped.
        residual = {"residual_read_of_descriptor_opened_before_install": "allowed:b'decoy'"}
        for name, result in out.items():
            self.assertEqual(result, {**empty, **residual}.get(name, "PermissionError"), name)
        self.assertEqual(len(out), 35)
        # No attack moved, copied or linked anything; the one new entry is the symbolic link,
        # which the hook cannot refuse (creating it reads nothing) and refuses to follow.
        self.assertEqual(sorted(set(after) - set(before)), ["alias"])
        self.assertEqual({name: after[name] for name in before}, before)

    def test_working_directory_inside_a_sealed_directory(self):
        out, _, _ = self.attack("working_directory", start="decoypkg/sealed")
        self.assertEqual(out, {"listdir_no_argument": "PermissionError", "scandir_no_argument": "PermissionError",
                               "listdir_dot": "PermissionError", "relative_open": "PermissionError",
                               "iterdir": "PermissionError", "glob": "allowed:[]"})

    def test_keep_list_can_only_tighten(self):
        out, _, _ = self.attack("keep")
        kept = "allowed:'{\"kept\": true}\\n'"
        self.assertEqual(out, {"kept": kept, "other": "PermissionError", "listdir": "PermissionError",
                               "kept_after_wider_keep": kept, "other_after_wider_keep": "PermissionError",
                               "kept_after_whole_seal": "PermissionError",
                               "kept_after_reseal_with_keep": "PermissionError"})

    def test_ordinary_work_is_not_refused(self):
        out, _, _ = self.attack("benign")
        self.assertEqual(out, {"read": "allowed:'readable\\n'", "relative_read": "allowed:'readable\\n'",
                               "listdir": "allowed:['corpus', 'decoypkg']", "rename": "allowed:None",
                               "new_import": "allowed:'colorsys'", "package_source": "allowed:True",
                               "temporary_directory": "allowed:'x'", "fork_pool": "allowed:[1, 2, 3]"})


class Programs(Attack):
    def test_starting_another_program_is_refused(self):
        out, _, _ = self.attack("spawn")
        self.assertEqual(out, {
            "subprocess": "PermissionError", "os_system": "PermissionError", "os_popen": "PermissionError",
            "posix_spawn": "PermissionError",
            # os.fork is allowed (the child inherits the hook); the exec is refused in the child:
            "spawnv": "allowed:127",              # os.spawnv's child exits 127 when its exec raises
            "fork_then_exec": "allowed:42",       # the child caught PermissionError and exited 42
            # The start methods that launch a fresh interpreter, and the unaudited file reader:
            "spawn_start_method": "ImportError", "forkserver_start_method": "ImportError",
            "readline": "ImportError", "readline_statement": "ImportError"})


class Imports(Attack):
    def test_importing_a_sealed_package_is_refused_in_every_form(self):
        out, _, _ = self.attack("imports")
        by_name = ("import", "import_below", "from_package", "from_module", "dunder_import",
                   "relative_dot", "relative_dotdot", "relative_module", "run_module")
        by_path = ("import_module", "import_module_relative", "spec_loader")   # no import event is raised
        self.assertEqual(out, {**{name: "ImportError" for name in by_name},
                               **{name: "PermissionError" for name in by_path},
                               "sealed_modules_loaded": []})

    def test_modules_imported_before_install_are_reported(self):
        out, _, _ = self.attack("preloaded")
        self.assertEqual(out, {"before": [], "after_install": ["multiprocessing.popen_spawn_posix"],
                               "after_seal": ["colorsys", "multiprocessing.popen_spawn_posix"]})


class SealedSet(unittest.TestCase):
    """The rules on the real paths, decided from strings alone: nothing is opened or listed
    except the names of RSI-2's task-file directory."""

    def test_judge_directory_is_sealed_whole(self):
        inside = os.path.join(guard.BLOCKED_DIR, "anything", "below.json")
        self.assertTrue(guard._is_blocked(guard.BLOCKED_DIR))
        self.assertTrue(guard._is_blocked(inside))
        self.assertTrue(guard._contains_sealed(str(RSI5)))                 # so rsi5/ cannot be renamed
        self.assertFalse(guard._is_blocked(guard.BLOCKED_DIR + "_other"))
        self.assertFalse(guard._is_blocked(str(RSI5 / "probes.py")))
        self.assertEqual(guard.BLOCKED_DIR, os.path.join(str(RSI5), "judge"))
        self.assertTrue(guard._refused_module("rsi5.judge.pools"))
        self.assertFalse(guard._refused_module("rsi5.judgement"))

    def test_task_file_directory_exposes_only_the_listed_files(self):
        """Every file of RSI-2's task-file directory is sealed except the four an
        exposed-partition loader reads; the partition that is never opened is among the
        sealed ones without being named here."""
        names = sorted(os.listdir(guard.CORPUS_DIR))
        for name in guard.EXPOSED_CORPUS_FILES:
            self.assertIn(name, names)
        self.assertGreater(len(names), len(guard.EXPOSED_CORPUS_FILES))    # the rule is not vacuous
        for name in names:
            blocked = guard.blocked_path(os.path.join(guard.CORPUS_DIR, name))
            self.assertEqual(blocked, name not in guard.EXPOSED_CORPUS_FILES, name)
        self.assertTrue(guard.blocked_path(guard.CORPUS_DIR))              # the directory cannot be listed

    def test_process_memory_files_are_sealed(self):
        self.assertTrue(guard.blocked_path("/proc/self/mem"))
        self.assertTrue(guard.blocked_path(f"/proc/{os.getppid()}/mem"))
        self.assertFalse(guard.blocked_path("/proc/self/status"))
        self.assertFalse(guard.blocked_path(str(REPO / "mem")))

    def test_public_view_is_plain_data_without_hidden_examples(self):
        task = partitions.load("validation")[0]
        self.assertGreater(len(task.hidden), 0)
        view = partitions.public_view(task)
        self.assertEqual(sorted(vars(view)), ["examples", "name", "request"])
        self.assertEqual(view.examples, task.examples)
        self.assertIsInstance(view.request, dict)
        sent = pickle.dumps(("restored", view))
        for package in guard.LOADER_PACKAGES:                              # no loader class travels
            self.assertNotIn(package.encode() + b".", sent)
        for example in task.hidden:
            if example not in task.examples:
                self.assertNotIn(pickle.dumps(example)[2:-1], sent)


class Workers(Attack):
    def test_exposed_partitions_load_under_the_guard(self):
        out, _, _ = self.attack("loaders")
        self.assertEqual(out, {name: f"allowed:{size}" for name, size in PARTITION_SIZES.items()})
        self.assertEqual(sorted(PARTITION_SIZES), sorted(partitions.PHASE1_ORDER))

    def test_search_worker_cannot_load_or_generate_tasks(self):
        """After seal_task_data() the loader packages cannot be imported, read or listed: one
        of their modules generates a partition's hidden examples in code."""
        out, _, _ = self.attack("worker")
        expected = {"load_" + name: "ImportError" for name in PARTITION_SIZES}
        expected.update({"import": "ImportError", "from_import": "ImportError", "family": "ImportError",
                         "import_module": "PermissionError", "read_source": "PermissionError",
                         "list_package": "PermissionError", "loader_modules": [], "preloaded": []})
        self.assertEqual(out, expected)

    def test_workers_are_forked_before_any_task_is_loaded(self):
        """The driver's order: fork, then load. A worker holds no loader module, no object of
        a loader package and cannot load a partition, while the driver holds the tasks."""
        out, _, _ = self.attack("early_workers")
        self.assertTrue(out["driver_holds_loaders"])
        self.assertEqual(len(out["states"]), 4)
        for state in out["states"]:
            self.assertEqual(state, {"loader_modules": [], "loader_objects": [], "numpy": False,
                                     "load": "ImportError"})
        self.assertTrue(out["names_match"])
        for record in out["records"]:                                      # a worker's record carries no verdict
            self.assertNotIn("solved", record)
            self.assertNotIn("family", record)
        self.assertEqual(out["pool_after_load"], "other:RuntimeError")     # a pool after the first load is refused

    def test_worker_forked_after_the_tasks_refuses_to_search(self):
        """The attack: a worker forked once the driver holds the tasks inherits them (the
        layout before the review). Such a worker must refuse every task."""
        out, _, _ = self.attack("late_worker")
        self.assertEqual(out, {"inherits_loader_modules": True, "inherits_loader_objects": True,
                               "run_task": "other:RuntimeError"})


if __name__ == "__main__":
    unittest.main()
