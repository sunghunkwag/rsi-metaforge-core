"""A goal-directed proof search for the proof form (development; 2026-11-28).

The search the proof form starts from, before anything is learned. It knows the language and
nothing of mathematics: what it may use is a *library* of assertions it is handed (statements
only, never their proofs), and the hypotheses of the theorem it is asked to prove.

**How it searches.** Backward chaining with unification, as in logic programming. A goal is a
tree (``rsi6/kernel/metamath.py``). It is closed by one of the theorem's own hypotheses that is
the same tree, or by an assertion of the library whose conclusion unifies with it; the
assertion's hypotheses, under the unifier, become new goals. The variables of an assertion are
renamed apart at every use, so a variable that occurs only in an assertion's hypotheses (the
``ph`` of modus ponens) stays open until another goal fixes it. The goal worked on next is the
one with the most fixed structure; a goal that is nothing but an open variable is closed last,
by anything provable, because whatever closes it is accepted. Depth is deepened one step at a
time until the budget ends.

**What it returns.** A proof in the normal format of the language, every step a label, with
the steps that prove each substituted expression is a ``wff``. The kernel's checker decides
whether it is a proof; the search is not trusted.

**Units.** One unit for every attempt to unify a goal with a candidate (a hypothesis or an
assertion of the library). The budget is a ``Meter`` of the kernel.
"""
from __future__ import annotations

from rsi6.kernel.problem import BudgetExhausted, Meter


class Entry:
    """An assertion of the library as trees."""
    __slots__ = ("label", "concl", "hyps", "vars", "seq", "head", "index")

    def __init__(self, db, label):
        a = db.assertions[label]
        if a.typecode != "|-" or any(tc != "wff" for _, tc, _ in a.floats):
            raise ValueError(f"{label}: not an assertion about wffs")
        self.label, self.index = label, a.index
        self.concl = db.parse("wff", a.stmt[1:])
        self.hyps = tuple(db.parse("wff", st[1:]) for _, _, st in a.essentials)
        self.vars = tuple(v for _, _, v in a.floats)
        seq, k = [], 0
        for h in a.hyps:
            kind, _, st = db.hyp[h]
            if kind == "f":
                seq.append(("f", st[1]))
            else:
                seq.append(("e", k))
                k += 1
        self.seq = tuple(seq)
        self.head = self.concl[0] if isinstance(self.concl, tuple) else None


class Library:
    """Entries by the head of their conclusion; those whose conclusion is a bare variable apply to any goal."""

    def __init__(self):
        self.by_head, self.anyhead, self.closed, self.entries = {}, [], [], {}

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, e: Entry) -> None:
        if e.label in self.entries:
            return
        self.entries[e.label] = e
        lst = self.by_head.setdefault(e.head, []) if e.head is not None else self.anyhead
        lst.append(e)
        lst.sort(key=lambda x: (len(x.hyps), -x.index))
        if not e.hyps:
            self.closed.append(e)
            self.closed.sort(key=lambda x: x.index)

    def candidates(self, head):
        return self.by_head.get(head, []) + self.anyhead


def _walk(t, S):
    while isinstance(t, int) and t in S:
        t = S[t]
    return t


def _occurs(v, t, S) -> bool:
    stack = [t]
    while stack:
        x = _walk(stack.pop(), S)
        if x == v and isinstance(x, int):
            return True
        if isinstance(x, tuple):
            stack.extend(x[1:])
    return False


def _unify(a, b, S, trail) -> bool:
    stack = [(a, b)]
    while stack:
        x, y = stack.pop()
        x, y = _walk(x, S), _walk(y, S)
        if x is y:
            continue
        xi, yi = isinstance(x, int), isinstance(y, int)
        if xi and yi and x == y:
            continue
        if xi:
            if _occurs(x, y, S):
                return False
            S[x] = y
            trail.append(x)
            continue
        if yi:
            if _occurs(y, x, S):
                return False
            S[y] = x
            trail.append(y)
            continue
        if isinstance(x, str) or isinstance(y, str):
            if x != y:
                return False
            continue
        if x[0] != y[0] or len(x) != len(y):
            return False
        stack.extend(zip(x[1:], y[1:]))
    return True


def _rename(t, m):
    if isinstance(t, str):
        return m.get(t, t)
    return (t[0],) + tuple(_rename(c, m) for c in t[1:])


