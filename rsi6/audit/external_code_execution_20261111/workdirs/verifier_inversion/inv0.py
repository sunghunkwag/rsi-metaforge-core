"""Prototype core of a verifier-inversion acquisition mechanism (M_0) on P3 development puzzles.
Pipeline per instance: parse sat -> mine closed sub-expression values -> conjunct split ->
graded objective -> stage 1 enumerate typed candidates from mined values via derivation
expressions -> stage 2 hill-climb with typed mutations on the graded objective.
Every candidate evaluation of the full sat counts as one verifier call (the budget unit).
"""
import ast, json, signal, sys, math, random, time, itertools, collections
from typing import List

DEV = sys.argv[1]
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
MODE = sys.argv[3] if len(sys.argv) > 3 else "full"   # full | enum | random
MAXLEN = 200000

class TO(Exception): pass
def _h(s, f): raise TO()
signal.signal(signal.SIGALRM, _h)

def timed(fn, *a, t=0.2):
    signal.setitimer(signal.ITIMER_REAL, t)
    try:
        return fn(*a)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

def sizeok(v):
    if isinstance(v, (str, list, tuple, set, dict)):
        return len(v) <= MAXLEN
    if isinstance(v, int) and not isinstance(v, bool):
        return abs(v) < 10 ** 4000
    return True

ENV = {"List": List, "math": math}

def load(sat_src):
    g = dict(ENV); exec(sat_src, g); return g["sat"]

def analyse(sat_src):
    tree = ast.parse(sat_src)
    fn = tree.body[0]
    ans = fn.args.args[0].arg
    pnames = [a.arg for a in fn.args.args[1:]]
    defaults = [ast.literal_eval(d) for d in fn.args.defaults]
    params = dict(zip(pnames, defaults))
    # conjuncts: only for single-return bodies
    conj = []
    if len(fn.body) == 1 and isinstance(fn.body[0], ast.Return):
        e = fn.body[0].value
        conj = e.values if isinstance(e, ast.BoolOp) and isinstance(e.op, ast.And) else [e]
    # closed sub-expressions: nodes not mentioning ans and not bound by comprehensions
    mined = []
    def uses(n, names):
        return any(isinstance(x, ast.Name) and x.id in names for x in ast.walk(n))
    bound = {t.id for c in ast.walk(fn) if isinstance(c, ast.comprehension) for t in ast.walk(c.target) if isinstance(t, ast.Name)}
    bound |= {t.id for c in ast.walk(fn) if isinstance(c, (ast.For,)) for t in ast.walk(c.target) if isinstance(t, ast.Name)}
    bound |= {t.id for c in ast.walk(fn) if isinstance(c, ast.Assign) for tt in c.targets for t in ast.walk(tt) if isinstance(t, ast.Name)}
    for n in ast.walk(fn):
        if isinstance(n, ast.expr) and not uses(n, {ans} | bound) and not isinstance(n, (ast.Name,)) or (isinstance(n, ast.Name) and n.id in params):
            if isinstance(n, ast.Name) and n.id not in params: continue
            try:
                v = timed(eval, compile(ast.Expression(n), "<m>", "eval"), dict(ENV, **params), t=0.2)
            except BaseException:
                continue
            if isinstance(v, (int, float, str, list, tuple, set, range)) and not isinstance(v, bool) and sizeok(v):
                if isinstance(v, (range, tuple, set)): v = list(v)
                src = ast.unparse(n)
                mined.append((src, v))
    # conjunct objective functions: compile each conjunct as lambda ans, **params
    cfuns = []
    for c in conj:
        # for comparisons A op B produce a distance; otherwise 0/1
        try:
            if isinstance(c, ast.Compare) and len(c.ops) == 1 and isinstance(c.ops[0], ast.Eq):
                l, r = ast.unparse(c.left), ast.unparse(c.comparators[0])
                f = eval(f"lambda {ans}, {', '.join(pnames + ['_'])}=None: ({l}, {r})".replace(", _=None", ", _=None"), dict(ENV, **params))
                cfuns.append(("eq", f))
            else:
                f = eval(f"lambda {ans}: bool({ast.unparse(c)})", dict(ENV, **params))
                cfuns.append(("bool", f))
        except BaseException:
            pass
    return ans, params, mined, cfuns

