"""Experiment 4: top-down inversion of verifier conjuncts with mechanically discovered inverses.
For each Eq conjunct L == R where exactly one side mentions the answer, walk the answer side's AST
from the root: at an operation node with the answer in one argument, map the node to pool op ids by
name, evaluate the closed arguments, apply the discovered inverse to the current target, recurse.
Each resulting candidate costs one verifier call. Compared against M0 enumeration at budget 150 and
against the union (inversion first, then M0 with the remaining budget)."""
import sys, json, random, collections, itertools, pickle, ast, os
sys.argv=[sys.argv[0]]
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))
INV = pickle.load(open("inverses.pkl", "rb")) if os.environ.get("NOINV") != "1" else {}
def norm(r):
    if isinstance(r, (tuple, range, set, map, filter, reversed)) or hasattr(r, "__next__"): r = list(r)
    return r
def evg(e, env):
    if isinstance(e, str): return env[e] if e in env else eval(e)
    return norm(POOL[e[0]][0](*[evg(c, env) for c in e[1]]))
BINOPS = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.FloorDiv: "floordiv", ast.Mod: "mod"}
def mentions(n, name): return any(isinstance(x, ast.Name) and x.id == name for x in ast.walk(n))
def op_matches(node, ans):
    """yield (name_key, ans_position, other_arg_nodes) for a node applying an op to an answer-dependent arg."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        args = [node.func.value] + list(node.args)
        yield ("." + node.func.attr + "/" + str(len(node.args)) + ":", args)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        yield ("b." + node.func.id + ":", list(node.args))
    elif isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
        yield ("op." + BINOPS[type(node.op)] + ":", [node.left, node.right])
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        yield ("op.neg:", [node.operand])
    elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice) and node.slice.step is not None and node.slice.lower is None and node.slice.upper is None:
        yield ("b.rev:", [node.value])
def invert(node, target, ans, env, depth=0):
    """yield candidate answers x such that node[ans:=x] plausibly == target."""
    if isinstance(node, ast.Name) and node.id == ans:
        yield target; return
    if depth > 4: return
    for key, args in op_matches(node, ans):
        pos = [i for i, a in enumerate(args) if mentions(a, ans)]
        if len(pos) != 1: continue
        p = pos[0]
        try: others = [eval(compile(ast.Expression(a), "<a>", "eval"), dict(ENV, **env)) for i, a in enumerate(args) if i != p]
        except Exception: continue
        for pid, g in INV.items():
            if key not in pid: continue
            fn, argt, out = POOL[pid]
            if tname(target) != out: continue
            # commutative swap: inverse expects answer in slot 0
            if p != 0 and not pid.startswith(("op.add", "op.mul")): continue
            try: sub = evg(g, {"y": target, **{f"c{i}": c for i, c in enumerate(others)}})
            except Exception: continue
            yield from invert(args[p], sub, ans, env, depth + 1)
def inversion_candidates(sat_src):
    tree = ast.parse(sat_src); fn = tree.body[0]; ans = fn.args.args[0].arg
    params = dict(zip([a.arg for a in fn.args.args[1:]], [ast.literal_eval(d) for d in fn.args.defaults]))
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.Eq):
            l, r = n.left, n.comparators[0]
            for a, b in ((l, r), (r, l)):
                if mentions(a, ans) and not mentions(b, ans):
                    try: tgt = eval(compile(ast.Expression(b), "<t>", "eval"), dict(ENV, **params))
                    except Exception: continue
                    yield from invert(a, norm(tgt), ans, params)
data = json.load(open('../p3_development.json'))
first = {}
for d in data: first.setdefault(d["name"].split(":")[0], d)
B = 150; rng = random.Random(0)
res = collections.Counter(); onlyinv = []
for scope, insts in (("first-instance-per-family", list(first.values())), ("all-instances", data)):
    c = collections.Counter()
    for inst in insts:
        sat = load(inst["sat"]); calls = 0; hit = False
        for x in itertools.islice(inversion_candidates(inst["sat"]), 20):
            if inst["ans_type"] == "float": 
                try: x = float(x)
                except Exception: continue
            calls += 1
            if check(sat, x): hit = True; break
        try: c0, x0 = run_M(M0, inst, B, random.Random(0))
        except BaseException: x0 = None
        u = hit
        if not hit:
            try: c1, x1 = run_M(M0, inst, B - calls, random.Random(0)); u = x1 is not None
            except BaseException: pass
        c["inversion_alone"] += hit; c["M0"] += x0 is not None; c["inversion_then_M0"] += u
        if hit and x0 is None and scope.startswith("first"): onlyinv.append(inst["name"])
    print(scope, len(insts), dict(c))
print("solved by inversion but not M0 (first instances):", onlyinv)
