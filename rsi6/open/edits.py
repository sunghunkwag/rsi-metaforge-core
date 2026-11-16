"""Edits of a mechanism of the open design: generic changes of its programs and constants.

The growth edits (``term``, ``cross``, theta ``grow``) add a constant whose starting value makes
the new instruction a no-op (a term times zero, a register times one or plus zero) and read no
noise: before learning the policy is unchanged, and the learning principle's draws for the
existing constants are unchanged too (``design_o`` draws noise per coordinate). Learning then
has one more direction.

An edit knows the syntax of the machine and nothing else: it inserts, deletes, replaces or
changes instructions, swaps two, splices a block from a library, perturbs or adds a constant,
or changes one of the mechanism's numbers. Which edits are drawn, and how often, is decided by
the discoverer (``discovery.py``); this module only makes them and checks that the result is a
valid mechanism.

``behaviour(mechanism)`` is a key that is equal for two mechanisms whose effective programs are
equal: instructions of ``score`` and ``pick`` whose result never reaches register 0 are
dropped before the key is taken, so an edit that only changes dead code is recognised as no
change at all and is never measured.
"""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from rsi6.learner import design_o as O

PROGRAMS = ("score", "pick", "init", "propose", "update")
KINDS = {
    "score": ("insert", "delete", "replace", "mutop", "mutarg", "swap", "splice", "term", "cross"),
    "pick": ("insert", "delete", "replace", "mutop", "mutarg", "swap", "splice", "term", "cross"),
    "init": ("insert", "delete", "replace", "mutarg"),
    "propose": ("insert", "delete", "replace", "mutop", "mutarg", "swap", "splice"),
    "update": ("insert", "delete", "replace", "mutop", "mutarg", "swap", "splice"),
    "theta": ("perturb", "grow"),
    "scalar": ("pop", "batch", "shortlist", "holdback", "select"),
}
CELLS = [(part, kind) for part, kinds in KINDS.items() for kind in kinds]
CLASSES = {
    "score": [O.UNARY, O.BINARY, O.PARAM, ("const",), ("load",), ("rel", "relt")],
    "pick": [O.UNARY, O.BINARY, O.PARAM, ("const",), ("load",)],
    "init": [O.A_UNARY, O.A_BINARY, O.A_CONST, O.A_NULLARY],
    "propose": [O.A_UNARY, O.A_BINARY, O.A_CONST, O.A_NULLARY, O.POP_OPS],
    "update": [O.A_UNARY, O.A_BINARY, O.A_CONST, O.A_NULLARY,
               ("wfit", "wrank", "wcenter", "wtop", "wexp", "wnorm", "wmul", "wadd", "wneg", "wbest"), ("comb", "combabs")],
}


def _class_of(part, op):
    for group in CLASSES[part]:
        if op in group:
            return group
    return (op,)


def random_instruction(part: str, n_theta: int, rng) -> list:
    """A random valid instruction of one program."""
    op = str(rng.choice(O.PARTS_OPS[part]))
    if part in ("score", "pick"):
        nreg = O.N_REG if part == "score" else O.N_PREG
        sensors = O.SCORE_SENSORS if part == "score" else O.PICK_SENSORS
        dst = int(rng.integers(nreg))
        if op == "load":
            return [op, dst, int(rng.integers(len(sensors))), int(rng.integers(O.SENSOR_ARGS))]
        if op in O.PARAM:
            return [op, dst, int(rng.integers(nreg)), int(rng.integers(n_theta))]
        if op == "const":
            return [op, dst, 0, int(rng.integers(n_theta))]
        if op in ("rel", "relt"):
            return [op, dst, int(rng.integers(nreg)), int(rng.integers(O.SENSOR_ARGS))]
        if op in O.BINARY:
            return [op, dst, int(rng.integers(nreg)), int(rng.integers(nreg))]
        return [op, dst, int(rng.integers(nreg)), 0]
    if op in O.POP_OPS:
        return [op, int(rng.integers(16)), int(rng.integers(O.N_AREG)), int(rng.integers(O.N_AREG))]
    if op in ("comb", "combabs"):
        return [op, int(rng.integers(O.N_AREG)), int(rng.integers(O.N_WREG)), int(rng.integers(O.N_AREG))]
    if op in O.W_OPS:
        return [op, int(rng.integers(O.N_WREG)), int(rng.integers(O.N_WREG)), int(rng.integers(len(O.CONST)))]
    b = int(rng.integers(len(O.CONST))) if op in O.A_CONST else int(rng.integers(O.N_AREG))
    return [op, int(rng.integers(O.N_AREG)), int(rng.integers(O.N_AREG)), b]


def _mutarg(part, ins, n_theta, rng):
    """One field of an instruction changed to another valid value (tried by validation)."""
    out = list(ins)
    field = int(rng.integers(1, 4))
    out[field] = int(rng.integers(0, 16))
    if part in ("score", "pick") and ins[0] in O.PARAM + ("const",) and field == 3:
        out[3] = int(rng.integers(n_theta))
    return out


