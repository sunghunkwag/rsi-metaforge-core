"""The path half of the sealing audit for RSI-5: the solver process cannot open, list or
import J (a copy of ``rsi4/guard.py`` pointed at ``rsi5/judge``).

``install()`` adds a Python audit hook (PEP 578) that raises ``PermissionError`` on any
``open``, ``os.listdir`` or ``os.scandir`` of a path under ``rsi5/judge/`` or of a file
named ``list_tasks2.json``, and ``ImportError`` on importing J's package. Audit hooks
cannot be removed, so it lasts for the life of the process. Run drivers call
``install()`` first thing in ``main()``.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

BLOCKED_DIR = os.path.realpath(Path(__file__).resolve().parent / "judge")
BLOCKED_FILES = ("list_tasks2.json",)
BLOCKED_MODULE = "rsi5.judge"
_installed = False


def blocked_path(path) -> bool:
    if isinstance(path, int):
        return False
    try:
        real = os.path.realpath(os.fsdecode(path))
    except (TypeError, ValueError):
        return False
    return (real == BLOCKED_DIR or real.startswith(BLOCKED_DIR + os.sep)
            or os.path.basename(real) in BLOCKED_FILES)


def _hook(event: str, args) -> None:
    if event in ("open", "os.listdir", "os.scandir") and args:
        if blocked_path(args[0]):
            raise PermissionError(f"the solver process may not read {args[0]!r}")
    elif event == "import" and args:
        name = args[0]
        if isinstance(name, str) and (name == BLOCKED_MODULE or name.startswith(BLOCKED_MODULE + ".")):
            raise ImportError(f"the solver process may not import {name}")


def install() -> bool:
    """Install the hook once per process; True if it was installed by this call."""
    global _installed
    if _installed:
        return False
    sys.addaudithook(_hook)
    _installed = True
    return True
