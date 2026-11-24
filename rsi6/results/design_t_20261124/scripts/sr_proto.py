"""Scratch (prototype): the laws of the regression kind as monomials with parts.

Model: log|y| = sum_i a_i log|x_i| + sum_k b_k log|P_k| + sum_j c_j m_j + const, with the sign of y from the signs of what has
an odd exponent. A part P is built on a monomial m of one or two variables (exponents -2..2): "one": 1 + k*m, "sin": sin(k*m),
"cos": cos(k*m), each with an inner constant k found by a scan; "lin": m itself as a linear term (an exponential factor).
For every law: is it recovered (R2 > 0.999 on held-back observed rows AND on the queries) with no part, with one part
(every candidate tried), with two (greedy on the best three first parts)? Which (type, exponent pattern) does it?

    python3 -I sr_proto.py OUT.pkl
"""
# Development script, kept as it was run (2026-11-25) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import itertools
import pickle
import sys
import time
import warnings

warnings.filterwarnings("ignore")
import numpy as np

from rsi6 import environments
from rsi6.kernel.problem import Meter

FIT = 170                                                 # observed rows used to fit; the rest are held back
SCAN = [10.0 ** j for j in (-2, -1.5, -1, -0.5, 0, 0.5, 1)]
TRIG = [1.0, 2.0, 0.5, np.pi, 2 * np.pi]


def r2(pred, y):
    s = ((y - y.mean()) ** 2).sum()
    if s <= 0 or not np.all(np.isfinite(pred)):
        return 0.0
    return float(1.0 - ((pred - y) ** 2).sum() / s)


class Law:
    def __init__(self, P):
        keep = P.ctx_x.std(axis=0) > 0
        self.X = np.vstack([P.ctx_x[:, keep], P.qry_x[:, keep]])
        self.n, self.d = len(P.ctx_x), int(keep.sum())
        self.y, self.q = P.ctx_y, P.qry_y
        a = np.abs(self.X)
        low = np.where(a > 0, a, np.inf).min(axis=0) * 1e-3
        self.L = np.log(np.maximum(a, np.where(np.isfinite(low), low, 1.0)))
        self.S = np.where(self.X < 0, -1.0, 1.0)
        ay = np.abs(self.y)
        self.ylow = ay[ay > 0].min() * 1e-3 if np.any(ay > 0) else 1.0
        self.t = np.log(np.maximum(ay, self.ylow))
        self.sy = np.where(self.y < 0, -1.0, 1.0)
        self.mixed = [i for i in range(self.d) if len(np.unique(self.S[:self.n, i])) > 1]
        self.fits = 0

    def monomials(self):
        out = []
        for i in range(self.d):
            for e in (1, 2, -1, -2):
                out.append((((i, e),), self.S[:, i] ** (e % 2) * np.exp(e * self.L[:, i])))
        for i, j in itertools.combinations(range(self.d), 2):
            for e, f in itertools.product((1, 2, -1, -2), repeat=2):
                out.append((((i, e), (j, f)), self.S[:, i] ** (e % 2) * self.S[:, j] ** (f % 2) * np.exp(e * self.L[:, i] + f * self.L[:, j])))
        return out

    def evaluate(self, logs, signs, lins):
        """Fit on the first FIT observed rows. Returns (R2 held back, R2 queries, variance of the log residual held back)."""
        self.fits += 1
        cols = [self.L] + [c[:, None] for c in logs] + [c[:, None] for c in lins] + [np.ones((len(self.L), 1))]
        A = np.hstack(cols)
        if not np.all(np.isfinite(A)):
            return -1.0, -1.0, np.inf
        n = self.n
        mu, sd = A[:FIT, :-1].mean(axis=0), A[:FIT, :-1].std(axis=0)
        A = np.hstack([(A[:, :-1] - mu) / np.where(sd > 0, sd, 1.0), A[:, -1:]])
        w = np.linalg.lstsq(A[:FIT], self.t[:FIT], rcond=None)[0]
        z = A @ w
        expo = w[:self.d] / np.where(sd[:self.d] > 0, sd[:self.d], 1.0)
        sign = np.ones(len(A))
        for i in self.mixed:
            if int(round(expo[i])) % 2:
                sign = sign * self.S[:, i]
        for k, s in enumerate(signs):
            b = w[self.d + k] / (sd[self.d + k] if sd[self.d + k] > 0 else 1.0)
            if int(round(b)) % 2:
                sign = sign * s
        s0 = 1.0 if np.sum(sign[:FIT] * self.sy[:FIT]) >= 0 else -1.0
        pred = s0 * sign * np.exp(np.clip(z, -700, 700))
        return r2(pred[FIT:n], self.y[FIT:n]), r2(pred[n:], self.q), float(np.var(z[FIT:n] - self.t[FIT:n]))

    def part(self, kind, m, k):
        v = k * m
        if kind == "one":
            p = 1.0 + v
        elif kind == "sin":
            p = np.sin(v)
        else:
            p = np.cos(v)
        a = np.abs(p)
        return np.log(np.maximum(a, 1e-12)), np.where(p < 0, -1.0, 1.0)

    def candidates(self, base=((), (), ())):
        """Every one-part extension of ``base`` (logs, signs, lins): yields (type, monomial, k, result)."""
        logs, signs, lins = base
        for mono, m in self.monomials():
            if not np.all(np.isfinite(m)):
                continue
            scale = np.median(np.abs(m[:self.n]))
            if not np.isfinite(scale) or scale <= 0:
                continue
            sd = m[:FIT].std()
            if sd > 0:
                yield "lin", mono, 0.0, self.evaluate(logs, signs, list(lins) + [(m - m[:FIT].mean()) / sd])
            best = None
            for c in SCAN:
                for sg in (1.0, -1.0):
                    k = sg * c / scale
                    lg, sn = self.part("one", m, k)
                    res = self.evaluate(list(logs) + [lg], list(signs) + [sn], lins)
                    if best is None or res[2] < best[1][2]:
                        best = (k, res)
            k0 = best[0]
            for f in (0.56, 0.75, 1.33, 1.78):                    # one refinement around the best of the scan
                lg, sn = self.part("one", m, k0 * f)
                res = self.evaluate(list(logs) + [lg], list(signs) + [sn], lins)
                if res[2] < best[1][2]:
                    best = (k0 * f, res)
            yield "one", mono, best[0], best[1]
            for kind in ("sin", "cos"):
                best = None
                for k in TRIG:
                    lg, sn = self.part(kind, m, k)
                    res = self.evaluate(list(logs) + [lg], list(signs) + [sn], lins)
                    if best is None or res[2] < best[1][2]:
                        best = (k, res)
                yield kind, mono, best[0], best[1]


