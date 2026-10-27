#!/usr/bin/env python3
"""Memory-feedback regulation study (toy scale, numpy only).

Question
  When a learner's processor is regulated through memory, does the way memory
  is used decide whether an externally injected change survives or reverts,
  and whether experience-driven change can accumulate?

Setup
  Processor : one-hidden-layer tanh MLP (numpy, not a transformer).
  Memory    : experience buffer = long-term reservoir + recent FIFO.
              Every regulator records the same experiences; they differ only
              in how the record is used.
  Regulators:
    none             no regulation; learns from incoming experience only.
    snapshot         pulls parameters toward the design-time snapshot (lam=0.05).
                     Memory is recorded but cannot move the reference.
    snapshot_strong  same, stronger (lam=0.5).
    replay           replays memory alongside incoming experience; no reference.
    replay_fixed     replay + fixed snapshot reference (control).
    evidence         replay + reference updated to the current parameters only
                     when memory shows no loss (consolidation gate).

Experiment 1 - injected patch
  A processor trained on task A receives a patch written directly into its
  parameters, then lives through task B.
    beneficial patch: an external trainer fits A+B jointly; the processor's own
                      memory is bypassed.
    harmful patch:    a random change with the same norm as the beneficial one.

Experiment 2 - dormant unit creation
  A small processor (4 hidden units) meets tasks A -> B -> C in sequence. When
  memory-replay loss plateaus, it adds hidden units whose output weights are
  zero, so the function is unchanged at insertion (dormant). The error signal
  grows their output weights and wakes them. Compares fixed small / mid /
  large, growth, and growth without memory feedback.

Run
  python -m rsi3.studies.regulation_toy            # full (5 seeds)
  python -m rsi3.studies.regulation_toy --seeds 2  # quick check
"""
import argparse
import time
from types import SimpleNamespace

import numpy as np

# ------------------------------------------------------------------ tasks
N_TASKS = 3
D_X = 2
D_IN = D_X + N_TASKS          # 2-d input + one-hot task context
TASK_NAME = {0: "A", 1: "B", 2: "C"}


def target(task, x):
    x1, x2 = x[:, 0], x[:, 1]
    if task == 0:
        return np.sin(2.0 * x1) * np.cos(1.5 * x2)
    if task == 1:
        return 0.8 * np.cos(2.0 * x1 + x2)
    return np.tanh(x1 * x2)


def make_batch(rng, task, n):
    x = rng.uniform(-2.0, 2.0, size=(n, D_X))
    c = np.zeros((n, N_TASKS))
    c[:, task] = 1.0
    return np.hstack([x, c]), target(task, x)[:, None]


TEST = {t: make_batch(np.random.default_rng(10_000 + t), t, 2000) for t in range(N_TASKS)}

# ------------------------------------------------------------------ processor (MLP)


def init_params(rng, h):
    return {
        "W1": rng.normal(0.0, 1.0 / np.sqrt(D_IN), (D_IN, h)),
        "b1": np.zeros(h),
        "W2": rng.normal(0.0, 1.0 / np.sqrt(h), (h, 1)),
        "b2": np.zeros(1),
    }


def forward(p, X):
    H = np.tanh(X @ p["W1"] + p["b1"])
    return H, H @ p["W2"] + p["b2"]


def loss(p, X, Y):
    _, out = forward(p, X)
    return float(np.mean((out - Y) ** 2))


def test_loss(p, t):
    return loss(p, *TEST[t])


def grad(p, X, Y):
    H, out = forward(p, X)
    n = X.shape[0]
    d_out = 2.0 * (out - Y) / n
    g = {"W2": H.T @ d_out, "b2": d_out.sum(0)}
    dH = (d_out @ p["W2"].T) * (1.0 - H ** 2)
    g["W1"] = X.T @ dH
    g["b1"] = dH.sum(0)
    return g


def n_params(p):
    return int(sum(v.size for v in p.values()))


def tree_copy(p):
    return {k: v.copy() for k, v in p.items()}


def tree_sub(a, b):
    return {k: a[k] - b[k] for k in a}


def tree_dot(a, b):
    return float(sum(np.sum(a[k] * b[k]) for k in a))


