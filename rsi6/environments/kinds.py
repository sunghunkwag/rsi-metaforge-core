"""Kinds of prediction problem added for design t, kept apart from the registry on disk.

``rsi6/environments/__init__.py`` is pinned by hash by earlier registrations, so these adapters
are not in it. A driver that uses them calls ``install()`` first: the admitted adapters of
``rsi6/registry/kinds_t.json`` are added to the kernel's registry in that process (and in the
workers it forks). Their roles are in ``rsi6/registry/roles.json`` like every category's, and
the kernel's role lock applies to them as to any other.
"""
from __future__ import annotations

import json
import os

from rsi6 import environments

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(os.path.dirname(HERE), "registry", "kinds_t.json")


def table() -> dict:
    return json.load(open(TABLE))


def install() -> list:
    names = []
    for name, entry in table()["categories"].items():
        if entry.get("admitted"):
            environments.REGISTRY.setdefault(name, (entry["module"], entry["class"]))
            names.append(name)
    return sorted(names)