def _resolve(t, S, filler):
    t = _walk(t, S)
    if isinstance(t, int):
        return filler
    if isinstance(t, str):
        return t
    return (t[0],) + tuple(_resolve(c, S, filler) for c in t[1:])


def _size(t, S) -> int:
    n, stack = 0, [t]
    while stack:
        x = _walk(stack.pop(), S)
        if isinstance(x, tuple):
            n += 1
            stack.extend(x[1:])
        elif isinstance(x, str):
            n += 1
    return n


class Prover:
    def __init__(self, db, library: Library, max_depth: int = 8):
        self.db, self.library, self.max_depth = db, library, max_depth

    def prove(self, label: str, meter: Meter):
        """A proof (labels, normal format) of the theorem ``label`` from the library, or ``None`` when the
        meter ends first. Raises nothing for a theorem it cannot read; returns ``None``."""
        db = self.db
        a = db.assertions[label]
        try:
            goal = db.parse("wff", a.stmt[1:])
            hyps = [(h, db.parse("wff", st[1:])) for h, _, st in a.essentials]
        except Exception:
            return None
        filler = next((v for _, tc, v in a.floats if tc == "wff"), "ph")
        state = {"S": {}, "trail": [], "fresh": [0]}
        for depth in range(1, self.max_depth + 1):
            root = [None, None, None, None]
            try:
                for _ in self._search([(goal, root, depth)], hyps, state, meter):
                    return self._emit(root, state["S"], a, filler)
            except BudgetExhausted:
                return None
        return None

    def _undo(self, state, mark):
        S, trail = state["S"], state["trail"]
        while len(trail) > mark:
            del S[trail.pop()]

    def _search(self, goals, hyps, state, meter):
        if not goals:
            yield True
            return
        S, trail = state["S"], state["trail"]
        best, best_size = 0, -1
        for k, (g, _, _) in enumerate(goals):
            sz = _size(g, S)
            if sz > best_size:
                best, best_size = k, sz
        g, node, depth = goals[best]
        rest = goals[:best] + goals[best + 1:]
        g = _walk(g, S)
        if isinstance(g, int):
            # nothing fixes it: close it with the theorem's first hypothesis or the first closed assertion
            meter.charge(1)
            if hyps:
                mark = len(trail)
                if _unify(g, hyps[0][1], S, trail):
                    node[:] = ["hyp", hyps[0][0], None, None]
                    yield from self._search(rest, hyps, state, meter)
                self._undo(state, mark)
                return
            for e in self.library.closed[:1]:
                mark = len(trail)
                ren = {}
                for v in e.vars:
                    state["fresh"][0] += 1
                    ren[v] = state["fresh"][0]
                if _unify(g, _rename(e.concl, ren), S, trail):
                    node[:] = ["app", e.label, ren, []]
                    yield from self._search(rest, hyps, state, meter)
                self._undo(state, mark)
            return
        for h, ht in hyps:
            meter.charge(1)
            mark = len(trail)
            if _unify(g, ht, S, trail):
                node[:] = ["hyp", h, None, None]
                yield from self._search(rest, hyps, state, meter)
            self._undo(state, mark)
        head = g[0] if isinstance(g, tuple) else None
        for e in self.library.candidates(head):
            if e.hyps and depth <= 0:
                continue
            meter.charge(1)
            mark = len(trail)
            ren = {}
            for v in e.vars:
                state["fresh"][0] += 1
                ren[v] = state["fresh"][0]
            if _unify(g, _rename(e.concl, ren), S, trail):
                children = [[None, None, None, None] for _ in e.hyps]
                node[:] = ["app", e.label, ren, children]
                new = [(_rename(ht, ren), c, depth - 1) for ht, c in zip(e.hyps, children)]
                yield from self._search(rest + new, hyps, state, meter)
            self._undo(state, mark)

    def _emit(self, root, S, theorem, filler):
        db = self.db
        floats = theorem.active_floats
        out = []

        def go(node):
            kind, label, ren, children = node
            if kind == "hyp":
                out.append(label)
                return
            e = self._entry(label)
            for part, x in e.seq:
                if part == "f":
                    out.extend(db.syntax_proof(_resolve(ren[x], S, filler), floats))
                else:
                    go(children[x])
            out.append(label)

        go(root)
        return out

    def _entry(self, label):
        return self.library.entries[label]
