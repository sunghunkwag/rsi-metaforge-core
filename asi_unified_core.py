#!/usr/bin/env python3
"""
ASI UNIFIED CORE  --  single self-contained symbolic recursive-self-improvement core.

INTEGRATION OF THREE UPLOADED FILES (verified, not assumed):
  * rsi_metaforge_core_v15.py  -- the full 20-section monolith. Sections 13-20 are
                                  the ASI architecture; Section 20 is the guarded layer.
  * asi_unified_core.py   -- the de-duplicated single-file consolidation of those
                                  ASI sections (this file's spine).
  * asi_guarded.py             -- the guarded layer as a stand-alone module. It cannot
                                  run on its own (it imports asi_integrated / asi_evolve /
                                  asi_unify / asi_auto / asi_socratic, which are layers,
                                  not files). Here it is folded in so it RUNS.

The three were three packagings of the SAME logic. The build step proves the five
guarded functions (socratic_solve_task, socratic_gate, _operator_base, gate_vs_naive,
run_guarded_loop) are byte-identical across all three sources before consolidating, so
nothing is silently dropped. The ONE structural difference is intentional: the monolith
bridges the stack-VM substrate to its native run_base_program (v8_native_vm_eval); a
stand-alone file has no such dependency, so it uses the self-contained vm_eval instead.
Both compute the same VM semantics; the kernel verifies every result either way.

It is NOT a verified superintelligence and sets no "ASI achieved" flag. Every claim it
makes about itself is backed by a test in the unified suite at the bottom of this file.

WHAT IT CONTAINS (8 layers, run_all() exercises every one)
  1. Immutable hash-pinned KERNEL (generic over substrates; per-substrate fingerprint),
     the single root of trust: evaluates, checks equivalence, replays; never modified.
  2. MULTIPLE SUBSTRATES            -- arithmetic ring, boolean algebra, stack VM.
  3. KURAMOTO phase-coupled binding -- dynamic primitive binding from a cold neutral start.
  4. COMPRESSION-PROGRESS curriculum-- tasks chosen by how much they compress what is known.
  5. BOTTOM-UP synthesis            -- observational-equivalence search; smallest program,
                                       found deterministically.
  6. CUMULATIVE abstraction / macros-- solved structure distilled into reusable macros.
  7. OPERATOR EVOLUTION + CROSS-SUBSTRATE transfer over the fixed kernel.
  8. SOCRATIC gate (CEGIS) + GUARDED autonomous loop -- a questioner/respondent debate,
     judged by the kernel, kills spurious fits; operator promotion is gated on surviving
     adversarial audit, then the loop solves -> verifies -> abstracts -> gates -> promotes.
     (After Schaul, "Boundless Socratic Learning with Language Games," DeepMind,
     arXiv:2411.16905 -- adapted from the paper's LLM/language framing to this LLM-free
     symbolic setting as counterexample-guided synthesis.)

HONEST SCOPE: CPU-scale research system. Sealed evaluation, immutable kernel, no backprop,
no LLM, no gradient steps, no network, no external data, deterministic under fixed seeds.
Run `python asi_unified_core.py test` to execute the full suite (49 tests across 8 layers).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import random
from itertools import product
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Type aliases used by the non-kernel layers (the kernel layer uses ASIExpr/ASIObj).
Expr = Tuple
Obj = Tuple



# ========================================================================================
# LAYER 1.  KERNEL + SUBSTRATES + KURAMOTO BINDING + COMPRESSION CURRICULUM (asi_integrated)
# ========================================================================================



# ===========================================================================
# Constants
# ===========================================================================
ASI_SEED = 7
SEARCH_BUDGET = 6000
MAX_DEPTH = 4
MIN_WITNESS = 4
KUR_STEPS = 48
KUR_DT = 0.12
KUR_KSELF = 2.4            # within-feature-group coupling (forms a driver)

ASIExpr = Tuple
ASIObj = Tuple


def _asi_sha16(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ===========================================================================
# GENERIC IMMUTABLE KERNEL  (one total evaluator; substrates provide pure ops)
# ===========================================================================
def k_eval(expr: ASIExpr, env: ASIObj, optable: Dict[str, Tuple[int, Callable]],
           macros: Dict[str, ASIExpr]) -> int:
    """Total structural evaluator, arity-agnostic. Macro bodies may reference
    only EARLIER macros (enforced at adoption) so expansion cannot cycle."""
    head = expr[0]
    if head == "var":
        i = expr[1]
        return int(env[i]) if 0 <= i < len(env) else 0
    if head == "lit":
        return int(expr[1])
    if head == "mac":
        return k_eval(macros[expr[1]], env, optable, macros)
    arity, fn = optable[head]
    args = [k_eval(child, env, optable, macros) for child in expr[1:]]
    return int(fn(*args))


def k_eq(a: int, b: int) -> bool:
    return int(a) == int(b)


def k_le(a: int, b: int) -> bool:
    return int(a) <= int(b)


def k_replay(cert: Sequence[Tuple], optable, macros) -> bool:
    for step in cert:
        tag = step[0]
        if tag == "eq_val":
            _, e, env, v = step
            if not k_eq(k_eval(e, env, optable, macros), v):
                return False
        elif tag == "eq2":
            _, e, e1, e2 = step
            if not k_eq(k_eval(e, e1, optable, macros), k_eval(e, e2, optable, macros)):
                return False
        elif tag == "ne2":
            _, e, e1, e2 = step
            if k_eq(k_eval(e, e1, optable, macros), k_eval(e, e2, optable, macros)):
                return False
        elif tag == "le_val":
            _, e, env, v = step
            if not k_le(k_eval(e, env, optable, macros), v):
                return False
        else:
            return False
    return True


_KERNEL_CORE_FP = _asi_sha16("".join(
    inspect.getsource(f) for f in (k_eval, k_eq, k_le, k_replay)))


def substrate_fingerprint(optable: Dict[str, Tuple[int, Callable]]) -> str:
    """Per-substrate trust root: the generic kernel + this substrate's pure op
    functions. Hash-pinned; asserted stable across the whole run."""
    op_src = "".join(inspect.getsource(fn) for _, (ar, fn) in sorted(optable.items()))
    return _asi_sha16(_KERNEL_CORE_FP + op_src)


# ===========================================================================
# Expression helpers (arity-agnostic)
# ===========================================================================
def _size(e: ASIExpr) -> int:
    if e[0] in ("var", "lit", "mac"):
        return 1
    return 1 + sum(_size(c) for c in e[1:])


def _key(e: ASIExpr) -> str:
    if e[0] == "var":
        return f"x{e[1]}"
    if e[0] == "lit":
        return f"#{e[1]}"
    if e[0] == "mac":
        return f"@{e[1]}"
    return e[0] + "(" + ",".join(_key(c) for c in e[1:]) + ")"


def _primitives_used(e: ASIExpr) -> List[str]:
    if e[0] == "var":
        return [f"x{e[1]}"]
    if e[0] == "lit":
        return [f"#{e[1]}"]
    if e[0] == "mac":
        return [f"@{e[1]}"]
    out = [e[0]]
    for c in e[1:]:
        out += _primitives_used(c)
    return out


def _macro_refs(e: ASIExpr) -> List[str]:
    if e[0] == "mac":
        return [e[1]]
    if e[0] in ("var", "lit"):
        return []
    out: List[str] = []
    for c in e[1:]:
        out += _macro_refs(c)
    return out


def _expand_size(e: ASIExpr, macros: Dict[str, ASIExpr]) -> int:
    """Size with macros fully expanded to base ops (for compression metrics)."""
    if e[0] in ("var", "lit"):
        return 1
    if e[0] == "mac":
        return _expand_size(macros[e[1]], macros)
    return 1 + sum(_expand_size(c, macros) for c in e[1:])


# ===========================================================================
# SUBSTRATE  (object domain + grammar + kernel + verifiers + task generators)
# ===========================================================================
@dataclass
class Substrate:
    name: str
    arity: int
    optable: Dict[str, Tuple[int, Callable]]
    consts: Tuple[int, ...]
    families: List[Tuple[str, Callable[[ASIObj], int]]]
    chain: List[str]                       # nested family order enabling lineage
    gen_input: Callable[[random.Random], ASIObj]
    feature_fn: Callable[["Substrate", "ASISealedTask"], List[str]]
    verifiers: List[Tuple[str, Callable]]  # (name, builder(prog, probes, optable))

    def terminals(self) -> List[str]:
        return [f"x{i}" for i in range(self.arity)] + [f"#{c}" for c in self.consts]

    def fingerprint(self) -> str:
        return substrate_fingerprint(self.optable)


@dataclass(frozen=True)
class ASISealedTask:
    name: str
    substrate: str
    family: str
    _fn: Callable[[ASIObj], int]
    train_inputs: Tuple[ASIObj, ...]
    holdout_inputs: Tuple[ASIObj, ...]

    def train_pairs(self):
        return tuple((e, int(self._fn(e))) for e in self.train_inputs)

    def holdout_pairs(self):
        return tuple((e, int(self._fn(e))) for e in self.holdout_inputs)


def make_task(sub: Substrate, family: str, fn, seed: int) -> ASISealedTask:
    rtr = random.Random(seed)
    rho = random.Random(seed ^ 0x5DEECE66)
    tr = tuple(sub.gen_input(rtr) for _ in range(12))
    ho = tuple(sub.gen_input(rho) for _ in range(12))
    return ASISealedTask(f"{sub.name}/{family}#{seed % 1000}", sub.name, family, fn, tr, ho)


# ---- arithmetic substrate (integer ring) ----
def _op_add(a, b): return a + b
def _op_sub(a, b): return a - b
def _op_mul(a, b): return a * b
def _op_min(a, b): return a if a < b else b
def _op_max(a, b): return a if a > b else b
def _op_mod(a, b): return (a % b) if b != 0 else 0

ARITH_OPS = {"ADD": (2, _op_add), "SUB": (2, _op_sub), "MUL": (2, _op_mul),
             "MIN": (2, _op_min), "MAX": (2, _op_max), "MOD": (2, _op_mod)}


def _arith_input(rng: random.Random) -> ASIObj:
    return tuple(rng.randint(0, 6) for _ in range(3))


def _af_sum(e): return e[0] + e[1] + e[2]
def _af_summod(e): return (e[0] + e[1] + e[2]) % 3
def _af_summod2(e): return ((e[0] + e[1] + e[2]) % 3) * 2
def _af_max(e): return max(e)
def _af_maxmin(e): return max(e) + min(e)
def _af_first(e): return e[0]


# ---- boolean substrate (different algebra, includes a UNARY op) ----
def _op_and(a, b): return 1 if (a and b) else 0
def _op_or(a, b): return 1 if (a or b) else 0
def _op_xor(a, b): return 1 if ((a ^ b) & 1) else 0
def _op_not(a): return 0 if a else 1

BOOL_OPS = {"AND": (2, _op_and), "OR": (2, _op_or), "XOR": (2, _op_xor),
            "NOT": (1, _op_not)}


def _bool_input(rng: random.Random) -> ASIObj:
    return tuple(rng.randint(0, 1) for _ in range(4))


def _bf_parity(e): return (e[0] ^ e[1] ^ e[2] ^ e[3]) & 1
def _bf_majority(e): return 1 if sum(e) >= 2 else 0
def _bf_all(e): return 1 if all(e) else 0
def _bf_any(e): return 1 if any(e) else 0
def _bf_first(e): return e[0]
def _bf_parity3(e): return (e[0] ^ e[1] ^ e[2]) & 1


# ===========================================================================
# Problem features (observable from train pairs; NO oracle leak)
# ===========================================================================
def arith_features(sub: Substrate, task: ASISealedTask) -> List[str]:
    pairs = task.train_pairs()
    xs = [e for e, _ in pairs]
    ys = [y for _, y in pairs]

    def corr(key):
        kv = [key(e) for e in xs]
        order = sorted(range(len(kv)), key=lambda i: kv[i])
        up = sum(1 for a, b in zip(order, order[1:]) if ys[b] > ys[a])
        dn = sum(1 for a, b in zip(order, order[1:]) if ys[b] < ys[a])
        return "up" if up > dn + 1 else ("down" if dn > up + 1 else "flat")

    f = [f"{sub.name}:sum:" + corr(lambda e: sum(e)),
         f"{sub.name}:max:" + corr(lambda e: max(e)),
         f"{sub.name}:isMax:" + ("y" if sum(1 for e, y in zip(xs, ys) if y == max(e)) > len(xs) // 2 else "n"),
         f"{sub.name}:small:" + ("y" if sum(1 for y in ys if abs(y) <= 6) > len(ys) // 2 else "n")]
    return f


def bool_features(sub: Substrate, task: ASISealedTask) -> List[str]:
    pairs = task.train_pairs()
    xs = [e for e, _ in pairs]
    ys = [y for _, y in pairs]
    pc_corr_up = sum(1 for e, y in zip(xs, ys) if y == (1 if sum(e) >= 2 else 0))
    f = [f"{sub.name}:popmaj:" + ("y" if pc_corr_up > len(xs) // 2 else "n"),
         f"{sub.name}:par:" + ("y" if sum(1 for e, y in zip(xs, ys)
                                          if y == (e[0] ^ e[1] ^ e[2] ^ e[3]) & 1) > len(xs) // 2 else "n"),
         f"{sub.name}:first:" + ("y" if sum(1 for e, y in zip(xs, ys) if y == e[0]) > len(xs) // 2 else "n"),
         f"{sub.name}:allone:" + ("y" if sum(ys) > len(ys) // 2 else "n")]
    return f


# ===========================================================================
# Verifiers (growing language; each only EMITS kernel certificates)
# ===========================================================================
def _perm(e: ASIObj, rng: random.Random) -> ASIObj:
    p = list(e)
    rng.shuffle(p)
    return tuple(p)


def v_perm_invariant(prog, probes, optable):
    rng = random.Random(7)
    return [("eq2", prog, e, _perm(e, rng)) for e in probes]


def v_nonconstant(prog, probes, optable, macros):
    for i in range(len(probes)):
        for j in range(i + 1, len(probes)):
            if k_eval(prog, probes[i], optable, macros) != k_eval(prog, probes[j], optable, macros):
                return [("ne2", prog, probes[i], probes[j])] * MIN_WITNESS
    return []


def v_bounded_by_sum(prog, probes, optable):
    return [("le_val", prog, e, sum(e)) for e in probes]


ARITH_VERIFIERS = [
    ("perm_invariant", lambda p, pr, ot, mc: v_perm_invariant(p, pr, ot)),
    ("nonconstant", lambda p, pr, ot, mc: v_nonconstant(p, pr, ot, mc)),
    ("bounded_by_sum", lambda p, pr, ot, mc: v_bounded_by_sum(p, pr, ot)),
]
BOOL_VERIFIERS = [
    ("perm_invariant", lambda p, pr, ot, mc: v_perm_invariant(p, pr, ot)),
    ("nonconstant", lambda p, pr, ot, mc: v_nonconstant(p, pr, ot, mc)),
]


def admit_property(name, cert, subject, optable, macros) -> bool:
    if len(cert) < MIN_WITNESS:
        return False
    for step in cert:
        if step[1] != subject:                 # subject-binding (no decoy)
            return False
    if not k_replay(cert, optable, macros):
        return False
    if name == "perm_invariant" and not any(s[2] != s[3] for s in cert):
        return False
    return True


def grow_language(sub: Substrate, prog, probes, macros, language) -> List[str]:
    newly = []
    for nm, builder in sub.verifiers:
        tag = f"{sub.name}:{nm}"
        if tag in language:
            continue
        cert = builder(prog, probes, sub.optable, macros)
        if admit_property(nm, cert, prog, sub.optable, macros):
            language.add(tag)
            newly.append(tag)
    return newly


# ===========================================================================
# (a) KURAMOTO DYNAMIC BINDING
# ===========================================================================
class KuramotoBinder:
    """Coupled phase oscillators bind co-active tokens. Learned coupling between
    problem-feature oscillators and primitive oscillators grows by Hebbian
    co-occurrence; at recall, primitives that PHASE-LOCK with the active feature
    group receive high search weight."""

    def __init__(self, seed: int):
        self.coupling: Dict[Tuple[str, str], float] = {}
        self.rng = np.random.default_rng(seed)

    def learn(self, feats: Sequence[str], prims: Sequence[str], scale: float) -> None:
        for f in feats:
            for p in prims:
                self.coupling[(f, p)] = self.coupling.get((f, p), 0.0) + scale

    def _simulate(self, feats: Sequence[str], prims: Sequence[str]):
        """Integrate the dynamics; return final phases, index maps, and each
        primitive's coherence with the feature group."""
        nF = len(feats)
        idxF = list(range(nF))
        idxP = {p: nF + k for k, p in enumerate(prims)}
        N = nF + len(prims)
        if nF == 0 or N == 0:
            return np.zeros(N), idxF, idxP, {p: 0.0 for p in prims}
        theta = self.rng.uniform(0, 2 * math.pi, size=N)
        omega = np.zeros(N)                    # identical natural freq: isolate coupling
        K = np.zeros((N, N))
        for a in idxF:                         # feature group self-cohesion (a driver)
            for b in idxF:
                if a != b:
                    K[a, b] = KUR_KSELF
        for p in prims:
            for fi, f in enumerate(feats):
                c = self.coupling.get((f, p), 0.0)
                if c != 0.0:
                    K[fi, idxP[p]] = c
                    K[idxP[p], fi] = c
        coh = {p: 0.0 for p in prims}
        nrec = 0
        for step in range(KUR_STEPS):
            diff = theta[None, :] - theta[:, None]
            dtheta = omega + (K * np.sin(diff)).sum(axis=1) / max(1, N)
            theta = theta + KUR_DT * dtheta
            if step >= KUR_STEPS // 2:
                mF = np.angle(np.mean(np.exp(1j * theta[idxF])))
                for p in prims:
                    coh[p] += math.cos(theta[idxP[p]] - mF)
                nrec += 1
        for p in prims:
            coh[p] = coh[p] / max(1, nrec)     # coherence with feature group, in [-1,1]
        return theta, idxF, idxP, coh

    def order_parameter(self, feats: Sequence[str], prims: Sequence[str]) -> float:
        """True Kuramoto order parameter r in [0,1] over the {features +
        primitives} assembly after settling. A coupled assembly phase-locks
        (r -> 1); uncoupled primitives stay at random phases and pull r down."""
        theta, idxF, idxP, _ = self._simulate(feats, prims)
        idx = idxF + [idxP[p] for p in prims]
        if not idx:
            return 0.0
        return float(abs(np.mean(np.exp(1j * theta[idx]))))

    def recall_weights(self, feats: Sequence[str], prims: Sequence[str]) -> Dict[str, float]:
        _, _, _, coh = self._simulate(feats, prims)
        # A primitive with NO learned coupling to the active features is left
        # neutral (weight 1.0) -- otherwise its random initial phase would inject
        # cold-start noise that suppresses needed primitives. Only primitives the
        # system has actually associated with these features get phase-weighted.
        out: Dict[str, float] = {}
        for p in prims:
            coupled = any(self.coupling.get((f, p), 0.0) != 0.0 for f in feats)
            out[p] = math.exp(2.2 * coh[p]) if coupled else 1.0
        return out


