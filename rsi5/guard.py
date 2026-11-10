"""The path half of the sealing audit for RSI-5: a tripwire, not a wall.

It started as a copy of ``rsi4/guard.py`` pointed at ``rsi5/judge`` and refuses a superset
of what that hook refuses. ``install()`` adds a Python audit hook (PEP 578). A hook cannot
be removed, so it lasts for the life of the process and every forked child inherits it.
Run drivers call ``install()`` first thing in ``main()``; search workers call it again and
then ``seal_task_data()``.

What the hook refuses (``PermissionError`` unless noted):

* ``open``, ``os.listdir``, ``os.scandir`` and ``os.chdir`` of a sealed path, however it is
  named: absolute, relative to the working directory, through a symbolic link, as an
  integer descriptor, with no argument (the working directory), or relative to a directory
  descriptor. The ``open`` event does not carry ``dir_fd``, so a relative ``open`` is
  resolved against the working directory and against every directory the process holds
  open; that is deliberately conservative.
* ``os.link`` out of or into a sealed path, and ``os.rename`` / ``os.replace`` of a sealed
  path, of anything inside one, or of a directory that contains one.
* Starting another program (``subprocess``, ``os.system``, ``os.posix_spawn``,
  ``os.exec*``, ``os.spawn*``, ``pty.spawn``): a new interpreter would carry no hook.
  ``os.fork`` stays allowed because the child inherits the hook.
* ``ImportError`` on importing J's package in any form (absolute, relative, ``__import__``)
  and on importing the modules that read files or start interpreters without raising an
  audit event (``UNGUARDED_MODULES``). ``importlib.import_module`` raises no ``import``
  event: for J's package it is stopped by the path rule when it opens the module's file;
  for ``UNGUARDED_MODULES``, which may be built into the interpreter and open no file,
  ``install()`` holds their names in ``sys.modules`` so that every import form fails.

Sealed paths: J's directory; any file named ``list_tasks2.json``; a process's memory file
under ``/proc`` (a search worker could read the driver's through it); RSI-2's task-file
directory except the four files the exposed-partition loaders read (so the one partition
that is never opened stays unopened without this package naming it); and, in a search
worker after ``seal_task_data()``, the ``rsi2`` and ``rsi3`` packages whole, sources and
data, whose import is refused there as well: a worker needs neither, and one of their
modules generates a partition's hidden examples in code. ``seal()`` only adds: a sealed
path cannot be released and a kept file cannot be added back.

What it does not stop (``RESULTS_P1.md`` states the Target Property and Criterion). Routes
no audit event covers: a native extension module; a function ``ctypes`` builds from an
address (its ``dlopen`` and ``dlsym`` events are not acted on either, so ``ctypes`` is open
whole); ``_posixsubprocess.fork_exec`` and ``multiprocessing.util.spawnv_passfds``; Tcl file
commands through ``tkinter``; reading a descriptor opened before ``install()``; existence,
size and time probing (``os.stat`` raises no event). Routes the hook cannot see through: a
hard link or a bind mount made before ``install()``; as root, ``os.chroot`` and raw memory
and block devices; code that rebinds this module's names or removes a held name from
``sys.modules``. Races: the hook checks a name and the system call then uses it, so a thread
that retargets a symbolic link or changes the working directory in between gets through, as
does an object whose ``__fspath__`` answers differently on each call. Reported, not
stopped: a module in ``UNGUARDED_MODULES`` imported before ``install()``, and a loader
module imported before a worker was forked (``preloaded()``). The static import list in
``tests/test_sealing.py`` keeps the first group out of the solver's source. Removal,
truncation and permission changes are integrity routes, outside this hook; J's manifest and
ledger are the integrity instruments. The descriptor rules read ``/proc/self/fd`` and need
Linux. Work that starts a program, such as ``platform.platform()``, must run before
``install()``.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

_PACKAGE = Path(__file__).resolve().parent
_REPOSITORY = _PACKAGE.parent

BLOCKED_DIR = os.path.realpath(_PACKAGE / "judge")
BLOCKED_FILES = ("list_tasks2.json",)
BLOCKED_MODULE = "rsi5.judge"
BLOCKED_MODULES = (BLOCKED_MODULE,)
#: RSI-2's task-file directory and the only files in it that an exposed-partition loader reads.
CORPUS_DIR = os.path.realpath(_REPOSITORY / "rsi2" / "data")
EXPOSED_CORPUS_FILES = ("source_list_tasks.json", "split_manifest.json", "train.json", "validation.json")
#: The packages whose loaders read or generate tasks; ``seal_task_data()`` seals them whole.
LOADER_PACKAGES = ("rsi2", "rsi3")
LOADER_DIRS = tuple(os.path.realpath(_REPOSITORY / name) for name in LOADER_PACKAGES)
#: Modules that start an interpreter or read a file without raising an audit event.
UNGUARDED_MODULES = ("multiprocessing.popen_spawn_posix", "multiprocessing.popen_forkserver",
                     "multiprocessing.popen_spawn_win32", "readline")
SPAWN_EVENTS = ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn",
                "os.startfile", "pty.spawn")
#: A process's memory as a file: a search worker could read the driver's through it.
MEMORY_FILES = ("mem",)
_PROC = "/proc"
_FD_DIR = "/proc/self/fd"

_installed = False
_sealed: dict = {}      # real path of a sealed file or directory -> real paths kept readable inside it


def seal(path, keep=()) -> str:
    """Seal a file or directory for the rest of the process; ``keep`` names files directly
    inside a sealed directory that stay readable. Sealing again can only tighten."""
    root = os.path.realpath(os.fsdecode(path))
    kept = frozenset(os.path.realpath(os.path.join(root, name)) for name in keep)
    _sealed[root] = kept & _sealed[root] if root in _sealed else kept
    return root


def seal_task_data() -> None:
    """Seal everything a task can be loaded or generated from: the loader packages whole,
    sources and data, and their import. A search worker receives public views only."""
    global BLOCKED_MODULES
    for directory in LOADER_DIRS:
        seal(directory)
    BLOCKED_MODULES = tuple(dict.fromkeys(BLOCKED_MODULES + LOADER_PACKAGES))


seal(BLOCKED_DIR)
seal(CORPUS_DIR, keep=EXPOSED_CORPUS_FILES)


def _is_blocked(real: str) -> bool:
    name = os.path.basename(real)
    if name in BLOCKED_FILES or (name in MEMORY_FILES and real.startswith(_PROC + os.sep)):
        return True
    for root, kept in tuple(_sealed.items()):
        if (real == root or real.startswith(root + os.sep)) and real not in kept:
            return True
    return False


def _contains_sealed(real: str) -> bool:
    return any(root.startswith(real + os.sep) for root in tuple(_sealed))


def _descriptor_path(descriptor):
    try:
        target = os.readlink(f"{_FD_DIR}/{descriptor}")
    except OSError:
        return None
    return target if target.startswith(os.sep) else None


def _open_directories() -> list:
    try:
        names = os.listdir(_FD_DIR)
    except OSError:
        return []
    targets = (_descriptor_path(name) for name in names)
    return [target for target in targets if target is not None and os.path.isdir(target)]


def _working_directory():
    try:
        return os.getcwd()
    except OSError:
        return None


def _resolutions(path, dir_fd=None, scan=False) -> list:
    """Every real path ``path`` may name. ``None`` is the working directory; an integer is
    a descriptor; a relative path is taken against ``dir_fd`` when one is given, else the
    working directory, and with ``scan`` also against every open directory."""
    try:
        if path is None:
            bases, text = [_working_directory()], ""
        elif isinstance(path, int):
            bases, text = [_descriptor_path(path)], ""
        else:
            text = os.fsdecode(path)
            if os.path.isabs(text):
                bases = [text]
            else:
                given = isinstance(dir_fd, int) and dir_fd >= 0
                bases = [_descriptor_path(dir_fd) if given else _working_directory()]
                if scan:
                    bases.extend(_open_directories())
        return [os.path.realpath(os.path.join(base, text) if text else base)
                for base in bases if base is not None]
    except (TypeError, ValueError, OSError):
        return []


def blocked_path(path, dir_fd=None, scan=False) -> bool:
    return any(_is_blocked(real) for real in _resolutions(path, dir_fd, scan))


def _refuse(what, verb="read") -> None:
    raise PermissionError(f"the solver process may not {verb} {what!r}")


def _on_open(event, args) -> None:                  # (path or descriptor, mode, flags)
    if args and blocked_path(args[0], scan=True):
        _refuse(args[0])


def _on_directory(event, args) -> None:             # (path, descriptor or None,)
    path = args[0] if args else None
    if blocked_path(path):
        _refuse(path, "enter" if event == "os.chdir" else "list")


def _fourth(args) -> tuple:
    return (tuple(args) + (None, None, None, None))[:4]


def _on_link(event, args) -> None:                  # (src, dst, src_dir_fd, dst_dir_fd)
    source, target, source_fd, target_fd = _fourth(args)
    if blocked_path(source, source_fd) or blocked_path(target, target_fd):
        _refuse(source, "link")


def _on_rename(event, args) -> None:                # os.rename and os.replace, same shape as os.link
    source, target, source_fd, target_fd = _fourth(args)
    if any(_is_blocked(real) or _contains_sealed(real) for real in _resolutions(source, source_fd)):
        _refuse(source, "move")
    if blocked_path(target, target_fd):
        _refuse(target, "move onto")


def _on_spawn(event, args) -> None:
    raise PermissionError(f"the solver process may not start another program ({event}): "
                          "a new interpreter would carry no audit hook")


def _refused_module(name) -> bool:
    if not isinstance(name, str):
        return False
    return (name in UNGUARDED_MODULES
            or any(name == module or name.startswith(module + ".") for module in BLOCKED_MODULES))


def _on_import(event, args) -> None:                # (module, filename, sys.path, sys.meta_path, sys.path_hooks)
    if args and _refused_module(args[0]):
        raise ImportError(f"the solver process may not import {args[0]}")


_HANDLERS = {"open": _on_open, "os.listdir": _on_directory, "os.scandir": _on_directory,
             "os.chdir": _on_directory, "os.link": _on_link, "os.rename": _on_rename,
             "import": _on_import}
_HANDLERS.update((event, _on_spawn) for event in SPAWN_EVENTS)


def _hook(event: str, args) -> None:
    handler = _HANDLERS.get(event)
    if handler is not None:
        handler(event, args)


def loader_modules() -> list:
    """Loader-package modules this process has imported. It must be empty when the search
    workers are forked: a worker forked later inherits them and whatever they have loaded."""
    return sorted(name for name in list(sys.modules) if name.split(".")[0] in LOADER_PACKAGES)


def preloaded() -> list:
    """Modules already imported that the import rule would have refused. The ``import``
    event is raised only on a first import, so a driver checks this right after ``install()``."""
    return sorted(name for name, module in list(sys.modules.items())
                  if module is not None and _refused_module(name))


def install() -> bool:
    """Install the hook once per process; True if it was installed by this call."""
    global _installed
    if _installed:
        return False
    for name in UNGUARDED_MODULES:           # ``None`` makes every import form raise ImportError
        sys.modules.setdefault(name, None)
    sys.addaudithook(_hook)
    _installed = True
    return True
