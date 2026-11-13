"""Experiment 3: inverse discovery as self-posed puzzles. For each harvested operation f (with a fixed
constant argument), pose sat_inv(g) = all(f(g(y)) == y for y in images f(x) of random x); search g as
a depth<=2 expression over {y, small constants} with the pool; validate on fresh images."""
import sys, json, random, collections, itertools, time
sys.argv=[sys.argv[0]]
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))
rng = random.Random(7)
def rand_val(t):
    if t == "int": return rng.randint(-50, 50)
    if t == "str": return "".join(rng.choice("ab c!_xy") for _ in range(rng.randint(0, 9)))
    if t == "list": return [rng.randint(-9, 9) for _ in range(rng.randint(0, 6))]
    if t == "lstr": return ["".join(rng.choice("abxy") for _ in range(rng.randint(1, 3))) for _ in range(rng.randint(1, 4))]
CONSTS = {"int": [0, 1, 2, -1], "str": ["", " ", "!", "_"], "list": [[]], "lstr": [[]]}
# targets: f(x, *c) partial applications, x in first slot
targets = []
for pid, (fn, argt, out) in POOL.items():
    rest = argt[1:]
    for cs in itertools.product(*[CONSTS[t][:3] for t in rest]):
        targets.append((pid, cs, fn, argt[0], out))
def apply(fn, x, cs):
    r = fn(x, *cs)
    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
    return r
prims = list(POOL.items())
def candidates_g(T_in, T_out):
    """expressions g(y): y has type T_in (f's output); produce values of type T_out. depth 1 and 2."""
    leaves = [("y", T_in)] + [(repr(c), tname(c)) for t in CONSTS for c in CONSTS[t]]
    exprs1 = []
    for pid, (fn, argt, out) in prims:
        for args in itertools.product(*[[l for l in leaves if l[1] == t] for t in argt]):
            if not any(a[0] == "y" for a in args): continue
            exprs1.append(((pid, [a[0] for a in args]), out))
    for e, o in exprs1:
        if o == T_out: yield e
    for pid, (fn, argt, out) in prims:
        if out != T_out: continue
        opts = [[l[0] for l in leaves if l[1] == t] + [e for e, o in exprs1 if o == t][:60] for t in argt]
        for args in itertools.product(*opts):
            if any(isinstance(a, tuple) for a in args): yield (pid, list(args))
def evg(e, y):
    if isinstance(e, str): return y if e == "y" else eval(e)
    fn = POOL[e[0]][0]; r = fn(*[evg(c, y) for c in e[1]])
    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
    return r
found = []; tried = 0; t0 = time.time(); evals = 0
for pid, cs, fn, T, out in targets:
    if out not in ("int", "str", "list", "lstr") or T == out and pid.startswith("b.list"): continue
    xs = [rand_val(T) for _ in range(24)]
    ys = []
    for x in xs:
        try: ys.append(apply(fn, x, cs))
        except Exception: pass
    ys = [y for y in ys if tname(y) == out]
    if len(ys) < 12: continue
    tried += 1
    train, held = ys[:6], ys[6:]
    hit = None; n = 0
    for g in candidates_g(out, T):
        n += 1
        if n > 4000: break
        ok = True
        for y in train:
            evals += 1
            try:
                if apply(fn, evg(g, y), cs) != y: ok = False; break
            except Exception: ok = False; break
        if ok:
            # validation on held-out images (independent of the search)
            try: okh = all(apply(fn, evg(g, y), cs) == y for y in held)
            except Exception: okh = False
            if okh: hit = g; break
    # trivial inverse (g == y) excluded: only count if f is not identity on images
    if hit is not None and hit != "y":
        found.append((pid, cs, hit))
print("targets tried", tried, "inverses found+validated", len(found), "inner evals", evals, "wall", round(time.time() - t0, 1))
for f in found[:400]:
    if any(k in f[0] for k in ("split", "join", "upper", "rev", "replace", "count", "index", "strip", "add", "sub", "neg", "mul", "sorted", "str", "int", "len", "range")):
        print(f[0], f[1], "->", f[2])
