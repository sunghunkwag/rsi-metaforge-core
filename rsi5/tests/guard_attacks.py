"""Attacks on the guard, run by ``test_guard.py`` in a fresh interpreter (an audit hook
cannot be removed, so every scenario needs its own process).

Usage: ``python guard_attacks.py <mode> <decoy root>``. Prints one JSON object, attack ->
outcome. Every attack targets a decoy tree built by the test. The ``loaders``,
``early_workers``, ``late_worker``, ``dead_worker`` and ``driver`` modes also load exposed
partitions through the package's own loaders, as the run driver does; nothing here names
J's directory.
"""
import contextlib
import gc
import glob
import hashlib
import importlib
import importlib.util
import io
import json
import multiprocessing
import os
import pathlib
import pkgutil
import runpy
import shutil
import signal
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from rsi5 import guard  # noqa: E402


def outcome(action) -> str:
    try:
        value = action()
    except PermissionError:
        return "PermissionError"
    except ImportError:
        return "ImportError"
    except Exception as error:  # an unexpected failure is reported, never hidden
        return "other:" + type(error).__name__
    return "allowed:" + repr(value)[:48]


def run(attacks) -> dict:
    return {name: outcome(action) for name, action in attacks.items()}


def statement(source):
    return lambda: exec(source, {})


class Index:
    """An object that stands for a descriptor through ``__index__``."""
    def __init__(self, descriptor):
        self.descriptor = descriptor

    def __index__(self):
        return self.descriptor


class Liar(str):
    """A ``str`` whose methods describe another, harmless path; the system call sees the real one."""
    def startswith(self, *args):
        return False

    def __str__(self):
        return "harmless.txt"

    def __add__(self, other):
        return "harmless.txt"

    def __radd__(self, other):
        return "harmless.txt"


