"""Types and unification for the frozen RSI-2 functional language."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from typing import Any, Mapping


@dataclass(frozen=True)
class Type:
    tag: str
    args: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "args", tuple(self.args))
        arities = {"int": 0, "bool": 0, "list": 1, "arrow": 2, "var": 1}
        if self.tag not in arities or len(self.args) != arities[self.tag]:
            raise TypeError(f"invalid type: {self.tag!r}")
        if self.tag == "var":
            if not isinstance(self.args[0], str):
                raise TypeError("type variable names must be strings")
        elif not all(isinstance(arg, Type) for arg in self.args):
            raise TypeError("type arguments must be types")

    @property
    def is_variable(self):
        return self.tag == "var"

    @property
    def name(self):
        return self.args[0] if self.is_variable else self.tag

    def __str__(self):
        if self.tag == "list":
            return f"list[{self.args[0]}]"
        if self.tag == "arrow":
            left, right = self.args
            return f"({left}) -> {right}" if left.tag == "arrow" else f"{left} -> {right}"
        return self.name

    def to_dict(self):
        return {"tag": self.tag, "args": [a.to_dict() if isinstance(a, Type) else a for a in self.args]}

    @classmethod
    def from_dict(cls, value):
        return cls(value["tag"], tuple(cls.from_dict(a) if isinstance(a, dict) else a
                                       for a in value.get("args", ())))


INT = Type("int")
BOOL = Type("bool")


def ListOf(element: Type) -> Type:
    return Type("list", (element,))


def Arrow(argument: Type, result: Type) -> Type:
    return Type("arrow", (argument, result))


def TVar(name: str) -> Type:
    return Type("var", (str(name),))


def arrows(*types: Type) -> Type:
    if not types:
        raise TypeError("arrows requires at least one type")
    result = types[-1]
    for arg in reversed(types[:-1]):
        result = Arrow(arg, result)
    return result


def function_parts(type_: Type) -> tuple[tuple[Type, ...], Type]:
    arguments = []
    while type_.tag == "arrow":
        arguments.append(type_.args[0])
        type_ = type_.args[1]
    return tuple(arguments), type_


class TypeInferenceError(TypeError):
    pass


def substitute(type_: Type, substitutions: Mapping[str, Type]) -> Type:
    if type_.is_variable:
        replacement = substitutions.get(type_.name)
        return substitute(replacement, substitutions) if replacement is not None else type_
    if not type_.args:
        return type_
    arguments = tuple(substitute(arg, substitutions) for arg in type_.args)
    return type_ if arguments == type_.args else Type(type_.tag, arguments)


def _occurs(name: str, type_: Type) -> bool:
    return type_.name == name if type_.is_variable else any(_occurs(name, a) for a in type_.args)


def unify(left: Type, right: Type, substitutions=None) -> dict[str, Type]:
    """Return an extended substitution without mutating the caller's mapping."""
    result = dict(substitutions or {})
    pending = [(left, right)]
    while pending:
        first, second = (substitute(t, result) for t in pending.pop())
        if first == second:
            continue
        if first.is_variable or second.is_variable:
            if not first.is_variable:
                first, second = second, first
            if _occurs(first.name, second):
                raise TypeInferenceError(f"infinite type: {first} occurs in {second}")
            result[first.name] = second
        elif first.tag == second.tag:
            pending.extend(zip(first.args, second.args))
        else:
            raise TypeInferenceError(f"cannot unify {first} with {second}")
    return result


_fresh_ids = count()


def instantiate(type_: Type, prefix: str = "t") -> Type:
    variables = {}

    def visit(current):
        if current.is_variable:
            if current.name not in variables:
                variables[current.name] = TVar(f"{prefix}{next(_fresh_ids)}")
            return variables[current.name]
        if not current.args:
            return current
        arguments = tuple(visit(a) for a in current.args)
        return current if arguments == current.args else Type(current.tag, arguments)

    return visit(type_)


