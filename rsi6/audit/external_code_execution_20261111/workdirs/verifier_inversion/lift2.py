"""Experiment 2: lift an instance solution (a derivation tree over mined leaves) to a program over
the puzzle's parameters; check it on the family's other instances (hidden from the solver)."""
import sys, json, random, collections, ast
sys.argv=[sys.argv[0]]
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))

PREFER_PARAMS = len(sys.argv) > 0 and __import__('os').environ.get('PREF','1') == '1'
def leaves_prov(mined, cap):
    out = []
    if PREFER_PARAMS:
        mined = sorted(mined, key=lambda sv: 0 if sv[0].isidentifier() else 1)
    for src, v in mined:
        out.append((("leaf", src), v))
        if isinstance(v, list):
            for i, e in enumerate(v[:20]): out.append((("leaf", f"({src})[{i}]"), e))
    for k in (0, 1, 2, -1, 10): out.append((("leaf", repr(k)), k))
    seen = set(); L = []
    for e, v in out:
        t = tname(v)
        if t is None: continue
        key = (t, repr(v)[:300])
        if key in seen: continue
        seen.add(key); L.append((e, v))
    return L[:cap * 2]

def enum_prov(M, leaves, want, budget_vals):
    allv = collections.defaultdict(list); seen = set()
    for e, v in leaves:
        t = tname(v); key = (t, repr(v)[:500]); 
        if key in seen: continue
        seen.add(key); allv[t].append((e, v))
    for e, v in list(allv.get(want, [])): yield e, v
    prims = [(p,) + POOL[p] for p in M["active"] if p in POOL]; produced = 0
    for d in range(1, M["stages"][0].get("depth", 2) + 1):
        new = collections.defaultdict(list)
        for pid, fn, argt, out in prims:
            for args in itertools.product(*[allv.get(t, [])[:M["leafcap"]] for t in argt]):
                produced += 1
                if produced > budget_vals * 20: return
                vals = [a[1] for a in args]
                if out in ("str", "list", "lstr") and any(isinstance(a, int) and abs(a) > 10 ** 5 for a in vals): continue
                try:
                    r = fn(*vals)
                    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
                except Exception: continue
                if r is None or not sizeok(r): continue
                t = tname(r)
                if t is None: continue
                if isinstance(r, (str, list)) and len(r) > 3000:
                    if t == want: yield (pid, [a[0] for a in args]), r
                    continue
                key = (t, repr(r)[:500])
                if key in seen: continue
                seen.add(key); new[t].append(((pid, [a[0] for a in args]), r))
                if t == want: yield (pid, [a[0] for a in args]), r
        for t, vs in new.items(): allv[t].extend(vs)

def ev(expr, env):
    if expr[0] == "leaf": return eval(expr[1], dict(ENV, **env))
    fn = POOL[expr[0]][0]; r = fn(*[ev(c, env) for c in expr[1]])
    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
    return r

data = json.load(open('../p3_development.json'))
fam = collections.defaultdict(list)
for d in data: fam[d["name"].split(":")[0]].append(d)
M = M0; B = 300
stats = collections.Counter()
for f, insts in fam.items():
    i0 = insts[0]; sat = load(i0["sat"]); ans, params, mined, cfuns = analyse(i0["sat"])
    want = ANSMAP[i0["ans_type"]]; calls = 0; sol = None
    for e, x in enum_prov(M, leaves_prov(mined, M["leafcap"]), want, B):
        if calls >= B: break
        if want == "float": x = float(x)
        calls += 1
        if check(sat, x): sol = e; break
    if sol is None: stats["inst0_unsolved"] += 1; continue
    stats["inst0_solved"] += 1
    if len(insts) == 1: stats["no_hidden"] += 1; continue
    ok = 0
    for h in insts[1:]:
        _, hp, _, _ = analyse(h["sat"])
        try:
            x = ev(sol, hp); x = float(x) if want == "float" else x
            ok += check(load(h["sat"]), x)
        except Exception: pass
    stats["hidden_insts"] += len(insts) - 1; stats["hidden_ok"] += ok
    stats["lift_all"] += ok == len(insts) - 1; stats["lift_none"] += ok == 0
    if ok < len(insts) - 1: print("partial", f, ok, "/", len(insts) - 1, str(sol)[:100])
print(dict(stats))
