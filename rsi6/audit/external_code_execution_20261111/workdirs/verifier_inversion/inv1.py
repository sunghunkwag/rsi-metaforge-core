"""v1: the mechanism M is a data structure (strategy program) interpreted by a fixed kernel.
M = {"active": [primitive ids], "stages": [stage dicts], "objective": {kind: rule}, "leafcap": int}
Primitive pool: harvested mechanically from Python's own types (dir(str), dir(list), dir(int)),
operator module and a few builtins; signatures found by probing, not written by hand.
Meta step: propose structural edits to M (activate/deactivate primitives, chosen by residue of
unsolved verifiers' AST names; add/remove/reorder stages; swap objective rules; change budget
shares), evaluate on train modules, adopt only if a held-out module set improves.
"""
import ast, json, signal, sys, math, random, time, itertools, collections, operator, copy, hashlib
sys.setrecursionlimit(10000)
import resource; resource.setrlimit(resource.RLIMIT_AS, (3*2**30, 3*2**30))
from typing import List
exec(open(__file__.replace("inv1.py", "inv0_lib.py")).read())

# ---------------- primitive pool: mechanical harvest ----------------
SAMPLES = {"int": [0, 1, 2, 3, 7, -2, 10], "str": ["", "a", "ab", "foo bar", "x!y!z", "Hello"], "list": [[], [1], [3, 1, 2], [1, 1, 2]], "lstr": [["a", "b"], ["foo", "bar"]]}
def tname(v):
    if isinstance(v, bool): return "bool"
    if isinstance(v, int): return "int"
    if isinstance(v, float): return "float"
    if isinstance(v, str): return "str"
    if isinstance(v, list):
        h = v[:8] + v[-8:]
        if h and all(isinstance(e, str) for e in h): return "lstr"
        if all(isinstance(e, int) and not isinstance(e, bool) for e in h): return "list"
        return "lmix"
    return None

def harvest():
    pool = {}
    def add(pid, fn, argt):
        outs = set()
        for args in itertools.product(*[SAMPLES[t] for t in argt]):
            try:
                r = timed(fn, *args, t=0.05)
                if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
                if tname(r) and sizeok(r): outs.add(tname(r))
            except BaseException:
                pass
        if len(outs) == 1:
            pool[pid] = (fn, tuple(argt), outs.pop())
    for T, tn in ((str, "str"), (list, "list")):
        for m in dir(T):
            if m.startswith("_") or m in ("clear", "pop", "remove", "insert", "append", "extend", "sort", "reverse", "copy"):
                continue
            meth = getattr(T, m)
            for argt in ([tn], [tn, "int"], [tn, "str"], [tn, "str", "str"], [tn, "lstr"] if tn == "str" else [tn, "int", "int"]):
                add(f"{tn}.{m}/{len(argt)-1}:" + ",".join(argt[1:]), (lambda meth: lambda *a: meth(*a))(meth), argt)
    for name in ("add", "sub", "mul", "floordiv", "mod", "neg", "abs", "getitem"):
        f = getattr(operator, name)
        for argt in (["int", "int"], ["int"], ["str", "str"], ["str", "int"], ["list", "list"], ["list", "int"]):
            add(f"op.{name}:" + ",".join(argt), f, argt)
    for name, f in (("len", len), ("sorted", sorted), ("str", str), ("int", int), ("sum", sum), ("max", max), ("min", min), ("list", list),
                    ("range", lambda n: list(range(n)) if 0 <= n <= MAXLEN else None), ("rev", lambda s: s[::-1]), ("isqrt", lambda n: math.isqrt(n) if n >= 0 else None),
                    ("take", lambda s, n: s[:n]), ("drop", lambda s, n: s[n:]), ("rep", lambda s, n: s * n if 0 <= n and len(s) * n <= MAXLEN else None)):
        for argt in (["int"], ["str"], ["list"], ["lstr"], ["str", "int"], ["list", "int"]):
            add(f"b.{name}:" + ",".join(argt), f, argt)
    return pool
POOL = harvest()

GENERIC0 = [p for p in POOL if p.startswith(("op.add", "op.sub", "op.mul", "op.floordiv", "op.neg", "b.rev", "b.take", "b.drop", "b.rep", "b.range", "b.list", "b.len"))]

M0 = {"active": sorted(GENERIC0),
      "stages": [{"op": "enum", "depth": 2, "share": 0.6}, {"op": "climb", "seed": "best", "share": 0.4}],
      "objective": {"eq": "seqdist", "bool": "01"},
      "leafcap": 30}

