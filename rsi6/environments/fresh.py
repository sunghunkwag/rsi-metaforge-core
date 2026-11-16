"""The categories that no process had used before 2026-11-16, kept apart from the registry.

``rsi6/environments/__init__.py`` and ``rsi6/kernel/roles.py`` are pinned by hash by the
registration of the open experiment (``registry/registration_o.json``) until its last stage has
run, so these adapters are not in the registry on disk. A driver that is registered to use them
calls ``install()`` before it measures anything: the adapters are added to the kernel's registry
in that process (and in the workers it forks), and nowhere else. Their role is ``fresh``
(``registry/roles.json``): locked by the kernel's role lock until the ledger holds an ``unlock``
record for it, which only the held-out stage of a registered experiment writes.

Every adapter here was written by a builder agent in its own copy of the package and audited by
other agents with their own parsers and evaluators (``rsi6/audit/adapters_fresh_20261116/``);
no learner has run on any of their instances before the held-out stage that unlocks them.
"""
from __future__ import annotations

import json
import os

from rsi6 import environments

HERE = os.path.dirname(os.path.abspath(__file__))
FRESH = os.path.join(os.path.dirname(HERE), "registry", "fresh.json")


def table() -> dict:
    return json.load(open(FRESH))


def install() -> list:
    """Add the admitted fresh adapters to the kernel's registry in this process; returns their names."""
    names = []
    for name, entry in table()["categories"].items():
        if entry.get("admitted"):
            environments.REGISTRY.setdefault(name, (entry["module"], entry["class"]))
            names.append(name)
    return sorted(names)
