"""Budgeted interpreter for the frozen functional DSL.

Application uses memoized argument thunks so ``if`` evaluates only its selected
branch. Fold provides bounded iteration without adding an unrestricted fixpoint.
Input validation, AST preflight, applications, and list work consume steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .terms import Term
from .types import (Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, TVar,
                    TypeInferenceError, function_parts, infer, library_entries,
                    library_entry, substitute, unify)


MAX_INTEGER_BITS = 4096
MAX_INT_BIT_LENGTH = MAX_INTEGER_BITS


@dataclass(frozen=True)
class Result:
    ok: bool
    value: object = None
    error: str | None = None
    steps: int = 0


class _BudgetExceeded(Exception):
    pass


class _RuntimeFailure(Exception):
    pass


_UNFORCED = object()


@dataclass
class _Thunk:
    term: Term | None = None
    env: tuple = ()
    value: object = _UNFORCED


@dataclass(frozen=True)
class _Closure:
    body: Term
    env: tuple


@dataclass(frozen=True)
class _Primitive:
    name: str
    arguments: tuple = ()


_ARITIES = {name: len(function_parts(type_)[0]) for name, type_ in PRIMITIVE_TYPES.items()}


@lru_cache(maxsize=8192)
def _infer_without_library(term):
    """Immutable ASTs share typing work across a candidate's I/O examples."""
    return infer(term)


class _Interpreter:
    def __init__(self, budget, library):
        self.budget = budget
        self.steps = 0
        self.entries = library_entries(library)
        self.references = {}
        self.active_references = set()

    def tick(self, amount=1):
        if amount > self.budget - self.steps:
            self.steps = self.budget
            raise _BudgetExceeded()
        self.steps += amount

    def integer(self, value):
        if type(value) is not int:
            raise _RuntimeFailure("expected int")
        if value.bit_length() > MAX_INTEGER_BITS:
            raise _RuntimeFailure("integer exceeds bit limit")
        return value

    def boolean(self, value):
        if type(value) is not bool:
            raise _RuntimeFailure("expected bool")
        return value

    def list_value(self, value):
        if type(value) is not list:
            raise _RuntimeFailure("expected list")
        return value

    def preflight(self, term):
        """Charge structural/type checking before recursive inference can run."""
        pending, scanned_entries = [term], set()
        while pending:
            self.tick()
            current = pending.pop()
            if not isinstance(current, Term):
                raise TypeInferenceError("expected a Term AST")
            if current.tag == "int":
                self.integer(current.value)
            if current.tag == "lam":
                type_nodes = [current.value]
                while type_nodes:
                    self.tick()
                    type_node = type_nodes.pop()
                    if type_node.tag != "var":
                        type_nodes.extend(type_node.args)
            pending.extend(current.children)
            if current.tag == "ref" or (current.tag == "prim" and current.value not in PRIMITIVE_TYPES):
                name = current.value
                if name not in self.entries:
                    raise TypeInferenceError(f"unknown library entry {name!r}")
                if name not in scanned_entries:
                    scanned_entries.add(name)
                    body, _ = library_entry(self.entries[name])
                    if body is None:
                        raise TypeInferenceError(f"library entry {name!r} has no executable term")
                    pending.append(body)

    def input_value(self, value, serial):
        self.tick()
        if type(value) is bool:
            return value, BOOL
        if type(value) is int:
            return self.integer(value), INT
        if type(value) is list:
            # Reject impossible work before copying a potentially enormous list.
            if len(value) > self.budget - self.steps:
                self.tick(len(value))
            copied, element_type, substitutions = [], TVar(f"_input_{next(serial)}"), {}
            for element in value:
                actual, actual_type = self.input_value(element, serial)
                substitutions = unify(element_type, actual_type, substitutions)
                element_type = substitute(element_type, substitutions)
                copied.append(actual)
            return copied, ListOf(element_type)
        raise TypeInferenceError("inputs must contain only ints, bools, and homogeneous lists")

    def force(self, thunk):
        if thunk.value is _UNFORCED:
            thunk.value = self.run(thunk.term, thunk.env)
        return thunk.value

    def run(self, term, env):
        self.tick()
        tag = term.tag
        if tag in ("int", "bool"):
            return term.value
        if tag == "var":
            return self.force(env[term.value])
        if tag == "lam":
            return _Closure(term.children[0], env)
        if tag == "app":
            function, argument = term.children
            return self.apply(self.run(function, env), _Thunk(argument, env))
        if tag == "prim" and term.value in PRIMITIVE_TYPES:
            return [] if term.value == "nil" else _Primitive(term.value)
        if tag in ("prim", "ref"):
            name = term.value
            if name in self.active_references:
                raise _RuntimeFailure("recursive library reference")
            if name not in self.references:
                body, _ = library_entry(self.entries[name])
                self.active_references.add(name)
                try:
                    self.references[name] = self.run(body, ())
                finally:
                    self.active_references.remove(name)
            return self.references[name]
        raise _RuntimeFailure(f"unknown term tag {tag!r}")

    def apply(self, function, argument):
        self.tick()
        if isinstance(function, _Closure):
            return self.run(function.body, (argument,) + function.env)
        if isinstance(function, _Primitive):
            arguments = function.arguments + (argument,)
            return self.primitive(function.name, arguments) if len(arguments) == _ARITIES[function.name] else _Primitive(function.name, arguments)
        raise _RuntimeFailure("attempted application of a non-function")

    def primitive(self, name, arguments):
        self.tick()
        if name == "if":
            selected = 1 if self.boolean(self.force(arguments[0])) else 2
            return self.force(arguments[selected])
        if name in ("and", "or"):
            left = self.boolean(self.force(arguments[0]))
            return (left and self.boolean(self.force(arguments[1]))) if name == "and" else (left or self.boolean(self.force(arguments[1])))
        values = [self.force(argument) for argument in arguments]
        if name in ("add", "sub", "mul", "div", "mod", "eq", "lt", "le", "gt", "ge"):
            left, right = (self.integer(value) for value in values)
            if name == "mul" and left and right and left.bit_length() + right.bit_length() - 1 > MAX_INTEGER_BITS:
                raise _RuntimeFailure("integer exceeds bit limit")
            if name == "add":
                result = left + right
            elif name == "sub":
                result = left - right
            elif name == "mul":
                result = left * right
            elif name == "div":
                result = left // right
            elif name == "mod":
                result = left % right
            elif name == "eq":
                return left == right
            elif name == "lt":
                return left < right
            elif name == "le":
                return left <= right
            elif name == "gt":
                return left > right
            else:
                return left >= right
            return self.integer(result)
        if name in ("neg", "abs"):
            value = self.integer(values[0])
            return -value if name == "neg" else abs(value)
        if name == "not":
            return not self.boolean(values[0])
        if name == "cons":
            tail = self.list_value(values[1])
            self.tick(len(tail) + 1)
            return [values[0]] + tail
        if name in ("head", "tail", "is_empty", "length"):
            sequence = self.list_value(values[0])
            if name == "head":
                if not sequence:
                    raise _RuntimeFailure("head of empty list")
                return sequence[0]
            if name == "tail":
                if not sequence:
                    raise _RuntimeFailure("tail of empty list")
                self.tick(len(sequence) - 1)
                return sequence[1:]
            return not sequence if name == "is_empty" else len(sequence)
        if name == "range":
            length = max(0, self.integer(values[0]))
            self.tick(length)
            return list(range(length))
        if name in ("map", "filter"):
            function, sequence = values[0], self.list_value(values[1])
            result = []
            for element in sequence:
                self.tick()
                transformed = self.apply(function, _Thunk(value=element))
                if name == "map":
                    result.append(transformed)
                elif self.boolean(transformed):
                    result.append(element)
            return result
        if name == "fold":
            function, accumulator, sequence = values[0], values[1], self.list_value(values[2])
            for element in sequence:
                self.tick()
                partial = self.apply(function, _Thunk(value=accumulator))
                accumulator = self.apply(partial, _Thunk(value=element))
            return accumulator
        raise _RuntimeFailure(f"unknown primitive {name!r}")


