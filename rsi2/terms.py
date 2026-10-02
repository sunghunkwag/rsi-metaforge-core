"""Immutable de Bruijn ASTs, serialization, and readable display."""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from .types import Type


@dataclass(frozen=True)
class Term:
    tag: str
    value: object = None
    children: tuple["Term", ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "children", tuple(self.children))
        arities = {"prim": 0, "ref": 0, "var": 0, "int": 0, "bool": 0, "hole": 0,
                   "lam": 1, "app": 2}
        if self.tag not in arities or len(self.children) != arities[self.tag]:
            raise TypeError(f"invalid term shape: {self.tag!r}")
        if not all(isinstance(child, Term) for child in self.children):
            raise TypeError("term children must be terms")
        if self.tag in ("prim", "ref") and not isinstance(self.value, str):
            raise TypeError("primitive and library names must be strings")
        if self.tag in ("var", "int") and type(self.value) is not int:
            raise TypeError("indices and integer literals must be ints")
        if self.tag == "var" and self.value < 0:
            raise TypeError("de Bruijn indices must be nonnegative")
        if self.tag == "bool" and type(self.value) is not bool:
            raise TypeError("boolean literals must be bools")
        if self.tag == "lam" and not isinstance(self.value, Type):
            raise TypeError("lambda parameters require a type")
        if self.tag == "hole" and not isinstance(self.value, Type):
            raise TypeError("enumeration holes require an expected type")

    @cached_property
    def size(self) -> int:
        return 1 + sum(child.size for child in self.children)

    @cached_property
    def depth(self) -> int:
        return 1 + max((child.depth for child in self.children), default=0)

    def to_dict(self):
        return term_to_dict(self)

    @classmethod
    def from_dict(cls, value):
        return term_from_dict(value)

    def __str__(self):
        return pretty(self)


def Prim(name: str) -> Term:
    return Term("prim", name)


def Ref(name: str) -> Term:
    return Term("ref", name)


def Var(index: int) -> Term:
    return Term("var", index)


def Lam(type_: Type, body: Term) -> Term:
    return Term("lam", type_, (body,))


def App(function: Term, argument: Term) -> Term:
    return Term("app", None, (function, argument))


def Int(value: int) -> Term:
    return Term("int", value)


def Bool(value: bool) -> Term:
    return Term("bool", value)


def apply(function: Term, *arguments: Term) -> Term:
    for argument in arguments:
        function = App(function, argument)
    return function


def Literal(value) -> Term:
    if type(value) is bool:
        return Bool(value)
    if type(value) is int:
        return Int(value)
    if type(value) is list:
        result = Prim("nil")
        for element in reversed(value):
            result = apply(Prim("cons"), Literal(element), result)
        return result
    raise TypeError("literal values must be ints, bools, or lists")


def term_to_dict(term: Term) -> dict:
    value = term.value.to_dict() if isinstance(term.value, Type) else term.value
    return {"tag": term.tag, "value": value,
            "children": [term_to_dict(child) for child in term.children]}


def term_from_dict(data: dict) -> Term:
    value = Type.from_dict(data["value"]) if data["tag"] in ("lam", "hole") else data.get("value")
    return Term(data["tag"], value, tuple(term_from_dict(c) for c in data.get("children", ())))


def pretty(term: Term, names=()) -> str:
    if term.tag == "var":
        return names[term.value] if term.value < len(names) else f"${term.value}"
    if term.tag in ("prim", "ref"):
        return term.value
    if term.tag in ("int", "bool"):
        return str(term.value).lower()
    if term.tag == "lam":
        name = f"x{len(names)}"
        return f"(lambda {name}: {term.value}. {pretty(term.children[0], (name,) + tuple(names))})"
    if term.tag == "hole":
        return f"?{term.value}"
    function, argument = term.children
    return f"({pretty(function, names)} {pretty(argument, names)})"


def shift(term: Term, amount: int, cutoff: int = 0) -> Term:
    """Shift free de Bruijn indices, preserving all bound indices."""
    if term.tag == "var":
        return Var(term.value + amount) if term.value >= cutoff else term
    if not term.children:
        return term
    child_cutoff = cutoff + (term.tag == "lam")
    return Term(term.tag, term.value, tuple(shift(c, amount, child_cutoff) for c in term.children))


def replace_subterm(term: Term, path: tuple[int, ...], replacement: Term) -> Term:
    if not path:
        return replacement
    index, *rest = path
    children = list(term.children)
    children[index] = replace_subterm(children[index], tuple(rest), replacement)
    return Term(term.tag, term.value, tuple(children))


def subterms(term: Term, path=()):
    yield tuple(path), term
    for index, child in enumerate(term.children):
        yield from subterms(child, tuple(path) + (index,))
