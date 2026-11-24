"""A restricted interpreter for verifier code.

The tasks of this package are verifiers written by other people. They are not executed by
Python: no ``exec``, no ``eval``, no ``compile``. Their source is parsed and walked by this
interpreter, which knows a pure subset of the language:

  * expressions, comprehensions, generator expressions, lambdas, f-strings;
  * assignments, ``if`` / ``for`` / ``while`` / ``assert`` / ``return`` / ``try``, nested
    functions;
  * a fixed list of builtins and of methods of the basic types (numbers, strings, lists,
    tuples, sets, dictionaries);
  * a fixed list of pure standard-library modules (``math``, ``itertools``, ``collections``,
    ``heapq``, ``functools``, ``bisect``, ``fractions``, ``string``, ``re``) and a seeded
    ``random``.

Anything else is ``Unsupported`` and the verifier is reported as such: there is no file, no
network, no process, no attribute access outside the lists, no double-underscore name.

Cost is counted in *steps* (one per syntax node evaluated and one per item drawn from an
iterator), so a budget is a number, not a duration, and a run is reproducible. An operation
that would build a huge value in one native call (a power, a repetition, a range handed to a
native aggregate) is ``Refused`` before it happens.
"""
from __future__ import annotations

import ast
import bisect
import collections
import fractions
import functools
import heapq
import itertools
import math
import operator
import random
import re
import string

FUEL = 200_000                   # default steps per call of a verifier
MAX_BITS = 40_000                # bits of an integer a power or a shift may produce
MAX_SEQUENCE = 2_000_000         # length a repetition, a concatenation or a native aggregate may see
MAX_DEPTH = 120                  # nested calls of interpreted functions


class Fuel(Exception):
    """The step budget ran out."""


class Refused(Exception):
    """An operation over the size caps."""


class Unsupported(Exception):
    """Syntax, a name or an attribute outside the supported subset."""


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


CONTROL = (Fuel, Refused, Unsupported, _Return, _Break, _Continue)

METHODS = {
    str: {"count", "startswith", "endswith", "find", "rfind", "index", "rindex", "join", "split", "rsplit", "strip",
          "lstrip", "rstrip", "upper", "lower", "isdigit", "isalpha", "isalnum", "isupper", "islower", "isspace",
          "replace", "title", "capitalize", "swapcase", "zfill", "center", "ljust", "rjust", "partition",
          "rpartition", "splitlines", "isnumeric", "isdecimal", "casefold", "encode", "translate", "expandtabs",
          "removeprefix", "removesuffix", "isidentifier", "isprintable", "istitle", "isascii", "maketrans"},
    bytes: {"count", "startswith", "endswith", "find", "index", "decode", "hex", "split", "join", "strip", "replace",
            "upper", "lower"},
    list: {"append", "extend", "insert", "pop", "remove", "index", "count", "sort", "reverse", "copy", "clear"},
    tuple: {"count", "index"},
    dict: {"get", "keys", "values", "items", "pop", "setdefault", "update", "copy", "clear", "popitem", "fromkeys"},
    set: {"add", "remove", "discard", "union", "intersection", "difference", "issubset", "issuperset",
          "symmetric_difference", "update", "pop", "copy", "clear", "isdisjoint", "intersection_update",
          "difference_update", "symmetric_difference_update"},
    frozenset: {"union", "intersection", "difference", "issubset", "issuperset", "symmetric_difference", "copy",
                "isdisjoint"},
    int: {"bit_length", "bit_count", "to_bytes", "conjugate", "real", "imag", "numerator", "denominator",
          "is_integer"},
    float: {"is_integer", "conjugate", "real", "imag", "hex", "as_integer_ratio"},
    complex: {"real", "imag", "conjugate"},
    range: {"count", "index", "start", "stop", "step"},
    collections.Counter: {"most_common", "elements", "get", "keys", "values", "items", "update", "subtract", "copy",
                          "total", "pop", "setdefault"},
    collections.defaultdict: {"get", "keys", "values", "items", "pop", "setdefault", "update", "copy"},
    collections.deque: {"append", "appendleft", "pop", "popleft", "extend", "extendleft", "rotate", "count", "index",
                        "clear", "copy", "reverse"},
    fractions.Fraction: {"numerator", "denominator", "limit_denominator", "as_integer_ratio"},
    random.Random: {"seed", "random", "randint", "choice", "choices", "shuffle", "sample", "randrange", "uniform",
                    "gauss", "getrandbits", "normalvariate", "betavariate", "expovariate", "triangular"},
    re.Match: {"group", "groups", "start", "end", "span"},
}
EXCEPTIONS = {name: getattr(__builtins__ if isinstance(__builtins__, dict) is False else None, name, None)
              for name in ()}          # filled below without touching __builtins__ by name tricks