def leaves_of(mined, cap):
    out = []
    for src, v in mined:
        out.append(v)
        if isinstance(v, list):
            out.extend(v[:20])
    for k in (0, 1, 2, -1, 10): out.append(k)
    seen = set(); L = []
    for v in out:
        t = tname(v)
        if t is None: continue
        key = (t, repr(v)[:300])
        if key in seen: continue
        seen.add(key); L.append(v)
    return L[:cap * 2]

def enumerate_exprs(M, leaves, want, budget_vals):
    """bottom-up typed enumeration; yields values of type `want` in order of depth."""
    level = collections.defaultdict(list); seen = set()
    for v in leaves:
        t = tname(v); key = (t, repr(v)[:500])
        if key not in seen: seen.add(key); level[t].append(v)
    allv = {t: list(vs) for t, vs in level.items()}
    for v in allv.get(want, []): yield v
    prims = [POOL[p] for p in M["active"] if p in POOL]
    produced = 0
    for d in range(1, M["stages"][0].get("depth", 2) + 1):
        new = collections.defaultdict(list)
        for fn, argt, out in prims:
            pools = [allv.get(t, [])[:M["leafcap"]] for t in argt]
            for args in itertools.product(*pools):
                produced += 1
                if produced > budget_vals * M.get('expand', 20): return
                if out in ("str", "list", "lstr") and any(isinstance(a, int) and abs(a) > 10 ** 5 for a in args): continue
                if out == "int" and any(isinstance(a, int) and abs(a) > 10 ** 30 for a in args) and fn is operator.mul: continue
                try:
                    r = fn(*args)
                    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
                except Exception:
                    continue
                if r is None or not sizeok(r): continue
                if isinstance(r, (str, list)) and len(r) > 3000:
                    if tname(r) == want: yield r
                    continue
                if isinstance(r, int) and abs(r) > 10 ** 60: continue
                t = tname(r)
                if t is None: continue
                key = (t, repr(r)[:500] if not isinstance(r, (str, list)) or len(r) < 200 else (len(r), hash(repr(r))))
                if key in seen: continue
                seen.add(key); new[t].append(r)
                if t == want or (want == "float" and t == "int"):
                    yield r
        for t, vs in new.items(): allv.setdefault(t, []).extend(vs)

ANSMAP = {"int": "int", "str": "str", "List[int]": "list", "List[str]": "lstr", "float": "float"}

def run_M(M, inst, budget, rng):
    sat = load(inst["sat"])
    ans, params, mined, cfuns = analyse(inst["sat"])
    want = ANSMAP.get(inst["ans_type"])
    calls = 0; best = []
    leaves = leaves_of(mined, M["leafcap"])
    for st in M["stages"]:
        cap = calls + int(budget * st["share"])
        if st["op"] == "enum":
            for x in enumerate_exprs(M, leaves, want, budget):
                if calls >= cap: break
                if want == "float": x = float(x)
                calls += 1
                if check(sat, x): return calls, x
                if cfuns and st.get("keep", 1):
                    best.append((score(cfuns, x), calls, x)); best = sorted(best, key=lambda z: z[:2])[:5]
        elif st["op"] == "climb":
            ints, flts, strs, lists = base_vals(mined)
            start = best[0][2] if (st.get("seed") == "best" and best) else {"int": 0, "float": 0.0, "str": "", "list": [], "lstr": []}.get(want)
            cur = start; cs = score(cfuns, cur) if cfuns else 1.0
            while calls < cap:
                y = mutate(cur, rng, ints or [1], strs or ["a"])
                if not sizeok(y): continue
                calls += 1
                if check(sat, y): return calls, y
                if cfuns:
                    ys = score(cfuns, y)
                    if ys <= cs: cur, cs = y, ys
                else:
                    cur = y
    return calls, None

def evaluate(M, data, budget, seed=0):
    rng = random.Random(seed); solved = set(); calls = 0
    for inst in data:
        try:
            c, x = run_M(M, inst, budget, rng)
        except BaseException:
            c, x = budget, None
        calls += c
        if x is not None: solved.add(inst["name"])
    return solved, calls

# ---------------- meta level: proposals from residue ----------------
def residue_names(data, solved):
    """attribute/call names appearing in verifiers of unsolved instances (external residue)."""
    cnt = collections.Counter()
    for inst in data:
        if inst["name"] in solved: continue
        for n in ast.walk(ast.parse(inst["sat"])):
            if isinstance(n, ast.Attribute): cnt[n.attr] += 1
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name): cnt[n.func.id] += 1
    return cnt

