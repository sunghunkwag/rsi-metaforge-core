"""Mutation test of ``test_guard.py``: does the guard's test file notice a broken guard?

Each mutant breaks one property of ``guard.py``: how a name is read from the object that carries
it, the fail-closed branches, the working directory, ``dir_fd`` and open directories, the rename
and link rules, the sealed set, the rules for programs and imports. The tool rewrites
``rsi5/guard.py`` in the tree it is given, runs ``rsi5.tests.test_guard`` there and restores the
file. It therefore refuses a git checkout: give it a scratch copy of the tree. A copy without the
sealed material is enough; the one test that then fails for that reason is the baseline.

Usage: ``python guard_mutation.py <scratch copy of the repository tree>``

Recorded in ``RESULTS_P1.md``: the test file as it stood after the second review noticed 22 of
these 30 mutants. Three of the eight it missed were masked by the scenario itself (the attacking
process held a descriptor on the sealed directory, so the scan of open directories refused the
name whatever the hook read from the object); five were fail-closed branches no test reached.
With the ``carried_names`` scenario and the ``FailClosed`` cases all 30 are noticed, on Python
3.13 and 3.11.
"""
import os
import re
import subprocess
import sys

MUTANTS = [
    ("text: a name the hook cannot read is allowed (fail open)",
     '        raise _Unresolved(f"a path of type {type(path).__name__}")',
     '        return ""'),
    ("text: a str subclass is asked for its own text",
     "        return str.__str__(path)",
     "        return str(path)"),
    ("text: bytes-like objects other than bytes are not read",
     "        return os.fsdecode(bytes(memoryview(path)))",
     "        return os.fsdecode(path) if isinstance(path, bytes) else ''"),
    ("descriptor: only a real int is a descriptor",
     "        return operator.index(path)",
     "        return path if isinstance(path, int) else None"),
    ("descriptor: an __index__ object is taken as an allowed name",
     "    try:\n        return operator.index(path)\n    except TypeError:\n        return None",
     "    return path if isinstance(path, int) else -1"),
    ("working directory: unknown means the root",
     '        raise _Unresolved("the working directory is unknown")',
     '        return "/"'),
    ("working directory: a deleted one is not resolved",
     '    try:                                    # a deleted working directory still resolves ".."\n'
     '        target = os.readlink("/proc/self/cwd")\n    except OSError:\n'
     '        raise _Unresolved("the working directory is unknown")\n'
     '    deleted = " (deleted)"\n    return target[:-len(deleted)] if target.endswith(deleted) else target',
     '    return "/nonexistent"'),
    ("resolutions: dir_fd is ignored",
     "                bases = [_descriptor_path(fd) if fd is not None and fd >= 0 else _working_directory()]",
     "                bases = [_working_directory()]"),
    ("resolutions: open directories are not scanned",
     "                if scan:\n                    bases.extend(_open_directories())",
     "                pass"),
    ("resolutions: an unresolvable name is no name",
     '        raise _Unresolved("a name the hook cannot resolve")',
     "        return []"),
    ("blocked_path: fail open",
     "    except _Unresolved:\n        return True",
     "    except _Unresolved:\n        return False"),
    ("rename: a directory that contains a sealed path may move",
     "        moved = any(_is_blocked(real) or _contains_sealed(real) for real in _resolutions(source, source_fd))",
     "        moved = any(_is_blocked(real) for real in _resolutions(source, source_fd))"),
    ("rename: an unresolvable source may move",
     "    except _Unresolved:\n        moved = True",
     "    except _Unresolved:\n        moved = False"),
    ("rename: the target is not checked",
     '    if blocked_path(target, target_fd):\n        _refuse(target, "move onto")',
     "    pass"),
    ("link: the target is not checked",
     "    if blocked_path(source, source_fd) or blocked_path(target, target_fd):",
     "    if blocked_path(source, source_fd):"),
    ("link: the source is not checked",
     "    if blocked_path(source, source_fd) or blocked_path(target, target_fd):",
     "    if blocked_path(target, target_fd):"),
    ("link: dir_fd of the source is ignored",
     "    if blocked_path(source, source_fd) or blocked_path(target, target_fd):",
     "    if blocked_path(source) or blocked_path(target, target_fd):"),
    ("directory: no argument is allowed",
     "    path = args[0] if args else None\n    if blocked_path(path):",
     "    path = args[0] if args else None\n    if path is not None and blocked_path(path):"),
    ("open: a relative name is not taken against open directories",
     "    if args and blocked_path(args[0], scan=True):",
     "    if args and blocked_path(args[0]):"),
    ("is_blocked: a memory file is allowed",
     "    if name in BLOCKED_FILES or (name in MEMORY_FILES and real.startswith(_PROC + os.sep)):",
     "    if name in BLOCKED_FILES:"),
    ("is_blocked: a sealed file name is allowed outside sealed directories",
     "    if name in BLOCKED_FILES or (name in MEMORY_FILES and real.startswith(_PROC + os.sep)):",
     "    if name in MEMORY_FILES and real.startswith(_PROC + os.sep):"),
    ("is_blocked: a kept file's siblings are allowed",
     "        if (real == root or real.startswith(root + os.sep)) and real not in kept:",
     "        if (real == root or real.startswith(root + os.sep)) and not kept:"),
    ("is_blocked: the sealed directory itself is allowed",
     "        if (real == root or real.startswith(root + os.sep)) and real not in kept:",
     "        if real.startswith(root + os.sep) and real not in kept:"),
    ("seal: sealing again can widen what is kept",
     "    _sealed[root] = kept & _sealed[root] if root in _sealed else kept",
     "    _sealed[root] = kept | _sealed[root] if root in _sealed else kept"),
    ("descriptor path: a descriptor is never resolved",
     "    return target if target.startswith(os.sep) else None",
     "    return None"),
    ("spawn: starting a program is allowed",
     '    raise PermissionError(f"the solver process may not start another program ({event}): "\n'
     '                          "a new interpreter would carry no audit hook")',
     "    return None"),
    ("import: an unguarded module may be imported",
     "    return (name in UNGUARDED_MODULES\n            or any(",
     "    return (False\n            or any("),
    ("import: the sealed package may be imported",
     "            or any(name == module or name.startswith(module + \".\") for module in BLOCKED_MODULES))",
     "            or False)"),
    ("install: unguarded modules are not held in sys.modules",
     "        sys.modules.setdefault(name, None)",
     "        pass"),
    ("seal_task_data: the loader packages are not sealed",
     "    for directory in LOADER_DIRS:\n        seal(directory)",
     "    pass"),
]




