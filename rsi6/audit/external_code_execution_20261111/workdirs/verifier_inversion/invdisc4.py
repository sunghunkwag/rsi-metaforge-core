"""Experiment 3b: parameterised inverse discovery. For harvested f(x, c1..ck) pose
sat_inv(g) = all(f(g(y, c), c) == y for sampled (x, c), y = f(x, c)); g is a depth<=2 expression over
leaves {y, c1..ck, small constants}; non-trivial (g(y,c) != y on some sample); validated on fresh samples."""
import sys, json, random, collections, itertools, time, pickle
sys.argv=[sys.argv[0]]
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))
rng = random.Random(7)
def rand_val(t):
    if t == "int": return rng.randint(-30, 30)
    if t == "str": return "".join(rng.choice("ab c!_xy") for _ in range(rng.randint(0, 9)))
    if t == "list": return [rng.randint(-9, 9) for _ in range(rng.randint(0, 6))]
    if t == "lstr": return ["".join(rng.choice("abxy") for _ in range(rng.randint(1, 3))) for _ in range(rng.randint(1, 4))]
def rand_c(t):
    if t == "int": return rng.randint(1, 4)
    if t == "str": return rng.choice(["!", "_", "ab", "x"])
    return rand_val(t)
SMALL = [(repr(c), tname(c)) for c in (0, 1, -1, "", " ")]
def norm(r):
    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
    return r
prims = list(POOL.items())
def gens(leaves, T_out, cap):
    ex1 = []
    for pid, (fn, argt, out) in prims:
        for args in itertools.product(*[[l for l in leaves if l[1] == t] for t in argt]):
            if not any(a[0] == "y" for a in args): continue
            ex1.append(((pid, [a[0] for a in args]), out))
    n = 0
    for e, o in ex1:
        if o == T_out: n += 1; yield e
    for pid, (fn, argt, out) in prims:
        if out != T_out: continue
        opts = [[l[0] for l in leaves if l[1] == t] + [e for e, o in ex1 if o == t][:40] for t in argt]
        for args in itertools.product(*opts):
            if any(isinstance(a, tuple) for a in args):
                n += 1
                if n > cap: return
                yield (pid, list(args))
def evg(e, env):
    if isinstance(e, str): return env[e] if e in env else eval(e)
    return norm(POOL[e[0]][0](*[evg(c, env) for c in e[1]]))
found = {}; tried = 0; t0 = time.time(); evals = 0
for pid, (fn, argt, out) in POOL.items():
    T = argt[0]; rest = argt[1:]
    if out not in ("int", "str", "list", "lstr"): continue
    samples = []
    for _ in range(40):
        x = rand_val(T); cs = [rand_c(t) for t in rest]
        try:
            y = norm(fn(x, *cs))
            if tname(y) == out: samples.append((y, cs))
        except Exception: pass
    if len(samples) < 16: continue
    tried += 1
    leaves = [("y", out)] + [(f"c{i}", t) for i, t in enumerate(rest)] + SMALL
    train, held = samples[:8], samples[8:]
    for g in gens(leaves, T, 6000):
        ok = True; nontriv = False
        for y, cs in train:
            evals += 1
            env = {"y": y, **{f"c{i}": c for i, c in enumerate(cs)}}
            try:
                x = evg(g, env)
                if norm(fn(x, *cs)) != y: ok = False; break
                if x != y: nontriv = True
            except Exception: ok = False; break
        if ok and nontriv:
            try:
                okh = all(norm(fn(evg(g, {"y": y, **{f"c{i}": c for i, c in enumerate(cs)}}), *cs)) == y for y, cs in held)
            except Exception: okh = False
            if okh: found[pid] = g; break
print("operations posed", tried, "non-trivial inverses found and held-out-validated", len(found), "inner evals", evals, "wall", round(time.time() - t0, 1))
for k, g in found.items(): print(" ", k, "->", g)
pickle.dump(found, open("inverses.pkl", "wb"))