for _name in ("Exception", "ValueError", "TypeError", "IndexError", "KeyError", "ZeroDivisionError",
              "AssertionError", "StopIteration", "OverflowError", "ArithmeticError", "LookupError",
              "AttributeError", "RuntimeError", "NotImplementedError"):
    EXCEPTIONS[_name] = getattr(ast.literal_eval.__globals__["__builtins__"], _name) \
        if not isinstance(ast.literal_eval.__globals__["__builtins__"], dict) \
        else ast.literal_eval.__globals__["__builtins__"][_name]
CATCHABLE = (ValueError, TypeError, IndexError, KeyError, ZeroDivisionError, AssertionError, StopIteration,
             OverflowError, AttributeError, RuntimeError)


def _module(module, names):
    return {name: getattr(module, name) for name in names if hasattr(module, name)}


MODULES = {
    "math": _module(math, [n for n in dir(math) if not n.startswith("_")]),
    "itertools": _module(itertools, ["product", "permutations", "combinations", "combinations_with_replacement",
                                     "accumulate", "chain", "count", "cycle", "islice", "repeat", "groupby",
                                     "zip_longest", "takewhile", "dropwhile", "starmap", "compress", "pairwise",
                                     "tee", "filterfalse"]),
    "collections": _module(collections, ["Counter", "defaultdict", "deque", "OrderedDict", "namedtuple"]),
    "heapq": _module(heapq, ["heappush", "heappop", "heapify", "heapreplace", "heappushpop", "nlargest", "nsmallest",
                             "merge"]),
    "functools": _module(functools, ["reduce", "lru_cache", "cache", "partial", "cmp_to_key"]),
    "bisect": _module(bisect, ["bisect", "bisect_left", "bisect_right", "insort", "insort_left", "insort_right"]),
    "fractions": _module(fractions, ["Fraction"]),
    "string": _module(string, ["ascii_letters", "ascii_lowercase", "ascii_uppercase", "digits", "hexdigits",
                               "octdigits", "punctuation", "printable", "whitespace"]),
    "re": _module(re, ["match", "fullmatch", "search", "findall", "finditer", "sub", "split", "compile", "escape",
                       "IGNORECASE", "MULTILINE", "DOTALL"]),
    "operator": _module(operator, ["add", "sub", "mul", "truediv", "floordiv", "mod", "pow", "neg", "eq", "ne", "lt",
                                   "le", "gt", "ge", "and_", "or_", "xor", "itemgetter", "not_", "abs"]),
    "typing": {},
    "copy": {"copy": lambda v: v.copy() if hasattr(v, "copy") else v, "deepcopy": None},
}
RANDOM_NAMES = ("seed", "random", "randint", "choice", "choices", "shuffle", "sample", "randrange", "uniform",
                "gauss", "getrandbits", "normalvariate")


def _deepcopy(value):
    if isinstance(value, list):
        return [_deepcopy(v) for v in value]
    if isinstance(value, dict):
        return {k: _deepcopy(v) for k, v in value.items()}
    if isinstance(value, set):
        return set(value)
    if isinstance(value, tuple):
        return tuple(_deepcopy(v) for v in value)
    return value