def evaluate(term: Term, inputs=(), library=None, step_budget: int = 1000) -> Result:
    """Evaluate an AST applied to sequential host arguments; failures never escape."""
    interpreter = None
    try:
        if type(step_budget) is not int or step_budget < 0:
            return Result(False, error="runtime_error: budget must be a nonnegative integer")
        interpreter = _Interpreter(step_budget, library)
        interpreter.preflight(term)
        result_type = infer(term, library=library) if interpreter.entries else _infer_without_library(term)
        from itertools import count
        serial = count()
        arguments = []
        if type(inputs) not in (tuple, list):
            raise TypeInferenceError("inputs must be a tuple or list of function arguments")
        for input_value in inputs:
            value, type_ = interpreter.input_value(input_value, serial)
            output = TVar(f"_output_{next(serial)}")
            substitutions = unify(result_type, Arrow(type_, output))
            result_type = substitute(output, substitutions)
            arguments.append(_Thunk(value=value))
        value = interpreter.run(term, ())
        for argument in arguments:
            value = interpreter.apply(value, argument)
        return Result(True, value=value, steps=interpreter.steps)
    except _BudgetExceeded:
        error = "budget_exhausted"
    except (TypeInferenceError, TypeError) as exc:
        error = f"type_error: {exc}"
    except Exception as exc:
        error = f"runtime_error: {type(exc).__name__}: {exc}"
    return Result(False, error=error, steps=interpreter.steps if interpreter is not None else 0)
