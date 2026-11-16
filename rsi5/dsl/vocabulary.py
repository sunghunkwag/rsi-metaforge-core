"""Vocabularies: which primitives and constants a search may use.

The language (``types.PRIMITIVE_TYPES``, ``evaluator.evaluate``) understands every
primitive. A ``Vocabulary`` is the subset a search is allowed to build with, plus its
integer constants. Two are fixed here:

* ``ORIGINAL``: RSI-2's grammar, exactly (``rsi2/grammar.py`` constants -1, 0, 1, 2 and
  the twenty-six primitives of ``rsi2/types.py``).
* ``RESTORED``: ORIGINAL plus the DreamCoder vocabulary RSI-2 lacked (``VOCABULARY.md``).

Admitted primitives (Phase 2) extend a vocabulary through ``with_admitted``; nothing
human-authored is added beyond the restored set (OWNER_DIRECTIVE.md §12).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .types import (ORIGINAL_PRIMITIVE_TYPES, PRIMITIVE_TYPES, RESTORED_PRIMITIVE_TYPES,
                    Type)


@dataclass(frozen=True)
class Vocabulary:
    name: str
    primitives: tuple[str, ...]
    integer_constants: tuple[int, ...]
    boolean_constants: tuple[bool, ...] = (False, True)
    admitted: dict = field(default_factory=dict)   # name -> (Type, witness Term)

    def __post_init__(self):
        unknown = [p for p in self.primitives if p not in PRIMITIVE_TYPES and p not in self.admitted]
        if unknown:
            raise ValueError(f"unknown primitives {unknown}")
        if len(set(self.primitives)) != len(self.primitives):
            raise ValueError("duplicate primitives")
        if len(set(self.integer_constants)) != len(self.integer_constants):
            raise ValueError("duplicate integer constants")

    def type_of(self, name: str) -> Type:
        if name in PRIMITIVE_TYPES:
            return PRIMITIVE_TYPES[name]
        return self.admitted[name][0]

    @property
    def signatures(self) -> dict:
        return {name: self.type_of(name) for name in self.primitives}

    def with_admitted(self, name: str, type_: Type, witness) -> "Vocabulary":
        if name in PRIMITIVE_TYPES or name in self.primitives:
            raise ValueError(f"name {name!r} already in the vocabulary")
        admitted = dict(self.admitted)
        admitted[name] = (type_, witness)
        return Vocabulary(self.name, self.primitives + (name,), self.integer_constants,
                          self.boolean_constants, admitted)


ORIGINAL = Vocabulary("original", tuple(ORIGINAL_PRIMITIVE_TYPES), (-1, 0, 1, 2))
RESTORED = Vocabulary("restored",
                      tuple(ORIGINAL_PRIMITIVE_TYPES) + tuple(RESTORED_PRIMITIVE_TYPES),
                      (-1, 0, 1, 2, 3, 4, 5))
VOCABULARIES = {"original": ORIGINAL, "restored": RESTORED}
