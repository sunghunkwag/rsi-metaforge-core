"""Parse the readable form ``terms.pretty`` prints back into a ``Term``.

The result files keep programs in this form (``(lambda x0: list[int]. ((map (lambda x1:
int. ((sub x1) 2))) x0))``); the audit re-executes them from it. Variable names ``xN``
are the binder depth at which they were introduced; they become de Bruijn indices.
"""
from __future__ import annotations

import re

from .terms import App, Bool, Int, Lam, Prim, Term, Var
from .types import Arrow, BOOL, INT, ListOf, PairOf, TVar, Type

_TOKEN = re.compile(r"\s*(\(|\)|\[|\]|,|->|:|\.|-?\d+|[A-Za-z_][A-Za-z0-9_]*)")


class ParseError(ValueError):
    pass


def _tokens(text: str) -> list[str]:
    out, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            if text[pos:].strip() == "":
                break
            raise ParseError(f"cannot tokenise at {text[pos:pos + 20]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, text: str):
        self.tokens = _tokens(text)
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, expected=None):
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise ParseError(f"expected {expected!r}, got {tok!r} at {self.i}")
        self.i += 1
        return tok

    # ---- types: T ::= A ('->' T)? ; A ::= int | bool | list '[' T ']' | '(' T ',' T ')' | '(' T ')' | name
    def type_(self) -> Type:
        left = self.atom_type()
        if self.peek() == "->":
            self.take("->")
            return Arrow(left, self.type_())
        return left

    def atom_type(self) -> Type:
        tok = self.take()
        if tok == "int":
            return INT
        if tok == "bool":
            return BOOL
        if tok == "list":
            self.take("[")
            inner = self.type_()
            self.take("]")
            return ListOf(inner)
        if tok == "(":
            first = self.type_()
            if self.peek() == ",":
                self.take(",")
                second = self.type_()
                self.take(")")
                return PairOf(first, second)
            self.take(")")
            return first
        return TVar(tok)

    # ---- terms
    def term(self, names: tuple) -> Term:
        tok = self.peek()
        if tok == "(":
            self.take("(")
            if self.peek() == "lambda":
                self.take("lambda")
                name = self.take()
                self.take(":")
                type_ = self.type_()
                self.take(".")
                body = self.term((name,) + names)
                self.take(")")
                return Lam(type_, body)
            function = self.term(names)
            argument = self.term(names)
            self.take(")")
            return App(function, argument)
        self.take()
        if tok == "true":
            return Bool(True)
        if tok == "false":
            return Bool(False)
        if re.fullmatch(r"-?\d+", tok):
            return Int(int(tok))
        if tok in names:
            return Var(names.index(tok))
        if tok.startswith("$"):
            return Var(int(tok[1:]))
        return Prim(tok)


def parse(text: str) -> Term:
    parser = _Parser(text)
    term = parser.term(())
    if parser.peek() is not None:
        raise ParseError(f"trailing tokens at {parser.i}")
    return term
