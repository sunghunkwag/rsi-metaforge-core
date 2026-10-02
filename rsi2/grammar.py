"""Contextual typed production probabilities for the frozen RSI-2 DSL.

A production is a primitive, a library reference, a bound variable, a literal,
or a lambda. Applications use a curried head and a fixed number of arguments.
The distribution at each hole is normalized over *type-compatible* productions;
its context is the parent production name and the argument position. Library
entries and primitive heads go through the same selection and application path.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import count
import math
from typing import Mapping

from .terms import Term
from .types import (
    Arrow, BOOL, INT, PRIMITIVE_TYPES, TVar, Type, TypeInferenceError,
    function_parts, infer, instantiate, library_entries, substitute, unify,
)


ROOT_CONTEXT = ("ROOT", 0)
_fresh = count()


@dataclass(frozen=True)
class Production:
    """One typed choice, including constraints shared with sibling holes."""

    name: str
    head: Term | None
    arguments: tuple[Type, ...]
    substitutions: dict[str, Type]
    log_probability: float = 0.0
    parameter: Type | None = None

    @property
    def arity(self):
        return len(self.arguments)

    @property
    def is_lambda(self):
        return self.head is None


def _constant_name(term):
    if term.tag == "int":
        return f"int:{term.value}"
    if term.tag == "bool":
        return f"bool:{str(term.value).lower()}"
    raise ValueError("grammar constants must be integer or boolean literals")


def _spine(term):
    arguments = []
    while term.tag == "app":
        arguments.append(term.children[1])
        term = term.children[0]
    return term, tuple(reversed(arguments))


class Grammar:
    """A type-directed PCFG with optional parent/argument weight tables.

    ``weights`` maps production names (``add``, ``lambda``, ``var:0``,
    ``int:0``) to positive weights. ``context_weights[(parent, argument)]``
    overrides weights in that context. A ``name/arity`` key can distinguish
    partial from full applications. Unspecified weights are one. The ordinary
    ``var`` key supplies a default for every bound variable.

    The primitive table and constants can be restricted for small exhaustive
    checks. Such restrictions select a language fragment; no task-specific
    templates or solve-time grammar changes are used by this module.
    """

    def __init__(self, library=None, *, primitives=None, constants=None,
                 weights=None, context_weights=None):
        self.library = library if library is not None else {}
        self.primitives = dict(PRIMITIVE_TYPES if primitives is None else primitives)
        self.constants = tuple(constants) if constants is not None else (
            Term("int", -1), Term("int", 0), Term("int", 1), Term("int", 2),
            Term("bool", False), Term("bool", True),
        )
        if len(set(self.constants)) != len(self.constants):
            raise ValueError("duplicate grammar constants")
        for term in self.constants:
            _constant_name(term)
            infer(term)
        if not all(isinstance(t, Type) for t in self.primitives.values()):
            raise TypeError("primitive signatures must be Type values")
        for name, signature in self.primitives.items():
            if name not in PRIMITIVE_TYPES:
                raise ValueError(f"unknown frozen DSL primitive {name!r}; use a library entry")
            unify(instantiate(PRIMITIVE_TYPES[name], "_grammar_check_"), signature)
        self.weights = dict(weights or {})
        self.context_weights = {tuple(k): dict(v) for k, v in (context_weights or {}).items()}
        for table in (self.weights, *self.context_weights.values()):
            if any(not math.isfinite(float(w)) or float(w) <= 0 for w in table.values()):
                raise ValueError("grammar weights must be positive and finite")
        self._library_types = {}
        for name in library_entries(self.library):
            if name in self.primitives:
                raise ValueError(f"library name shadows primitive {name!r}")
            self._library_types[name] = infer(Term("ref", name), library=self.library)

    def _weight(self, production, context):
        keys = (f"{production.name}/{production.arity}", production.name)
        if production.name.startswith("var:"):
            keys += ("var",)
        contextual = self.context_weights.get(tuple(context), {})
        for table in (contextual, self.weights):
            for key in keys:
                if key in table:
                    return float(table[key])
        return 1.0

    def productions(self, request_type, env=(), substitutions=None,
                    context=ROOT_CONTEXT):
        """Return all compatible choices; constraints are copied, never mutated."""
        substitutions = dict(substitutions or {})
        target = substitute(request_type, substitutions)
        choices = []
        serial = next(_fresh)

        if target.tag in ("arrow", "var"):
            argument, result = (target.args if target.tag == "arrow" else
                                (TVar(f"_grammar_{serial}_arg"),
                                 TVar(f"_grammar_{serial}_result")))
            try:
                updated = unify(target, Arrow(argument, result), substitutions)
                choices.append(Production("lambda", None, (result,), updated,
                                          parameter=argument))
            except TypeInferenceError:
                pass

        heads = [(name, Term("prim", name), instantiate(signature, "_grammar_p_"))
                 for name, signature in self.primitives.items()]
        heads.extend((name, Term("ref", name), instantiate(signature, "_grammar_l_"))
                     for name, signature in self._library_types.items())
        heads.extend((f"var:{i}", Term("var", i), substitute(t, substitutions))
                     for i, t in enumerate(env))
        heads.extend((_constant_name(t), t, INT if t.tag == "int" else BOOL)
                     for t in self.constants)

        for name, head, signature in heads:
            arguments, _ = function_parts(signature)
            residual = signature
            for arity in range(len(arguments) + 1):
                try:
                    updated = unify(residual, target, substitutions)
                except TypeInferenceError:
                    pass
                else:
                    choices.append(Production(name, head, arguments[:arity], updated))
                if residual.tag == "arrow":
                    residual = residual.args[1]

        if not choices:
            return ()
        weighted = [(choice, math.log(self._weight(choice, context))) for choice in choices]
        maximum = max(weight for _, weight in weighted)
        normalizer = maximum + math.log(math.fsum(math.exp(w - maximum)
                                                   for _, w in weighted))
        return tuple(Production(c.name, c.head, c.arguments, c.substitutions,
                                weight - normalizer, c.parameter)
                     for c, weight in weighted)

    def log_probability(self, term, request_type=None, env=()):
        """Replay a derivation, including its evolving polymorphic constraints.

        Pass the original request type when it is more specific than the
        program's principal type (for example ``nil : list[int]``). Omitting
        it scores the program under its inferred principal type.
        """
        actual_type = infer(term, env=env, library=self.library)
        request_type = actual_type if request_type is None else request_type
        unify(actual_type, request_type)

        def visit(node, target, bindings, constraints, context):
            head, arguments = _spine(node)
            if head.tag == "lam":
                if arguments:
                    raise ValueError("grammar scores beta-normal programs only")
                name = "lambda"
            elif head.tag in ("prim", "ref"):
                name = str(head.value)
            elif head.tag == "var":
                name = f"var:{head.value}"
            elif head.tag in ("int", "bool"):
                name = _constant_name(head)
            else:
                raise ValueError(f"unsupported grammar head {head.tag!r}")
            arity = 1 if name == "lambda" else len(arguments)
            available = self.productions(target, bindings, constraints, context)
            selected = next((p for p in available
                             if p.name == name and p.arity == arity), None)
            if selected is None:
                raise ValueError(f"term uses an unavailable production {name}/{arity}")
            score, updated = selected.log_probability, selected.substitutions
            if selected.is_lambda:
                subtotal, updated = visit(head.children[0], selected.arguments[0],
                                          (selected.parameter,) + tuple(bindings),
                                          updated, (name, 0))
                return score + subtotal, updated
            for index, (child, child_type) in enumerate(zip(arguments, selected.arguments)):
                subtotal, updated = visit(child, child_type, bindings, updated, (name, index))
                score += subtotal
            return score, updated

        return visit(term, request_type, tuple(env), {}, ROOT_CONTEXT)[0]

    def fit(self, solutions):
        """Stage 3 learning hook; Stage 1 deliberately contains no updates."""
        raise NotImplementedError("grammar fitting is introduced after the Stage 1 freeze")