MODULES["copy"]["deepcopy"] = _deepcopy
NATIVE = {"abs": abs, "all": all, "any": any, "bin": bin, "bool": bool, "chr": chr, "dict": dict, "divmod": divmod,
          "enumerate": enumerate, "filter": filter, "float": float, "frozenset": frozenset, "hex": hex, "int": int,
          "isinstance": isinstance, "iter": iter, "len": len, "list": list, "map": map, "max": max, "min": min,
          "next": next, "oct": oct, "ord": ord, "pow": pow, "range": range, "repr": repr, "reversed": reversed,
          "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
          "type": type, "complex": complex, "bytes": bytes, "hash": hash, "callable": callable, "slice": slice,
          "print": lambda *a, **k: None, "id": None, "format": format, "ascii": ascii, "bytearray": None,
          "True": True, "False": False, "None": None}
NATIVE = {k: v for k, v in NATIVE.items() if v is not None or k in ("None",)}
NATIVE.update(EXCEPTIONS)
AGGREGATES = {all, any, list, tuple, set, frozenset, sorted, sum, max, min, dict, enumerate, zip, map, filter,
              reversed, iter, len, str, repr, bytes}
LAZY = {map, filter, zip, enumerate, reversed, iter, itertools.product, itertools.permutations,
        itertools.combinations, itertools.combinations_with_replacement, itertools.accumulate, itertools.chain,
        itertools.count, itertools.cycle, itertools.islice, itertools.repeat, itertools.zip_longest,
        itertools.takewhile, itertools.dropwhile, itertools.starmap, itertools.compress, itertools.filterfalse,
        heapq.merge, re.finditer}
if hasattr(itertools, "pairwise"):
    LAZY.add(itertools.pairwise)
ALLOWED_CALLABLES = set(v for v in NATIVE.values() if callable(v))
for _names in MODULES.values():
    ALLOWED_CALLABLES.update(v for v in _names.values() if callable(v))
ALLOWED_TYPES = tuple(METHODS)


class Scope:
    __slots__ = ("vars", "parent")

    def __init__(self, parent=None):
        self.vars, self.parent = {}, parent

    def lookup(self, name):
        scope = self
        while scope is not None:
            if name in scope.vars:
                return scope.vars[name]
            scope = scope.parent
        raise KeyError(name)


class Function:
    """A function or lambda of the interpreted code. Calling it runs the interpreter."""

    def __init__(self, interpreter, node, scope, defaults, kw_defaults):
        self.interpreter, self.node, self.scope = interpreter, node, scope
        self.defaults, self.kw_defaults = defaults, kw_defaults
        self.name = getattr(node, "name", "<lambda>")

    def __call__(self, *args, **kwargs):
        return self.interpreter.call(self, args, kwargs)