def tree_axpy(g, a, x):
    for k in g:
        g[k] = g[k] + a * x[k]


def clip(g, max_norm=5.0):
    n = np.sqrt(tree_dot(g, g))
    if n > max_norm:
        return {k: v * (max_norm / n) for k, v in g.items()}
    return g


class Momentum:
    def __init__(self, p, lr, mu=0.9):
        self.lr, self.mu = lr, mu
        self.v = {k: np.zeros_like(a) for k, a in p.items()}

    def step(self, p, g):
        for k in p:
            self.v[k] = self.mu * self.v[k] + g[k]
            p[k] -= self.lr * self.v[k]

    def extend(self, p):
        """Grow momentum buffers with the processor (new entries are zero)."""
        for k, a in p.items():
            old = self.v[k]
            if old.shape != a.shape:
                new = np.zeros_like(a)
                new[tuple(slice(0, s) for s in old.shape)] = old
                self.v[k] = new


# ------------------------------------------------------------------ memory


class Memory:
    """Long-term reservoir (old experience kept evenly) + recent FIFO."""

    def __init__(self, seed, cap_long=400, cap_recent=200):
        self.rng = np.random.default_rng(seed)
        self.cap_long, self.cap_recent = cap_long, cap_recent
        self.long_X, self.long_Y = [], []
        self.recent_X, self.recent_Y = [], []
        self.seen = 0

    def clone(self, seed):
        m = Memory(seed, self.cap_long, self.cap_recent)
        m.long_X, m.long_Y = list(self.long_X), list(self.long_Y)
        m.recent_X, m.recent_Y = list(self.recent_X), list(self.recent_Y)
        m.seen = self.seen
        return m

    def add(self, X, Y):
        for x, y in zip(X, Y):
            self.seen += 1
            if len(self.long_X) < self.cap_long:
                self.long_X.append(x)
                self.long_Y.append(y)
            else:
                j = self.rng.integers(0, self.seen)
                if j < self.cap_long:
                    self.long_X[j] = x
                    self.long_Y[j] = y
            self.recent_X.append(x)
            self.recent_Y.append(y)
            if len(self.recent_X) > self.cap_recent:
                self.recent_X.pop(0)
                self.recent_Y.pop(0)

    def all(self):
        return np.array(self.long_X + self.recent_X), np.array(self.long_Y + self.recent_Y)

    def sample(self, rng, n):
        h = n // 2
        il = rng.integers(0, len(self.long_X), h)
        ir = rng.integers(0, len(self.recent_X), n - h)
        X = np.array([self.long_X[i] for i in il] + [self.recent_X[i] for i in ir])
        Y = np.array([self.long_Y[i] for i in il] + [self.recent_Y[i] for i in ir])
        return X, Y


def memory_report(p, mem):
    """Loss over all of memory, and per context (task)."""
    X, Y = mem.all()
    groups = X[:, D_X:].argmax(1)
    per = {}
    for t in np.unique(groups):
        m = groups == t
        per[int(t)] = loss(p, X[m], Y[m])
    return loss(p, X, Y), per


def consolidate_ok(p, ref, mem, cfg):
    """True if, according to memory, the current state is no worse than the reference:
    total loss not worse, and no context noticeably worse."""
    tp, gp = memory_report(p, mem)
    tr, gr = memory_report(ref, mem)
    if tp > tr * (1.0 + cfg.tol_total) + 1e-6:
        return False
    for t in gp:
        if gp[t] > gr[t] * (1.0 + cfg.tol_group) + cfg.abs_tol:
            return False
    return True


# ------------------------------------------------------------------ life (online learning + regulation)


def new_state(ref):
    return {"ref": ref, "accepts": 0, "first_accept": None, "t": 0,
            "last_L": None, "grow_events": 0}


def grow_units(p, opt, state, k, rng):
    """Dormant unit creation: random input weights, zero output weights.
    The function is unchanged at insertion; the error grows the output weights."""
    W1n = rng.normal(0.0, 1.0 / np.sqrt(D_IN), (D_IN, k))
    trees = [p] + ([state["ref"]] if state["ref"] is not None else [])
    for tree in trees:
        tree["W1"] = np.hstack([tree["W1"], W1n])
        tree["b1"] = np.concatenate([tree["b1"], np.zeros(k)])
        tree["W2"] = np.vstack([tree["W2"], np.zeros((k, 1))])
    opt.extend(p)