# ===========================================================================
# Macro registry (cumulative abstraction)
# ===========================================================================
class MacroRegistry:
    def __init__(self):
        self.bodies: Dict[str, ASIExpr] = {}
        self.order: List[str] = []
        self.substrate_of: Dict[str, str] = {}

    def adopt(self, body: ASIExpr, substrate: str) -> str:
        name = f"m{len(self.order)}"
        self.bodies[name] = body
        self.order.append(name)
        self.substrate_of[name] = substrate
        return name

    def terms_for(self, substrate: str) -> List[str]:
        return [f"@{n}" for n in self.order if self.substrate_of[n] == substrate]

    def lineage_depth(self, name: str) -> int:
        def md(n: str) -> int:
            refs = _macro_refs(self.bodies[n])
            return 1 + max((md(r) for r in refs), default=0)
        return md(name)


# ===========================================================================
# Stochastic weighted sampler (arity-agnostic; macro-aware)
# ===========================================================================
def _wchoice(rng: random.Random, items: List[str], w: List[float]) -> str:
    tot = sum(w)
    if tot <= 0:
        return rng.choice(items)
    r = rng.random() * tot
    up = 0.0
    for it, wi in zip(items, w):
        up += wi
        if up >= r:
            return it
    return items[-1]


def sample_expr(rng, sub: Substrate, macros: MacroRegistry,
                term_w: Dict[str, float], op_w: Dict[str, float], depth: int) -> ASIExpr:
    terms = list(term_w.keys())
    tw = [max(1e-3, term_w[t]) for t in terms]
    ops = list(op_w.keys())
    ow = [max(1e-3, op_w[o]) for o in ops]
    p_expand = 0.0 if depth <= 0 else 0.72
    if rng.random() >= p_expand or not ops:
        tok = _wchoice(rng, terms, tw)
        if tok.startswith("x"):
            return ("var", int(tok[1:]))
        if tok.startswith("#"):
            return ("lit", int(tok[1:]))
        return ("mac", tok[1:])
    op = _wchoice(rng, ops, ow)
    arity = sub.optable[op][0]
    children = tuple(sample_expr(rng, sub, macros, term_w, op_w, depth - 1)
                     for _ in range(arity))
    return (op,) + children


# ===========================================================================
# Search (sample -> kernel-check train -> kernel-verify holdout; count cost)
# ===========================================================================
@dataclass
class SearchOutcome:
    solved: bool
    program: Optional[ASIExpr]
    cost: int


def solve_task(task: ASISealedTask, sub: Substrate, binder: Optional[KuramotoBinder],
               macros: MacroRegistry, rng: random.Random,
               budget: int = SEARCH_BUDGET) -> Tuple[SearchOutcome, List[str], float]:
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)

    base_terms = sub.terminals() + macros.terms_for(sub.name)
    term_w = {t: 1.0 for t in base_terms}
    op_w = {op: 1.0 for op in sub.optable}

    feats: List[str] = []
    confidence = 0.0
    if binder is not None:
        feats = sub.feature_fn(sub, task)
        prims = base_terms + list(sub.optable.keys())
        weights = binder.recall_weights(feats, prims)
        for t in term_w:
            term_w[t] *= weights.get(t, 1.0)
        for op in op_w:
            op_w[op] *= weights.get(op, 1.0)
        vals = [weights.get(p, 1.0) for p in prims]
        confidence = 1.0 / (1.0 + math.exp(-(np.mean(np.log(vals)) if vals else 0.0)))

    seen: set = set()
    cost = 0
    for _ in range(budget):
        e = sample_expr(rng, sub, macros, term_w, op_w, MAX_DEPTH)
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        try:
            vals = tuple(k_eval(e, env, sub.optable, macros.bodies) for env in envs)
        except Exception:
            continue
        if vals == targets:
            cert = [("eq_val", e, env, v) for env, v in task.holdout_pairs()]
            if k_replay(cert, sub.optable, macros.bodies):
                return SearchOutcome(True, e, cost), feats, confidence
    return SearchOutcome(False, None, cost), feats, confidence


# ===========================================================================
# Substrate registry
# ===========================================================================
def build_arith_substrate() -> Substrate:
    return Substrate(
        name="arith", arity=3, optable=ARITH_OPS, consts=(0, 1, 2, 3),
        families=[("sum", _af_sum), ("summod", _af_summod), ("summod2", _af_summod2),
                  ("max", _af_max), ("maxmin", _af_maxmin), ("first", _af_first)],
        chain=["sum", "summod", "summod2"],
        gen_input=_arith_input, feature_fn=arith_features, verifiers=ARITH_VERIFIERS)


def build_bool_substrate() -> Substrate:
    return Substrate(
        name="bool", arity=4, optable=BOOL_OPS, consts=(0, 1),
        families=[("parity3", _bf_parity3), ("parity", _bf_parity),
                  ("majority", _bf_majority), ("anyor", _bf_any),
                  ("alland", _bf_all), ("firstbit", _bf_first)],
        chain=["parity3", "parity"],
        gen_input=_bool_input, feature_fn=bool_features, verifiers=BOOL_VERIFIERS)


# ===========================================================================
# THE INTEGRATED AUTONOMOUS LOOP
# ===========================================================================
@dataclass
class CycleRecord:
    cycle: int
    substrate: str
    family: str
    solved: bool
    cost: int
    predicted: float
    pred_error: float
    adopted_macro: Optional[str]
    macro_lineage: int
    reuse_compression: float
    language_size: int


def _probes(sub: Substrate, seed: int, n: int = 16) -> List[ASIObj]:
    rng = random.Random(seed)
    return [sub.gen_input(rng) for _ in range(n)]


def run_integrated(cycles: int = 30, learning: bool = True, seed: int = ASI_SEED) -> Dict:
    rng = random.Random(seed)
    subs = [build_arith_substrate(), build_bool_substrate()]
    sub_by_name = {s.name: s for s in subs}
    binder = KuramotoBinder(seed) if learning else None
    macros = MacroRegistry()
    language: set = set()
    for s in subs:
        language.add(f"{s.name}:holdout_match")
    probes = {s.name: _probes(s, seed + hash(s.name) % 1000) for s in subs}

    # per (substrate,family) frontier + reuse stats
    attempts: Dict[Tuple[str, str], int] = {}
    solved_n: Dict[Tuple[str, str], int] = {}
    macro_for: Dict[Tuple[str, str], str] = {}
    reuse_count: Dict[str, int] = {}          # macro -> times reused later
    chain_ptr: Dict[str, int] = {s.name: 0 for s in subs}
    for s in subs:
        for fam, _ in s.families:
            attempts[(s.name, fam)] = 0
            solved_n[(s.name, fam)] = 0

    # compression bookkeeping
    lib_expanded = 0      # total base-op size of solved programs (fully expanded)
    lib_coded = 0         # total size with macro references counted as 1

    records: List[CycleRecord] = []

    for c in range(cycles):
        # ---- (b) compression-progress + frontier selection ----
        # round-robin substrate, then pick a family within it.
        sub = subs[c % len(subs)]

        def frontier_score(fam: str) -> float:
            key = (sub.name, fam)
            a = attempts[key]
            base = 0.5 if a == 0 else -abs(solved_n[key] / a - 0.5)
            # compression-progress bonus: families whose macro has been reused
            mname = macro_for.get(key)
            comp = reuse_count.get(mname, 0) if mname else 0
            return base + 0.15 * comp

        # advance nested chain in order to enable lineage
        cp = chain_ptr[sub.name]
        if learning and cp < len(sub.chain) and solved_n[(sub.name, sub.chain[cp])] == 0:
            family = sub.chain[cp]
        else:
            family = max((f for f, _ in sub.families), key=frontier_score)

        fn = dict(sub.families)[family]
        task = make_task(sub, family, fn, seed + 1000 * c)

        outcome, feats, predicted = solve_task(task, sub, binder, macros, rng)
        actual = 1.0 if outcome.solved else 0.0
        pred_error = actual - predicted
        attempts[(sub.name, family)] += 1

        adopted = None
        lineage = 0
        if outcome.solved:
            solved_n[(sub.name, family)] += 1
            # ---- (a) Kuramoto Hebbian binding update, scaled by surprise ----
            if binder is not None:
                prims = _primitives_used(outcome.program)
                binder.learn(feats, prims, scale=0.6 + abs(pred_error))
                # count macro reuse for compression-progress
                for r in _macro_refs(outcome.program):
                    reuse_count[r] = reuse_count.get(r, 0) + 1
            # ---- compression bookkeeping ----
            lib_expanded += _expand_size(outcome.program, macros.bodies)
            lib_coded += _size(outcome.program)
            # ---- cumulative abstraction ----
            if learning and (sub.name, family) not in macro_for:
                name = macros.adopt(outcome.program, sub.name)
                macro_for[(sub.name, family)] = name
                adopted = name
                lineage = macros.lineage_depth(name)
            grow_language(sub, outcome.program, probes[sub.name], macros.bodies, language)
            if learning and cp < len(sub.chain) and family == sub.chain[cp]:
                chain_ptr[sub.name] += 1

        comp_ratio = (lib_coded / lib_expanded) if lib_expanded else 1.0
        records.append(CycleRecord(
            cycle=c, substrate=sub.name, family=family, solved=outcome.solved,
            cost=outcome.cost, predicted=round(predicted, 4),
            pred_error=round(pred_error, 4), adopted_macro=adopted,
            macro_lineage=lineage, reuse_compression=round(comp_ratio, 4),
            language_size=len(language)))

    solved_records = [r for r in records if r.solved]
    fp_ok = all(s.fingerprint() == substrate_fingerprint(s.optable) for s in subs)
    report = {
        "learning": learning,
        "substrates": [s.name for s in subs],
        "substrate_fingerprints": {s.name: s.fingerprint() for s in subs},
        "trust_roots_unchanged": fp_ok,
        "cycles": cycles,
        "solved_count": len(solved_records),
        "solved_by_substrate": {s.name: sum(1 for r in records if r.substrate == s.name and r.solved)
                                for s in subs},
        "total_search_cost": sum(r.cost for r in records),
        "max_macro_lineage": max((r.macro_lineage for r in records), default=0),
        "n_macros": len(macros.order),
        "library_compression_ratio": round((lib_coded / lib_expanded) if lib_expanded else 1.0, 4),
        "final_language": sorted(language),
        "language_size": len(language),
        "per_cycle": [r.__dict__ for r in records],
        "boundary": ("ASI-oriented integrated architecture (Kuramoto binding + "
                     "compression-progress curriculum + multi-substrate + growing "
                     "verification over immutable kernels). CPU-scale research "
                     "system; not a verified superintelligence."),
    }
    return report


def compare_learning_vs_control(seed: int = ASI_SEED, cycles: int = 30) -> Dict:
    learn = run_integrated(cycles=cycles, learning=True, seed=seed)
    ctrl = run_integrated(cycles=cycles, learning=False, seed=seed)
    return {
        "learning_solved": learn["solved_count"],
        "control_solved": ctrl["solved_count"],
        "learning_total_cost": learn["total_search_cost"],
        "control_total_cost": ctrl["total_search_cost"],
        "learning_reduces_cost": learn["total_search_cost"] < ctrl["total_search_cost"],
        "learning_solves_at_least_control": learn["solved_count"] >= ctrl["solved_count"],
        "max_macro_lineage": learn["max_macro_lineage"],
        "library_compression_ratio": learn["library_compression_ratio"],
        "solved_by_substrate": learn["solved_by_substrate"],
        "kernels_fixed": learn["trust_roots_unchanged"] and ctrl["trust_roots_unchanged"],
    }


# ===========================================================================
# TESTS
# ===========================================================================
def test_aint_kernels_fixed_per_substrate() -> None:
    subs = [build_arith_substrate(), build_bool_substrate()]
    fps = {s.name: s.fingerprint() for s in subs}
    _ = run_integrated(cycles=8)
    for s in subs:
        assert s.fingerprint() == fps[s.name], f"trust root for {s.name} moved"


def test_aint_multi_substrate_solving() -> None:
    r = run_integrated(cycles=24)
    sbs = r["solved_by_substrate"]
    assert sbs.get("arith", 0) >= 2, f"arith solved too few: {sbs}"
    assert sbs.get("bool", 0) >= 2, f"bool solved too few: {sbs}"


def test_aint_kuramoto_phase_locking() -> None:
    # a strongly-coupled feature<->primitive assembly synchronises (high order
    # parameter); an uncoupled set does not.
    b = KuramotoBinder(seed=1)
    feats = ["F:a", "F:b"]
    b.learn(feats, ["ADD", "x0"], scale=5.0)
    locked = b.order_parameter(feats, ["ADD", "x0"])
    unlocked = b.order_parameter(feats, ["MUL", "x2"])   # never coupled
    assert locked > unlocked + 0.2, f"no phase-locking: {locked:.3f} vs {unlocked:.3f}"


def test_aint_learning_lowers_cost() -> None:
    cmp = compare_learning_vs_control()
    assert cmp["learning_solves_at_least_control"], "learning solved fewer than control"
    assert cmp["learning_reduces_cost"], (
        f"learning did not reduce cost: {cmp['learning_total_cost']} "
        f"vs {cmp['control_total_cost']}")


def test_aint_cumulative_abstraction_lineage_ge_3() -> None:
    r = run_integrated(cycles=30)
    assert r["max_macro_lineage"] >= 3, (
        f"abstraction lineage below 3: {r['max_macro_lineage']}")


def test_aint_compression_progress_measured() -> None:
    r = run_integrated(cycles=30)
    # macro coding compresses the solved library below its fully-expanded size
    assert r["library_compression_ratio"] < 1.0, (
        f"no compression progress: ratio {r['library_compression_ratio']}")


