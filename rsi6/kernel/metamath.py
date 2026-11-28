"""The proof form: a Metamath database read as data, and the checking rule that decides a proof.

This is the third form of ``RESEARCH_PLAN.md`` (section 2, C1): an answer is a sequence of steps,
and it is accepted only if the proof-checking machine of the Metamath language accepts it. The
machine is the reference. Nothing here searches for a proof; it reads statements and checks.

**Reading.** ``Database.read`` takes the source text of a database (``set.mm``), removes comments,
and keeps every statement up to a label at which it is told to stop: constants (``$c``), variables
(``$v``), floating hypotheses (``$f``: a variable has a type), essential hypotheses (``$e``),
disjoint-variable conditions (``$d``), axioms (``$a``) and theorems (``$p``) with their proofs, in
nested scopes (``${ $}``). Every assertion gets its *frame*: the hypotheses it needs (the floating
hypotheses of the variables that occur in it or in its essential hypotheses, and its essential
hypotheses, in the order they appear) and the disjoint-variable conditions among those variables.

**Checking.** ``Database.verify(label, proof)`` runs a proof (normal or compressed) on the stack
machine of the language: a hypothesis pushes its statement; an assertion pops its hypotheses,
reads the substitution off its floating hypotheses, requires every essential hypothesis to match
under it, requires its disjoint-variable conditions to hold, and pushes its conclusion under the
substitution. The proof is accepted when one statement is left and it is the theorem's.

**Trees.** For a search, a statement is also given as a tree: ``Database.parse`` reads an expression
of a type (``wff``) by the syntax axioms of that type, and ``Database.syntax_proof`` writes the steps
that prove the tree is of its type, which a proof needs for every substitution it makes.
"""
from __future__ import annotations

import re


class MetamathError(Exception):
    """The database or a proof does not follow the language."""


class Rejected(Exception):
    """The checking machine does not accept a proof."""


_COMMENT = re.compile(r"\$\(.*?\$\)", re.S)


def tokens(text: str):
    """The tokens of a database source, comments removed."""
    return _COMMENT.sub(" ", text).split()


class Assertion:
    __slots__ = ("label", "kind", "typecode", "stmt", "hyps", "floats", "essentials", "dvs", "proof", "index",
                 "active_floats", "active_dvs")

    def __init__(self, label, kind, typecode, stmt, hyps, floats, essentials, dvs, proof, index, active_floats,
                 active_dvs):
        self.label, self.kind, self.typecode, self.stmt = label, kind, typecode, stmt
        self.hyps = hyps                      # labels of the mandatory hypotheses, in database order
        self.floats = floats                  # (label, typecode, variable) of the mandatory floating hypotheses
        self.essentials = essentials          # (label, typecode, tokens) of the essential hypotheses
        self.dvs = dvs                        # mandatory disjoint-variable pairs (frozensets)
        self.proof = proof                    # the database's own proof tokens (``$p`` only)
        self.index = index                    # position in the database
        self.active_floats = active_floats    # every floating hypothesis in scope: variable -> label
        self.active_dvs = active_dvs          # every disjoint-variable pair in scope