def paths(root, sealed, secret) -> dict:
    join = os.path.join
    before_dir = os.open(sealed, os.O_RDONLY)       # descriptors opened before install()
    before_file = os.open(secret, os.O_RDONLY)
    above = os.open(root, os.O_RDONLY)
    guard.seal(sealed)
    guard.install()
    os.chdir(join(root, "open"))                    # relative names below do not resolve from here
    alias = join(root, "alias")
    inside = "decoypkg/sealed/secret.txt"
    sys.path.insert(0, root)
    return run({
        "absolute": lambda: open(secret).read(),
        "dotdot": lambda: open(join(root, "open", "..", inside)).read(),
        "relative": lambda: open("../" + inside).read(),
        "os_open": lambda: os.open(secret, os.O_RDONLY),
        "open_code": lambda: io.open_code(secret).read(),
        "read_text": lambda: pathlib.Path(secret).read_text(),
        "dir_fd": lambda: os.open(inside, os.O_RDONLY, dir_fd=above),
        "dir_fd_inside": lambda: os.open("secret.txt", os.O_RDONLY, dir_fd=before_dir),
        "descriptor_listdir": lambda: os.listdir(before_dir),
        "descriptor_scandir": lambda: list(os.scandir(before_dir)),
        "descriptor_reopen": lambda: open(before_file, closefd=False).read(),
        "descriptor_fdopen": lambda: os.fdopen(before_file, closefd=False).read(),
        "fchdir": lambda: os.fchdir(before_dir),
        "chdir": lambda: os.chdir(sealed),
        "listdir": lambda: os.listdir(sealed),
        "scandir": lambda: list(os.scandir(sealed)),
        "listdir_below": lambda: os.listdir(join(sealed, "pools")),
        "iterdir": lambda: list(pathlib.Path(sealed).iterdir()),
        "walk": lambda: list(os.walk(sealed)),
        "glob": lambda: glob.glob(join(sealed, "*")),
        "symlink_open": lambda: (os.symlink(sealed, alias), open(join(alias, "secret.txt")).read())[1],
        "symlink_listdir": lambda: os.listdir(alias),
        "hard_link": lambda: os.link(secret, join(root, "open", "copy.txt")),
        "hard_link_dir_fd": lambda: os.link(inside, "open/copy2.txt", src_dir_fd=above, dst_dir_fd=above),
        "rename_directory": lambda: os.rename(sealed, join(root, "moved")),
        "rename_ancestor": lambda: os.rename(join(root, "decoypkg"), join(root, "renamed")),
        "replace_file": lambda: os.replace(secret, join(root, "open", "taken.txt")),
        "rename_into": lambda: os.rename(join(root, "open", "spare.txt"), join(sealed, "planted.txt")),
        "copyfile": lambda: shutil.copyfile(secret, join(root, "open", "copied.txt")),
        "copytree": lambda: shutil.copytree(sealed, join(root, "open", "tree")),
        "get_data": lambda: pkgutil.get_data("decoypkg", "sealed/secret.txt"),
        "blocked_name": lambda: open(join(root, "open", "list_tasks2.json")).read(),
        # The same name carried by other objects.
        "bytes_path": lambda: open(os.fsencode(secret)).read(),
        "bytes_listdir": lambda: os.listdir(os.fsencode(sealed)),
        "bytearray_path": lambda: os.read(os.open(bytearray(os.fsencode(secret)), os.O_RDONLY), 5),
        "memoryview_path": lambda: os.read(os.open(memoryview(os.fsencode(secret)), os.O_RDONLY), 5),
        "pathlike_os_open": lambda: os.open(pathlib.Path(secret), os.O_RDONLY),
        "str_subclass": lambda: open(Liar(secret)).read(),
        "index_listdir": lambda: os.listdir(Index(before_dir)),
        "index_scandir": lambda: list(os.scandir(Index(before_dir))),
        "index_dir_fd": lambda: os.open(inside, os.O_RDONLY, dir_fd=Index(above)),
        # Links and renames relative to a directory descriptor, and a link into the sealed directory.
        "link_into_sealed": lambda: os.link(join(root, "open", "readme.txt"), join(sealed, "planted_link.txt")),
        "link_into_sealed_dir_fd": lambda: os.link("open/readme.txt", "decoypkg/sealed/planted2.txt",
                                                   src_dir_fd=above, dst_dir_fd=above),
        "rename_dir_fd": lambda: os.rename("decoypkg/sealed", "moved2", src_dir_fd=above, dst_dir_fd=above),
        "replace_dir_fd": lambda: os.replace(inside, "open/taken2.txt", src_dir_fd=above, dst_dir_fd=above),
        "rename_ancestor_dir_fd": lambda: os.rename("decoypkg", "renamed2", src_dir_fd=above, dst_dir_fd=above),
        "own_memory": lambda: open("/proc/self/mem", "rb").close(),
        "parent_memory": lambda: open(f"/proc/{os.getppid()}/mem", "rb").close(),
        # A documented residual, pinned so that no document can claim otherwise:
        "residual_read_of_descriptor_opened_before_install": lambda: os.read(before_file, 5),
    })


def working_directory(root, sealed, secret) -> dict:
    """The process starts inside the sealed directory (the test sets cwd)."""
    guard.seal(sealed)
    guard.install()
    return run({
        "listdir_no_argument": lambda: os.listdir(),
        "scandir_no_argument": lambda: list(os.scandir()),
        "listdir_dot": lambda: os.listdir("."),
        "relative_open": lambda: open("secret.txt").read(),
        "iterdir": lambda: list(pathlib.Path().iterdir()),
        "glob": lambda: glob.glob("*"),
    })


