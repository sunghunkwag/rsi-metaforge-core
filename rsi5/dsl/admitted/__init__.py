"""Admitted primitives (Phase 2): one module per primitive, named by the first 12 hex
characters of the SHA-256 of its C2 witness term, holding its type, the witness term, its
probe-set I/O table and the admission record (OWNER_DIRECTIVE.md §3.1, §5). Empty in
Phase 1: nothing enters a vocabulary except through gates G1–G3, and no gate exists yet.
``load()`` returns the admitted entries in name order for ``Vocabulary.with_admitted``."""
from __future__ import annotations

import importlib
from pathlib import Path


def names() -> list[str]:
    here = Path(__file__).resolve().parent
    return sorted(p.stem for p in here.glob("*.py") if p.stem != "__init__" and len(p.stem) == 12)


def load() -> dict:
    found = {}
    for name in names():
        module = importlib.import_module(f"{__name__}.{name}")
        found[name] = (module.TYPE, module.WITNESS, module.IO_TABLE, module.ADMISSION)
    return found