def dist(a, b):
    if isinstance(a, bool) or isinstance(b, bool): return 0.0 if a == b else 1.0
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = abs(a - b); return d / (1 + d)
    if isinstance(a, (str, list)) and isinstance(b, (str, list)):
        n = max(len(a), len(b)) or 1
        same = sum(1 for x, y in zip(a, b) if x == y)
        return 1 - same / n
    return 0.0 if a == b else 1.0

def score(cfuns, x):
    s = 0.0
    for kind, f in cfuns:
        try:
            if kind == "eq":
                a, b = timed(f, x, t=0.05); s += dist(a, b)
            else:
                s += 0.0 if timed(f, x, t=0.05) else 1.0
        except BaseException:
            s += 1.0
    return s

# ---------- typed candidate generation from mined values (derivation expressions) ----------
def base_vals(mined):
    ints = [v for _, v in mined if isinstance(v, int)]
    flts = [v for _, v in mined if isinstance(v, float)]
    strs = [v for _, v in mined if isinstance(v, str)]
    lists = [v for _, v in mined if isinstance(v, list)]
    for L in lists:
        for e in L[:50]:
            if isinstance(e, str): strs.append(e)
            elif isinstance(e, int) and not isinstance(e, bool): ints.append(e)
    ints = list(dict.fromkeys(ints + [0, 1, 2, -1, 10]))[:40]
    strs = list(dict.fromkeys(strs + ["", "a", "ab"]))[:40]
    return ints, flts, strs, lists