def deleted_cwd(root, sealed, secret) -> dict:
    """The working directory is removed after the hook is installed: os.getcwd() fails, yet
    the kernel still resolves ".." from it."""
    gone = os.path.join(root, "gone")
    os.mkdir(gone)
    guard.seal(sealed)
    guard.install()
    os.chdir(gone)
    os.rmdir(gone)
    return run({
        "getcwd": os.getcwd,
        "relative_open": lambda: open("../decoypkg/sealed/secret.txt").read(),
        "relative_os_open": lambda: os.open("../decoypkg/sealed/secret.txt", os.O_RDONLY),
        "relative_listdir": lambda: os.listdir("../decoypkg/sealed"),
        "relative_scandir": lambda: list(os.scandir("../decoypkg/sealed")),
        "benign_relative_open": lambda: open("../open/readme.txt").read(),
    })


def symlinked_seal(root, sealed, secret) -> dict:
    """The seal and a keep-list are given through symbolic names; the real paths are sealed."""
    join = os.path.join
    link, corpus_link = join(root, "link_to_sealed"), join(root, "corpus_link")
    os.symlink(sealed, link)
    os.symlink(join(root, "corpus"), corpus_link)
    guard.seal(link)
    guard.seal(corpus_link, keep=("kept.json",))
    guard.install()
    return run({
        "real_path": lambda: open(secret).read(),
        "through_link": lambda: open(join(link, "secret.txt")).read(),
        "listdir_real": lambda: os.listdir(sealed),
        "kept_real": lambda: open(join(root, "corpus", "kept.json")).read(),
        "kept_through_link": lambda: open(join(corpus_link, "kept.json")).read(),
        "other_real": lambda: open(join(root, "corpus", "other.json")).read(),
        "other_through_link": lambda: open(join(corpus_link, "other.json")).read(),
    })


def spawn(root, sealed, secret) -> dict:
    import subprocess
    guard.seal(sealed)
    guard.install()

    def fork_then_exec():
        child = os.fork()
        if child == 0:
            code = 1
            try:
                os.execv("/bin/cat", ["cat", secret])
            except PermissionError:
                code = 42
            finally:
                os._exit(code)
        return os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])

    return run({
        "subprocess": lambda: subprocess.run(["cat", secret], capture_output=True).stdout,
        "os_system": lambda: os.system("cat " + secret),
        "os_popen": lambda: os.popen("cat " + secret).read(),
        "posix_spawn": lambda: os.posix_spawn("/bin/cat", ["cat", secret], dict(os.environ)),
        "spawnv": lambda: os.spawnv(os.P_WAIT, "/bin/cat", ["cat", secret]),
        "fork_then_exec": fork_then_exec,
        "spawn_start_method": lambda: multiprocessing.get_context("spawn").Process(target=abs, args=(1,)).start(),
        "forkserver_start_method":
            lambda: multiprocessing.get_context("forkserver").Process(target=abs, args=(1,)).start(),
        "pty_spawn": lambda: importlib.import_module("pty").spawn(["/bin/cat", secret]),
        "readline": lambda: importlib.import_module("readline"),
        "readline_statement": statement("import readline"),
    })


def imports(root, sealed, secret) -> dict:
    sys.path.insert(0, root)
    guard.BLOCKED_MODULES = guard.BLOCKED_MODULES + ("decoypkg.sealed",)
    guard.install()
    by_name = run({                                 # the name rule alone: the path is not sealed yet
        "import": statement("import decoypkg.sealed"),
        "import_below": statement("import decoypkg.sealed.inner"),
        "from_package": statement("from decoypkg import sealed"),
        "from_module": statement("from decoypkg.sealed import inner"),
        "dunder_import": lambda: __import__("decoypkg.sealed.inner"),
        "relative_dot": statement("import decoypkg.relative_dot"),
        "relative_dotdot": statement("import decoypkg.sub.relative_dotdot"),
        "relative_module": statement("import decoypkg.relative_module"),
        "run_module": lambda: runpy.run_module("decoypkg.sealed.inner"),
    })
    guard.seal(sealed)                              # importlib raises no import event: the path rule stops it

    def load_from_spec():
        spec = importlib.util.find_spec("decoypkg.sealed")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.VALUE

    by_path = run({
        "import_module": lambda: importlib.import_module("decoypkg.sealed").VALUE,
        "import_module_relative": lambda: importlib.import_module(".sealed", "decoypkg").VALUE,
        "spec_loader": load_from_spec,
    })
    return {**by_name, **by_path, "sealed_modules_loaded": sorted(m for m in sys.modules if "sealed" in m)}