def maybe_grow(p, opt, state, mem, cfg, rng):
    L, _ = memory_report(p, mem)
    prev = state["last_L"]
    state["last_L"] = L
    if prev is None or p["W1"].shape[1] >= cfg.h_max:
        return
    if L > cfg.grow_thresh and (prev - L) < cfg.plateau_rel * prev:
        before = test_loss(p, 0), test_loss(p, 1), test_loss(p, 2)
        grow_units(p, opt, state, cfg.grow_k, rng)
        after = test_loss(p, 0), test_loss(p, 1), test_loss(p, 2)
        assert np.allclose(before, after, atol=1e-12), "dormant units changed the function"
        state["grow_events"] += 1
        state["last_L"] = None


def live(p, opt, task, steps, regulator, mem, state, cfg, stream_rng, aux_rng, grow=False):
    for s in range(steps):
        X, Y = make_batch(stream_rng, task, cfg.batch)
        mem.add(X, Y)                      # every regulator records the same experience
        g = grad(p, X, Y)
        if regulator == "snapshot":
            tree_axpy(g, cfg.lam, tree_sub(p, state["ref"]))
        elif regulator == "snapshot_strong":
            tree_axpy(g, cfg.lam_strong, tree_sub(p, state["ref"]))
        elif regulator in ("evidence", "replay_fixed"):
            Xr, Yr = mem.sample(aux_rng, cfg.replay)
            tree_axpy(g, 1.0, grad(p, Xr, Yr))
            tree_axpy(g, cfg.lam, tree_sub(p, state["ref"]))
        elif regulator == "replay":
            Xr, Yr = mem.sample(aux_rng, cfg.replay)
            tree_axpy(g, 1.0, grad(p, Xr, Yr))
        opt.step(p, clip(g))
        state["t"] += 1
        if regulator == "evidence" and (s + 1) % cfg.consolidate_every == 0:
            if consolidate_ok(p, state["ref"], mem, cfg):
                state["ref"] = tree_copy(p)
                state["accepts"] += 1
                if state["first_accept"] is None:
                    state["first_accept"] = state["t"]
        if grow and (s + 1) % cfg.grow_every == 0:
            maybe_grow(p, opt, state, mem, cfg, aux_rng)


# ------------------------------------------------------------------ experiment 1: injected patch


