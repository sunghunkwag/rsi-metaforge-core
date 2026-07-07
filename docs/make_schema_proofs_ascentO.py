#!/usr/bin/env python3
"""Ascent Phase O schema-skeleton proofs (run once at spec-freeze).

Builds docs/schema_proofs_ascentO.json: kernel-checkable proof objects for
the two registered Channel B schema skeletons —

  B (hypothetical syllogism): (p->q) -> ((q->r) -> (p->r))
  C (exchange):               (p->(q->r)) -> (q->(p->r))

The proofs are constructed mechanically by the standard deduction-theorem
algorithm over the frozen Lukasiewicz axiom base (A1, A2, modus ponens)
and verified by the frozen N-1 kernel before being written. Authorship is
irrelevant to soundness: the kernel re-checks every step structurally at
every battery start. After this snapshot the file is read-only; its
SHA-256 is pinned inside the runtime.

Usage (from the repository root):
    python3 docs/make_schema_proofs_ascentO.py > docs/schema_proofs_ascentO.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rsi_levels_metaforge_unified as M

P, Q, R = ("v", 0), ("v", 1), ("v", 2)


def imp(a, b):
    return ("imp", a, b)


def line_formula(line, formulas):
    if line[0] == "hyp":
        return line[1]
    if line[0] == "ax":
        return M.an_subst(M.AN_AXIOMS[line[1]], line[2])
    return formulas[line[2]][2]


def discharge(hyp, lines):
    """The deduction-theorem algorithm: convert a proof of the sequent
    (hyps + [hyp]) |- goal into a proof of hyps |- hyp -> goal."""
    out = []
    formulas = []
    where = {}

    def emit(line, formula):
        out.append((line, formula))
        return len(out) - 1

    for idx, line in enumerate(lines):
        f = line_formula(line, formulas)
        formulas.append(f)
        if line[0] == "hyp" and line[1] == hyp:
            k0 = emit(("ax", 0, {0: hyp, 1: imp(hyp, hyp), 2: hyp}),
                      imp(hyp, imp(imp(hyp, hyp), hyp)))
            k1 = emit(("ax", 1, {0: hyp, 1: imp(hyp, hyp), 2: hyp}),
                      imp(imp(hyp, imp(imp(hyp, hyp), hyp)),
                          imp(imp(hyp, imp(hyp, hyp)), imp(hyp, hyp))))
            k2 = emit(("mp", k0, k1),
                      imp(imp(hyp, imp(hyp, hyp)), imp(hyp, hyp)))
            k3 = emit(("ax", 0, {0: hyp, 1: hyp, 2: hyp}),
                      imp(hyp, imp(hyp, hyp)))
            where[idx] = emit(("mp", k3, k2), imp(hyp, hyp))
        elif line[0] in ("hyp", "ax"):
            base = emit(line, f)
            lift = emit(("ax", 0, {0: f, 1: hyp, 2: f}),
                        imp(f, imp(hyp, f)))
            where[idx] = emit(("mp", base, lift), imp(hyp, f))
        else:
            i, j = line[1], line[2]
            a = formulas[i]
            k0 = emit(("ax", 1, {0: hyp, 1: a, 2: f}),
                      imp(imp(hyp, imp(a, f)),
                          imp(imp(hyp, a), imp(hyp, f))))
            k1 = emit(("mp", where[j], k0),
                      imp(imp(hyp, a), imp(hyp, f)))
            where[idx] = emit(("mp", where[i], k1), imp(hyp, f))
    return [line for line, _ in out]


def close(hyps, lines, goal):
    """Discharge hypotheses right-to-left, kernel-verify, and encode."""
    cur = list(lines)
    g = goal
    for h in reversed(hyps):
        cur = discharge(h, cur)
        g = imp(h, g)
    proof = []
    steps = []
    for line in cur:
        if line[0] == "hyp":
            raise AssertionError("undischarged hypothesis")
        if line[0] == "ax":
            proof.append(("ax", line[1], dict(line[2])))
            steps.append(["ax", line[1],
                          {str(k): list(M.an_encode_formula(v))
                           for k, v in line[2].items()}])
        else:
            proof.append(("mp", line[1], line[2]))
            steps.append(["mp", line[1], line[2]])
    assert M.an_check_proof(tuple(proof), g), "kernel rejected the proof"
    return g, steps


# B: {p->q, q->r, p} |- r, then discharge p, q->r, p->q.
b_lines = [
    ("hyp", P),
    ("hyp", imp(P, Q)),
    ("mp", 0, 1),
    ("hyp", imp(Q, R)),
    ("mp", 2, 3),
]
b_goal, b_steps = close([imp(P, Q), imp(Q, R), P], b_lines, R)

# C: {p->(q->r), q, p} |- r, then discharge p, q, p->(q->r).
c_lines = [
    ("hyp", P),
    ("hyp", imp(P, imp(Q, R))),
    ("mp", 0, 1),
    ("hyp", Q),
    ("mp", 3, 2),
]
c_goal, c_steps = close([imp(P, imp(Q, R)), Q, P], c_lines, R)

doc = {
    "meta": {
        "instrument": "schema_proofs_ascentO",
        "note": "kernel-verified proof objects for the Channel B schema "
                "skeletons; read-only after the Phase O spec-freeze; "
                "SHA-256 pinned in the runtime.",
    },
    "schemas": {
        "B_hypothetical_syllogism": {
            "goal": list(M.an_encode_formula(b_goal)),
            "steps": b_steps,
            "n_steps": len(b_steps),
        },
        "C_exchange": {
            "goal": list(M.an_encode_formula(c_goal)),
            "steps": c_steps,
            "n_steps": len(c_steps),
        },
    },
}
print(json.dumps(doc, indent=2, sort_keys=True))
