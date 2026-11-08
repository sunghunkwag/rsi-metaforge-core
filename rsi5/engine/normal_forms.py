"""The syntactic normal-form filter: terms with a known shorter equivalent are never built.

Every rule here is a rewrite ``left -> right`` whose left-hand side the engine refuses
to construct (``NORMAL_FORMS.md`` lists them with their justification). A refused term
is never evaluated and never counted against the candidate budget. The rules are
syntactic: ``same(a, b)`` is object identity in the pool, which observational
equivalence makes the same as "a and b have one behaviour on the evaluation points".
"""
from __future__ import annotations

COMMUTATIVE = ("add", "mul", "eq", "and", "or")


def _lit(e, value=None):
    return e.kind == "const" and (value is None or e.head == value)


def _is(e, name):
    return e.kind == "prim" and e.head == name


def _lam_body(e, binders=1):
    """The body of a lambda with exactly ``binders`` binders, or None."""
    return e.args[0] if e.kind == "lam" and len(e.head) == binders else None


def normal(name: str, args) -> bool:
    """True when ``name`` applied to ``args`` (pool programs) is in normal form."""
    k = len(args)
    if name in COMMUTATIVE:
        if args[0].ident > args[1].ident:            # commutative arguments in canonical order
            return False
    if name == "if":
        c, t, e = args
        if _lit(c) or _is(c, "not") or t is e:
            return False
        if _is(t, "if") and t.args[0] is c:
            return False
        if _is(e, "if") and e.args[0] is c:
            return False
        return True
    if name == "not":
        return not (_is(args[0], "not") or _lit(args[0]))
    if name == "neg":
        return not (_is(args[0], "neg") or _lit(args[0]))
    if name == "abs":
        return not (_is(args[0], "abs") or _is(args[0], "neg") or _lit(args[0]))
    if name == "add":
        return not (_lit(args[0], 0) or _lit(args[1], 0))
    if name == "sub":
        return not (_lit(args[1], 0) or args[0] is args[1])
    if name == "mul":
        return not (_lit(args[0], 0) or _lit(args[1], 0) or _lit(args[0], 1) or _lit(args[1], 1))
    if name == "div":
        return not (_lit(args[1], 1) or _lit(args[1], 0) or args[0] is args[1])
    if name == "mod":
        return not (_lit(args[1], 1) or _lit(args[1], 0) or args[0] is args[1])
    if name in ("eq", "lt", "le", "gt", "ge"):
        return args[0] is not args[1]
    if name in ("and", "or"):
        return not (args[0] is args[1] or _lit(args[0]) or _lit(args[1]))
    if name == "cons":
        h, t = args
        return not (_is(h, "head") and _is(t, "tail") and h.args[0] is t.args[0])
    if name in ("head", "tail", "is_empty", "length"):
        x = args[0]
        return not (_is(x, "cons") or _is(x, "nil") or (name in ("head", "tail") and _is(x, "range")
                                                           and False))
    if name in ("map", "filter"):
        f, xs = args
        if _is(xs, "nil"):
            return False
        body = _lam_body(f)
        if name == "filter" and body is not None and _lit(body):
            return False
        return True
    if name == "fold":
        f, z, xs = args
        if _is(xs, "nil"):
            return False
        body = _lam_body(f, 2)
        if body is not None and body.kind == "var" and body.head == 1:   # λacc.λe. acc
            return False
        return True
    if name == "zip":
        return not (_is(args[0], "nil") or _is(args[1], "nil"))
    if name == "index":
        return not _is(args[1], "nil")
    if name == "unfold":
        stop = _lam_body(args[0])
        return not (stop is not None and _lit(stop))
    if name == "fix1":
        body = _lam_body(args[1], 2)
        if body is not None and 1 not in body.uses:        # the body never recurses
            return False
        return True
    if name in ("fst", "snd"):
        return not _is(args[0], "pair")
    if name == "pair":
        a, b = args
        return not (_is(a, "fst") and _is(b, "snd") and a.args[0] is b.args[0])
    return True
