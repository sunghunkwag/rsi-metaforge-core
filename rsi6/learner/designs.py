"""One door to the designs of the learner.

A version record without the field ``design`` belongs to the first design (``learner.py`` and
``version.py``, frozen as generation 0); a record with ``design: "b"`` to the second
(``design_b.py``); a record with ``design: "o"`` to the open design (``design_o.py``), whose
versions are programs. Everything outside ``rsi6/learner`` goes through this module, so that
the kernel treats every design alike. For records of the first design every function here calls
the frozen module unchanged.
"""
from __future__ import annotations

from rsi6.learner import design_b
from rsi6.learner import design_o
from rsi6.learner import version as design_a
from rsi6.learner.learner import Learner


def design_of(version: dict) -> str:
    return version.get("design", "a")


def _module(version: dict):
    return {"b": design_b, "o": design_o}.get(design_of(version), design_a)


def make(version: dict):
    kind = design_of(version)
    if kind == "b":
        return design_b.LearnerB(version)
    if kind == "o":
        return design_o.OpenLearner(version)
    return Learner(version)


def digest(version: dict) -> str:
    return _module(version).digest(version)


def validate(version: dict) -> dict:
    return _module(version).validate(version)


def differences(a: dict, b: dict) -> dict:
    return _module(a).differences(a, b)


def schema(version: dict) -> dict:
    return _module(version).SCHEMA


def default(design: str = "a") -> dict:
    return {"b": design_b.default, "o": design_o.default}.get(design, design_a.default)()