_A, _B = TVar("a"), TVar("b")
PRIMITIVE_TYPES = {
    **{name: arrows(INT, INT, INT) for name in ("add", "sub", "mul", "div", "mod")},
    **{name: Arrow(INT, INT) for name in ("neg", "abs")},
    **{name: arrows(INT, INT, BOOL) for name in ("eq", "lt", "le", "gt", "ge")},
    **{name: arrows(BOOL, BOOL, BOOL) for name in ("and", "or")},
    "not": Arrow(BOOL, BOOL),
    "if": arrows(BOOL, _A, _A, _A),
    "nil": ListOf(_A),
    "cons": arrows(_A, ListOf(_A), ListOf(_A)),
    "head": Arrow(ListOf(_A), _A),
    "tail": Arrow(ListOf(_A), ListOf(_A)),
    "is_empty": Arrow(ListOf(_A), BOOL),
    "length": Arrow(ListOf(_A), INT),
    "range": Arrow(INT, ListOf(INT)),
    "map": arrows(Arrow(_A, _B), ListOf(_A), ListOf(_B)),
    "filter": arrows(Arrow(_A, BOOL), ListOf(_A), ListOf(_A)),
    "fold": arrows(arrows(_B, _A, _B), _B, ListOf(_A), _B),
}


def library_entries(library) -> Mapping:
    if library is None:
        return {}
    entries = library if isinstance(library, Mapping) else getattr(library, "entries", None)
    if not isinstance(entries, Mapping):
        raise TypeInferenceError("library must be a mapping or expose an entries mapping")
    return entries


def library_entry(entry) -> tuple[Any, Type | None]:
    """Support plain terms, declared (type, term) pairs, and named entry objects."""
    if isinstance(entry, Type):
        return None, entry
    if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], Type):
        return entry[1], entry[0]
    if hasattr(entry, "term"):
        return entry.term, getattr(entry, "type", None)
    return entry, None


def infer(term, env=(), library=None) -> Type:
    """Infer a curried type; environment index zero is the newest lambda binder."""
    entries, cache, active = library_entries(library), {}, set()
    substitutions = {}
    fresh = count()

    def new_variable():
        return TVar(f"_infer_{next(fresh)}")

    def annotation(type_, renames):
        if type_.is_variable:
            if type_.name not in renames:
                renames[type_.name] = new_variable()
            return renames[type_.name]
        if not type_.args:
            return type_
        arguments = tuple(annotation(a, renames) for a in type_.args)
        return type_ if arguments == type_.args else Type(type_.tag, arguments)

    def constrain(a, b):
        nonlocal substitutions
        substitutions = unify(a, b, substitutions)

    def reference(name):
        if name not in entries:
            raise TypeInferenceError(f"unknown library entry {name!r}")
        if name in active:
            raise TypeInferenceError(f"recursive library entry {name!r}")
        if name not in cache:
            active.add(name)
            body, declared = library_entry(entries[name])
            if body is None and declared is None:
                raise TypeInferenceError(f"library entry {name!r} has no term or type")
            actual = visit(body, (), {}) if body is not None else instantiate(declared, "_decl_")
            if declared is not None:
                constrain(actual, instantiate(declared, "_decl_"))
            cache[name] = substitute(actual, substitutions)
            active.remove(name)
        return instantiate(cache[name], "_lib_")

    def visit(node, bindings, renames):
        if node.tag == "int":
            if type(node.value) is not int:
                raise TypeInferenceError("integer literal must be an int")
            return INT
        if node.tag == "bool":
            if type(node.value) is not bool:
                raise TypeInferenceError("boolean literal must be a bool")
            return BOOL
        if node.tag == "var":
            if type(node.value) is not int or not 0 <= node.value < len(bindings):
                raise TypeInferenceError(f"unbound de Bruijn index {node.value!r}")
            return bindings[node.value]
        if node.tag == "prim":
            return instantiate(PRIMITIVE_TYPES[node.value], "_prim_") if node.value in PRIMITIVE_TYPES else reference(node.value)
        if node.tag == "ref":
            return reference(node.value)
        if node.tag == "lam":
            if not isinstance(node.value, Type) or len(node.children) != 1:
                raise TypeInferenceError("lambda requires a parameter type and one body")
            parameter = annotation(node.value, renames)
            result = visit(node.children[0], (parameter,) + tuple(bindings), renames)
            return Arrow(substitute(parameter, substitutions), result)
        if node.tag == "app":
            if len(node.children) != 2:
                raise TypeInferenceError("application requires a function and argument")
            function = visit(node.children[0], bindings, renames)
            argument = visit(node.children[1], bindings, renames)
            result = new_variable()
            constrain(function, Arrow(argument, result))
            return substitute(result, substitutions)
        raise TypeInferenceError(f"unknown term tag {node.tag!r}")

    try:
        return substitute(visit(term, tuple(env), {}), substitutions)
    except (AttributeError, IndexError, KeyError, RecursionError) as exc:
        raise TypeInferenceError(f"malformed or excessively deep term: {exc}") from exc