def preloaded(root, sealed, secret) -> dict:
    clean = guard.preloaded()
    import multiprocessing.popen_spawn_posix  # noqa: F401  (before install(): the import rule cannot see it)
    guard.install()
    after_install = guard.preloaded()
    import colorsys  # noqa: F401  (stands in for a loader module a late-forked worker inherits)
    guard.LOADER_PACKAGES = ("colorsys",)
    guard.LOADER_DIRS = (os.path.join(root, "corpus"),)
    guard.seal_task_data()
    return {"before": clean, "after_install": after_install, "after_seal": guard.preloaded()}


def keep(root, sealed, secret) -> dict:
    corpus = os.path.join(root, "corpus")
    kept, other = os.path.join(corpus, "kept.json"), os.path.join(corpus, "other.json")
    guard.seal(corpus, keep=("kept.json",))
    guard.install()
    first = run({"kept": lambda: open(kept).read(), "other": lambda: open(other).read(),
                 "listdir": lambda: os.listdir(corpus)})
    guard.seal(corpus, keep=("kept.json", "other.json"))        # sealing again cannot widen
    second = run({"other_after_wider_keep": lambda: open(other).read(),
                  "kept_after_wider_keep": lambda: open(kept).read()})
    guard.seal(corpus)                                          # whole
    third = run({"kept_after_whole_seal": lambda: open(kept).read()})
    guard.seal(corpus, keep=("kept.json",))
    fourth = run({"kept_after_reseal_with_keep": lambda: open(kept).read()})
    return {**first, **second, **third, **fourth}


def benign(root, sealed, secret) -> dict:
    """What must keep working with the hook installed and the task data sealed."""
    held = os.open(root, os.O_RDONLY)               # an open directory, so relative opens are scanned
    guard.seal(sealed)
    guard.install()
    guard.seal_task_data()
    os.chdir(os.path.join(root, "open"))

    def temporary_directory():
        with tempfile.TemporaryDirectory() as directory:
            os.mkdir(os.path.join(directory, "below"))
            pathlib.Path(directory, "below", "file.txt").write_text("x")
            return pathlib.Path(directory, "below", "file.txt").read_text()

    def fork_pool():
        with multiprocessing.get_context("fork").Pool(2) as pool:
            return pool.map(abs, [-1, -2, -3])

    result = run({
        "read": lambda: open(os.path.join(root, "open", "readme.txt")).read(),
        "relative_read": lambda: open("readme.txt").read(),
        "listdir": lambda: sorted(os.listdir(root))[:2],
        "rename": lambda: os.rename("spare.txt", "spare2.txt"),
        "new_import": lambda: importlib.import_module("colorsys").__name__,
        "package_source": lambda: len(open(os.path.join(REPO, "rsi5", "probes.py")).read()) > 0,
        "temporary_directory": temporary_directory,
        "fork_pool": fork_pool,
    })
    os.close(held)
    return result


def loaders(root, sealed, secret) -> dict:
    """The exposed partitions load with the hook installed, as in the run driver."""
    from rsi5 import partitions
    guard.install()
    return {name: outcome(lambda name=name: len(partitions.load(name))) for name in partitions.PHASE1_ORDER}