class Interpreter:
    def __init__(self, fuel: int = FUEL, seed: int = 0):
        self.fuel = fuel
        self.depth = 0
        self.rng = random.Random(seed)
        self.random_module = {name: getattr(self.rng, name) for name in RANDOM_NAMES}
        self.random_module["Random"] = random.Random
        self.globals = Scope()

    # ---- budget -------------------------------------------------------------------------------
    def tick(self, n: int = 1) -> None:
        self.fuel -= n
        if self.fuel < 0:
            raise Fuel()

    def counted(self, iterable):
        for item in iterable:
            self.tick()
            yield item

    # ---- definitions and calls ----------------------------------------------------------------
    def define(self, source: str) -> Function:
        """Run the top level of a verifier's source (function definitions) and return ``sat``."""
        tree = ast.parse(source)
        self.block(tree.body, self.globals)
        try:
            return self.globals.vars["sat"]
        except KeyError:
            raise Unsupported("the source defines no function sat") from None

    def call(self, function: Function, args, kwargs):
        self.tick()
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth -= 1
            raise Refused("call depth")
        try:
            spec = function.node.args
            if spec.posonlyargs:
                raise Unsupported("positional-only parameters")
            scope = Scope(function.scope)
            names = [a.arg for a in spec.args]
            if len(args) > len(names) and spec.vararg is None:
                raise TypeError("too many arguments")
            for name, value in zip(names, args):
                scope.vars[name] = value
            if spec.vararg is not None:
                scope.vars[spec.vararg.arg] = tuple(args[len(names):])
            first_default = len(names) - len(function.defaults)
            extra = {}
            for key, value in kwargs.items():
                if key in names or key in [a.arg for a in spec.kwonlyargs]:
                    if key in scope.vars:
                        raise TypeError(f"multiple values for {key}")
                    scope.vars[key] = value
                elif spec.kwarg is not None:
                    extra[key] = value
                else:
                    raise TypeError(f"unexpected keyword {key}")
            for i, name in enumerate(names):
                if name not in scope.vars:
                    if i >= first_default:
                        scope.vars[name] = function.defaults[i - first_default]
                    else:
                        raise TypeError(f"missing argument {name}")
            for a, default in zip(spec.kwonlyargs, function.kw_defaults):
                if a.arg not in scope.vars:
                    if default is _MISSING:
                        raise TypeError(f"missing argument {a.arg}")
                    scope.vars[a.arg] = default
            if spec.kwarg is not None:
                scope.vars[spec.kwarg.arg] = extra
            if isinstance(function.node, ast.Lambda):
                return self.eval(function.node.body, scope)
            try:
                self.block(function.node.body, scope)
            except _Return as result:
                return result.value
            return None
        finally:
            self.depth -= 1

    # ---- statements ---------------------------------------------------------------------------
    def block(self, statements, scope) -> None:
        for statement in statements:
            self.statement(statement, scope)

    def statement(self, node, scope) -> None:
        self.tick()
        kind = type(node)
        if kind is ast.Return:
            raise _Return(self.eval(node.value, scope) if node.value is not None else None)
        if kind is ast.Assign:
            value = self.eval(node.value, scope)
            for target in node.targets:
                self.assign(target, value, scope)
        elif kind is ast.AugAssign:
            current = self.eval(_as_load(node.target), scope)
            self.assign(node.target, self.binary(node.op, current, self.eval(node.value, scope)), scope)
        elif kind is ast.AnnAssign:
            if node.value is not None:
                self.assign(node.target, self.eval(node.value, scope), scope)
        elif kind is ast.Expr:
            self.eval(node.value, scope)
        elif kind is ast.If:
            self.block(node.body if self.eval(node.test, scope) else node.orelse, scope)
        elif kind is ast.For:
            broke = False
            for item in self.iterate(self.eval(node.iter, scope)):
                self.assign(node.target, item, scope)
                try:
                    self.block(node.body, scope)
                except _Break:
                    broke = True
                    break
                except _Continue:
                    continue
            if not broke:
                self.block(node.orelse, scope)
        elif kind is ast.While:
            broke = False
            while self.eval(node.test, scope):
                self.tick()
                try:
                    self.block(node.body, scope)
                except _Break:
                    broke = True
                    break
                except _Continue:
                    continue
            if not broke:
                self.block(node.orelse, scope)
        elif kind is ast.Assert:
            if not self.eval(node.test, scope):
                raise AssertionError()
        elif kind is ast.FunctionDef:
            if node.decorator_list:
                raise Unsupported("decorators")
            scope.vars[node.name] = self.function(node, scope)
        elif kind is ast.Pass:
            pass
        elif kind is ast.Break:
            raise _Break()
        elif kind is ast.Continue:
            raise _Continue()
        elif kind is ast.Import:
            for alias in node.names:
                scope.vars[alias.asname or alias.name] = self.module(alias.name)
        elif kind is ast.ImportFrom:
            module = self.module(node.module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                if alias.name not in module.names:
                    raise Unsupported(f"{node.module}.{alias.name}")
                scope.vars[alias.asname or alias.name] = module.names[alias.name]
        elif kind is ast.Try:
            self.attempt(node, scope)
        elif kind is ast.Raise:
            raise self.eval(node.exc, scope) if node.exc is not None else RuntimeError()
        elif kind is ast.Delete:
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    del self.eval(target.value, scope)[self.index(target.slice, scope)]
                elif isinstance(target, ast.Name):
                    scope.vars.pop(target.id, None)
                else:
                    raise Unsupported("del")
        else:
            raise Unsupported(kind.__name__)

    def attempt(self, node, scope) -> None:
        try:
            self.block(node.body, scope)
        except CONTROL:
            raise
        except CATCHABLE as error:
            for handler in node.handlers:
                wanted = self.eval(handler.type, scope) if handler.type is not None else Exception
                if isinstance(error, wanted):
                    if handler.name:
                        scope.vars[handler.name] = error
                    self.block(handler.body, scope)
                    break
            else:
                raise
        else:
            self.block(node.orelse, scope)
        finally:
            self.block(node.finalbody, scope)

    def module(self, name: str):
        if name == "random":
            return _Module(name, self.random_module)
        if name not in MODULES:
            raise Unsupported(f"import {name}")
        return _Module(name, MODULES[name])

    def function(self, node, scope) -> Function:
        spec = node.args
        defaults = [self.eval(d, scope) for d in spec.defaults]
        kw_defaults = [self.eval(d, scope) if d is not None else _MISSING for d in spec.kw_defaults]
        return Function(self, node, scope, defaults, kw_defaults)

    def assign(self, target, value, scope) -> None:
        kind = type(target)
        if kind is ast.Name:
            if target.id.startswith("__"):
                raise Unsupported("a double-underscore name")
            scope.vars[target.id] = value
        elif kind in (ast.Tuple, ast.List):
            items = list(self.iterate(value))
            starred = [i for i, e in enumerate(target.elts) if isinstance(e, ast.Starred)]
            if starred:
                at = starred[0]
                after = len(target.elts) - at - 1
                if len(items) < len(target.elts) - 1:
                    raise ValueError("not enough values to unpack")
                for element, item in zip(target.elts[:at], items[:at]):
                    self.assign(element, item, scope)
                self.assign(target.elts[at].value, items[at:len(items) - after], scope)
                for element, item in zip(target.elts[at + 1:], items[len(items) - after:]):
                    self.assign(element, item, scope)
            else:
                if len(items) != len(target.elts):
                    raise ValueError("wrong number of values to unpack")
                for element, item in zip(target.elts, items):
                    self.assign(element, item, scope)
        elif kind is ast.Subscript:
            container = self.eval(target.value, scope)
            if not isinstance(container, (list, dict, collections.defaultdict, collections.Counter, collections.deque)):
                raise Unsupported("item assignment on this type")
            container[self.index(target.slice, scope)] = value
        else:
            raise Unsupported(f"assignment to {kind.__name__}")

    # ---- expressions --------------------------------------------------------------------------
    def iterate(self, value):
        if isinstance(value, (list, tuple, str, bytes, set, frozenset, dict, range, collections.deque)):
            return self.counted(value)
        if hasattr(value, "__next__") or isinstance(value, (collections.Counter, collections.defaultdict)):
            return self.counted(value)
        if isinstance(value, (type({}.keys()), type({}.values()), type({}.items()))):
            return self.counted(value)
        raise TypeError("not iterable")

    def index(self, node, scope):
        if isinstance(node, ast.Slice):
            return slice(self.eval(node.lower, scope) if node.lower is not None else None,
                         self.eval(node.upper, scope) if node.upper is not None else None,
                         self.eval(node.step, scope) if node.step is not None else None)
        if isinstance(node, ast.Tuple):
            return tuple(self.index(e, scope) for e in node.elts)
        return self.eval(node, scope)

    def eval(self, node, scope):
        self.tick()
        kind = type(node)
        if kind is ast.Constant:
            return node.value
        if kind is ast.Name:
            name = node.id
            try:
                return scope.lookup(name)
            except KeyError:
                pass
            if name in NATIVE:
                return NATIVE[name]
            if name.startswith("__"):
                raise Unsupported("a double-underscore name")
            raise NameError(name)
        if kind is ast.BinOp:
            return self.binary(node.op, self.eval(node.left, scope), self.eval(node.right, scope))
        if kind is ast.Compare:
            left = self.eval(node.left, scope)
            for op, right_node in zip(node.ops, node.comparators):
                right = self.eval(right_node, scope)
                if not self.compare(op, left, right):
                    return False
                left = right
            return True
        if kind is ast.BoolOp:
            value = None
            if isinstance(node.op, ast.And):
                for item in node.values:
                    value = self.eval(item, scope)
                    if not value:
                        return value
                return value
            for item in node.values:
                value = self.eval(item, scope)
                if value:
                    return value
            return value
        if kind is ast.UnaryOp:
            operand = self.eval(node.operand, scope)
            op = type(node.op)
            if op is ast.Not:
                return not operand
            if op is ast.USub:
                return -operand
            if op is ast.UAdd:
                return +operand
            return ~operand
        if kind is ast.Call:
            return self.invoke(node, scope)
        if kind is ast.Subscript:
            container = self.eval(node.value, scope)
            if not isinstance(container, (str, bytes, list, tuple, dict, range, collections.deque)):
                raise TypeError("not subscriptable")
            return container[self.index(node.slice, scope)]
        if kind is ast.Attribute:
            return self.attribute(self.eval(node.value, scope), node.attr)
        if kind is ast.List:
            return self.sequence(node.elts, scope)
        if kind is ast.Tuple:
            return tuple(self.sequence(node.elts, scope))
        if kind is ast.Set:
            return set(self.sequence(node.elts, scope))
        if kind is ast.Dict:
            out = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    out.update(self.eval(value, scope))
                else:
                    out[self.eval(key, scope)] = self.eval(value, scope)
            return out
        if kind is ast.IfExp:
            return self.eval(node.body if self.eval(node.test, scope) else node.orelse, scope)
        if kind is ast.ListComp:
            return list(self.comprehension(node.generators, scope, lambda inner: self.eval(node.elt, inner)))
        if kind is ast.SetComp:
            return set(self.comprehension(node.generators, scope, lambda inner: self.eval(node.elt, inner)))
        if kind is ast.DictComp:
            return dict(self.comprehension(node.generators, scope,
                                           lambda inner: (self.eval(node.key, inner), self.eval(node.value, inner))))
        if kind is ast.GeneratorExp:
            return self.comprehension(node.generators, scope, lambda inner: self.eval(node.elt, inner))
        if kind is ast.Lambda:
            return self.function(node, scope)
        if kind is ast.JoinedStr:
            return "".join(self.formatted(v, scope) for v in node.values)
        if kind is ast.NamedExpr:
            value = self.eval(node.value, scope)
            scope.vars[node.target.id] = value
            return value
        if kind is ast.Starred:
            raise Unsupported("a starred expression here")
        if kind is ast.Slice:
            return self.index(node, scope)
        raise Unsupported(kind.__name__)

    def formatted(self, node, scope) -> str:
        if isinstance(node, ast.Constant):
            return str(node.value)
        value = self.eval(node.value, scope)
        if node.conversion == 114:
            value = repr(value)
        elif node.conversion == 115:
            value = str(value)
        spec = "".join(self.formatted(v, scope) for v in node.format_spec.values) if node.format_spec else ""
        if not isinstance(value, (int, float, str, bool, fractions.Fraction, complex)):
            value = str(value)
        return format(value, spec)

    def sequence(self, elements, scope) -> list:
        out = []
        for element in elements:
            if isinstance(element, ast.Starred):
                out.extend(self.iterate(self.eval(element.value, scope)))
            else:
                out.append(self.eval(element, scope))
        return out

    def comprehension(self, generators, scope, produce, at: int = 0, inner=None):
        inner = Scope(scope) if inner is None else inner
        generator = generators[at]
        if generator.is_async:
            raise Unsupported("async comprehension")
        for item in self.iterate(self.eval(generator.iter, inner)):
            self.assign(generator.target, item, inner)
            if all(self.eval(condition, inner) for condition in generator.ifs):
                if at + 1 < len(generators):
                    yield from self.comprehension(generators, scope, produce, at + 1, inner)
                else:
                    yield produce(inner)

    def attribute(self, value, name: str):
        if name.startswith("_"):
            raise Unsupported("an underscore attribute")
        if isinstance(value, _Module):
            if name not in value.names:
                raise Unsupported(f"{value.name}.{name}")
            return value.names[name]
        for type_, allowed in METHODS.items():
            if isinstance(value, type_) and not isinstance(value, bool) or (type_ is int and isinstance(value, bool)):
                if isinstance(value, type_) and name in allowed:
                    return getattr(value, name)
        if value in (str, int, float, dict, list, bytes) and name in ("join", "fromkeys", "from_bytes", "fromhex",
                                                                    "maketrans", "format", "lower", "upper", "isdigit",
                                                                    "isalpha", "strip", "split", "count"):
            return getattr(value, name)
        raise Unsupported(f"attribute {name} of {type(value).__name__}")

    def invoke(self, node, scope):
        function = self.eval(node.func, scope)
        args = self.sequence(node.args, scope)
        kwargs = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                kwargs.update(self.eval(keyword.value, scope))
            else:
                kwargs[keyword.arg] = self.eval(keyword.value, scope)
        if isinstance(function, Function):
            return function(*args, **kwargs)
        return self.native(function, args, kwargs)

    def native(self, function, args, kwargs):
        owner = getattr(function, "__self__", None)
        allowed = False
        try:
            allowed = function in ALLOWED_CALLABLES
        except TypeError:
            allowed = False
        if not allowed and owner is not None and not isinstance(owner, type(math)):
            allowed = isinstance(owner, ALLOWED_TYPES) or owner in (str, int, float, dict, list, bytes)
        if not allowed and isinstance(function, type) and function in (collections.Counter, collections.defaultdict,
                                                                       collections.deque, fractions.Fraction,
                                                                       random.Random, collections.OrderedDict):
            allowed = True
        if not allowed and isinstance(function, (functools.partial, re.Pattern)):
            allowed = True
        if not allowed and type(function).__name__ in ("itemgetter", "_lru_cache_wrapper", "method_descriptor",
                                                       "builtin_function_or_method"):
            allowed = type(function).__name__ != "builtin_function_or_method" or owner is not None
        if not allowed:
            raise Unsupported(f"a call of {getattr(function, '__name__', type(function).__name__)}")
        if function in AGGREGATES or (owner is not None and getattr(function, "__name__", "") in ("join", "extend",
                                                                                               "update", "fromkeys")):
            for value in args:
                if isinstance(value, range) and len(value) > MAX_SEQUENCE:
                    raise Refused("a range too long for a native call")
        if function is pow and len(args) == 2:
            return self.binary(ast.Pow(), args[0], args[1])
        if function in (math.factorial, math.perm, math.comb) and args and isinstance(args[0], int) and args[0] > 20_000:
            raise Refused("factorial too large")
        if function is isinstance and len(args) == 2:
            wanted = args[1] if isinstance(args[1], tuple) else (args[1],)
            if not all(isinstance(w, type) for w in wanted):
                raise TypeError("isinstance needs types")
        self.tick()
        result = function(*args, **kwargs)
        if function in LAZY or type(result).__name__ in ("generator", "callable_iterator"):
            return self.counted(result)
        return result

    def binary(self, op, left, right):
        kind = type(op)
        if kind is ast.Add:
            if isinstance(left, (str, list, tuple, bytes)) and isinstance(right, (str, list, tuple, bytes)) \
                    and len(left) + len(right) > MAX_SEQUENCE:
                raise Refused("concatenation too long")
            return left + right
        if kind is ast.Sub:
            return left - right
        if kind is ast.Mult:
            for a, b in ((left, right), (right, left)):
                if isinstance(a, (str, list, tuple, bytes)) and isinstance(b, int) and len(a) * max(b, 0) > MAX_SEQUENCE:
                    raise Refused("repetition too long")
            if isinstance(left, int) and isinstance(right, int) and left.bit_length() + right.bit_length() > 4 * MAX_BITS:
                raise Refused("product too large")
            return left * right
        if kind is ast.Div:
            return left / right
        if kind is ast.FloorDiv:
            return left // right
        if kind is ast.Mod:
            if isinstance(left, (str, bytes)):
                if isinstance(right, (int, float, str, tuple)):
                    return left % right
                raise Unsupported("string formatting of this value")
            return left % right
        if kind is ast.Pow:
            if isinstance(left, int) and isinstance(right, int) and not isinstance(left, bool):
                if right > 0 and left.bit_length() * right > MAX_BITS:
                    raise Refused("power too large")
            if isinstance(left, float) or isinstance(right, float):
                try:
                    return left ** right
                except OverflowError:
                    return math.inf
            return left ** right
        if kind is ast.LShift:
            if isinstance(right, int) and right > MAX_BITS:
                raise Refused("shift too large")
            return left << right
        if kind is ast.RShift:
            return left >> right
        if kind is ast.BitAnd:
            return left & right
        if kind is ast.BitOr:
            return left | right
        if kind is ast.BitXor:
            return left ^ right
        if kind is ast.MatMult:
            raise Unsupported("matrix multiplication")
        raise Unsupported(kind.__name__)

    def compare(self, op, left, right) -> bool:
        kind = type(op)
        if kind is ast.Eq:
            return left == right
        if kind is ast.NotEq:
            return left != right
        if kind is ast.Lt:
            return left < right
        if kind is ast.LtE:
            return left <= right
        if kind is ast.Gt:
            return left > right
        if kind is ast.GtE:
            return left >= right
        if kind is ast.In:
            if isinstance(right, range) or not hasattr(right, "__next__"):
                return left in right
            return any(left == item for item in right)
        if kind is ast.NotIn:
            return left not in right
        if kind is ast.Is:
            return left is right
        return left is not right


class _Module:
    def __init__(self, name, names):
        self.name, self.names = name, names


_MISSING = object()


def _as_load(target):
    """The target of an augmented assignment, as an expression that reads it."""
    if isinstance(target, ast.Name):
        return ast.Name(id=target.id, ctx=ast.Load())
    if isinstance(target, ast.Subscript):
        return ast.Subscript(value=target.value, slice=target.slice, ctx=ast.Load())
    raise Unsupported("this augmented assignment")


TRUE, FALSE, ERROR, FUEL_OUT, REFUSED, UNSUPPORTED = "true", "false", "error", "fuel", "refused", "unsupported"


class Verifier:
    """One instance's verifier under the interpreter. ``verdict`` is a string; only ``true``
    is a solve. ``steps`` is the total number of steps spent in calls so far."""

    def __init__(self, source: str, fuel: int = FUEL):
        self.source, self.fuel = source, fuel
        self.tree = ast.parse(source)
        self.calls = 0
        self.steps = 0
        self.unsupported = None

    def verdict(self, answer) -> str:
        self.calls += 1
        interpreter = Interpreter(self.fuel)
        try:
            interpreter.block(self.tree.body, interpreter.globals)
            function = interpreter.globals.vars["sat"]
            value = function(answer)
            return TRUE if value is True else FALSE
        except Fuel:
            return FUEL_OUT
        except Refused:
            return REFUSED
        except Unsupported as reason:
            self.unsupported = str(reason)
            return UNSUPPORTED
        except RecursionError:
            return REFUSED
        except MemoryError:
            return REFUSED
        except Exception:
            return ERROR
        finally:
            self.steps += self.fuel - max(interpreter.fuel, 0)

    def __call__(self, answer) -> bool:
        return self.verdict(answer) == TRUE
