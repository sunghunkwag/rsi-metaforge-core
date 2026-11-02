"""Compile a Builder-DSL program into the kernel's checker language (generation 0; Builder-owned).

The kernel judges only checker-language programs, so every solution the
Builder submits is compiled here. Primitives map one to one (the two
languages share RSI-2's value domain: ints, bools and lists); partially
applied primitives become lambdas over the missing arguments; library
entries and forged primitives are inlined (the library is acyclic, so
inlining terminates); de Bruijn variables become named variables.
"""
from __future__ import annotations

from .terms import Term
from .types import FORGED, PRIMITIVE_TYPES, function_parts

PRIMITIVE_MAP = {"add": "+", "sub": "-", "mul": "*", "div": "div", "mod": "mod", "neg": "neg",
                 "abs": "abs", "eq": "=", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
                 "and": "and", "or": "or", "not": "not", "cons": "cons", "head": "head",
                 "tail": "tail", "is_empty": "empty?", "length": "len", "range": "range",
                 "map": "map", "filter": "filter", "fold": "fold", "if": "if"}
SPECIAL = {"and", "or", "if"}


def _arity(name: str) -> int:
    return len(function_parts(PRIMITIVE_TYPES[name])[0])


def _spine(term: Term):
    arguments = []
    while term.tag == "app":
        arguments.append(term.children[1])
        term = term.children[0]
    return term, list(reversed(arguments))


class Compiler:
    def __init__(self, library: dict):
        self.library = dict(library)
        self.counter = 0

    def fresh(self) -> str:
        self.counter += 1
        return f"v{self.counter}"

    def compile(self, term: Term, names=()) -> object:
        """``names``: bound variable names, innermost first (de Bruijn order)."""
        if term.tag == "int" or term.tag == "bool":
            return term.value
        if term.tag == "var":
            if term.value >= len(names):
                raise ValueError("unbound variable")
            return names[term.value]
        if term.tag == "lam":
            # Nested DSL lambdas are curried; the checker language's are not,
            # so a chain of lambdas becomes one lambda over all of them.
            params, body, bound = [], term, tuple(names)
            while body.tag == "lam":
                name = self.fresh()
                params.append(name)
                bound = (name,) + bound
                body = body.children[0]
            return ["lambda", params, self.compile(body, bound)]
        head, arguments = _spine(term)
        compiled_arguments = [self.compile(a, names) for a in arguments]
        if head.tag == "prim" and head.value == "nil":
            if compiled_arguments:
                raise ValueError("nil takes no arguments")
            return ["list"]
        if head.tag == "prim" and head.value in FORGED:
            body = FORGED[head.value]["body"]
            arity = _arity(head.value)
            return self._apply(body, compiled_arguments, arity)
        if head.tag == "prim":
            name = PRIMITIVE_MAP[head.value]
            arity = _arity(head.value)
            if name in SPECIAL and len(compiled_arguments) == arity:
                return [name, *compiled_arguments]
            if name in SPECIAL:
                return self._apply(self._special_lambda(name, arity), compiled_arguments, arity)
            return self._apply(name, compiled_arguments, arity)
        if head.tag == "ref":
            body = self.compile(self.library[head.value], ())
            return self._apply(body, compiled_arguments, None)
        if head.tag == "lam":
            function = self.compile(head, names)
            return self._apply(function, compiled_arguments, None)
        raise ValueError(f"cannot compile {term.tag}")

    def _special_lambda(self, name: str, arity: int):
        params = [self.fresh() for _ in range(arity)]
        return ["lambda", params, [name, *params]]

    @staticmethod
    def _arity_of(function) -> int | None:
        if isinstance(function, list) and function and function[0] == "lambda":
            return len(function[1])
        return None

    def _apply(self, function, arguments: list, arity):
        """Apply ``function`` to arguments in curried steps of its arity; eta-expand a partial application."""
        if arity is None:
            arity = self._arity_of(function)
        if not arguments:
            return function
        if arity is None:
            return [function, *arguments]
        if len(arguments) < arity:
            missing = [self.fresh() for _ in range(arity - len(arguments))]
            return ["lambda", missing, [function, *arguments, *missing]]
        applied = [function, *arguments[:arity]] if arity else function
        rest = arguments[arity:]
        return self._apply(applied, rest, None) if rest else applied


def compile_program(term: Term, library: dict) -> object:
    """A closed DSL term as a checker-language function expression."""
    return Compiler(library).compile(term)