def gen_int(ints):
    yield from ints
    for a in ints: yield -a
    for a, b in itertools.product(ints, repeat=2):
        yield a + b; yield a - b; yield a * b
        if b: yield a // b; yield a % b
    for a in ints:
        if a >= 0: r = math.isqrt(a); yield r; yield -r
    for a, b in itertools.product(ints, repeat=2):
        if b and abs(a) < 10 ** 30: yield a * b + 1; yield a * b - 1; yield (a // b) * b
    for k in range(-1000, 1000): yield k

def gen_float(ints, flts):
    for v in flts + ints: yield float(v); yield -float(v)
    for v in flts + ints:
        if v >= 0: yield math.sqrt(v); yield -math.sqrt(v)
    for a, b in itertools.product(flts + ints, repeat=2):
        yield float(a + b); yield float(a - b)
        if b: yield a / b

def gen_str(ints, strs):
    for s in strs: yield s; yield s[::-1]
    for s, t in itertools.product(strs, repeat=2):
        if s.startswith(t): yield s[len(t):]
        if s.endswith(t): yield s[:-len(t)] if t else s
        yield s + t
    for s in strs:
        for n in ints:
            if 0 < n < 5000 and len(s) * n < MAXLEN: yield s * n
            if 0 < n <= len(s) and len(s) % n == 0: yield s[: len(s) // n]
        for i in range(len(s)):
            for j in range(i + 1, min(len(s), i + 20) + 1):
                yield s[i:j]
    for n in ints:
        if 0 < n < MAXLEN: yield "a" * n; yield str(n)
    for s in strs:
        for n in ints:
            if 0 <= n < 100 and s: yield "".join(sorted(s))[:n]

def gen_list_int(ints, lists):
    for L in lists:
        if all(isinstance(e, int) for e in L): yield list(L); yield L[::-1]; yield sorted(L)
    for n in ints:
        if 0 < n < MAXLEN: yield list(range(n)); yield [0] * n; yield [1] * n
    for a, b in itertools.product(ints, repeat=2): yield [a, b]
    for a, b, c in itertools.product(ints[:15], repeat=3): yield [a, b, c]

def gen_list_str(ints, strs, lists):
    for L in lists:
        if all(isinstance(e, str) for e in L): yield list(L)
    for n in ints:
        if 0 < n < 5000: yield [str(i) for i in range(n)]; yield ["a"] * n
    for s in strs: yield list(s); yield [s]

def candidates(ans_type, mined):
    ints, flts, strs, lists = base_vals(mined)
    if ans_type == "int": return gen_int(ints)
    if ans_type == "float": return gen_float(ints, flts)
    if ans_type == "str": return gen_str(ints, strs)
    if ans_type == "List[int]": return gen_list_int(ints, lists)
    if ans_type == "List[str]": return gen_list_str(ints, strs, lists)
    return iter(())

# ---------- typed mutations for graded hill-climb ----------
def mutate(x, rng, ints, strs):
    if isinstance(x, bool): return x
    if isinstance(x, int):
        k = rng.choice([1, 1, 2, 10, 100, 1000, 10 ** 6, rng.choice(ints) or 1])
        return x + rng.choice([-1, 1]) * k if rng.random() < .8 else rng.choice(ints)
    if isinstance(x, float):
        return x + rng.gauss(0, 1) * 10 ** rng.randint(-6, 3)
    if isinstance(x, str):
        alph = "".join(set("".join(strs)))[:60] or "ab"
        op = rng.randrange(4); i = rng.randint(0, len(x))
        if op == 0: return x[:i] + rng.choice(alph) + x[i:]
        if op == 1 and x: return x[:i] + x[i + 1:]
        if op == 2 and x and i < len(x): return x[:i] + rng.choice(alph) + x[i + 1:]
        return x + rng.choice(strs)
    if isinstance(x, list):
        x = list(x); op = rng.randrange(4); i = rng.randint(0, len(x))
        el = (rng.choice(ints) if not x or isinstance(x[0], int) else rng.choice(strs))
        if op == 0: x.insert(i, el)
        elif op == 1 and x: x.pop(min(i, len(x) - 1))
        elif op == 2 and x: x[min(i, len(x) - 1)] = mutate(x[min(i, len(x) - 1)], rng, ints, strs)
        else: x.append(el)
        return x
    return x

def check(sat, x):
    try: return timed(sat, x, t=0.2) is True
    except BaseException: return False

def solve(inst, budget, mode, rng):
    sat = load(inst["sat"])
    ans, params, mined, cfuns = analyse(inst["sat"])
    calls = 0
    seen = set()
    if mode in ("full", "enum"):
        frac = 1.0 if mode == "enum" else 0.5
        for x in candidates(inst["ans_type"], mined):
            if calls >= budget * frac: break
            if not sizeok(x): continue
            key = repr(x)[:2000] if not isinstance(x, (str, list)) or len(x) < 500 else (type(x).__name__, len(x), hash(repr(x)))
            if key in seen: continue
            seen.add(key); calls += 1
            if check(sat, x): return calls, "enum", x
    if mode == "random":
        pass
    ints, flts, strs, lists = base_vals(mined)
    # hill-climb from best enumerated seeds (graded objective, not counted as verifier calls? -> count them)
    start = {"int": 0, "float": 0.0, "str": "", "List[int]": [], "List[str]": []}.get(inst["ans_type"])
    cur, cs = start, score(cfuns, start) if cfuns else 1.0
    while calls < budget:
        y = mutate(cur, rng, ints, strs) if mode != "random" or rng.random() < 2 else cur
        if not sizeok(y): continue
        calls += 1
        if check(sat, y): return calls, "climb", y
        if cfuns:
            ys = score(cfuns, y)
            if ys <= cs: cur, cs = y, ys
        else:
            cur = y
    return calls, None, None

def main():
    data = json.load(open(DEV))
    rng = random.Random(0)
    res = collections.Counter(); bymod = collections.defaultdict(lambda: [0, 0]); fams = collections.defaultdict(list)
    tot_calls = 0; t0 = time.time(); solved_calls = []
    for inst in data:
        try:
            calls, how, x = solve(inst, BUDGET, MODE, rng)
        except BaseException as e:
            calls, how = BUDGET, None
        tot_calls += calls
        res[how] += 1
        bymod[inst["module"]][0] += 1; bymod[inst["module"]][1] += how is not None
        fams[inst["name"].split(":")[0]].append(how is not None)
        if how: solved_calls.append(calls)
    n = len(data); s = n - res[None]
    print(f"budget={BUDGET} mode={MODE} solved {s}/{n} instances  how={dict(res)}")
    print("per module", {k: tuple(v) for k, v in bymod.items()})
    print("families with >=1 solved", sum(any(v) for v in fams.values()), "/", len(fams), " all instances solved", sum(all(v) for v in fams.values()))
    solved_calls.sort()
    if solved_calls: print("median calls per solve", solved_calls[len(solved_calls)//2], "total calls", tot_calls, "wall", round(time.time()-t0,1))
    unsolved = sorted({k for k, v in fams.items() if not any(v)})
    print("unsolved families:", " ".join(unsolved))

main()