def failures(tree: str) -> set:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=tree)
    done = subprocess.run([sys.executable, "-m", "unittest", "rsi5.tests.test_guard"], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=900)
    failed = set(re.findall(r"^(?:FAIL|ERROR): (\S+)", done.stderr, flags=re.M))
    if "Ran " not in done.stderr:
        failed.add("(the test file did not run: " + done.stderr.strip().splitlines()[-1][:120] + ")")
    return failed


def main(tree: str) -> int:
    tree = os.path.realpath(tree)
    if os.path.exists(os.path.join(tree, ".git")):
        print("refused: this tool rewrites rsi5/guard.py in the tree; give it a scratch copy, not a checkout")
        return 2
    target = os.path.join(tree, "rsi5", "guard.py")
    original = open(target).read()
    survived = []
    try:
        baseline = failures(tree)
        print("baseline failures:", sorted(baseline))
        for name, old, new in MUTANTS:
            assert original.count(old) == 1, (name, original.count(old))
            with open(target, "w") as handle:
                handle.write(original.replace(old, new))
            noticed = sorted(failures(tree) - baseline)
            print(f"{'noticed ' if noticed else 'MISSED  '} | {name} | {len(noticed)} tests: {', '.join(noticed[:4])}")
            if not noticed:
                survived.append(name)
    finally:
        with open(target, "w") as handle:
            handle.write(original)
    print(f"\n{len(MUTANTS) - len(survived)} of {len(MUTANTS)} mutants noticed; missed: {survived}")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
