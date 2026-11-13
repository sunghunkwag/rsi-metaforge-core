"""Experiment 5 (Phase P angle): self-posed relaxation puzzles derived from unsolved EXTERNAL verifiers.
Each int literal / int default with |c| >= 10 becomes a parameter K_i; relaxed instances set K_i small.
M0 solves relaxed instances with provenance-tracking enumeration; the derivation is lifted to the
original constants and checked on the original verifier (1 call per lifted candidate)."""
import sys, json, random, collections, itertools, ast, os
os.environ["PREF"] = "1"
src = open('lift2.py').read().split("data = json.load")[0]
exec(src)
class Lit(ast.NodeTransformer):
    def __init__(s): s.k = []
    def visit_Constant(s, n):
        if isinstance(n.value, int) and not isinstance(n.value, bool) and abs(n.value) >= 10:
            s.k.append(n.value); return ast.copy_location(ast.Name(id=f"K{len(s.k)-1}", ctx=ast.Load()), n)
        return n
def parametrise(sat_src):
    tree = ast.parse(sat_src); fn = tree.body[0]
    ans = fn.args.args[0]; olds = fn.args.args[1:]; defs = [ast.literal_eval(d) for d in fn.args.defaults]
    # int params become K's too
    env = {}
    t = Lit(); fn.body = [t.visit(b) for b in fn.body]
    ks = list(t.k)
    newargs = [ans]; newdefs = []
    for a, d in zip(olds, defs):
        if isinstance(d, int) and not isinstance(d, bool) and abs(d) >= 10:
            # rename param to keep, add K alias
            ks.append(d); fn.body.insert(0, ast.parse(f"{a.arg} = K{len(ks)-1}").body[0])
        else:
            newargs.append(a); newdefs.append(d)
    fn.args.args = newargs + [ast.arg(arg=f"K{i}") for i in range(len(ks))]
    fn.args.defaults = [ast.Constant(value=v) for v in newdefs] + [ast.Constant(value=v) for v in ks]
    return ks, newdefs, newargs, fn
def with_defaults(fn, vals_other, ks):
    fn2 = copy.deepcopy(fn); fn2.args.defaults = [ast.Constant(value=v) for v in vals_other] + [ast.Constant(value=v) for v in ks]
    return ast.unparse(fn2)
data = json.load(open('../p3_development.json'))
first = {}
for d in data: first.setdefault(d["name"].split(":")[0], d)
B = 150; st = collections.Counter(); wins = []
for f, i0 in first.items():
    sat = load(i0["sat"]); want = ANSMAP[i0["ans_type"]]
    _, params, mined, _ = analyse(i0["sat"])
    base = None; calls = 0
    for e, x in enum_prov(M0, leaves_prov(mined, M0["leafcap"]), want, B):
        if calls >= B: break
        calls += 1
        if check(sat, float(x) if want == "float" else x): base = e; break
    if base is not None: continue
    st["unsolved_by_M0"] += 1
    ks, others, _, fn = parametrise(i0["sat"])
    if not ks: st["no_int_literals"] += 1; continue
    st["relaxable"] += 1; solved_orig = False; tried_calls = 0
    for scale in (lambda c: (1 if c > 0 else -1) * 3, lambda c: (1 if c > 0 else -1) * 5, lambda c: (1 if c > 0 else -1) * 12):
        rk = [scale(c) for c in ks]
        rsrc = with_defaults(fn, others, rk)
        try: rsat = load(rsrc); _, rp, rmined, _ = analyse(rsrc)
        except Exception: continue
        calls = 0
        for e, x in enum_prov(M0, leaves_prov(rmined, M0["leafcap"]), want, B):
            if calls >= B: break
            calls += 1; tried_calls += 1
            if want == "float": x = float(x)
            if check(rsat, x):
                st["relaxed_solved"] += 1; print(f, rk, str(e)[:150], flush=True)
                # lift: evaluate derivation under ORIGINAL constants (params of the parametrised verifier)
                origp = dict(rp); origp.update({f"K{i}": c for i, c in enumerate(ks)})
                try:
                    y = ev(e, origp); y = float(y) if want == "float" else y
                    tried_calls += 1
                    if sizeok(y) and check(sat, y): solved_orig = True
                except Exception: pass
                break
        if solved_orig: break
    st["original_solved_via_relaxation"] += solved_orig
    if solved_orig: wins.append((f, tried_calls))
print(dict(st)); print("wins (family, calls incl. relaxed):", wins)