def apply_edit(mechanism: dict, cell, library: list, rng) -> tuple:
    """``(new mechanism, description)``, or ``(None, reason)`` if the edit does not apply. The
    new mechanism is validated; an edit that would make it invalid does not apply."""
    part, kind = cell
    g = copy.deepcopy(mechanism)
    n_theta = len(g["theta"])
    info = {"part": part, "kind": kind}
    if part in PROGRAMS:
        prog = g[part]
        limit = O.LIMITS[part]
        if kind == "insert":
            if len(prog) >= limit:
                return None, "full"
            pos = int(rng.integers(len(prog) + 1))
            ins = random_instruction(part, n_theta, rng)
            prog.insert(pos, ins)
            info["block"] = [ins]
        elif kind in ("term", "cross"):
            # a new term with a new constant set to 0 at the end of the program: register 0 gains
            # theta_new * norm(sensor) (or of the product of two sensors). It changes nothing until
            # the learning principle moves the new constant, and gives that principle a new direction.
            nreg = O.N_REG if part == "score" else O.N_PREG
            sensors = O.SCORE_SENSORS if part == "score" else O.PICK_SENSORS
            if n_theta >= O.LIMITS["theta"]:
                return None, "no room for a constant"
            r = int(rng.integers(1, nreg))
            r2 = 1 + (r % (nreg - 1))
            quiet = [k for k, name in enumerate(sensors) if name != "noise"]     # a new term draws no noise
            block = [["load", r, int(rng.choice(quiet)), int(rng.integers(O.SENSOR_ARGS))]]
            if kind == "cross":
                block += [["load", r2, int(rng.choice(quiet)), int(rng.integers(O.SENSOR_ARGS))], ["mul", r, r, r2]]
            block += [[str(rng.choice(["mm", "rank", "z"])), r, r, 0], ["scale", r, r, n_theta], ["add", 0, 0, r]]
            if len(prog) + len(block) > limit:
                return None, "full"
            g["theta"].append(0.0)
            prog.extend(block)
            info["block"] = block
        elif kind == "splice":
            blocks = [b for b in library if b["part"] == part and len(prog) + len(b["block"]) <= limit]
            if not blocks:
                return None, "no block in the library"
            block = blocks[int(rng.integers(len(blocks)))]["block"]
            pos = int(rng.integers(len(prog) + 1))
            prog[pos:pos] = copy.deepcopy(block)
            info["block"] = block
        elif not prog:
            return None, "empty program"
        elif kind == "delete":
            del prog[int(rng.integers(len(prog)))]
        elif kind == "replace":
            pos = int(rng.integers(len(prog)))
            prog[pos] = random_instruction(part, n_theta, rng)
            info["block"] = [prog[pos]]
        elif kind == "mutop":
            pos = int(rng.integers(len(prog)))
            group = [op for op in _class_of(part, prog[pos][0]) if op != prog[pos][0]]
            if not group:
                return None, "no other op in the class"
            prog[pos] = [str(rng.choice(group))] + list(prog[pos][1:])
            info["block"] = [prog[pos]]
        elif kind == "mutarg":
            pos = int(rng.integers(len(prog)))
            prog[pos] = _mutarg(part, prog[pos], n_theta, rng)
            info["block"] = [prog[pos]]
        elif kind == "swap":
            if len(prog) < 2:
                return None, "too short"
            i, j = (int(x) for x in rng.choice(len(prog), size=2, replace=False))
            prog[i], prog[j] = prog[j], prog[i]
    elif part == "theta":
        if kind == "perturb":
            k = int(rng.integers(n_theta))
            g["theta"][k] = float(np.clip(g["theta"][k] + rng.normal(0.0, max(1.0, abs(g["theta"][k])) * 0.5), -50.0, 50.0))
        else:                                                   # grow: a new constant that changes nothing until it is learned
            if n_theta >= O.LIMITS["theta"]:
                return None, "no room for a constant"
            target = str(rng.choice(["score", "pick"]))
            if len(g[target]) >= O.LIMITS[target]:
                return None, "full"
            nreg = O.N_REG if target == "score" else O.N_PREG
            r = int(rng.integers(nreg))
            op = str(rng.choice(["scale", "shift"]))
            g["theta"].append(1.0 if op == "scale" else 0.0)         # times one, or plus zero, at the start
            ins = [op, r, r, n_theta]
            g[target].insert(int(rng.integers(len(g[target]) + 1)), ins)
            info["block"] = [ins]
            info["target"] = target
    else:                                                       # scalar
        choices = {"pop": [4, 6, 8, 12, 16, 24, 32], "batch": [1, 2, 3, 4, 6, 8], "shortlist": [1, 2, 4],
                   "holdback": [0.1, 0.2, 0.25, 0.3, 0.4, 0.5], "select": list(O.SELECT)}[kind]
        others = [c for c in choices if c != g[kind]]
        g[kind] = others[int(rng.integers(len(others)))]
    try:
        g = O.validate(g)
    except ValueError as error:
        return None, f"invalid: {error}"
    return g, info


def effective(mechanism: dict) -> dict:
    """The mechanism with the dead instructions of every program removed: they are never run
    (``design_o.live``, ``design_o.live_principle``). Every constant keeps its value, read or not:
    the learning principle starts from all of them and can mix them (``mean``, ``norm``)."""
    g = copy.deepcopy(mechanism)
    for part in ("score", "pick"):
        g[part] = O.live(g[part])
    g.update(O.live_principle(g))                       # dead instructions of the learning programs are not run either
    return g


def behaviour(mechanism: dict) -> str:
    """A key equal for mechanisms that behave alike."""
    return hashlib.sha256(json.dumps(effective(mechanism), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