class Database:
    def __init__(self):
        self.constants, self.variables = set(), set()
        self.hyp = {}                         # label -> (kind 'f'/'e', typecode, tokens)
        self.assertions = {}                  # label -> Assertion
        self.order = []                       # assertion labels in database order
        self.syntax = {}                      # typecode -> syntax axioms of that type (labels)

    # ---- reading ------------------------------------------------------------------------------
    @classmethod
    def read(cls, text: str, stop: str | None = None) -> "Database":
        """Read ``text`` up to (not including) the statement labelled ``stop``."""
        db = cls()
        toks = tokens(text)
        # a scope: floating hyps (var -> label), essential hyps (labels), dv pairs, declared vars
        scopes = [{"floats": {}, "ess": [], "dvs": set(), "vars": set()}]
        order_of = {}                          # hypothesis label -> position, for frame order
        position = 0
        i, n = 0, len(toks)
        label = None

        def active_floats():
            out = {}
            for sc in scopes:
                out.update(sc["floats"])
            return out

        def active_ess():
            return [lab for sc in scopes for lab in sc["ess"]]

        def active_dvs():
            out = set()
            for sc in scopes:
                out |= sc["dvs"]
            return out

        def statement(end="$."):
            nonlocal i
            out = []
            while toks[i] != end:
                out.append(toks[i])
                i += 1
            i += 1
            return out

        while i < n:
            t = toks[i]
            i += 1
            if t == "${":
                scopes.append({"floats": {}, "ess": [], "dvs": set(), "vars": set()})
            elif t == "$}":
                scopes.pop()
            elif t == "$c":
                db.constants.update(statement())
            elif t == "$v":
                vs = statement()
                db.variables.update(vs)
                scopes[-1]["vars"].update(vs)
            elif t == "$d":
                vs = statement()
                for a in range(len(vs)):
                    for b in range(a + 1, len(vs)):
                        scopes[-1]["dvs"].add(frozenset((vs[a], vs[b])))
            elif t.startswith("$"):
                raise MetamathError(f"unexpected keyword {t}")
            else:
                label = t
                if stop is not None and label == stop:
                    break
                kw = toks[i]
                i += 1
                if kw == "$f":
                    tc, var = statement()
                    db.hyp[label] = ("f", tc, (tc, var))
                    scopes[-1]["floats"][var] = label
                    order_of[label] = position
                    position += 1
                elif kw == "$e":
                    st = tuple(statement())
                    db.hyp[label] = ("e", st[0], st)
                    scopes[-1]["ess"].append(label)
                    order_of[label] = position
                    position += 1
                elif kw in ("$a", "$p"):
                    if kw == "$a":
                        st, proof = tuple(statement()), None
                    else:
                        st = tuple(statement("$="))
                        proof = statement()
                    fl = active_floats()
                    ess = active_ess()
                    mand = {tok for tok in st[1:] if tok in db.variables}
                    for e in ess:
                        mand |= {tok for tok in db.hyp[e][2][1:] if tok in db.variables}
                    for v in mand:
                        if v not in fl:
                            raise MetamathError(f"{label}: variable {v} has no type in scope")
                    hyps = sorted([fl[v] for v in mand] + ess, key=lambda h: order_of[h])
                    floats = tuple((h, db.hyp[h][1], db.hyp[h][2][1]) for h in hyps if db.hyp[h][0] == "f")
                    essentials = tuple((h, db.hyp[h][1], db.hyp[h][2]) for h in hyps if db.hyp[h][0] == "e")
                    adv = active_dvs()
                    dvs = frozenset(p for p in adv if p <= mand)
                    a = Assertion(label, kw[1], st[0], st, tuple(hyps), floats, essentials, dvs,
                                  None if proof is None else tuple(proof), len(db.order), fl, frozenset(adv))
                    db.assertions[label] = a
                    db.order.append(label)
                    if kw == "$a" and st[0] != "|-":
                        db.syntax.setdefault(st[0], []).append(label)
                else:
                    raise MetamathError(f"{label}: unknown keyword {kw}")
        return db

    # ---- checking -----------------------------------------------------------------------------
    def _decode(self, a: Assertion, proof):
        """The steps of a proof: labels for a normal proof; for a compressed one, ints and the save mark."""
        proof = list(proof)
        if not proof or proof[0] != "(":
            return proof, None
        k = proof.index(")")
        labels = list(a.hyps) + proof[1:k]
        letters = "".join(proof[k + 1:])
        steps, num = [], 0
        for c in letters:
            if "A" <= c <= "T":
                steps.append(num * 20 + (ord(c) - ord("A") + 1))
                num = 0
            elif "U" <= c <= "Y":
                num = num * 5 + (ord(c) - ord("U") + 1)
            elif c == "Z":
                steps.append("Z")
            else:
                raise Rejected(f"{a.label}: bad character {c!r} in a compressed proof")
        return steps, labels

    def _apply(self, theorem: Assertion, step: str, stack: list) -> tuple:
        if step in self.hyp:
            kind, tc, st = self.hyp[step]
            if kind == "f" and theorem.active_floats.get(st[1]) != step:
                raise Rejected(f"{theorem.label}: floating hypothesis {step} is not in scope")
            if kind == "e" and step not in {h for h, _, _ in theorem.essentials}:
                raise Rejected(f"{theorem.label}: essential hypothesis {step} is not the theorem's")
            return st
        b = self.assertions.get(step)
        if b is None or b.index >= theorem.index:
            raise Rejected(f"{theorem.label}: {step} is not an earlier assertion")
        need = len(b.hyps)
        if len(stack) < need:
            raise Rejected(f"{theorem.label}: stack underflow at {step}")
        args = stack[len(stack) - need:]
        del stack[len(stack) - need:]
        sub = {}
        j = 0
        for h in b.hyps:
            kind, tc, st = self.hyp[h]
            got = args[j]
            j += 1
            if kind == "f":
                if got[0] != tc:
                    raise Rejected(f"{theorem.label}: {step} wants a {tc} for {st[1]}, got {got[0]}")
                sub[st[1]] = got[1:]
        j = 0
        for h in b.hyps:
            kind, tc, st = self.hyp[h]
            got = args[j]
            j += 1
            if kind == "e" and self.substitute(st, sub) != got:
                raise Rejected(f"{theorem.label}: {step}: hypothesis {h} does not match")
        for pair in b.dvs:
            x, y = tuple(pair)
            vx = {t for t in sub.get(x, ()) if t in self.variables}
            vy = {t for t in sub.get(y, ()) if t in self.variables}
            for p in vx:
                for q in vy:
                    if p == q or frozenset((p, q)) not in theorem.active_dvs:
                        raise Rejected(f"{theorem.label}: {step}: disjoint variables {p}, {q} not allowed")
        return self.substitute(b.stmt, sub)

    def substitute(self, st, sub) -> tuple:
        out = [st[0]]
        for t in st[1:]:
            out.extend(sub[t] if t in sub else (t,))
        return tuple(out)

    def verify(self, label: str, proof=None) -> bool:
        """Accept ``proof`` (tokens; the database's own when ``None``) of the theorem ``label``, or raise
        ``Rejected``."""
        a = self.assertions[label]
        if proof is None:
            proof = a.proof
        if proof is None:
            raise Rejected(f"{label} is an axiom")
        if "?" in proof:
            raise Rejected(f"{label}: the proof is incomplete")
        steps, labels = self._decode(a, proof)
        stack, saved = [], []
        if labels is None:
            for s in steps:
                stack.append(self._apply(a, s, stack))
        else:
            nl = len(labels)
            for s in steps:
                if s == "Z":
                    if not stack:
                        raise Rejected(f"{label}: nothing to save")
                    saved.append(stack[-1])
                elif s <= nl:
                    stack.append(self._apply(a, labels[s - 1], stack))
                elif s - nl - 1 < len(saved):
                    stack.append(saved[s - nl - 1])
                else:
                    raise Rejected(f"{label}: step {s} refers to nothing")
        if len(stack) != 1 or stack[0] != a.stmt:
            raise Rejected(f"{label}: the proof does not end on the theorem")
        return True

    # ---- trees, for a search ------------------------------------------------------------------
    def _patterns(self, typecode: str):
        key = ("_pat", typecode)
        if key not in self.__dict__:
            pats = []
            for lab in self.syntax.get(typecode, []):
                a = self.assertions[lab]
                var_type = {v: tc for _, tc, v in a.floats}
                pats.append((lab, a.stmt[1:], var_type, tuple(v for _, _, v in a.floats)))
            self.__dict__[key] = pats
        return self.__dict__[key]

    def parse(self, typecode: str, expr) -> object:
        """The tree of an expression of a type: a variable is its name; a syntax axiom ``lab`` with arguments
        is ``(lab, arg1, ...)`` in the order of its floating hypotheses. ``MetamathError`` if it is not one."""
        expr = tuple(expr)
        memo = {}

        def at(tc, i):
            key = (tc, i)
            if key in memo:
                return memo[key]
            memo[key] = []                     # a pattern that starts with its own type reads nothing here
            out = []
            if i < len(expr) and expr[i] in self.variables:
                out.append((expr[i], i + 1))
            for lab, pat, var_type, order in self._patterns(tc):
                if not pat:
                    continue
                if pat[0] not in self.variables and (i >= len(expr) or expr[i] != pat[0]):
                    continue
                partial = [(i, {})]
                for sym in pat:
                    nxt = []
                    for pos, binds in partial:
                        if sym in var_type:
                            for tree, j in at(var_type[sym], pos):
                                b = dict(binds)
                                b[sym] = tree
                                nxt.append((j, b))
                        elif pos < len(expr) and expr[pos] == sym:
                            nxt.append((pos + 1, binds))
                    partial = nxt
                    if not partial:
                        break
                for pos, binds in partial:
                    out.append(((lab,) + tuple(binds[v] for v in order), pos))
            memo[key] = out
            return out

        whole = [t for t, j in at(typecode, 0) if j == len(expr)]
        if len(whole) != 1:
            raise MetamathError(f"{' '.join(expr)}: {len(whole)} parses as {typecode}")
        return whole[0]

    def unparse(self, tree) -> tuple:
        """The expression (tokens) of a tree."""
        if isinstance(tree, str):
            return (tree,)
        lab = tree[0]
        a = self.assertions[lab]
        args = {v: tree[1 + k] for k, (_, _, v) in enumerate(a.floats)}
        out = []
        for sym in a.stmt[1:]:
            out.extend(self.unparse(args[sym]) if sym in args else (sym,))
        return tuple(out)

    def syntax_proof(self, tree, floats_in_scope: dict) -> list:
        """Steps that prove ``tree`` is of its type, with the floating hypotheses in scope for variables."""
        if isinstance(tree, str):
            return [floats_in_scope[tree]]
        out = []
        for sub in tree[1:]:
            out.extend(self.syntax_proof(sub, floats_in_scope))
        out.append(tree[0])
        return out