def worker(root, sealed, secret) -> dict:
    """A search worker: the hook installed and the task data sealed before any loader is imported."""
    from rsi5 import partitions
    guard.install()
    guard.seal_task_data()
    source = os.path.join(REPO, "rsi3", "compose24.py")
    result = {"load_" + name: outcome(lambda name=name: len(partitions.load(name)))
              for name in partitions.PHASE1_ORDER}
    result.update(run({
        "import": statement("import rsi3.compose24"),
        "from_import": statement("from rsi2 import corpus"),
        "import_module": lambda: importlib.import_module("rsi3.compose24"),
        "read_source": lambda: len(open(source).read()),
        "list_package": lambda: os.listdir(os.path.dirname(source)),
        "family": lambda: partitions.family("((add-k (dyn . 0) (static . 3)))"),
    }))
    result["loader_modules"] = sorted(m for m in sys.modules if m.split(".")[0] in guard.LOADER_PACKAGES)
    result["preloaded"] = guard.preloaded()
    return result


def worker_state(_) -> dict:
    """Runs inside a search worker: what the worker holds and what it can load."""
    from rsi5 import partitions
    held = {type(thing).__module__ for thing in gc.get_objects()}
    return {"loader_modules": guard.loader_modules(),
            "loader_objects": sorted(m for m in held if m.split(".")[0] in guard.LOADER_PACKAGES),
            "numpy": "numpy" in sys.modules,
            "load": outcome(lambda: len(partitions.load("validation")))}


def _plan():
    from rsi5 import phase1
    return dict(phase1.load_plan(os.path.join(REPO, "rsi5", "runs", "p1.json")), budget=300)


def early_workers(root, sealed, secret) -> dict:
    """The run driver's order: the workers are forked first, the tasks are loaded afterwards."""
    from rsi5 import partitions, phase1
    guard.install()
    plan = _plan()
    with phase1.worker_pool(plan, 2) as pool:
        tasks = partitions.load("validation")       # from here on the driver holds hidden examples
        states = list(pool.map(worker_state, range(4), chunksize=1))
        jobs = [("restored", partitions.public_view(task)) for task in tasks[:2]]
        records = list(pool.map(phase1.run_task, jobs, chunksize=1))
        second_pool = outcome(lambda: phase1.worker_pool(plan, 1))
    return {"driver_holds_loaders": bool(guard.loader_modules()), "states": states,
            "records": [sorted(record) for record in records],
            "names_match": [record["name"] for record in records] == [task.name for task in tasks[:2]],
            "pool_after_load": second_pool}


def late_worker(root, sealed, secret) -> dict:
    """A worker forked after the tasks were loaded, as the pool does when it replaces a worker
    that died: it inherits the loaders and the tasks, and must refuse to search."""
    from rsi5 import partitions, phase1
    guard.install()
    plan = _plan()
    tasks = partitions.load("validation")
    job = ("restored", partitions.public_view(tasks[0]))
    with multiprocessing.get_context("fork").Pool(1, initializer=phase1._init_worker, initargs=(plan,)) as pool:
        state = pool.map(worker_state, [0])[0]
        searched = outcome(lambda: pool.map(phase1.run_task, [job]))
    return {"inherits_loader_modules": bool(state["loader_modules"]),
            "inherits_loader_objects": bool(state["loader_objects"]), "run_task": searched}


def die_on_first(job):
    """Runs inside a search worker: the worker that receives the marked job kills itself."""
    if job[0] == "die":
        os.kill(os.getpid(), signal.SIGKILL)
    return phase1_run_task(job)


def phase1_run_task(job):
    from rsi5 import phase1
    return phase1.run_task(job)


def dead_worker(root, sealed, secret) -> dict:
    """A search worker dies in the middle of a run: the driver must fail, at once."""
    from rsi5 import partitions, phase1
    guard.install()
    plan = _plan()
    started = time.perf_counter()
    with phase1.worker_pool(plan, 2) as pool:
        tasks = partitions.load("validation")
        jobs = [("restored", partitions.public_view(task)) for task in tasks[:4]]
        jobs.insert(1, ("die", jobs[0][1]))
        failed = outcome(lambda: list(pool.map(die_on_first, jobs, chunksize=1)))
    return {"map": failed, "within_a_minute": time.perf_counter() - started < 60}


