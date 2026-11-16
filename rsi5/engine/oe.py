"""Observational equivalence: one program per behaviour on the evaluation points.

A behaviour is the tuple of a program's values on a context's evaluation points, with
a failed evaluation recorded as ``ERR``. Lists become tuples and pairs stay tuples;
pools are keyed by type, so a list and a pair of the same shape never meet.
"""
from __future__ import annotations


class _Error:
    __slots__ = ()

    def __repr__(self):
        return "ERR"

    def __reduce__(self):
        return "ERR"


ERR = _Error()


def freeze(value):
    """A hashable image of a value; lists become tuples recursively."""
    if type(value) is list:
        return tuple(freeze(v) for v in value)
    if type(value) is tuple:
        return (freeze(value[0]), freeze(value[1]))
    return value


def key_of(outputs) -> tuple:
    return tuple(freeze(v) for v in outputs)


class OETable:
    """Per-type map from behaviour key to the first program that showed it."""

    def __init__(self):
        self.tables: dict = {}
        self.pruned = 0

    def admit(self, type_, key, program) -> bool:
        table = self.tables.get(type_)
        if table is None:
            table = self.tables[type_] = {}
        if key in table:
            self.pruned += 1
            return False
        table[key] = program
        return True

    def lookup(self, type_, key):
        table = self.tables.get(type_)
        return None if table is None else table.get(key)

    def size(self, type_=None) -> int:
        if type_ is None:
            return sum(len(t) for t in self.tables.values())
        return len(self.tables.get(type_, ()))