def pattern(kind, mono):
    return kind, tuple(sorted(e for _, e in mono))


def solved(res):
    return res[0] > 0.999 and res[1] > 0.999


def study(law):
    out = {"d": law.d, "mixed": len(law.mixed)}
    base = law.evaluate([], [], [])
    out["base"] = base
    if solved(base):
        out["level"] = 0
        return out
    first = []
    for kind, mono, k, res in law.candidates():
        first.append((kind, mono, k, res))
    out["n_candidates"] = len(first)
    out["fits_one"] = law.fits
    wins = [c for c in first if solved(c[3])]
    out["one"] = [(pattern(c[0], c[1]), c[1], c[2], c[3]) for c in wins]
    order = sorted(range(len(first)), key=lambda i: first[i][3][2])
    out["best_one"] = [(pattern(first[i][0], first[i][1]), first[i][1], first[i][2], first[i][3]) for i in order[:3]]
    out["rank_of_win"] = [order.index(i) for i, c in enumerate(first) if solved(c[3])][:5]
    if wins:
        out["level"] = 1
        return out
    two = []
    for i in order[:3]:
        kind, mono, k, res = first[i]
        m = dict((tuple(mm), v) for mm, v in law.monomials())[tuple(mono)]
        if kind == "lin":
            base2 = ((), (), ((m - m[:FIT].mean()) / m[:FIT].std(),))
        else:
            lg, sn = law.part(kind, m, k)
            base2 = ((lg,), (sn,), ())
        for kind2, mono2, k2, res2 in law.candidates(base2):
            if solved(res2):
                two.append((pattern(kind, mono), pattern(kind2, mono2), mono, mono2, res2))
        if two:
            break
    out["two"] = two[:20]
    out["level"] = 2 if two else 9
    return out


def main():
    env = environments.load("regression")
    result = {}
    started = time.time()
    for i in env.instance_ids():
        law = Law(env.problem(i, Meter(float("inf")), 0, True)[0])
        result[i] = study(law)
        result[i]["fits"] = law.fits
    pickle.dump(result, open(sys.argv[1], "wb"))
    print("seconds", round(time.time() - started, 1))
    volume = lambda i: i.split("feynman-")[1].split(".")[0]
    for group, key in (("tier", lambda i: i.split("/")[0]), ("volume", volume)):
        for g in sorted({key(i) for i in result}):
            mine = [result[i] for i in result if key(i) == g]
            print(f"{group} {g:6s}: {len(mine):3d} laws | no part {sum(r['level'] == 0 for r in mine):2d} | one part {sum(r['level'] == 1 for r in mine):2d} | "
                  f"two parts {sum(r['level'] == 2 for r in mine):2d} | not recovered {sum(r['level'] == 9 for r in mine):2d}")
    from collections import Counter
    c1 = Counter()
    for i, r in result.items():
        if r["level"] == 1:
            for p in {w[0] for w in r["one"]}:
                c1[p] += 1
    print("one-part laws by (type, exponents) that recovers them (a law can count for several):")
    for p, n in c1.most_common(25):
        print("   ", p, n)
    c2 = Counter()
    for i, r in result.items():
        if r["level"] == 2:
            for p in {(w[0], w[1]) for w in r["two"]}:
                c2[p] += 1
    print("two-part laws by pair:", c2.most_common(12))
    print("one-part laws: candidates per law, median", int(np.median([r["n_candidates"] for r in result.values() if "n_candidates" in r])),
          "| fits for all candidates, median", int(np.median([r["fits_one"] for r in result.values() if "fits_one" in r])),
          "| rank of the first winning candidate by held-back residual:", sorted(r["rank_of_win"][0] for r in result.values() if r.get("rank_of_win")))


if __name__ == "__main__":
    main()