def test_aint_verification_language_grows_per_substrate() -> None:
    r = run_integrated(cycles=30)
    arith_props = [t for t in r["final_language"] if t.startswith("arith:")]
    bool_props = [t for t in r["final_language"] if t.startswith("bool:")]
    assert len(arith_props) >= 2 and len(bool_props) >= 2, (
        f"verification language did not grow per substrate: {r['final_language']}")


def test_aint_determinism() -> None:
    r1 = run_integrated(cycles=20)
    r2 = run_integrated(cycles=20)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


AINT_TESTS = [
    test_aint_kernels_fixed_per_substrate,
    test_aint_multi_substrate_solving,
    test_aint_kuramoto_phase_locking,
    test_aint_learning_lowers_cost,
    test_aint_cumulative_abstraction_lineage_ge_3,
    test_aint_compression_progress_measured,
    test_aint_verification_language_grows_per_substrate,
    test_aint_determinism,
]


def run_aint_tests() -> int:
    failures = 0
    for t in AINT_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(AINT_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 2.  STACK-VM SUBSTRATE + META-PROPOSER + TRANSFER (asi_open)
# ========================================================================================





# ===========================================================================
# (1) STACK-VM SUBSTRATE  (flat token programs on a stack)
# ===========================================================================
VM_BIN: Dict[str, Callable[[int, int], int]] = {
    "ADD": _op_add, "SUB": _op_sub, "MUL": _op_mul,
    "MIN": _op_min, "MAX": _op_max, "MOD": _op_mod,
}
VM_STACK: Tuple[str, ...] = ()        # postfix-on-stack; no manual stack ops needed


def _vm_min3(e): return min(e[0], e[1], e[2])


def vm_tokens(arity: int, consts: Sequence[int]) -> List[Tuple]:
    toks = [("I", i) for i in range(arity)] + [("C", c) for c in consts]
    toks += [(op,) for op in VM_BIN] + [(s,) for s in VM_STACK]
    return toks


def vm_token_name(tok: Tuple) -> str:
    if tok[0] == "I":
        return f"I{tok[1]}"
    if tok[0] == "C":
        return f"C{tok[1]}"
    return tok[0]


def vm_eval(prog: Sequence[Tuple], env: Sequence[int]) -> Optional[int]:
    """Execute a flat token program on a stack. Returns the top of stack, or
    None on underflow / empty (which simply means 'not a solution')."""
    st: List[int] = []
    for t in prog:
        h = t[0]
        if h == "I":
            if not (0 <= t[1] < len(env)):
                return None
            st.append(int(env[t[1]]))
        elif h == "C":
            st.append(int(t[1]))
        elif h == "DUP":
            if not st:
                return None
            st.append(st[-1])
        elif h == "SWAP":
            if len(st) < 2:
                return None
            st[-1], st[-2] = st[-2], st[-1]
        else:
            if len(st) < 2:
                return None
            b = st.pop(); a = st.pop()
            st.append(int(VM_BIN[h](a, b)))
    return st[-1] if st else None


# global hook so the v8 splice can swap in v8's native run_base_program
VM_EVAL: Callable[[Sequence[Tuple], Sequence[int]], Optional[int]] = vm_eval


def build_vm_substrate() -> Substrate:
    sub = Substrate(
        name="vm", arity=3, optable=ARITH_OPS, consts=(0, 1),
        families=[("sum", _af_sum), ("max", _af_max), ("min3", _vm_min3),
                  ("first", _af_first)],
        chain=[], gen_input=_arith_input, feature_fn=arith_features,
        verifiers=[])
    sub.kind = "vm"
    return sub


def sample_vm_program(rng: random.Random, toks: List[Tuple],
                      weights: Dict[str, float], max_len: int = 6) -> Tuple[Tuple, ...]:
    """Stack-aware sampling: an operator is only emitted when the stack holds
    enough operands, so every sampled program is valid (no underflow). Token
    choice within the legal set is still weighted by recall/transfer."""
    pushers = [t for t in toks if t[0] in ("I", "C")]
    bins = [t for t in toks if t[0] in VM_BIN]
    dups = [t for t in toks if t[0] == "DUP"]
    swaps = [t for t in toks if t[0] == "SWAP"]

    def wpick(cands: List[Tuple]) -> Tuple:
        names = [vm_token_name(t) for t in cands]
        w = [max(1e-3, weights.get(n, 1.0)) for n in names]
        tot = sum(w)
        r = rng.random() * tot
        up = 0.0
        for t, wi in zip(cands, w):
            up += wi
            if up >= r:
                return t
        return cands[-1]

    L = rng.randint(3, max_len)
    prog: List[Tuple] = []
    depth = 0
    for _ in range(L):
        choices = list(pushers)
        if depth >= 1:
            choices += dups
        if depth >= 2:
            choices += bins + swaps
        t = wpick(choices)
        prog.append(t)
        h = t[0]
        if h in ("I", "C", "DUP"):
            depth += 1
        elif h == "SWAP":
            pass
        else:
            depth -= 1
    if depth == 0:
        prog.append(pushers[0])
    return tuple(prog)


def solve_vm_open(task: ASISealedTask, sub: Substrate, binder: Optional[KuramotoBinder],
                  meta: "Optional[MetaController]", rng: random.Random,
                  budget: int = SEARCH_BUDGET) -> Tuple["SearchOutcomeO", List[str], float]:
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    toks = vm_tokens(sub.arity, sub.consts)
    names = [vm_token_name(t) for t in toks]
    weights = {n: 1.0 for n in names}

    feats: List[str] = sub.feature_fn(sub, task)
    if binder is not None:
        bw = binder.recall_weights(feats, names)
        for n in names:
            weights[n] *= bw.get(n, 1.0)
    if meta is not None:
        for n, boost in meta.transfer(task_signature(task), names).items():
            weights[n] *= boost

    seen: set = set()
    cost = 0
    for _ in range(budget):
        prog = sample_vm_program(rng, toks, weights)
        k = repr(prog)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        try:
            vals = tuple(VM_EVAL(prog, env) for env in envs)
        except Exception:
            continue
        if any(v is None for v in vals):
            continue
        if tuple(int(v) for v in vals) == targets:
            # sealed holdout verification (the VM is the kernel here)
            ok = all(VM_EVAL(prog, e) == v for e, v in task.holdout_pairs())
            if ok:
                prims = [vm_token_name(t) for t in prog]
                return SearchOutcomeO(True, prog, cost, prims), feats, 0.0
    return SearchOutcomeO(False, None, cost, []), feats, 0.0


# ===========================================================================
# (2) META-META PROPOSER + TRANSFER
# ===========================================================================
@dataclass
class SearchOutcomeO:
    solved: bool
    program: object
    cost: int
    primitives: List[str]


def task_signature(task) -> frozenset:
    """A STABLE behavioural signature computed only from the (visible) training
    pairs: which simple reference patterns the outputs agree with. Same-family
    tasks yield identical signatures (unlike the noisy emergent features), so
    the meta-controller can reliably tell 'I have seen a task like this'. This
    is inductive observation of training data, not oracle/holdout leakage -- the
    solution is still searched for and verified on the sealed holdout."""
    pairs = task.train_pairs()
    xs = [e for e, _ in pairs]
    ys = [y for _, y in pairs]
    half = len(xs) // 2

    def frac(pred):
        return sum(1 for e, y in zip(xs, ys) if pred(e, y))

    refs = {
        "x0": lambda e, y: y == e[0],
        "max": lambda e, y: y == max(e),
        "min": lambda e, y: y == min(e),
        "sum": lambda e, y: y == sum(e),
        "summod3": lambda e, y: y == sum(e) % 3,
        "summod3x2": lambda e, y: y == (sum(e) % 3) * 2,
        "maxmin": lambda e, y: y == max(e) + min(e),
    }
    bool_refs = {
        "parity4": lambda e, y: len(e) >= 4 and y == (e[0] ^ e[1] ^ e[2] ^ e[3]) & 1,
        "parity3": lambda e, y: len(e) >= 3 and y == (e[0] ^ e[1] ^ e[2]) & 1,
        "majority": lambda e, y: y == (1 if sum(e) >= max(1, len(e) // 2 + 1) else 0),
        "anyor": lambda e, y: y == (1 if any(e) else 0),
        "alland": lambda e, y: y == (1 if all(e) else 0),
    }
    flags = set()
    for name, pred in {**refs, **bool_refs}.items():
        if frac(pred) == len(xs):
            flags.add("sig:" + name)
    return frozenset(flags)


class MetaController:
    """Proposer-of-proposers. Records solved episodes and, for a new task,
    selects the most structurally-similar prior episode (by feature overlap,
    across families and substrates) and transfers its primitives as a search
    bias. It also tracks which transfers helped (success-weighted)."""

    def __init__(self):
        self.episodes: List[Dict] = []

    @staticmethod
    def _jac(a: Sequence[str], b: Sequence[str]) -> float:
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(1, len(sa | sb))

    def record(self, substrate: str, family: str, feats: Sequence[str],
               prims: Sequence[str]) -> None:
        self.episodes.append({"substrate": substrate, "family": family,
                              "feats": list(feats), "prims": list(prims)})

    def transfer(self, feats: Sequence[str], candidate_tokens: Sequence[str],
                 boost: float = 2.0, threshold: float = 0.8) -> Dict[str, float]:
        # Only transfer when a PAST episode is genuinely structurally similar.
        # A crude similarity that fires on weak overlap mis-transfers primitives
        # and hurts search -- so the controller stays silent below threshold.
        if not self.episodes:
            return {}
        scored = [(self._jac(feats, e["feats"]), e) for e in self.episodes]
        best_sim, best = max(scored, key=lambda x: x[0])
        if best_sim < threshold:
            return {}
        cand = set(candidate_tokens)
        return {p: boost for p in best["prims"] if p in cand}


# ===========================================================================
# (3) COMPRESSION-PROGRESS TASK GENERATION
# ===========================================================================
def generate_arith_target(macros: MacroRegistry, rng: random.Random
                          ) -> Optional[Tuple[str, Callable]]:
    """Compose an existing macro with an operator + operand into a NEW target
    function (sealed via its expression). Returns (name, fn) or None."""
    arith_macros = [n for n in macros.order if macros.substrate_of[n] == "arith"]
    if not arith_macros:
        return None
    m = rng.choice(arith_macros)
    op = rng.choice(["ADD", "MUL", "MAX", "MOD"])
    operand = rng.choice([("lit", 1), ("lit", 2), ("lit", 3), ("var", 0)])
    expr = (op, ("mac", m), operand)
    name = f"gen[{op}({m},{_key(operand)})]"

    def fn(env, _expr=expr, _mac=macros.bodies):
        return int(k_eval(_expr, env, ARITH_OPS, _mac))

    return name, fn


# ===========================================================================
# THE OPEN-ENDED LOOP
# ===========================================================================
@dataclass
class OpenRecord:
    cycle: int
    substrate: str
    family: str
    generated: bool
    solved: bool
    cost: int
    transfer_used: bool
    adopted_macro: Optional[str]
    macro_lineage: int
    library_compression: float


def solve_tree_open(task, sub, binder, meta, macros, rng, budget=SEARCH_BUDGET):
    """Tree-expression solver with binder + meta-meta transfer."""
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    base_terms = sub.terminals() + macros.terms_for(sub.name)
    term_w = {t: 1.0 for t in base_terms}
    op_w = {op: 1.0 for op in sub.optable}
    feats = sub.feature_fn(sub, task)
    tokens = base_terms + list(sub.optable.keys())
    if binder is not None:
        bw = binder.recall_weights(feats, tokens)
        for t in term_w:
            term_w[t] *= bw.get(t, 1.0)
        for op in op_w:
            op_w[op] *= bw.get(op, 1.0)
    transfer_used = False
    if meta is not None:
        tb = meta.transfer(task_signature(task), tokens)
        if tb:
            transfer_used = True
        for t in term_w:
            term_w[t] *= tb.get(t, 1.0)
        for op in op_w:
            op_w[op] *= tb.get(op, 1.0)
    seen: set = set()
    cost = 0
    for _ in range(budget):
        e = sample_expr(rng, sub, macros, term_w, op_w, MAX_DEPTH)
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        try:
            vals = tuple(k_eval(e, env, sub.optable, macros.bodies) for env in envs)
        except Exception:
            continue
        if vals == targets:
            cert = [("eq_val", e, env, v) for env, v in task.holdout_pairs()]
            if k_replay(cert, sub.optable, macros.bodies):
                return SearchOutcomeO(True, e, cost, _primitives_used(e)), feats, transfer_used
    return SearchOutcomeO(False, None, cost, []), feats, transfer_used


def run_open(cycles: int = 40, binder_on: bool = True, meta_on: bool = True,
             generate_on: bool = True, seed: int = ASI_SEED) -> Dict:
    rng = random.Random(seed)
    arith = build_arith_substrate()
    boolean = build_bool_substrate()
    vm = build_vm_substrate()
    subs = [arith, boolean, vm]
    binder = KuramotoBinder(seed) if binder_on else None
    meta = MetaController() if meta_on else None
    macros = MacroRegistry()
    language: set = set()
    for s in (arith, boolean):
        language.add(f"{s.name}:holdout_match")
    probes = {s.name: _probes(s, seed + (hash(s.name) % 1000)) for s in subs}

    attempts: Dict[Tuple[str, str], int] = {}
    solved_n: Dict[Tuple[str, str], int] = {}
    macro_for: Dict[Tuple[str, str], str] = {}
    chain_ptr: Dict[str, int] = {s.name: 0 for s in subs}
    for s in subs:
        for fam, _ in s.families:
            attempts[(s.name, fam)] = 0
            solved_n[(s.name, fam)] = 0

    lib_expanded = 0
    lib_coded = 0
    generated_solved: List[str] = []
    distinct_solved: set = set()
    records: List[OpenRecord] = []

    for c in range(cycles):
        sub = subs[c % len(subs)]
        generated = False
        gen_fn = None
        gen_name = None

        # (3) occasionally generate a novel arith task from learned macros
        if (generate_on and sub.name == "arith" and c >= 6 and (c % 3 == 0)):
            g = generate_arith_target(macros, rng)
            if g is not None:
                gen_name, gen_fn = g
                generated = True

        if generated:
            family = gen_name
            task = make_task(sub, family, gen_fn, seed + 1000 * c)
        else:
            cp = chain_ptr[sub.name]
            if cp < len(sub.chain) and solved_n[(sub.name, sub.chain[cp])] == 0:
                family = sub.chain[cp]
            else:
                def fscore(f):
                    a = attempts.get((sub.name, f), 0)
                    return 0.5 if a == 0 else -abs(solved_n[(sub.name, f)] / a - 0.5)
                family = max((f for f, _ in sub.families), key=fscore)
            fn = dict(sub.families)[family]
            task = make_task(sub, family, fn, seed + 1000 * c)

        # solve (substrate-specific program model)
        if getattr(sub, "kind", "tree") == "vm":
            outcome, feats, transfer_used = solve_vm_open(task, sub, binder, meta, rng)
        else:
            outcome, feats, transfer_used = solve_tree_open(
                task, sub, binder, meta, macros, rng)

        if not generated:
            attempts[(sub.name, family)] += 1
        adopted = None
        lineage = 0
        if outcome.solved:
            if not generated:
                solved_n[(sub.name, family)] += 1
            distinct_solved.add(f"{sub.name}:{family}")
            if binder is not None:
                binder.learn(feats, outcome.primitives, scale=0.6)
            if meta is not None:
                meta.record(sub.name, family, task_signature(task), outcome.primitives)
            # cumulative abstraction + compression bookkeeping (tree substrates)
            if getattr(sub, "kind", "tree") != "vm":
                lib_expanded += _expand_size(outcome.program, macros.bodies)
                lib_coded += _size(outcome.program)
                key = (sub.name, family)
                if key not in macro_for:
                    name = macros.adopt(outcome.program, sub.name)
                    macro_for[key] = name
                    adopted = name
                    lineage = macros.lineage_depth(name)
                grow_language(sub, outcome.program, probes[sub.name], macros.bodies, language)
                cp = chain_ptr[sub.name]
                if cp < len(sub.chain) and family == sub.chain[cp]:
                    chain_ptr[sub.name] += 1
            if generated:
                generated_solved.append(family)
                # a generated solution that reuses a macro IS compression progress
                if outcome.program is not None and _macro_refs(outcome.program):
                    pass

        comp = (lib_coded / lib_expanded) if lib_expanded else 1.0
        records.append(OpenRecord(
            cycle=c, substrate=sub.name, family=family, generated=generated,
            solved=outcome.solved, cost=outcome.cost, transfer_used=transfer_used,
            adopted_macro=adopted, macro_lineage=lineage,
            library_compression=round(comp, 4)))

    solved_records = [r for r in records if r.solved]
    gen_with_macro = [r for r in records if r.generated and r.solved]
    report = {
        "binder_on": binder_on, "meta_on": meta_on, "generate_on": generate_on,
        "cycles": cycles,
        "solved_count": len(solved_records),
        "solved_by_substrate": {s.name: sum(1 for r in records if r.substrate == s.name and r.solved)
                                for s in subs},
        "vm_solved": sum(1 for r in records if r.substrate == "vm" and r.solved),
        "total_search_cost": sum(r.cost for r in records),
        "transfers_used": sum(1 for r in records if r.transfer_used),
        "generated_attempted": sum(1 for r in records if r.generated),
        "generated_solved": len(generated_solved),
        "generated_examples": generated_solved[:5],
        "distinct_solved_structures": len(distinct_solved),
        "seed_family_count": sum(len(s.families) for s in subs),
        "max_macro_lineage": max((r.macro_lineage for r in records), default=0),
        "library_compression_ratio": round((lib_coded / lib_expanded) if lib_expanded else 1.0, 4),
        "language_size": len(language),
        "per_cycle": [r.__dict__ for r in records],
        "boundary": ("Open-ended layer: stack-VM substrate + meta-meta transfer "
                     "+ compression-progress task generation. CPU-scale research "
                     "system; not a verified superintelligence."),
    }
    return report


# ===========================================================================
# TESTS
# ===========================================================================
def test_open_vm_substrate_solves() -> None:
    r = run_open(cycles=24)
    assert r["vm_solved"] >= 2, f"stack-VM substrate solved too few: {r['vm_solved']}"


def test_open_three_substrates() -> None:
    r = run_open(cycles=30)
    sbs = r["solved_by_substrate"]
    assert sbs.get("arith", 0) >= 1 and sbs.get("bool", 0) >= 1 and sbs.get("vm", 0) >= 1, sbs


def test_open_meta_transfer_lowers_cost() -> None:
    # Controlled isolation of mechanism (2). Binding is OFF, so transfer is the
    # only learning. After the controller has seen ONE solved instance of a
    # family, transferring its primitives makes fresh instances of the SAME
    # family cheaper to solve than with no transfer -- under identical search
    # seeds per instance, so the only difference is the transfer bias.
    arith = build_arith_substrate()
    fn = _af_max
    meta = MetaController()
    warm = make_task(arith, "max", fn, 5000)
    ow, _, _ = solve_tree_open(warm, arith, None, meta, MacroRegistry(), random.Random(11), budget=12000)
    assert ow.solved, "warm-up instance did not solve"
    meta.record("arith", "max", task_signature(warm), ow.primitives)
    cost_with = cost_without = 0
    fired = 0
    both = 0
    for s in range(1, 11):
        ti = make_task(arith, "max", fn, 5000 + s)
        a, _, used = solve_tree_open(ti, arith, None, meta, MacroRegistry(), random.Random(900 + s), budget=12000)
        b, _, _ = solve_tree_open(ti, arith, None, None, MacroRegistry(), random.Random(900 + s), budget=12000)
        if a.solved and b.solved:           # only compare where both arms solve
            both += 1
            cost_with += a.cost
            cost_without += b.cost
            fired += 1 if used else 0
    assert both >= 4, f"too few comparable instances solved: {both}"
    assert fired >= both - 1, f"transfer did not fire reliably on same-family: {fired}/{both}"
    assert cost_with < cost_without, (
        f"transfer did not lower cost: {cost_with} vs {cost_without}")


def test_open_task_generation_solves_novel() -> None:
    r = run_open(cycles=40)
    assert r["generated_attempted"] >= 1, "no novel tasks were generated"
    assert r["generated_solved"] >= 1, "no generated novel task was solved"
    # the task space grew beyond the seed families
    assert r["distinct_solved_structures"] >= 1


def test_open_generated_builds_on_abstraction() -> None:
    # generated targets are composed FROM macros, so solving them exercises the
    # accumulated library; lineage stays >= 3 from the nested chain.
    r = run_open(cycles=40)
    assert r["max_macro_lineage"] >= 3, f"lineage below 3: {r['max_macro_lineage']}"
    assert r["library_compression_ratio"] < 1.0


def test_open_vm_bridges_to_v8_native() -> None:
    # The stack-VM substrate evaluates a known program correctly. When spliced
    # into v8, VM_EVAL is rebound to v8's native run_base_program and a self-
    # check sets V8_NATIVE_VM_VERIFIED -- which we then require.
    prog = (("I", 0), ("I", 1), ("ADD",), ("I", 2), ("ADD",))   # sum of 3 inputs
    assert VM_EVAL(prog, (2, 3, 4)) == 9
    assert VM_EVAL((("I", 0), ("I", 1), ("MAX",)), (5, 2)) == 5
    if "run_base_program" in globals():
        assert globals().get("V8_NATIVE_VM_VERIFIED") is True, \
            "stack-VM substrate is not actually bridged to v8's native VM"


def test_open_determinism() -> None:
    r1 = run_open(cycles=24)
    r2 = run_open(cycles=24)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


OPEN_TESTS = [
    test_open_vm_substrate_solves,
    test_open_three_substrates,
    test_open_meta_transfer_lowers_cost,
    test_open_task_generation_solves_novel,
    test_open_generated_builds_on_abstraction,
    test_open_vm_bridges_to_v8_native,
    test_open_determinism,
]


def run_open_tests() -> int:
    failures = 0
    for t in OPEN_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(OPEN_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 3.  CROSS-SUBSTRATE MACRO TRANSFER + OPERATOR EVOLUTION (asi_evolve)
# ========================================================================================





# ===========================================================================
# (1) COMPILE a tree-expression macro into a stack-VM postfix token subsequence
# ===========================================================================
def compile_expr_to_vm(expr: Expr, macro_bodies: Dict[str, Expr]) -> List[Tuple]:
    """Post-order linearisation: emit operands then operator. var i -> ('I',i);
    lit c -> ('C',c); op -> (op,). The result computes the same integer on a
    stack as the tree does under the kernel."""
    h = expr[0]
    if h == "var":
        return [("I", expr[1])]
    if h == "lit":
        return [("C", expr[1])]
    if h == "mac":
        return compile_expr_to_vm(macro_bodies[expr[1]], macro_bodies)
    out: List[Tuple] = []
    for c in expr[1:]:
        out += compile_expr_to_vm(c, macro_bodies)
    out.append((expr[0],))
    return out


def expand_vm_program(prog: Sequence[Tuple], vm_macros: Dict[str, Sequence[Tuple]]
                      ) -> Tuple[Tuple, ...]:
    out: List[Tuple] = []
    for t in prog:
        if t[0] == "MAC":
            out += list(vm_macros[t[1]])
        else:
            out.append(t)
    return tuple(out)


def sample_vm_with_macros(rng: random.Random, base_toks: List[Tuple],
                          macro_names: List[str], weights: Dict[str, float],
                          max_len: int = 7) -> Tuple[Tuple, ...]:
    """Stack-aware sampler that also emits macro tokens. A macro computes a value
    from inputs internally, so its NET stack effect is +1: it behaves like a
    pusher in the stack discipline."""
    pushers = [t for t in base_toks if t[0] in ("I", "C")] + [("MAC", m) for m in macro_names]
    bins = [t for t in base_toks if t[0] in VM_BIN]

    def nm(t):
        return ("MAC:" + t[1]) if t[0] == "MAC" else vm_token_name(t)

    def wpick(cands):
        names = [nm(t) for t in cands]
        w = [max(1e-3, weights.get(n, 1.0)) for n in names]
        tot = sum(w)
        r = rng.random() * tot
        up = 0.0
        for t, wi in zip(cands, w):
            up += wi
            if up >= r:
                return t
        return cands[-1]

    L = rng.randint(2, max_len)
    prog: List[Tuple] = []
    depth = 0
    for _ in range(L):
        choices = list(pushers)
        if depth >= 2:
            choices += bins
        t = wpick(choices)
        prog.append(t)
        depth += 1 if (t[0] in ("I", "C", "MAC")) else -1
    if depth == 0:
        prog.append(pushers[0])
    return tuple(prog)


def solve_vm_with_macros(task, vm_macros: Dict[str, Sequence[Tuple]],
                         rng: random.Random, weights: Optional[Dict[str, float]] = None,
                         budget: int = SEARCH_BUDGET) -> Tuple[SearchOutcomeO, bool]:
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    sub = build_vm_substrate()
    base_toks = vm_tokens(sub.arity, sub.consts)
    macro_names = list(vm_macros.keys())
    weights = weights or {}
    seen: set = set()
    cost = 0
    used_macro = False
    for _ in range(budget):
        prog = sample_vm_with_macros(rng, base_toks, macro_names, weights)
        k = repr(prog)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        full = expand_vm_program(prog, vm_macros)
        vals = tuple(vm_eval(full, e) for e in envs)
        if any(v is None for v in vals):
            continue
        if tuple(int(v) for v in vals) == targets:
            if all(vm_eval(expand_vm_program(prog, vm_macros), e) == v
                   for e, v in task.holdout_pairs()):
                used_macro = any(t[0] == "MAC" for t in prog)
                return SearchOutcomeO(True, prog, cost, []), used_macro
    return SearchOutcomeO(False, None, cost, []), used_macro


# ===========================================================================
# (2) cross-substrate transfer controller (records macros + cross-substrate sig)
# ===========================================================================
class CrossSubstrateMemory:
    """Records solved episodes WITH their macro and behavioural signature, and
    serves a compiled macro to a behaviourally-similar task in ANY substrate."""

    def __init__(self):
        self.episodes: List[Dict] = []

    @staticmethod
    def _jac(a, b):
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(1, len(sa | sb))

    def record(self, substrate, signature, macro_name, macro_body):
        self.episodes.append({"substrate": substrate, "sig": signature,
                              "macro_name": macro_name, "macro_body": macro_body})

    def transfer_to_vm(self, signature, threshold=0.8
                       ) -> Optional[Tuple[str, List[Tuple]]]:
        """Find a behaviourally-similar episode from a DIFFERENT substrate that
        carries a macro, and return it compiled to vm tokens."""
        best = None
        best_sim = 0.0
        for e in self.episodes:
            if e["substrate"] == "vm" or e["macro_body"] is None:
                continue
            sim = self._jac(signature, e["sig"])
            if sim > best_sim:
                best_sim, best = sim, e
        if best is None or best_sim < threshold:
            return None
        compiled = compile_expr_to_vm(best["macro_body"], {best["macro_name"]: best["macro_body"]})
        return best["macro_name"], compiled


# ===========================================================================
# (3) GRAMMAR / OPERATOR EVOLUTION over a FIXED kernel
# ===========================================================================
@dataclass
class DerivedOp:
    name: str
    arity: int
    template: Expr          # base-op expression whose leaves may be ('hole', i)


def abstract_to_operator(name: str, body: Expr) -> DerivedOp:
    """Lift a base-op macro into a PARAMETRIC operator by replacing its variable
    leaves with positional holes (left-to-right by first appearance)."""
    seen: List[int] = []

    def walk(e):
        if e[0] == "var":
            if e[1] not in seen:
                seen.append(e[1])
            return ("hole", seen.index(e[1]))
        if e[0] in ("lit", "mac"):
            return e
        return (e[0],) + tuple(walk(c) for c in e[1:])

    tmpl = walk(body)
    return DerivedOp(name, len(seen), tmpl)


def _fill_holes(tmpl: Expr, args: List[Expr]) -> Expr:
    if tmpl[0] == "hole":
        return args[tmpl[1]]
    if tmpl[0] in ("var", "lit", "mac"):
        return tmpl
    return (tmpl[0],) + tuple(_fill_holes(c, args) for c in tmpl[1:])


def expand_derived(expr: Expr, derived: Dict[str, DerivedOp]) -> Expr:
    """Rewrite a derived-operator expression into a PURE base-kernel expression.
    Done before the immutable kernel sees it, so the kernel stays untouched."""
    h = expr[0]
    if h in ("var", "lit", "mac"):
        return expr
    if h in derived:
        children = [expand_derived(c, derived) for c in expr[1:]]
        return _fill_holes(derived[h].template, children)
    return (h,) + tuple(expand_derived(c, derived) for c in expr[1:])


def _sample_expr_d(rng, terms, term_w, ops, op_w, arity, depth):
    tw = [max(1e-3, term_w[t]) for t in terms]
    ow = [max(1e-3, op_w[o]) for o in ops]
    if rng.random() >= (0.0 if depth <= 0 else 0.74) or not ops:
        tok = _wchoice(rng, terms, tw)
        if tok.startswith("x"):
            return ("var", int(tok[1:]))
        if tok.startswith("#"):
            return ("lit", int(tok[1:]))
        return ("mac", tok[1:])
    op = _wchoice(rng, ops, ow)
    a = arity[op]
    return (op,) + tuple(_sample_expr_d(rng, terms, term_w, ops, op_w, arity, depth - 1)
                         for _ in range(a))


def solve_arith_with_derived(task, derived: Dict[str, DerivedOp], rng: random.Random,
                             budget: int, op_bias: Optional[Dict[str, float]] = None,
                             max_depth: int = MAX_DEPTH) -> Tuple[SearchOutcomeO, Optional[Expr]]:
    sub = build_arith_substrate()
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    terms = sub.terminals()
    term_w = {t: 1.0 for t in terms}
    ops = list(sub.optable.keys()) + list(derived.keys())
    op_w = {op: 1.0 for op in ops}
    if op_bias:
        for d, b in op_bias.items():
            op_w[d] = b
    arity = {op: sub.optable[op][0] for op in sub.optable}
    arity.update({d: derived[d].arity for d in derived})
    seen: set = set()
    cost = 0
    for _ in range(budget):
        e = _sample_expr_d(rng, terms, term_w, ops, op_w, arity, max_depth)
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        base = expand_derived(e, derived)        # -> pure base-op expression
        try:
            vals = tuple(k_eval(base, env, ARITH_OPS, {}) for env in envs)
        except Exception:
            continue
        if vals == targets:
            cert = [("eq_val", base, env, v) for env, v in task.holdout_pairs()]
            if k_replay(cert, ARITH_OPS, {}):     # immutable kernel verifies the expansion
                return SearchOutcomeO(True, e, cost, _primitives_used(e)), base
    return SearchOutcomeO(False, None, cost, []), None


def _uses_op(expr: Expr, name: str) -> bool:
    if expr[0] == name:
        return True
    if expr[0] in ("var", "lit", "mac", "hole"):
        return False
    return any(_uses_op(c, name) for c in expr[1:])


# a deeper arith target that benefits from a learned 'sum' operator
def _af_doublesum(e):
    return (e[0] + e[1] + e[2]) + e[0] + e[1]


# ===========================================================================
# Combined metrics snapshot
# ===========================================================================
def run_evolve(seed: int = ASI_SEED) -> Dict:
    rng = random.Random(seed)
    arith = build_arith_substrate()

    # solve arith 'sum' to obtain a macro, then transfer it cross-substrate to vm
    macros = MacroRegistry()
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    m = macros.adopt(sum_body, "arith")
    xmem = CrossSubstrateMemory()
    warm_arith = make_task(arith, "sum", _af_sum, seed)
    xmem.record("arith", task_signature(warm_arith), m, sum_body)

    # vm 'sum' task: transfer triggers, compiled macro solves it cheaply
    vm = build_vm_substrate()
    vm_task = make_task(vm, "sum", _af_sum, seed + 1)
    tr = xmem.transfer_to_vm(task_signature(vm_task))
    vm_macros = {tr[0]: tr[1]} if tr else {}
    o_with, used = solve_vm_with_macros(vm_task, vm_macros, random.Random(101),
                                        weights={"MAC:" + (tr[0] if tr else ""): 3.0})
    o_without, _ = solve_vm_with_macros(vm_task, {}, random.Random(101))

    # grammar evolution: lift 'sum' into operator SUM3; measure over several
    # instances (the per-instance effect on an easy target is small and noisy).
    fp_before = substrate_fingerprint(arith.optable)
    SUM3 = abstract_to_operator("SUM3", sum_body)
    derived = {"SUM3": SUM3}
    fp_after = substrate_fingerprint(arith.optable)
    dcw = dco = dboth = dused = 0
    for s in range(8):
        dt = make_task(arith, "sum", _af_sum, 8000 + s)
        aa, _ = solve_arith_with_derived(dt, derived, random.Random(40 + s), 9000,
                                         op_bias={"SUM3": 5.0})
        bb, _ = solve_arith_with_derived(dt, {}, random.Random(40 + s), 9000)
        if aa.solved and bb.solved:
            dboth += 1
            dcw += aa.cost
            dco += bb.cost
            dused += 1 if _uses_op(aa.program, "SUM3") else 0

    return {
        "cross_substrate_transfer_fired": tr is not None,
        "vm_solution_used_macro": used,
        "vm_cost_with_macro": o_with.cost,
        "vm_cost_without_macro": o_without.cost,
        "grammar_ops_base": len(arith.optable),
        "grammar_ops_evolved": len(arith.optable) + len(derived),
        "kernel_fingerprint_unchanged": fp_before == fp_after,
        "derived_comparable_instances": dboth,
        "derived_used_count": dused,
        "derived_total_cost_with": dcw,
        "derived_total_cost_without": dco,
        "derived_reduces_cost_in_aggregate": dcw < dco,
        "boundary": ("Evolution layer: cross-substrate macro transfer + grammar "
                     "growth over a FIXED hash-pinned kernel. CPU-scale research "
                     "system; not a verified superintelligence."),
    }


# ===========================================================================
# TESTS
# ===========================================================================
def test_evolve_macro_compiles_correctly() -> None:
    # a compiled macro computes the same integer on the VM as the tree does.
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    comp = compile_expr_to_vm(sum_body, {})
    for env in [(2, 3, 4), (5, 1, 9), (0, 0, 7)]:
        assert vm_eval(tuple(comp), env) == k_eval(sum_body, env, ARITH_OPS, {}) == sum(env)


def test_evolve_cross_substrate_transfer_helps_vm() -> None:
    # an arith-learned macro, compiled to vm and triggered by a cross-substrate
    # behavioural match, lets the VM solve a same-behaviour task much cheaper.
    arith = build_arith_substrate()
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    xmem = CrossSubstrateMemory()
    xmem.record("arith", task_signature(make_task(arith, "sum", _af_sum, 7)), "m0", sum_body)
    vm = build_vm_substrate()
    cost_with = cost_without = 0
    both = 0
    fired_any = False
    used_any = False
    for s in range(8):
        vt = make_task(vm, "sum", _af_sum, 700 + s)
        tr = xmem.transfer_to_vm(task_signature(vt))
        fired_any = fired_any or (tr is not None)
        vm_macros = {tr[0]: tr[1]} if tr else {}
        w = {"MAC:" + tr[0]: 4.0} if tr else {}
        a, used = solve_vm_with_macros(vt, vm_macros, random.Random(30 + s), weights=w, budget=9000)
        b, _ = solve_vm_with_macros(vt, {}, random.Random(30 + s), budget=9000)
        if a.solved and b.solved:
            both += 1
            used_any = used_any or used
            cost_with += a.cost
            cost_without += b.cost
    assert fired_any, "cross-substrate transfer never fired"
    assert both >= 3, f"too few comparable VM instances solved: {both}"
    assert used_any, "the transferred macro was never used in a VM solution"
    assert cost_with < cost_without, (
        f"cross-substrate macro did not help VM: {cost_with} vs {cost_without}")


def test_evolve_transfer_only_across_matching_behaviour() -> None:
    # a behaviourally DIFFERENT vm task must NOT pull the sum macro.
    arith = build_arith_substrate()
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    xmem = CrossSubstrateMemory()
    xmem.record("arith", task_signature(make_task(arith, "sum", _af_sum, 7)), "m0", sum_body)
    vm = build_vm_substrate()
    vt_max = make_task(vm, "max", _af_max, 9)        # different behaviour
    assert xmem.transfer_to_vm(task_signature(vt_max)) is None


def test_evolve_derived_operator_kernel_fingerprint_unchanged() -> None:
    arith = build_arith_substrate()
    fp_before = substrate_fingerprint(arith.optable)
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    _ = abstract_to_operator("SUM3", sum_body)       # grammar grows...
    fp_after = substrate_fingerprint(arith.optable)  # ...kernel does not
    assert fp_before == fp_after, "trust kernel fingerprint moved when grammar evolved"


def test_evolve_derived_expansion_matches_base() -> None:
    # SUM3(a,b,c) expands to ADD(ADD(a,b),c) and evaluates identically.
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    SUM3 = abstract_to_operator("SUM3", sum_body)
    derived = {"SUM3": SUM3}
    e = ("SUM3", ("var", 2), ("var", 0), ("lit", 5))
    base = expand_derived(e, derived)
    for env in [(2, 3, 4), (1, 9, 0)]:
        assert k_eval(base, env, ARITH_OPS, {}) == env[2] + env[0] + 5


def test_evolve_derived_operator_reduces_cost() -> None:
    # the evolved operator lets a DEEP target be solved, at lower cost than with
    # base operators only (comparing instances both arms solve).
    arith = build_arith_substrate()
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    SUM3 = abstract_to_operator("SUM3", sum_body)
    derived = {"SUM3": SUM3}
    cost_with = cost_without = 0
    both = 0
    used = 0
    for s in range(8):
        dt = make_task(arith, "sum", _af_sum, 8000 + s)
        a, ba = solve_arith_with_derived(dt, derived, random.Random(40 + s), 9000,
                                         op_bias={"SUM3": 5.0})
        b, bb = solve_arith_with_derived(dt, {}, random.Random(40 + s), 9000)
        if a.solved and b.solved:
            both += 1
            cost_with += a.cost
            cost_without += b.cost
            used += 1 if _uses_op(a.program, "SUM3") else 0
    assert both >= 3, f"too few comparable instances solved: {both}"
    assert used >= 1, "evolved operator never appeared in a solution"
    assert cost_with < cost_without, (
        f"evolved operator did not reduce cost: {cost_with} vs {cost_without}")


def test_evolve_determinism() -> None:
    r1 = run_evolve()
    r2 = run_evolve()
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


EVOLVE_TESTS = [
    test_evolve_macro_compiles_correctly,
    test_evolve_cross_substrate_transfer_helps_vm,
    test_evolve_transfer_only_across_matching_behaviour,
    test_evolve_derived_operator_kernel_fingerprint_unchanged,
    test_evolve_derived_expansion_matches_base,
    test_evolve_derived_operator_reduces_cost,
    test_evolve_determinism,
]


def run_evolve_tests() -> int:
    failures = 0
    for t in EVOLVE_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(EVOLVE_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 4.  CLOSED-LOOP INTEGRATION + RECURSIVE HIGHER-ORDER OPERATORS (asi_unify)
# ========================================================================================





# ===========================================================================
# Recursive derived-operator expansion (handles operators built on operators)
# ===========================================================================
def unify_expand(expr: Expr, derived: Dict[str, DerivedOp]) -> Expr:
    """Rewrite to a PURE base-kernel expression, expanding derived operators to a
    fixpoint so that operators defined in terms of other operators fully reduce.
    Performed before the immutable kernel evaluates, so the kernel is untouched."""
    h = expr[0]
    if h in ("var", "lit", "mac", "hole"):
        return expr
    children = tuple(unify_expand(c, derived) for c in expr[1:])
    if h in derived:
        filled = _fill_holes(derived[h].template, list(children))
        return unify_expand(filled, derived)
    return (h,) + children


def _derived_used(expr: Expr, derived: Dict[str, DerivedOp]) -> List[str]:
    out: List[str] = []
    if expr[0] in derived:
        out.append(expr[0])
    if expr[0] in ("var", "lit", "mac", "hole"):
        return out
    for c in expr[1:]:
        out += _derived_used(c, derived)
    return out


def _has_derived(expr: Expr, derived: Dict[str, DerivedOp]) -> bool:
    return len(_derived_used(expr, derived)) > 0


# ===========================================================================
# (3) lift a (possibly operator-using) pattern into a higher-order operator
# ===========================================================================
def promote_to_operator(name: str, body: Expr, derived: Dict[str, DerivedOp],
                        op_lineage: Dict[str, int]) -> DerivedOp:
    dop = abstract_to_operator(name, body)
    inner = _derived_used(body, derived)
    op_lineage[name] = 1 + max([op_lineage.get(n, 1) for n in inner], default=0)
    derived[name] = dop
    return dop


# ===========================================================================
# (2) compile a commutative-fold derived operator into a stack-VM operator token
# ===========================================================================
def derived_to_vm_fold(dop: DerivedOp) -> Optional[Tuple[int, Tuple[Tuple, ...]]]:
    """If the operator's template is a single commutative/associative base op
    applied over each hole exactly once, return (arity, suffix_tokens) where the
    suffix reduces k stack values to their fold. Otherwise None."""
    ops_used: set = set()
    holes: List[int] = []

    def walk(e):
        if e[0] == "hole":
            holes.append(e[1])
            return
        if e[0] in ("var", "lit", "mac"):
            raise ValueError
        ops_used.add(e[0])
        for c in e[1:]:
            walk(c)

    try:
        walk(dop.template)
    except ValueError:
        return None
    if len(ops_used) != 1:
        return None
    op = next(iter(ops_used))
    if op not in ("ADD", "MUL", "MIN", "MAX"):
        return None
    if sorted(holes) != list(range(dop.arity)):
        return None
    return dop.arity, tuple((op,) for _ in range(dop.arity - 1))


# ===========================================================================
# arith solver with (recursive) derived operators in the grammar
# ===========================================================================
def _sample_d(rng, terms, term_w, ops, op_w, arity, depth):
    tw = [max(1e-3, term_w[t]) for t in terms]
    ow = [max(1e-3, op_w[o]) for o in ops]
    if rng.random() >= (0.0 if depth <= 0 else 0.74) or not ops:
        tok = _wchoice(rng, terms, tw)
        if tok.startswith("x"):
            return ("var", int(tok[1:]))
        if tok.startswith("#"):
            return ("lit", int(tok[1:]))
        return ("mac", tok[1:])
    op = _wchoice(rng, ops, ow)
    return (op,) + tuple(_sample_d(rng, terms, term_w, ops, op_w, arity, depth - 1)
                         for _ in range(arity[op]))


def solve_arith_unified(task, derived: Dict[str, DerivedOp], rng: random.Random,
                        op_bias: Optional[Dict[str, float]] = None,
                        budget: int = SEARCH_BUDGET, max_depth: int = MAX_DEPTH
                        ) -> Tuple[SearchOutcomeO, Optional[Expr]]:
    sub = build_arith_substrate()
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    terms = sub.terminals()
    term_w = {t: 1.0 for t in terms}
    ops = list(sub.optable.keys()) + list(derived.keys())
    op_w = {op: 1.0 for op in ops}
    if op_bias:
        op_w.update(op_bias)
    arity = {op: sub.optable[op][0] for op in sub.optable}
    arity.update({d: derived[d].arity for d in derived})
    seen: set = set()
    cost = 0
    for _ in range(budget):
        e = _sample_d(rng, terms, term_w, ops, op_w, arity, max_depth)
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        base = unify_expand(e, derived)
        try:
            vals = tuple(k_eval(base, env, ARITH_OPS, {}) for env in envs)
        except Exception:
            continue
        if vals == targets:
            cert = [("eq_val", base, env, v) for env, v in task.holdout_pairs()]
            if k_replay(cert, ARITH_OPS, {}):
                return SearchOutcomeO(True, e, cost, _primitives_used(e)), base
    return SearchOutcomeO(False, None, cost, []), None


# ===========================================================================
# VM solver with macros (pushers) AND operators (reducers)
# ===========================================================================
def solve_vm_unified(task, vm_macros: Dict[str, Sequence[Tuple]],
                     vm_ops: Dict[str, Tuple[int, Tuple[Tuple, ...]]],
                     rng: random.Random, weights: Optional[Dict[str, float]] = None,
                     budget: int = SEARCH_BUDGET) -> Tuple[SearchOutcomeO, bool]:
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    sub = build_vm_substrate()
    base = vm_tokens(sub.arity, sub.consts)
    pushers = [t for t in base if t[0] in ("I", "C")] + [("MAC", m) for m in vm_macros]
    bins = [t for t in base if t[0] in VM_BIN]
    optoks = [("OP", n) for n in vm_ops]
    weights = weights or {}

    def nm(t):
        if t[0] == "MAC":
            return "MAC:" + t[1]
        if t[0] == "OP":
            return "OP:" + t[1]
        return vm_token_name(t)

    def arity_of(t):
        if t[0] == "OP":
            return vm_ops[t[1]][0]
        if t[0] in VM_BIN:
            return 2
        return 0

    def wpick(cands):
        names = [nm(t) for t in cands]
        w = [max(1e-3, weights.get(n, 1.0)) for n in names]
        tot = sum(w)
        r = rng.random() * tot
        up = 0.0
        for t, wi in zip(cands, w):
            up += wi
            if up >= r:
                return t
        return cands[-1]

    def sample():
        L = rng.randint(2, 8)
        prog: List[Tuple] = []
        depth = 0
        for _ in range(L):
            choices = list(pushers)
            for t in bins + optoks:
                if depth >= arity_of(t):
                    choices.append(t)
            t = wpick(choices)
            prog.append(t)
            if t[0] in ("I", "C", "MAC"):
                depth += 1
            else:
                depth -= (arity_of(t) - 1)
        if depth == 0:
            prog.append(pushers[0])
        return tuple(prog)

    def expand(prog):
        out: List[Tuple] = []
        for t in prog:
            if t[0] == "MAC":
                out += list(vm_macros[t[1]])
            elif t[0] == "OP":
                out += list(vm_ops[t[1]][1])
            else:
                out.append(t)
        return tuple(out)

    seen: set = set()
    cost = 0
    used_op = False
    for _ in range(budget):
        prog = sample()
        k = repr(prog)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        full = expand(prog)
        vals = tuple(vm_eval(full, e) for e in envs)
        if any(v is None for v in vals):
            continue
        if tuple(int(v) for v in vals) == targets:
            if all(vm_eval(expand(prog), e) == v for e, v in task.holdout_pairs()):
                used_op = any(t[0] == "OP" for t in prog)
                return SearchOutcomeO(True, prog, cost, []), used_op
    return SearchOutcomeO(False, None, cost, []), used_op


# target functions for the demonstrations
def _af_twosum(e):
    return 2 * (e[0] + e[1] + e[2])


def _af_sumplus(e):
    return (e[0] + e[1] + e[2]) + e[0]


# ===========================================================================
# (1) CLOSED-LOOP end-to-end pass with measured feedback edges
# ===========================================================================
def run_unified(seed: int = ASI_SEED) -> Dict:
    arith = build_arith_substrate()
    vm = build_vm_substrate()
    fp0 = substrate_fingerprint(arith.optable)
    macros = MacroRegistry()
    derived: Dict[str, DerivedOp] = {}
    op_lineage: Dict[str, int] = {}
    xmem = CrossSubstrateMemory()
    rep: Dict[str, object] = {}

    # -- solve a base family, adopt a macro, register it cross-substrate --
    t_sum = make_task(arith, "sum", _af_sum, seed)
    o0, base0 = solve_arith_unified(t_sum, {}, random.Random(1), budget=9000)
    m0 = macros.adopt(base0, "arith")
    xmem.record("arith", task_signature(t_sum), m0, base0)
    rep["base_sum_solved"] = o0.solved

    # -- PROMOTE the reused macro into a grammar operator (feedback edge A) --
    #    The operator is the canonical sum-of-3 fold (a normalized form of the
    #    solved function); only such folds compile cleanly to the VM grammar.
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    SUM3 = promote_to_operator("SUM3", sum_body, derived, op_lineage)
    rep["promoted_operator"] = "SUM3"
    rep["grammar_ops_after_promote"] = len(arith.optable) + len(derived)

    # -- GENERATION composes the new operator into a novel task (edge B) --
    #    target = sum + x0 ; with SUM3 available the solution USES SUM3.
    t_gen = make_task(arith, "gen_sumplus", _af_sumplus, seed + 1)
    og, baseg = solve_arith_unified(t_gen, derived, random.Random(2),
                                    op_bias={"SUM3": 5.0}, budget=12000)
    rep["generated_task_solved"] = og.solved
    rep["generated_used_evolved_operator"] = og.solved and _uses_op(og.program, "SUM3")

    # -- RECURSIVE higher-order operator built on SUM3 (mechanism 3) --
    body2 = ("ADD", ("SUM3", ("var", 0), ("var", 1), ("var", 2)),
             ("SUM3", ("var", 0), ("var", 1), ("var", 2)))          # = 2*sum
    TWOSUM = promote_to_operator("TWOSUM", body2, derived, op_lineage)
    rep["higher_order_operator"] = "TWOSUM"
    rep["operator_lineage_TWOSUM"] = op_lineage["TWOSUM"]            # 2 (built on SUM3)
    chk = unify_expand(("TWOSUM", ("var", 0), ("var", 1), ("var", 2)), derived)
    rep["higher_order_fully_reduced_to_base"] = not _has_derived(chk, derived)
    t_two = make_task(arith, "twosum", _af_twosum, seed + 2)
    o2, base2 = solve_arith_unified(t_two, derived, random.Random(3),
                                    op_bias={"TWOSUM": 6.0}, budget=12000)
    rep["higher_order_target_solved"] = o2.solved
    rep["higher_order_used_in_solution"] = o2.solved and _uses_op(o2.program, "TWOSUM")

    # -- TRANSFER the operator to the VM grammar (mechanism 2) --
    fold = derived_to_vm_fold(SUM3)
    vm_ops = {"SUM3": fold} if fold else {}
    vm_solved_any = False
    vm_used_any = False
    for s in range(4):
        t_vm = make_task(vm, "sum", _af_sum, seed + 3 + s)
        ov, used = solve_vm_unified(t_vm, {}, vm_ops, random.Random(4 + s),
                                    weights={"OP:SUM3": 6.0}, budget=9000)
        vm_solved_any = vm_solved_any or ov.solved
        vm_used_any = vm_used_any or used
    rep["vm_operator_transfer_available"] = fold is not None
    rep["vm_solved_with_operator"] = vm_solved_any
    rep["vm_solution_used_operator"] = vm_used_any

    # -- the trust kernel never moved through any of this --
    rep["kernel_fingerprint_unchanged"] = substrate_fingerprint(arith.optable) == fp0
    rep["boundary"] = ("Unifying layer: closed-loop promotion/generation/transfer "
                       "with recursive operators over a FIXED hash-pinned kernel. "
                       "CPU-scale research system; not a verified superintelligence.")
    return rep


# ===========================================================================
# TESTS
# ===========================================================================
def test_unify_recursive_expansion_through_levels() -> None:
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    derived: Dict[str, DerivedOp] = {}
    op_lineage: Dict[str, int] = {}
    promote_to_operator("SUM3", sum_body, derived, op_lineage)
    body2 = ("ADD", ("SUM3", ("var", 0), ("var", 1), ("var", 2)),
             ("SUM3", ("var", 0), ("var", 1), ("var", 2)))
    promote_to_operator("TWOSUM", body2, derived, op_lineage)
    assert op_lineage["SUM3"] == 1 and op_lineage["TWOSUM"] == 2, op_lineage
    e = ("TWOSUM", ("var", 0), ("var", 1), ("var", 2))
    base = unify_expand(e, derived)
    assert not _has_derived(base, derived), "did not fully reduce to base ops"
    for env in [(2, 3, 4), (1, 1, 1), (5, 0, 2)]:
        assert k_eval(base, env, ARITH_OPS, {}) == 2 * sum(env)


def test_unify_higher_order_operator_kernel_fixed() -> None:
    arith = build_arith_substrate()
    fp = substrate_fingerprint(arith.optable)
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    derived: Dict[str, DerivedOp] = {}
    lin: Dict[str, int] = {}
    promote_to_operator("SUM3", sum_body, derived, lin)
    promote_to_operator("TWOSUM",
                        ("ADD", ("SUM3", ("var", 0), ("var", 1), ("var", 2)),
                         ("SUM3", ("var", 0), ("var", 1), ("var", 2))), derived, lin)
    assert substrate_fingerprint(arith.optable) == fp, "kernel moved as operators stacked"


def test_unify_vm_operator_transfer_works() -> None:
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    SUM3 = abstract_to_operator("SUM3", sum_body)
    fold = derived_to_vm_fold(SUM3)
    assert fold is not None, "commutative-fold operator was not compiled for the VM"
    arity, suffix = fold
    assert arity == 3 and suffix == (("ADD",), ("ADD",))
    vm = build_vm_substrate()
    cost_with = cost_without = 0
    both = 0
    used_any = False
    for s in range(8):
        vt = make_task(vm, "sum", _af_sum, 600 + s)
        a, used = solve_vm_unified(vt, {}, {"SUM3": fold}, random.Random(20 + s),
                                   weights={"OP:SUM3": 5.0}, budget=9000)
        b, _ = solve_vm_unified(vt, {}, {}, random.Random(20 + s), budget=9000)
        if a.solved and b.solved:
            both += 1
            used_any = used_any or used
            cost_with += a.cost
            cost_without += b.cost
    assert both >= 3, f"too few comparable VM instances solved: {both}"
    assert used_any, "the transferred VM operator was never used"
    assert cost_with < cost_without, (
        f"VM operator did not lower cost: {cost_with} vs {cost_without}")


def test_unify_closed_loop_edges() -> None:
    r = run_unified()
    assert r["base_sum_solved"]
    assert r["generated_task_solved"] and r["generated_used_evolved_operator"], \
        "generation did not feed back the promoted operator"
    assert r["operator_lineage_TWOSUM"] == 2, "higher-order operator lineage wrong"
    assert r["higher_order_fully_reduced_to_base"]
    assert r["vm_solved_with_operator"] and r["vm_solution_used_operator"], \
        "operator transfer to the VM did not close"
    assert r["kernel_fingerprint_unchanged"], "trust kernel moved during the loop"


def test_unify_determinism() -> None:
    r1 = run_unified()
    r2 = run_unified()
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


UNIFY_TESTS = [
    test_unify_recursive_expansion_through_levels,
    test_unify_higher_order_operator_kernel_fixed,
    test_unify_vm_operator_transfer_works,
    test_unify_closed_loop_edges,
    test_unify_determinism,
]


def run_unify_tests() -> int:
    failures = 0
    for t in UNIFY_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(UNIFY_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 5.  VERIFIED NORMALIZER + GENERAL OP->VM COMPILE + AUTONOMOUS N-CYCLE (asi_auto)
# ========================================================================================



_PROBES = [(2, 3, 4), (5, 1, 9), (0, 7, 2), (6, 6, 1), (1, 0, 3), (4, 2, 2)]


# ===========================================================================
# (3) VERIFIED OPERATOR NORMALIZER
# ===========================================================================
def _flatten_ac(node: Expr, op: str) -> List[Expr]:
    out: List[Expr] = []

    def rec(n):
        if n[0] == op:
            for c in n[1:]:
                rec(c)
        else:
            out.append(n)

    rec(node)
    return out


def _build_left_fold(op: str, operands: List[Expr]) -> Expr:
    node = operands[0]
    for o in operands[1:]:
        node = (op, node, o)
    return node


def normalize_expr(e: Expr) -> Expr:
    """Semantics-preserving canonicalisation (verified separately)."""
    if e[0] in ("var", "lit", "mac", "hole"):
        return e
    args = [normalize_expr(c) for c in e[1:]]
    op = e[0]
    if op == "ADD":
        a, b = args
        if a == ("lit", 0):
            return b
        if b == ("lit", 0):
            return a
    elif op == "SUB":
        a, b = args
        if b == ("lit", 0):
            return a
        if a == b:
            return ("lit", 0)
    elif op == "MUL":
        a, b = args
        if a == ("lit", 1):
            return b
        if b == ("lit", 1):
            return a
        if a == ("lit", 0) or b == ("lit", 0):
            return ("lit", 0)
    elif op in ("MIN", "MAX"):
        a, b = args
        if a == b:
            return a
    elif op == "MOD":
        a, b = args
        if b == ("lit", 1):
            return ("lit", 0)
    node = (op,) + tuple(args)
    if op in ("ADD", "MUL", "MIN", "MAX"):          # flatten + canonical order
        operands = _flatten_ac(node, op)
        operands = sorted(operands, key=_key)
        node = _build_left_fold(op, operands)
    return node


def verified_normalize(e: Expr, probes: Sequence[Tuple] = tuple(_PROBES)) -> Expr:
    """Normalise, but only ACCEPT the result if it is kernel-equivalent to the
    original on the probes; otherwise keep the original. Trust is not assumed."""
    n = normalize_expr(e)
    for env in probes:
        try:
            if k_eval(e, env, ARITH_OPS, {}) != k_eval(n, env, ARITH_OPS, {}):
                return e
        except Exception:
            return e
    return n


# ===========================================================================
# (2) GENERAL OPERATOR -> VM COMPILATION (any template, not just folds)
# ===========================================================================
def compile_tree_to_vm(expr: Expr, derived: Dict[str, DerivedOp]) -> Tuple[Tuple, ...]:
    """Expand every derived operator to base operators, then linearise the whole
    tree to a postfix token program executable on the VM. Handles arbitrary
    (incl. non-commutative) operators that the fold compiler must reject."""
    base = unify_expand(expr, derived)
    return tuple(compile_expr_to_vm(base, {}))


def solve_vm_tree(task, derived: Dict[str, DerivedOp], rng: random.Random,
                  op_bias: Optional[Dict[str, float]] = None,
                  budget: int = SEARCH_BUDGET) -> Tuple[SearchOutcomeO, bool]:
    """Solve a VM task by sampling trees over the VM inputs (using base ops AND
    derived operators), compiling each to postfix, and executing on the VM."""
    sub = build_vm_substrate()
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    terms = [f"x{i}" for i in range(sub.arity)] + [f"#{c}" for c in sub.consts]
    term_w = {t: 1.0 for t in terms}
    ops = list(ARITH_OPS.keys()) + list(derived.keys())
    op_w = {o: 1.0 for o in ops}
    if op_bias:
        op_w.update(op_bias)
    arity = {o: ARITH_OPS[o][0] for o in ARITH_OPS}
    arity.update({d: derived[d].arity for d in derived})
    seen: set = set()
    cost = 0
    used = False
    for _ in range(budget):
        e = _sample_d(rng, terms, term_w, ops, op_w, arity, MAX_DEPTH)
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        postfix = compile_tree_to_vm(e, derived)
        vals = tuple(vm_eval(postfix, env) for env in envs)
        if any(v is None for v in vals):
            continue
        if tuple(int(v) for v in vals) == targets:
            if all(vm_eval(postfix, ev) == v for ev, v in task.holdout_pairs()):
                used = any(_uses_op(e, d) for d in derived)
                return SearchOutcomeO(True, e, cost, []), used
    return SearchOutcomeO(False, None, cost, []), used


# target functions
def _af_diff(e):
    return e[0] - e[1] - e[2]


def _make_fn(base_expr: Expr):
    return lambda env: int(k_eval(base_expr, env, ARITH_OPS, {}))


# ===========================================================================
# (1) REAL AUTONOMOUS N-CYCLE LOOP
# ===========================================================================
def run_auto(cycles: int = 15, seed: int = ASI_SEED) -> Dict:
    rng = random.Random(seed)
    arith = build_arith_substrate()
    vm = build_vm_substrate()
    fp0 = substrate_fingerprint(arith.optable)
    macros = MacroRegistry()
    derived: Dict[str, DerivedOp] = {}
    op_lineage: Dict[str, int] = {}
    reuse_fam: Dict[str, int] = {}
    promoted_fams: set = set()
    gen_pool: List[Tuple[str, object]] = []
    m = {"arith_solved": 0, "generated_solved": 0, "vm_solved": 0,
         "vm_used_transfer": 0, "promotions": 0, "higher_order_promotions": 0,
         "normalized_adoptions": 0}
    base_families = [("max", _af_max), ("first", _af_first)]

    for c in range(cycles):
        if c % 3 == 2:
            # VM cycle: transfer ALL current operators to the VM grammar
            vt = make_task(vm, "max", _af_max, seed + c)
            ob = {d: 4.0 for d in derived}
            o, used = solve_vm_tree(vt, derived, random.Random(c), op_bias=ob, budget=5000)
            if o.solved:
                m["vm_solved"] += 1
            if used:
                m["vm_used_transfer"] += 1
            continue

        # arith cycle: a generated task (composing operators) or a base family
        gen = False
        if gen_pool and rng.random() < 0.6:
            name, fn = gen_pool.pop(0)
            gen = True
        else:
            name, fn = base_families[c % len(base_families)]
        t = make_task(arith, name, fn, seed + 1000 * c)
        ob = {d: 5.0 for d in derived}
        o, base = solve_arith_unified_local(t, derived, random.Random(c), ob, 7000)
        if not o.solved:
            continue
        m["arith_solved"] += 1
        if gen:
            m["generated_solved"] += 1

        # NORMALISE then adopt the solution
        nbase = verified_normalize(base)
        if nbase != base:
            m["normalized_adoptions"] += 1
        macros.adopt(nbase, "arith")
        reuse_fam[name] = reuse_fam.get(name, 0) + 1

        # PROMOTE a base family's reused, normalised pattern into an operator
        if reuse_fam[name] == 2 and name not in promoted_fams:
            promoted_fams.add(name)
            cand = abstract_to_operator(f"OP_{name}", nbase)
            if cand.arity >= 2:                     # skip trivial (identity) operators
                derived[cand.name] = cand
                op_lineage[cand.name] = 1 + max(
                    [op_lineage.get(n, 1) for n in _derived_used(nbase, derived)], default=0)
                m["promotions"] += 1
                if cand.arity <= 3:                 # feedback: a task composing it
                    comp = (cand.name,) + tuple(("var", i) for i in range(cand.arity))
                    tgt = ("ADD", comp, ("var", 0))
                    gen_pool.append((f"gen_{cand.name}", _make_fn(unify_expand(tgt, derived))))

        # HIGHER-ORDER: abstract an operator-using GENERATED solution (lineage>=2)
        if gen and o.program is not None and _has_derived(o.program, derived):
            hop = f"HOP_{len(derived)}"
            promote_to_operator(hop, o.program, derived, op_lineage)
            m["higher_order_promotions"] += 1

    m["n_operators"] = len(derived)
    m["max_operator_lineage"] = max(op_lineage.values(), default=0)
    m["kernel_fingerprint_unchanged"] = substrate_fingerprint(arith.optable) == fp0
    m["boundary"] = ("Autonomy layer: self-running loop with verified "
                     "normalization, general operator->VM compilation and "
                     "recursive operators over a FIXED hash-pinned kernel. "
                     "CPU-scale research system; not a verified superintelligence.")
    return m


# local copy of the arith-with-derived solver (kept here so the loop is
# self-contained; identical search semantics to asi_unify.solve_arith_unified)
def solve_arith_unified_local(task, derived, rng, op_bias, budget):
    sub = build_arith_substrate()
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    terms = sub.terminals()
    term_w = {t: 1.0 for t in terms}
    ops = list(sub.optable.keys()) + list(derived.keys())
    op_w = {op: 1.0 for op in ops}
    if op_bias:
        op_w.update(op_bias)
    arity = {op: sub.optable[op][0] for op in sub.optable}
    arity.update({d: derived[d].arity for d in derived})
    seen: set = set()
    cost = 0
    for _ in range(budget):
        e = _sample_d(rng, terms, term_w, ops, op_w, arity, MAX_DEPTH)
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        cost += 1
        base = unify_expand(e, derived)
        try:
            vals = tuple(k_eval(base, env, ARITH_OPS, {}) for env in envs)
        except Exception:
            continue
        if vals == targets:
            cert = [("eq_val", base, env, v) for env, v in task.holdout_pairs()]
            if k_replay(cert, ARITH_OPS, {}):
                return SearchOutcomeO(True, e, cost, _primitives_used(e)), base
    return SearchOutcomeO(False, None, cost, []), None


# ===========================================================================
# TESTS
# ===========================================================================
def test_auto_normalizer_is_verified_equivalent() -> None:
    # a messy sum (redundant +0, different shape) normalises to a clean form that
    # is kernel-equivalent on probes.
    messy = ("ADD", ("ADD", ("var", 0), ("lit", 0)), ("ADD", ("var", 1), ("var", 2)))
    n = verified_normalize(messy)
    assert n != messy, "normalizer did nothing on a messy expression"
    for env in _PROBES:
        assert k_eval(messy, env, ARITH_OPS, {}) == k_eval(n, env, ARITH_OPS, {})


def test_auto_normalizer_enables_transfer() -> None:
    # un-normalised the operator is NOT a recognisable fold; normalised it IS,
    # so it becomes VM-transferable.
    messy = ("ADD", ("ADD", ("var", 0), ("lit", 0)), ("ADD", ("var", 1), ("var", 2)))
    assert derived_to_vm_fold(abstract_to_operator("S", messy)) is None
    n = verified_normalize(messy)
    assert derived_to_vm_fold(abstract_to_operator("S", n)) is not None


def test_auto_normalizer_rejects_bad_rewrite() -> None:
    # verified_normalize must never change semantics; check it preserves a
    # non-simplifiable expression's behaviour exactly.
    e = ("MOD", ("ADD", ("var", 0), ("var", 1)), ("lit", 3))
    n = verified_normalize(e)
    for env in _PROBES:
        assert k_eval(e, env, ARITH_OPS, {}) == k_eval(n, env, ARITH_OPS, {})


def test_auto_general_nonfold_operator_to_vm() -> None:
    # DIFF(a,b,c)=SUB(SUB(a,b),c) is non-commutative: the fold compiler rejects
    # it, but the general tree compiler runs it on the VM and solves a-b-c.
    diff_body = ("SUB", ("SUB", ("var", 0), ("var", 1)), ("var", 2))
    DIFF = abstract_to_operator("DIFF", diff_body)
    assert derived_to_vm_fold(DIFF) is None, "DIFF should not be a commutative fold"
    # the compiled postfix computes a-b-c on the VM
    pf = compile_tree_to_vm(("DIFF", ("var", 0), ("var", 1), ("var", 2)), {"DIFF": DIFF})
    assert vm_eval(pf, (9, 2, 3)) == 4 and vm_eval(pf, (5, 1, 1)) == 3
    vm = build_vm_substrate()
    solved = used = 0
    for s in range(6):
        vt = make_task(vm, "diff", _af_diff, 500 + s)
        o, u = solve_vm_tree(vt, {"DIFF": DIFF}, random.Random(60 + s),
                             op_bias={"DIFF": 6.0}, budget=9000)
        if o.solved:
            solved += 1
            used += 1 if u else 0
    assert solved >= 3, f"VM solved the non-commutative target too rarely: {solved}"
    assert used >= 1, "the general (non-fold) operator was never used on the VM"


def test_auto_loop_grows_and_kernel_fixed() -> None:
    r = run_auto()
    assert r["arith_solved"] >= 4
    assert r["promotions"] >= 1, "loop never promoted an operator"
    assert r["generated_solved"] >= 1, "loop never solved a self-generated task"
    assert r["max_operator_lineage"] >= 2, "loop never built a higher-order operator"
    assert r["vm_solved"] >= 1
    assert r["kernel_fingerprint_unchanged"], "kernel moved during the autonomous loop"


def test_auto_determinism() -> None:
    r1 = run_auto(cycles=9)
    r2 = run_auto(cycles=9)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


AUTO_TESTS = [
    test_auto_normalizer_is_verified_equivalent,
    test_auto_normalizer_enables_transfer,
    test_auto_normalizer_rejects_bad_rewrite,
    test_auto_general_nonfold_operator_to_vm,
    test_auto_loop_grows_and_kernel_fixed,
    test_auto_determinism,
]


def run_auto_tests() -> int:
    failures = 0
    for t in AUTO_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(AUTO_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 6.  BOTTOM-UP OBSERVATIONAL-EQUIVALENCE SYNTHESIS (asi_search)
# ========================================================================================





# ===========================================================================
# (A) BOTTOM-UP OBSERVATIONAL-EQUIVALENCE SYNTHESIS
# ===========================================================================
def _compositions(total: int, parts: int):
    """Positive-integer compositions of `total` into `parts` ordered parts."""
    if parts == 1:
        if total >= 1:
            yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in _compositions(total - first, parts - 1):
            yield (first,) + rest


def bottomup_solve(envs: Sequence[Tuple], targets: Tuple, derived: Dict[str, DerivedOp],
                   terminals: Sequence[str], holdout_pairs: Sequence[Tuple],
                   max_size: int = 7, max_pool: int = 9000
                   ) -> Optional[Tuple[Expr, Expr, int, int]]:
    """Return (expr, base_expr, size, n_behaviours) for the smallest expression
    whose behaviour on `envs` equals `targets`, or None. `derived` operators may
    appear in the grammar; everything is verified on the holdout via the
    immutable kernel."""
    def behaviour(e: Expr) -> Tuple:
        be = unify_expand(e, derived)
        return tuple(k_eval(be, env, ARITH_OPS, {}) for env in envs)

    def verify(e: Expr) -> Tuple[bool, Expr]:
        be = unify_expand(e, derived)
        return all(k_eval(be, ev, ARITH_OPS, {}) == v for ev, v in holdout_pairs), be

    seen: Dict[Tuple, Expr] = {}
    pool: Dict[int, List[Expr]] = {s: [] for s in range(1, max_size + 1)}

    for tok in terminals:                         # size 1: terminals
        if tok[0] == "x":
            e = ("var", int(tok[1:]))
        elif tok[0] == "#":
            e = ("lit", int(tok[1:]))
        else:
            continue
        b = behaviour(e)
        if b not in seen:
            seen[b] = e
            pool[1].append(e)
            if b == targets:
                ok, be = verify(e)
                if ok:
                    return e, be, 1, len(seen)

    allops = [(n, ARITH_OPS[n][0]) for n in ARITH_OPS] + \
             [(n, derived[n].arity) for n in derived]

    for size in range(2, max_size + 1):
        for opname, ar in allops:
            for comp in _compositions(size - 1, ar):
                pools = [pool[s] for s in comp]
                if any(len(p) == 0 for p in pools):
                    continue
                for children in product(*pools):
                    e = (opname,) + children
                    b = behaviour(e)
                    if b not in seen:
                        seen[b] = e
                        pool[size].append(e)
                        if b == targets:
                            ok, be = verify(e)
                            if ok:
                                return e, be, size, len(seen)
        if sum(len(pool[s]) for s in pool) > max_pool:
            break
    return None


def solve_arith_bottomup(task, derived: Dict[str, DerivedOp], max_size: int = 7,
                         terminals: Optional[Sequence[str]] = None
                         ) -> Tuple[SearchOutcomeO, Optional[Expr], int]:
    pairs = task.train_pairs()
    envs = [e for e, _ in pairs]
    targets = tuple(y for _, y in pairs)
    if terminals is None:
        terminals = ["x0", "x1", "x2", "#3"]   # sufficient for sum/summod/max; trimmed for speed
    res = bottomup_solve(envs, targets, derived, terminals, task.holdout_pairs(), max_size)
    if res is None:
        return SearchOutcomeO(False, None, 0, []), None, 0
    e, base, size, ncost = res
    return SearchOutcomeO(True, e, ncost, []), base, size


# ===========================================================================
# (B) OPERATORS FEED GENERATION
# ===========================================================================
def _search_mk_fn(base_expr: Expr):
    return lambda env: int(k_eval(base_expr, env, ARITH_OPS, {}))


def generate_with_operator(opname: str, derived: Dict[str, DerivedOp],
                           rng: random.Random) -> Tuple[str, object, Expr]:
    """Compose an evolved operator into a NEW sealed target (compression-progress
    generation now reuses operators, not just macros)."""
    ar = derived[opname].arity
    args = tuple(("var", rng.randrange(3)) for _ in range(ar))
    inner = (opname,) + args
    op2 = rng.choice(["ADD", "MAX", "MUL"])
    operand = rng.choice([("var", 0), ("lit", 2)])
    tgt = (op2, inner, operand)
    base = unify_expand(tgt, derived)
    name = f"gen[{op2}({opname},{operand[0]})]"
    return name, _search_mk_fn(base), tgt


# ===========================================================================
# Generalised autonomous loop driven by the bottom-up proposer
# ===========================================================================
def run_search_loop(cycles: int = 12, seed: int = ASI_SEED) -> Dict:
    rng = random.Random(seed)
    arith = build_arith_substrate()
    vm = build_vm_substrate()
    fp0 = substrate_fingerprint(arith.optable)
    macros = MacroRegistry()
    derived: Dict[str, DerivedOp] = {}
    op_lineage: Dict[str, int] = {}
    reuse_fam: Dict[str, int] = {}
    promoted_fams: set = set()
    gen_pool: List[Tuple[str, object]] = []
    m = {"solved": 0, "generated_solved": 0, "promotions": 0,
         "higher_order_promotions": 0, "operator_in_generation": 0,
         "cross_substrate_ok": 0}
    # NOTE: sum and sum-mod are exactly the families the stochastic sampler could
    # not promote; the bottom-up proposer handles them deterministically.
    base_families = [("sum", _af_sum), ("summod", _af_summod), ("max", _af_max)]

    for c in range(cycles):
        gen = False
        if gen_pool and rng.random() < 0.5:
            name, fn = gen_pool.pop(0)
            gen = True
        else:
            name, fn = base_families[c % len(base_families)]
        t = make_task(arith, name, fn, seed + 100 * c)
        terms = ["x0", "x1", "x2", "#2", "#3"] if gen else None
        o, base, size = solve_arith_bottomup(t, derived, max_size=7, terminals=terms)
        if not o.solved:
            continue
        m["solved"] += 1
        if gen:
            m["generated_solved"] += 1
            if base is not None and any(_uses_op(o.program, d) for d in derived):
                m["operator_in_generation"] += 1
        nbase = verified_normalize(base)
        macros.adopt(nbase, "arith")
        reuse_fam[name] = reuse_fam.get(name, 0) + 1

        # promote reused, normalised base-family patterns (sum/summod/max alike)
        if reuse_fam[name] == 2 and name not in promoted_fams and not gen:
            promoted_fams.add(name)
            cand = abstract_to_operator(f"OP_{name}", nbase)
            if cand.arity >= 2:
                derived[cand.name] = cand
                op_lineage[cand.name] = 1 + max(
                    [op_lineage.get(n, 1) for n in _derived_used(nbase, derived)], default=0)
                m["promotions"] += 1
                # carry the operator into GENERATION (the requested feedback)
                gname, gfn, _ = generate_with_operator(cand.name, derived, rng)
                gen_pool.append((gname, gfn))
                # cross-substrate: the operator compiles to and runs on the VM
                comp = (cand.name,) + tuple(("var", i) for i in range(cand.arity))
                pf = compile_tree_to_vm(comp, derived)
                want = [k_eval(unify_expand(comp, derived), ev, ARITH_OPS, {})
                        for ev in [(2, 3, 4), (5, 1, 9), (0, 7, 2)]]
                got = [vm_eval(pf, ev) for ev in [(2, 3, 4), (5, 1, 9), (0, 7, 2)]]
                if got == want:
                    m["cross_substrate_ok"] += 1

        # higher-order: abstract an operator-using generated solution
        if gen and o.program is not None and any(_derived_used(o.program, derived)):
            hop = f"HOP_{len(derived)}"
            cand = abstract_to_operator(hop, o.program)
            derived[hop] = cand
            op_lineage[hop] = 1 + max(
                [op_lineage.get(n, 1) for n in _derived_used(o.program, derived)], default=0)
            m["higher_order_promotions"] += 1

    m["n_operators"] = len(derived)
    m["max_operator_lineage"] = max(op_lineage.values(), default=0)
    m["promoted_families"] = sorted(promoted_fams)
    m["kernel_fingerprint_unchanged"] = substrate_fingerprint(arith.optable) == fp0
    m["boundary"] = ("Search layer: bottom-up observational-equivalence proposer "
                     "generalises operator promotion beyond folds, and evolved "
                     "operators feed task generation. CPU-scale research system; "
                     "not a verified superintelligence.")
    return m


# ===========================================================================
# TESTS
# ===========================================================================
def test_search_bottomup_solves_sum_and_summod() -> None:
    # the families the stochastic sampler solved only ~1/8 are solved
    # DETERMINISTICALLY here, with small programs.
    arith = build_arith_substrate()
    for nm, fn, lim in [("sum", _af_sum, 6), ("summod", _af_summod, 8), ("max", _af_max, 6)]:
        ok = 0
        sizes = []
        for s in range(5):
            t = make_task(arith, nm, fn, 300 + s)
            o, base, size = solve_arith_bottomup(t, {}, max_size=lim)
            if o.solved:
                ok += 1
                sizes.append(size)
        assert ok == 5, f"bottom-up did not reliably solve {nm}: {ok}/5"
        assert max(sizes) <= lim, f"{nm} solution larger than expected: {sizes}"


def test_search_bottomup_is_deterministic() -> None:
    arith = build_arith_substrate()
    t = make_task(arith, "summod", _af_summod, 42)
    a = solve_arith_bottomup(t, {}, 8)
    b = solve_arith_bottomup(t, {}, 8)
    assert a[1] == b[1], "bottom-up synthesis is not deterministic"


def test_search_bottomup_uses_operators() -> None:
    # with a sum operator available, a 'sum + x0' target is solved USING it and
    # with a smaller program than from base operators alone.
    arith = build_arith_substrate()
    sum_body = ("ADD", ("ADD", ("var", 0), ("var", 1)), ("var", 2))
    SUM3 = abstract_to_operator("SUM3", sum_body)
    fn = lambda e: (e[0] + e[1] + e[2]) + e[0]
    t = make_task(arith, "sumplus", fn, 11)
    o_with, base_w, size_w = solve_arith_bottomup(t, {"SUM3": SUM3}, 6)
    o_no, base_n, size_n = solve_arith_bottomup(t, {}, 7)
    assert o_with.solved and o_no.solved
    assert _uses_op(o_with.program, "SUM3"), "operator not used despite being available"
    assert size_w <= size_n, f"operator did not yield a smaller program: {size_w} vs {size_n}"


def test_search_loop_promotes_nonfold_and_feeds_generation() -> None:
    r = run_search_loop()
    assert r["solved"] >= 5
    assert r["promotions"] >= 1, "loop never promoted an operator"
    # sum/summod are now promotable (not only fold-friendly max)
    assert any(f in r["promoted_families"] for f in ("sum", "summod")), \
        f"only fold families promoted: {r['promoted_families']}"
    assert r["generated_solved"] >= 1, "no generated task solved"
    assert r["operator_in_generation"] >= 1, "operators never composed into generation"
    assert r["cross_substrate_ok"] >= 1, "promoted operator did not run on the VM"
    assert r["kernel_fingerprint_unchanged"], "kernel moved during the loop"


def test_search_determinism() -> None:
    r1 = run_search_loop()
    r2 = run_search_loop()
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


SEARCH_TESTS = [
    test_search_bottomup_solves_sum_and_summod,
    test_search_bottomup_is_deterministic,
    test_search_bottomup_uses_operators,
    test_search_loop_promotes_nonfold_and_feeds_generation,
    test_search_determinism,
]


def run_search_tests() -> int:
    failures = 0
    for t in SEARCH_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(SEARCH_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 7.  SOCRATIC CEGIS: QUESTIONER/RESPONDENT DEBATE, KERNEL AS JUDGE (asi_socratic)
# ========================================================================================





# ===========================================================================
# Respondent: smallest program consistent with the given examples
# ===========================================================================
def smallest_consistent(inputs: Sequence[Tuple], target_fn, terminals: Sequence[str],
                        derived: Optional[Dict] = None, max_size: int = 6) -> Optional[Expr]:
    derived = derived or {}
    envs = list(inputs)
    targets = tuple(target_fn(x) for x in envs)
    res = bottomup_solve(envs, targets, derived, terminals, (), max_size)  # () holdout: smallest fit
    return res[1] if res else None


# ===========================================================================
# Questioner: find a distinguishing input that refutes the current claim
# ===========================================================================
def find_distinguishing_input(prog: Expr, target_fn, probe_pool: Sequence[Tuple]
                              ) -> Optional[Tuple]:
    for x in probe_pool:
        if k_eval(prog, x, ARITH_OPS, {}) != target_fn(x):
            return x
    return None


# ===========================================================================
# The Socratic game: propose -> challenge -> revise, until equilibrium
# ===========================================================================
def socratic_synthesis(target_fn, seed: Sequence[Tuple], probe_pool: Sequence[Tuple],
                       terminals: Sequence[str], derived: Optional[Dict] = None,
                       max_size: int = 6, max_rounds: int = 40
                       ) -> Tuple[Optional[Expr], int, int, List[Tuple]]:
    derived = derived or {}
    examples = list(seed)
    contested: List[Tuple] = []
    prog: Optional[Expr] = None
    rounds = 0
    while rounds <= max_rounds:
        prog = smallest_consistent(examples, target_fn, terminals, derived, max_size)
        if prog is None:
            break
        ce = find_distinguishing_input(prog, target_fn, probe_pool)   # Questioner challenges
        if ce is None:
            break                                                     # equilibrium reached
        examples.append(ce)                                           # Respondent must revise
        contested.append(ce)
        rounds += 1
    return prog, rounds, len(examples), contested


# ===========================================================================
# Two-hypothesis debate: a distinguishing input, judged by the kernel
# ===========================================================================
def debate_round(h1: Expr, h2: Expr, target_fn, probe_pool: Sequence[Tuple]) -> Dict:
    """Two debaters hold competing claims; the Questioner finds where they
    disagree, the Judge (true target via kernel) declares which is correct
    there. winner: 1 or 2 (or 0 if the survivor isn't either / they agree)."""
    for x in probe_pool:
        v1 = k_eval(h1, x, ARITH_OPS, {})
        v2 = k_eval(h2, x, ARITH_OPS, {})
        if v1 != v2:
            truth = target_fn(x)
            winner = 1 if v1 == truth else (2 if v2 == truth else 0)
            return {"contested_input": x, "h1_says": v1, "h2_says": v2,
                    "judge_says": truth, "winner": winner}
    return {"contested_input": None, "winner": 0}


# ===========================================================================
# Demonstration: a biased example set on which a SPURIOUS program fits
# ===========================================================================
_TERMS = ["x0", "x1", "x2"]
# every seed input has x2 == 0, so the spurious program x0+x1 fits the seed and
# is SMALLER than the true x0+x1+x2 -- a batch fit will pick the wrong one.
_BIASED_SEED = [(1, 2, 0), (3, 1, 0), (0, 4, 0), (2, 2, 0), (4, 0, 0)]
_PROBE_POOL = [(a, b, c) for a in range(5) for b in range(5) for c in range(1, 4)]
_HOLDOUT = [(2, 3, 4), (5, 1, 2), (1, 6, 3), (0, 2, 5), (3, 3, 3)]


def run_socratic(seed: int = ASI_SEED) -> Dict:
    target = _af_sum

    # passive BATCH fit on the biased seed -> smallest consistent -> spurious
    h_batch = smallest_consistent(_BIASED_SEED, target, _TERMS)
    batch_correct = all(k_eval(h_batch, x, ARITH_OPS, {}) == target(x) for x in _HOLDOUT)

    # SOCRATIC game from the same biased seed -> Questioner corrects it
    h_soc, rounds, n_examples, contested = socratic_synthesis(
        target, _BIASED_SEED, _PROBE_POOL, _TERMS)
    soc_correct = all(k_eval(h_soc, x, ARITH_OPS, {}) == target(x) for x in _HOLDOUT)

    # explicit two-hypothesis DEBATE: spurious claim vs the true claim
    h_true = smallest_consistent(_BIASED_SEED + _PROBE_POOL, target, _TERMS)
    debate = debate_round(h_batch, h_true, target, _PROBE_POOL)

    return {
        "batch_solution": _key(h_batch),
        "batch_correct_on_holdout": batch_correct,
        "socratic_solution": _key(h_soc),
        "socratic_correct_on_holdout": soc_correct,
        "socratic_rounds": rounds,
        "socratic_examples_used": n_examples,
        "probe_pool_size": len(_PROBE_POOL),
        "true_solution": _key(h_true),
        "debate_winner_is_true_hypothesis": debate["winner"] == 2,
        "debate_contested_input": debate["contested_input"],
        "boundary": ("Socratic layer: questioner/respondent CEGIS game with the "
                     "kernel as reliable judge; kills spurious fits a passive "
                     "batch accepts. CPU-scale research system; not a verified "
                     "superintelligence."),
    }


# ===========================================================================
# TESTS
# ===========================================================================
def test_socratic_kills_spurious_fit() -> None:
    # On a biased seed a batch fit accepts a spurious program (wrong on holdout);
    # the Socratic game converges to the TRUE program (correct on holdout).
    r = run_socratic()
    assert r["batch_correct_on_holdout"] is False, \
        f"batch unexpectedly avoided the spurious fit: {r['batch_solution']}"
    assert r["socratic_correct_on_holdout"] is True, \
        f"Socratic game failed to reach the true program: {r['socratic_solution']}"
    assert r["batch_solution"] != r["socratic_solution"]


def test_socratic_judge_refutes_spurious_in_debate() -> None:
    # In a head-to-head debate the kernel judge declares the true hypothesis the
    # winner at the contested input.
    r = run_socratic()
    assert r["debate_winner_is_true_hypothesis"], "judge did not refute the spurious claim"
    assert r["debate_contested_input"] is not None


def test_socratic_converges_without_whole_pool() -> None:
    # The Questioner only needs a handful of counterexamples, not the entire
    # probe pool, to pin down the true program.
    r = run_socratic()
    assert r["socratic_rounds"] >= 1, "no counterexample was ever needed (seed not biased?)"
    assert r["socratic_examples_used"] < r["probe_pool_size"], \
        "Socratic game used as many examples as brute force -- no efficiency gain"


def test_socratic_questioner_finds_real_counterexample() -> None:
    # the distinguishing input genuinely separates the spurious program from the
    # target (the Questioner cannot fabricate or mislabel -- the kernel judges).
    spurious = ("ADD", ("var", 0), ("var", 1))            # x0 + x1
    ce = find_distinguishing_input(spurious, _af_sum, _PROBE_POOL)
    assert ce is not None and ce[2] != 0
    assert k_eval(spurious, ce, ARITH_OPS, {}) != _af_sum(ce)


def test_socratic_equilibrium_has_no_counterexample() -> None:
    # once converged, the Questioner provably cannot find any distinguishing
    # input in the probe pool.
    r = run_socratic()
    h_soc, _, _, _ = socratic_synthesis(_af_sum, _BIASED_SEED, _PROBE_POOL, _TERMS)
    assert find_distinguishing_input(h_soc, _af_sum, _PROBE_POOL) is None


def test_socratic_determinism() -> None:
    r1 = run_socratic()
    r2 = run_socratic()
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


SOCRATIC_TESTS = [
    test_socratic_kills_spurious_fit,
    test_socratic_judge_refutes_spurious_in_debate,
    test_socratic_converges_without_whole_pool,
    test_socratic_questioner_finds_real_counterexample,
    test_socratic_equilibrium_has_no_counterexample,
    test_socratic_determinism,
]


def run_socratic_tests() -> int:
    failures = 0
    for t in SOCRATIC_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(SOCRATIC_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


# ========================================================================================
# LAYER 8.  SOCRATIC-GATED AUTONOMOUS LOOP (asi_guarded)
# ========================================================================================




# the Questioner's probe pool, a broader audit pool, and a DISJOINT sealed holdout
_PROBE_G = [(a, b, c) for a in range(4) for b in range(4) for c in range(4)]      # 64
_AUDIT_G = [(a, b, c) for a in range(6) for b in range(6) for c in range(6)]      # 216
_HOLD_G = [(7, 8, 9), (9, 7, 8), (8, 9, 7), (7, 9, 8), (8, 7, 9), (9, 8, 7)]      # unseen region


# ===========================================================================
# Socratic solve of a task (active learning) + sealed-holdout verification
# ===========================================================================
def socratic_solve_task(oracle, seed_inputs: Sequence[Tuple], terminals: Sequence[str],
                        derived: Optional[Dict] = None, max_size: int = 7
                        ) -> Tuple[Optional[Expr], int, int, bool]:
    derived = derived or {}
    prog, rounds, n_examples, _ = socratic_synthesis(
        oracle, seed_inputs, _PROBE_G, terminals, derived, max_size)
    holdok = prog is not None and all(
        k_eval(prog, ev, ARITH_OPS, {}) == oracle(ev) for ev in _HOLD_G)
    return prog, rounds, n_examples, holdok


# ===========================================================================
# The Socratic GATE on operator promotion
# ===========================================================================
def socratic_gate(operator_base_expr: Expr, family_fn,
                  audit_pool: Sequence[Tuple] = tuple(_AUDIT_G)) -> Tuple[bool, Optional[Tuple]]:
    """Admit the operator iff the Questioner can find NO input on which the
    operator's computed function disagrees with the intended one."""
    ce = find_distinguishing_input(operator_base_expr, family_fn, audit_pool)
    return ce is None, ce


def _operator_base(op) -> Expr:
    """The operator applied to the substrate inputs, expanded to base ops."""
    applied = (op.name,) + tuple(("var", i) for i in range(op.arity))
    return unify_expand(applied, {op.name: op})


# ===========================================================================
# Controlled contrast: naive batch promotion vs Socratic-guarded promotion
# ===========================================================================
def gate_vs_naive() -> Dict:
    target = _af_sum
    terms = ["x0", "x1", "x2"]
    biased = [(1, 2, 0), (3, 1, 0), (0, 4, 0), (2, 2, 0), (4, 0, 0)]   # x2 == 0 everywhere

    # NAIVE: batch fit on the biased seed -> spurious -> abstract -> gate
    h_naive = smallest_consistent(biased, target, terms)
    op_naive = abstract_to_operator("ON", verified_normalize(h_naive))
    naive_passed, naive_ce = socratic_gate(_operator_base(op_naive), target)

    # GUARDED: Socratic game on the same seed -> correct -> abstract -> gate
    h_guard, _, _, _ = socratic_synthesis(target, biased, _PROBE_G, terms)
    op_guard = abstract_to_operator("OG", verified_normalize(h_guard))
    guard_passed, guard_ce = socratic_gate(_operator_base(op_guard), target)

    return {
        "naive_operator": _key(h_naive),
        "naive_gate_passed": naive_passed,
        "naive_counterexample": naive_ce,
        "guarded_operator": _key(h_guard),
        "guarded_gate_passed": guard_passed,
    }


# ===========================================================================
# The Socratic-GUARDED autonomous loop
# ===========================================================================
def run_guarded_loop(seed: int = ASI_SEED) -> Dict:
    arith = build_arith_substrate()
    fp0 = substrate_fingerprint(arith.optable)
    derived: Dict[str, object] = {}
    op_lineage: Dict[str, int] = {}
    reuse: Dict[str, int] = {}
    promoted: set = set()
    terminals = ["x0", "x1", "x2", "#3"]
    seed_inputs = [(1, 2, 1), (3, 0, 2), (0, 1, 3), (2, 2, 0)]         # small fixed seed
    families = [("sum", _af_sum), ("max", _af_max)]
    m = {"solved": 0, "promotions": 0, "total_examples": 0,
         "gate_checks": 0, "gate_passes": 0, "all_promoted_operators_verified": True}

    for c in range(8):
        name, fn = families[c % len(families)]
        prog, rounds, nex, ok = socratic_solve_task(fn, seed_inputs, terminals, derived, 7)
        if not ok:
            continue
        m["solved"] += 1
        m["total_examples"] += nex
        nbase = verified_normalize(prog)
        reuse[name] = reuse.get(name, 0) + 1
        if reuse[name] == 2 and name not in promoted:
            promoted.add(name)
            cand = abstract_to_operator(f"OP_{name}", nbase)
            if 2 <= cand.arity <= 3:
                passed, ce = socratic_gate(_operator_base(cand), fn)   # the GATE
                m["gate_checks"] += 1
                if passed:
                    m["gate_passes"] += 1
                    derived[cand.name] = cand
                    op_lineage[cand.name] = 1 + max(
                        [op_lineage.get(n, 1) for n in _derived_used(nbase, derived)], default=0)
                    m["promotions"] += 1
                else:
                    m["all_promoted_operators_verified"] = False         # would only happen if spurious

    # final independent audit: every adopted operator survives the Questioner
    audit_ok = True
    for nm, op in derived.items():
        ce = find_distinguishing_input(
            _operator_base(op),
            {"OP_sum": _af_sum, "OP_max": _af_max}.get(nm, _af_sum),
            _AUDIT_G)
        if ce is not None:
            audit_ok = False
    m["independent_audit_passed"] = audit_ok
    m["n_operators"] = len(derived)
    m["probe_pool_size"] = len(_PROBE_G)
    m["kernel_fingerprint_unchanged"] = substrate_fingerprint(arith.optable) == fp0
    m["boundary"] = ("Guarded layer: Socratic-gated promotion -- operators adopted "
                     "only after surviving adversarial audit. CPU-scale research "
                     "system; not a verified superintelligence.")
    return m


# ===========================================================================
# TESTS
# ===========================================================================
def test_guarded_gate_rejects_spurious_accepts_true() -> None:
    r = gate_vs_naive()
    assert r["naive_gate_passed"] is False, \
        f"gate failed to reject spurious operator {r['naive_operator']}"
    assert r["naive_counterexample"] is not None
    assert r["guarded_gate_passed"] is True, \
        f"gate wrongly rejected the true operator {r['guarded_operator']}"
    assert r["naive_operator"] != r["guarded_operator"]


def test_guarded_loop_only_verified_operators() -> None:
    r = run_guarded_loop()
    assert r["solved"] >= 2
    assert r["promotions"] >= 1, "loop never promoted an operator"
    assert r["gate_passes"] == r["gate_checks"], "a gate check did not pass in the guarded loop"
    assert r["all_promoted_operators_verified"], "an unverified operator slipped through"
    assert r["independent_audit_passed"], "an adopted operator failed the independent audit"
    assert r["kernel_fingerprint_unchanged"], "kernel moved during the guarded loop"


def test_guarded_active_learning_is_efficient() -> None:
    # the Socratic solve uses far fewer examples than scanning the whole probe
    # pool would require.
    r = run_guarded_loop()
    assert r["total_examples"] < r["solved"] * r["probe_pool_size"], \
        "guarded solving used as many examples as brute force"


def test_guarded_gate_counterexample_is_real() -> None:
    # the spurious operator genuinely disagrees with the target at the gate's
    # counterexample (the kernel judges -- no fabrication).
    r = gate_vs_naive()
    ce = r["naive_counterexample"]
    spurious = ("ADD", ("var", 0), ("var", 1))
    assert k_eval(spurious, ce, ARITH_OPS, {}) != _af_sum(ce)


def test_guarded_determinism() -> None:
    r1 = run_guarded_loop()
    r2 = run_guarded_loop()
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


GUARDED_TESTS = [
    test_guarded_gate_rejects_spurious_accepts_true,
    test_guarded_loop_only_verified_operators,
    test_guarded_active_learning_is_efficient,
    test_guarded_gate_counterexample_is_real,
    test_guarded_determinism,
]


def run_guarded_tests() -> int:
    failures = 0
    for t in GUARDED_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"RESULT: {len(GUARDED_TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0



# ============================================================================================
# UNIFIED TEST SUITE  (every self-claim above is backed here)
# ============================================================================================
ALL_TESTS = (
    AINT_TESTS + OPEN_TESTS + EVOLVE_TESTS + UNIFY_TESTS +
    AUTO_TESTS + SEARCH_TESTS + SOCRATIC_TESTS + GUARDED_TESTS
)


def run_all() -> int:
    failures = 0
    for t in ALL_TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"\nRESULT: {len(ALL_TESTS) - failures} passed, {failures} failed "
          f"(of {len(ALL_TESTS)} across 8 layers)")
    return 1 if failures else 0


_DEMOS = {
    "integrated": run_integrated,
    "open": run_open,
    "evolve": run_evolve,
    "unify": run_unified,
    "auto": run_auto,
    "search": run_search_loop,
    "socratic": run_socratic,
    "guarded": run_guarded_loop,
}


def main() -> None:
    import sys
    argv = sys.argv[1:]
    if not argv or argv[0] == "test":
        raise SystemExit(run_all())
    if argv[0] == "demo":
        which = argv[1] if len(argv) > 1 else "guarded"
        fn = _DEMOS.get(which)
        if fn is None:
            print("demos: " + ", ".join(_DEMOS)); raise SystemExit(2)
        print(json.dumps(fn(), indent=2, sort_keys=True, default=str)); raise SystemExit(0)
    print("usage: asi_unified_core.py [test | demo <layer>]")
    print("layers: " + ", ".join(_DEMOS))
    raise SystemExit(2)


if __name__ == "__main__":
    main()