def surgeon_beneficial(theta0, cfg, rng):
    """An external trainer fits A+B jointly; the processor's memory is bypassed."""
    p = tree_copy(theta0)
    opt = Momentum(p, cfg.lr)
    for _ in range(cfg.surgeon_steps):
        Xa, Ya = make_batch(rng, 0, cfg.batch // 2)
        Xb, Yb = make_batch(rng, 1, cfg.batch // 2)
        opt.step(p, clip(grad(p, np.vstack([Xa, Xb]), np.vstack([Ya, Yb]))))
    return p


def surgeon_harmful(theta0, p_ben, rng):
    """A random change with the same norm as the beneficial patch."""
    d = tree_sub(p_ben, theta0)
    n = np.sqrt(tree_dot(d, d))
    r = {k: rng.normal(size=v.shape) for k, v in theta0.items()}
    rn = np.sqrt(tree_dot(r, r))
    return {k: theta0[k] + r[k] * (n / rn) for k in theta0}


REGS1 = ["none", "snapshot", "snapshot_strong", "replay", "replay_fixed", "evidence"]
REG_LABEL = {
    "none": "no regulation                    ",
    "snapshot": "fixed reference (weak, lam=0.05) ",
    "snapshot_strong": "fixed reference (strong, lam=0.5)",
    "replay": "[control] memory replay only     ",
    "replay_fixed": "[control] replay + fixed ref     ",
    "evidence": "replay + evidence-gated ref      ",
}


def run_exp1(seed, cfg):
    rng = np.random.default_rng(seed)
    p = init_params(rng, cfg.h)
    opt = Momentum(p, cfg.lr)
    mem0 = Memory(seed + 1)
    live(p, opt, 0, cfg.phase0_steps, "none", mem0, new_state(None), cfg,
         np.random.default_rng([seed, 0]), np.random.default_rng([seed, 1]))
    theta0 = tree_copy(p)                                  # design-time state
    p_ben = surgeon_beneficial(theta0, cfg, np.random.default_rng([seed, 2]))
    p_harm = surgeon_harmful(theta0, p_ben, np.random.default_rng([seed, 3]))

    res = {"A_pre": test_loss(theta0, 0), "B_pre": test_loss(theta0, 1)}
    for pi, (pname, pp) in enumerate([("beneficial", p_ben), ("harmful", p_harm)]):
        res[f"{pname}_A_patch"] = test_loss(pp, 0)
        res[f"{pname}_B_patch"] = test_loss(pp, 1)
        for reg in REGS1:
            q = tree_copy(pp)
            o = Momentum(q, cfg.lr)
            m = mem0.clone(seed + 7)
            st = new_state(tree_copy(theta0))              # reference = design-time state
            live(q, o, 1, cfg.life_steps, reg, m, st, cfg,
                 np.random.default_rng([seed, 10 + pi]),   # same experience stream for all
                 np.random.default_rng([seed, 20 + pi]))
            res[f"{pname}_{reg}_A"] = test_loss(q, 0)
            res[f"{pname}_{reg}_B"] = test_loss(q, 1)
            if reg == "evidence":
                res[f"{pname}_{reg}_accepts"] = st["accepts"]
                res[f"{pname}_{reg}_first_accept"] = st["first_accept"]
    return res


# ------------------------------------------------------------------ experiment 2: dormant unit creation


ARMS2 = [
    ("replay_fixed_small", "replay", "small", False),
    ("replay_fixed_large", "replay", "large", False),
    ("replay_fixed_mid", "replay", "mid", False),
    ("replay_grow", "replay", "small", True),
    ("evidence_fixed_large", "evidence", "large", False),
    ("evidence_grow", "evidence", "small", True),
    ("none_grow", "none", "small", True),
]


def run_exp2(seed, cfg):
    res = {}
    for ai, (name, reg, size, grow) in enumerate(ARMS2):
        rng = np.random.default_rng([seed, 100])           # same seed, same initialization
        h = {"small": cfg.h_small, "mid": cfg.h_mid, "large": cfg.h_max}[size]
        p = init_params(rng, h)
        opt = Momentum(p, cfg.lr)
        mem = Memory(seed + 3)
        st = new_state(tree_copy(p) if reg == "evidence" else None)
        stream = np.random.default_rng([seed, 200])        # same experience stream for all
        aux = np.random.default_rng([seed, 300 + ai])
        per_phase = []
        for task in range(N_TASKS):
            before = st["grow_events"]
            live(p, opt, task, cfg.phase2_steps, reg, mem, st, cfg, stream, aux, grow=grow)
            per_phase.append(st["grow_events"] - before)
        res[f"{name}_grow_by_phase"] = per_phase
        for t in range(N_TASKS):
            res[f"{name}_{TASK_NAME[t]}"] = test_loss(p, t)
        res[f"{name}_hidden"] = p["W1"].shape[1]
        res[f"{name}_params"] = n_params(p)
        res[f"{name}_grow_events"] = st["grow_events"]
        res[f"{name}_accepts"] = st["accepts"]
    return res


# ------------------------------------------------------------------ reporting


def ms(vals):
    a = np.array(vals, dtype=float)
    return f"{a.mean():.4f} ± {a.std():.4f}"


def report_exp1(rs, cfg):
    g = lambda k: [r[k] for r in rs]
    print("\n=== Experiment 1: injected patch (test MSE, lower is better) ===")
    print(f"design time (before patch)  A {ms(g('A_pre'))}   B {ms(g('B_pre'))}")
    for pname, label in [("beneficial", "beneficial patch"), ("harmful", "harmful patch")]:
        print(f"\n[{label}]  right after injection  A {ms(g(f'{pname}_A_patch'))}"
              f"   B {ms(g(f'{pname}_B_patch'))}")
        print(f"  after living through task B for {cfg.life_steps} steps:")
        for reg in REGS1:
            line = f"    {REG_LABEL[reg]}  A {ms(g(f'{pname}_{reg}_A'))}   B {ms(g(f'{pname}_{reg}_B'))}"
            if reg == "evidence":
                fa = [r[f"{pname}_evidence_first_accept"] for r in rs]
                fa_s = ", ".join("never" if v is None else str(v) for v in fa)
                line += f"   first reference update step: {fa_s}"
            print(line)

    # Errors span orders of magnitude, so retention is measured on a log scale.
    # Beneficial patch B retention: log(B_pre/B_end) / log(B_pre/B_patch)
    #   1 = patch effect kept, 0 = back to pre-patch, >1 = better than right after the patch
    print("\n  beneficial patch: B retention (log scale, 1 = kept, 0 = reverted)")
    for reg in REGS1:
        v = [np.log(r["B_pre"] / r[f"beneficial_{reg}_B"]) / np.log(r["B_pre"] / r["beneficial_B_patch"])
             for r in rs]
        print(f"    {REG_LABEL[reg]}  {ms(v)}")
    # Harmful patch A recovery: log(A_patch/A_end) / log(A_patch/A_pre)
    #   1 = fully recovered to pre-patch level, 0 = damage unchanged
    print("  harmful patch: A recovery (log scale, 1 = fully recovered, 0 = damage unchanged)")
    for reg in REGS1:
        v = [np.log(r["harmful_A_patch"] / r[f"harmful_{reg}_A"]) / np.log(r["harmful_A_patch"] / r["A_pre"])
             for r in rs]
        print(f"    {REG_LABEL[reg]}  {ms(v)}")


def report_exp2(rs, cfg):
    g = lambda k: [r[k] for r in rs]
    print(f"\n=== Experiment 2: dormant unit creation (A->B->C, {cfg.phase2_steps} steps each,"
          f" all three tasks measured at the end) ===")
    labels = {
        "replay_fixed_small": f"replay + fixed small (hidden {cfg.h_small})",
        "replay_fixed_large": f"replay + fixed large (hidden {cfg.h_max})",
        "replay_fixed_mid": f"replay + fixed mid (hidden {cfg.h_mid}, mean final size of growth arm)",
        "replay_grow": f"replay + growth ({cfg.h_small} -> max {cfg.h_max})",
        "evidence_fixed_large": f"replay + gated ref + fixed large (hidden {cfg.h_max})",
        "evidence_grow": f"replay + gated ref + growth ({cfg.h_small} -> max {cfg.h_max})",
        "none_grow": "no regulation + growth",
    }
    for name, *_ in ARMS2:
        print(f"  {labels[name]}")
        print(f"     A {ms(g(name + '_A'))}   B {ms(g(name + '_B'))}   C {ms(g(name + '_C'))}")
        print(f"     final hidden units {g(name + '_hidden')}   params {g(name + '_params')}   "
              f"growth events {g(name + '_grow_events')}")
        if any(r[name + "_grow_events"] for r in rs):
            print(f"     growth by phase [A,B,C] {g(name + '_grow_by_phase')}")
        if name.startswith("evidence"):
            print(f"     reference updates (out of {3 * cfg.phase2_steps // cfg.consolidate_every} checks) "
                  f"{g(name + '_accepts')}")


CONFIG = dict(
    h=32, lr=0.02, batch=32, replay=32, lam=0.05, lam_strong=0.5,
    phase0_steps=4000, surgeon_steps=4000, life_steps=3000,
    consolidate_every=50, tol_total=0.02, tol_group=0.10, abs_tol=0.005,
    h_small=4, h_mid=28, h_max=48, phase2_steps=3000,
    grow_every=200, grow_k=4, grow_thresh=0.01, plateau_rel=0.05,
)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--only", choices=["1", "2"], default=None)
    args = ap.parse_args(argv)
    cfg = SimpleNamespace(**CONFIG)
    print("config:", CONFIG)
    seeds = list(range(args.seeds))
    t0 = time.time()
    if args.only in (None, "1"):
        report_exp1([run_exp1(s, cfg) for s in seeds], cfg)
    if args.only in (None, "2"):
        report_exp2([run_exp2(s, cfg) for s in seeds], cfg)
    print(f"\nseeds {len(seeds)}, elapsed {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