_ORIGINAL_RUN_TASK = None


def probed_run_task(job):
    """Runs inside a search worker of the real driver: the record plus what the worker saw."""
    from rsi5 import partitions
    record = _ORIGINAL_RUN_TASK(job)
    view = job[1]
    record["_probe"] = {
        "hook_installed": guard._installed,
        "hook_refuses_a_program": outcome(lambda: os.system("true")),
        "job": [type(job[0]).__name__, type(view).__name__], "fields": sorted(vars(view)),
        "content": hashlib.sha256(repr((view.name, view.request, view.examples)).encode()).hexdigest(),
        "loader_modules": guard.loader_modules(),
        "load": outcome(lambda: len(partitions.load("validation"))),
    }
    return record


def driver(root, sealed, secret) -> dict:
    """The run driver itself, phase1.main, on RESERVE-FAR2 at a small budget: what its workers
    see, and whether the verdicts it writes are the frozen verifier's."""
    global _ORIGINAL_RUN_TASK
    from rsi5 import partitions, phase1
    from rsi5.dsl.pretty_parse import parse
    from rsi5.verifier import FrozenVerifier
    _ORIGINAL_RUN_TASK = phase1.run_task
    phase1.run_task = probed_run_task
    output = os.path.join(root, "driver_out")
    before = guard._installed
    with contextlib.redirect_stdout(io.StringIO()):
        phase1.main(["--output", output, "--partition", "far2", "--vocabulary", "original", "--workers", "2",
                     "--budget", "2000"])
    with open(os.path.join(output, "original_far2.json")) as handle:
        result = json.load(handle)
    tasks = partitions.load("far2")
    verifier = FrozenVerifier(tasks, step_budget=2000)
    records = result["records"]
    agree = [bool(verifier.verify(r["name"], parse(r["program"]) if r["program"] else None).verdict) == r["solved"]
             for r in records]
    expected = [hashlib.sha256(repr((v.name, v.request, v.examples)).encode()).hexdigest()
                for v in map(partitions.public_view, tasks)]
    probes = [r["_probe"] for r in records]
    with open(os.path.join(REPO, "rsi5", "results_p1", "original_far2.json")) as handle:
        registered = {r["name"]: r for r in json.load(handle)["records"]}
    same = all(r["solved"] == (registered[r["name"]]["solved"] and registered[r["name"]]["candidates_to_solution"] <= 2000)
               and (not r["solved"] or r["program"] == registered[r["name"]]["program"]) for r in records)
    return {"hook_before_main": before, "hook_after_main": guard._installed,
            "tasks": len(records), "solved": sum(r["solved"] for r in records),
            "verdicts_are_the_verifiers": all(agree),
            "workers_hooked": all(p["hook_installed"] for p in probes),
            "workers_refuse_programs": sorted({p["hook_refuses_a_program"] for p in probes}),
            "jobs": sorted({tuple(p["job"]) for p in probes}), "fields": sorted({tuple(p["fields"]) for p in probes}),
            "jobs_are_the_public_views": [p["content"] for p in probes] == expected,
            "workers_hold_loaders": any(p["loader_modules"] for p in probes),
            "workers_load": sorted({p["load"] for p in probes}),
            "agrees_with_registered_file": same}


MODES = {function.__name__: function for function in
         (paths, working_directory, deleted_cwd, symlinked_seal, spawn, imports, preloaded, keep, benign,
          loaders, worker, early_workers, late_worker, dead_worker, driver)}

if __name__ == "__main__":
    mode, root = sys.argv[1], sys.argv[2]
    sealed = os.path.join(root, "decoypkg", "sealed")
    print(json.dumps(MODES[mode](root, sealed, os.path.join(sealed, "secret.txt")), sort_keys=True))