def propose(M, data, solved, rng, k):
    res = residue_names(data, solved)
    props = []
    inactive = [p for p in POOL if p not in M["active"]]
    # residue-linked activations: primitives whose name matches a residue name, or whose name is a
    # known inverse partner by experiment (checked below), ranked by residue count
    def pname(p): return p.split(":")[0].split(".")[-1].split("/")[0]
    ranked = sorted(inactive, key=lambda p: -res.get(pname(p), 0))
    for p in ranked[:k]:
        if res.get(pname(p), 0) > 0:
            m2 = copy.deepcopy(M); m2["active"] = sorted(m2["active"] + [p]); props.append(("activate", p, m2))
    # structural edits
    for _ in range(k):
        m2 = copy.deepcopy(M); kind = rng.choice(["depth", "share", "addclimb", "drop", "leafcap", "seed", "random_activate"])
        if kind == "depth": m2["stages"][0]["depth"] = rng.choice([1, 2, 3])
        elif kind == "share": s = rng.choice([0.3, 0.5, 0.7, 0.9]); m2["stages"][0]["share"] = s; m2["stages"][-1]["share"] = 1 - s
        elif kind == "addclimb": m2["stages"].append({"op": "climb", "seed": "zero", "share": 0.2}); m2["stages"][0]["share"] *= 0.8
        elif kind == "drop" and len(m2["active"]) > 3: m2["active"].remove(rng.choice(m2["active"]))
        elif kind == "leafcap": m2["leafcap"] = rng.choice([15, 30, 50])
        elif kind == "seed": m2["stages"][-1]["seed"] = "zero" if m2["stages"][-1].get("seed") == "best" else "best"
        elif kind == "random_activate" and inactive: m2["active"] = sorted(m2["active"] + [rng.choice(inactive)])
        props.append((kind, "", m2))
    return props

if __name__ == "__main__":
    data = json.load(open(sys.argv[1])); B = int(sys.argv[2]); gens = int(sys.argv[3])
    fold = sys.argv[4] if len(sys.argv) > 4 else "A"
    trainmods = {"A": {"trivial_inverse.py", "study.py"}, "B": {"basic.py", "tutorial.py"}}[fold]
    first = {}
    for d in data: first.setdefault(d["name"].split(":")[0], d)
    data = list(first.values())
    tr = [d for d in data if d["module"] in trainmods]; va = [d for d in data if d["module"] not in trainmods]
    print("pool size", len(POOL), "M0 active", len(M0["active"]), "train", len(tr), "valid", len(va))
    rng = random.Random(1)
    import os
    stf = f"state_{fold}.json"
    M = json.load(open(stf)) if os.path.exists(stf) else M0
    rng = random.Random(len(open(stf).read()) if os.path.exists(stf) else 1)
    s_tr, c_tr = evaluate(M, tr, B); s_va, c_va = evaluate(M, va, B)
    print(f"gen0 train {len(s_tr)} valid {len(s_va)} calls {c_tr+c_va}")
    meta_calls = 0
    for g in range(gens):
        props = propose(M, tr, s_tr, rng, 5)
        scored = []
        for kind, p, m2 in props:
            s2, c2 = evaluate(m2, tr, B); meta_calls += c2
            scored.append((len(s2) - len(s_tr), kind, p, m2, s2))
        scored.sort(key=lambda z: -z[0])
        top = scored[0]
        if top[0] <= 0:
            print(f"gen{g+1} no train-improving proposal ({len(props)} tried)"); continue
        v2, _ = evaluate(top[3], va, B)
        lost = len(s_va - v2); gain = len(v2 - s_va)
        verdict = "ADOPT" if gain - lost >= 1 and lost <= 1 else "REJECT"
        print(f"gen{g+1} best train dTrain=+{top[0]} {top[1]} {top[2]} valid {len(s_va)}->{len(v2)} (gain {gain} lost {lost}) {verdict}")
        if verdict == "ADOPT":
            M = top[3]; s_tr = top[4]; s_va = v2
    json.dump(M, open(stf, "w"))
    print("final active added:", sorted(set(M["active"]) - set(M0["active"])), "removed:", sorted(set(M0["active"]) - set(M["active"])))
    print("final stages", M["stages"], "leafcap", M["leafcap"], "meta train calls", meta_calls)
