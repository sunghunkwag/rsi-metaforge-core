"""Admitted primitives (Phase 2): one module per primitive, named by the first 12 hex
characters of the SHA-256 of its C2 witness term, holding its type, the witness term, its
probe-set I/O table and the admission record (OWNER_DIRECTIVE.md §3.1, §5). Empty in
Phase 1: nothing enters a vocabulary except through gates G1–G3, and no gate exists yet.

Loading is static. J's audit refuses dynamic importers in solver modules, so the
admission gate appends one ``from . import <hash>`` line below the marker for every
primitive it admits, and each module calls ``register`` at import. ``load()`` returns the
registered entries in name order for ``Vocabulary.with_admitted``."""
from __future__ import annotations

ADMITTED: dict = {}


def register(name: str, type_, witness, io_table, admission) -> None:
    if name in ADMITTED:
        raise ValueError(f"admitted primitive {name!r} registered twice")
    ADMITTED[name] = (type_, witness, io_table, admission)


def names() -> list[str]:
    return sorted(ADMITTED)


def load() -> dict:
    return {name: ADMITTED[name] for name in names()}


# -- admitted primitives: one static import per module, appended by the admission gate --
