"""Open-world tool acquisition, development prototype.

discover(): introspect builtins / type attributes / chosen modules, characterise each callable by
             typed probing (inside the sandbox), keep pure, deterministic, non-mutating ones.
lift(): syntax templates from verifier source (holes for sub-expressions).
solve(): typed bottom-up enumeration over leaves harvested from the verifier, counted budgets.
"""
import ast, builtins, math, operator, itertools, string, json, sys, os, hashlib, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox import call_limited, Timeout, run_confined
from typing import List
sys.set_int_max_str_digits(0)

# ---------------- typed values ----------------

EXT_TYPES = set()      # learned representation: admitted opaque value types (by type name)
PRODUCERS = {}         # type name -> ids of callables producing it
UNKNOWN = {}           # type name -> sample values seen as outputs that no type could hold


def vtype(v):
    t = type(v)
    if t.__name__ in EXT_TYPES:
        return "T:" + t.__name__
    if t is bool: return "bool"
    if t is int: return "int"
    if t is float: return "float" if math.isfinite(v) else None
    if t is str: return "str"
    if t is list:
        if not v: return "list"
        et = {type(e) for e in v}
        if et == {int}: return "List[int]"
        if et == {str}: return "List[str]"
        if et <= {float, int} and float in et: return "List[float]"
        return None
    return None


def compatible(vt, want):
    return vt == want or (vt == "list" and want.startswith("List["))


def too_big(v):
    t = type(v)
    if t is int: return v.bit_length() > 20000
    if t in (str, list): return len(v) > 200000
    return False


def key(v):
    r = repr(v)
    return (vtype(v), r if len(r) < 300 else hashlib.sha1(r.encode()).hexdigest())

# probe inputs per type (mechanism parameter: the probe grammar)
PROBES = {
    "int": [0, 1, 2, 3, -1, 7, 10, 100],
    "str": ["", "a", "ab", "hello world", "a,b", "123", "aba"],
    "List[int]": [[], [1], [3, 1, 2], [1, 1, 2], [5, -2]],
    "List[str]": [["a", "b"], ["x"], ["ab", "c", "ab"]],
    "float": [0.5, 2.0, -1.5],
}
TYPES = list(PROBES)


def _clone(v):
    return list(v) if isinstance(v, list) else v


def characterise(f, arity):
    """typed signatures: list of (in_types, out_type) supported on >=2 of 3 samples;
    reject mutation and non-determinism."""
    sigs = []
    combos = itertools.product(TYPES, repeat=arity)
    for c in combos:
        allp = list(itertools.islice(itertools.product(*[PROBES[t] for t in c]), 200))
        step = max(1, len(allp) // 4)
        samples = allp[1::step][:4] if len(allp) > 4 else allp
        outs = set(); good = 0
        for s in samples:
            args = tuple(_clone(a) for a in s)
            try:
                o1 = call_limited(f, args, 0.01)
                o2 = call_limited(f, tuple(_clone(a) for a in s), 0.01)
            except BaseException:
                continue
            if any(a != b for a, b in zip(args, s)):   # mutated an input
                outs.add("MUT"); continue
            ot = vtype(o1)
            if ot is None:
                r1 = repr(o1)
                if r1 == repr(o2) and " at 0x" not in r1 and len(r1) < 2000:
                    UNKNOWN.setdefault(type(o1).__name__, {}).setdefault(r1, o1)
                    PRODUCERS.setdefault(type(o1).__name__, set()).add(id(f))
                continue
            if repr(o1) != repr(o2):
                continue
            outs.add(ot if ot != "list" else "list"); good += 1
        outs.discard("list")
        if "MUT" in outs or good < 2 or len(outs) != 1:
            continue
        sigs.append((c, outs.pop()))
    return sigs


# ---------------- discovery (exploration policy) ----------------

def candidate_callables(policy):
    out = []
    if "builtins" in policy:
        for n in dir(builtins):
            if n.startswith("_") or n in ("exit", "quit", "help", "input", "open", "print",
                                          "breakpoint", "exec", "eval", "compile", "__import__"):
                # these are refused by the sandbox anyway; skipping them saves probe cost
                continue
            f = getattr(builtins, n)
            if callable(f): out.append(("builtins." + n, f))
    if "typeattrs" in policy:
        for T in (int, str, list, float):
            for n in dir(T):
                if n in ("__init__", "__new__", "__init_subclass__", "__subclasshook__",
                         "__class__", "__getattribute__", "__setattr__", "__delattr__",
                         "__reduce__", "__reduce_ex__", "__dir__", "__sizeof__", "__format__"):
                    continue
                f = getattr(T, n)
                if callable(f): out.append((T.__name__ + "." + n, f))
    for m in policy.get("modules", []):
        mod = sys.modules[m]
        for n in dir(mod):
            if n.startswith("_"): continue
            f = getattr(mod, n)
            if callable(f) and not isinstance(f, type(sys)): out.append((m + "." + n, f))
    return out


def extend_representation(k=6, per=5):
    """Admit the k opaque output types produced most often, with probe values taken from
    the outputs themselves; returns the admitted names."""
    ranked = sorted(UNKNOWN, key=lambda n: (-len(PRODUCERS.get(n, ())), n))
    add = [n for n in ranked if n not in ("NoneType", "type", "builtin_function_or_method")][:k]
    for n in add:
        vals = [UNKNOWN[n][r] for r in sorted(UNKNOWN[n])][:per]
        EXT_TYPES.add(n); PROBES["T:" + n] = vals
        if "T:" + n not in TYPES: TYPES.append("T:" + n)
    return add


def _discover_ext_child(policy, max_arity, k=6):
    lib0, _ = _discover_child(policy, max_arity)
    added = extend_representation(k)
    lib, probes = _discover_child(policy, max_arity)
    return lib, probes, added, sorted(((len(PRODUCERS[n]), n) for n in PRODUCERS), reverse=True)[:12]


def _discover_child(policy, max_arity):
    lib = []; probes = 0
    for name, f in candidate_callables(policy):
        for a in range(1, max_arity + 1):
            sig = characterise(f, a)
            probes += len(TYPES) ** a
            if sig:
                lib.append((name, a, sig))
    return lib, probes


def discover(policy, max_arity=2):
    st, out, denied = run_confined(_discover_child, policy, max_arity, cpu_s=170)
    assert st == "ok", (st, out)
    lib, probes = out
    return lib, probes, denied


def resolve(name):
    head, n = name.split(".", 1)
    if head == "builtins": return getattr(builtins, n)
    if head in ("int", "str", "list", "float"): return getattr(getattr(builtins, head), n)
    return getattr(sys.modules[head], n)

# ---------------- syntax lifting from verifier source ----------------

class _Holer(ast.NodeTransformer):
    pass


def lift_templates(src):
    """For each expression node, a template where each direct sub-expression becomes a hole."""
    tree = ast.parse(src)
    fn = tree.body[0]
    out = set()
    for node in ast.walk(fn):
        if not isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Subscript, ast.Call)):
            continue
        holes = []
        def H(e):
            if isinstance(e, ast.Constant) and not isinstance(e.value, str):
                return e  # keep small structural constants (e.g. -1 in [::-1])
            if isinstance(e, ast.UnaryOp) and isinstance(e.operand, ast.Constant):
                return e
            nm = "h%d" % len(holes); holes.append(nm)
            return ast.Name(id=nm, ctx=ast.Load())
        n2 = None
        if isinstance(node, ast.BinOp):
            n2 = ast.BinOp(left=H(node.left), op=node.op, right=H(node.right))
        elif isinstance(node, ast.UnaryOp):
            n2 = ast.UnaryOp(op=node.op, operand=H(node.operand))
        elif isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Slice):
                sl2 = ast.Slice(lower=sl.lower and H(sl.lower), upper=sl.upper and H(sl.upper),
                                step=sl.step and H(sl.step))
            else:
                sl2 = H(sl)
            n2 = ast.Subscript(value=H(node.value), slice=sl2, ctx=ast.Load())
        elif isinstance(node, ast.Call):
            if node.keywords or any(isinstance(a, ast.Starred) for a in node.args): continue
            if isinstance(node.func, ast.Attribute):
                func = ast.Attribute(value=H(node.func.value), attr=node.func.attr, ctx=ast.Load())
            elif isinstance(node.func, ast.Name):
                func = node.func
            else:
                continue
            args = [H(a) if not isinstance(a, (ast.GeneratorExp, ast.ListComp)) else None for a in node.args]
            if any(a is None for a in args): continue
            n2 = ast.Call(func=func, args=args, keywords=[])
        if not holes or len(holes) > 3: continue
        lam = ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(h) for h in holes],
                                            kwonlyargs=[], kw_defaults=[], defaults=[]), body=n2)
        out.add(ast.unparse(lam))
    return out


def compile_template(t):
    return eval(t, {"__builtins__": builtins})  # template text is lifted verifier syntax


def _char_templates_child(tpls):
    res = []
    for t in sorted(tpls):
        try:
            f = compile_template(t)
        except Exception:
            continue
        a = f.__code__.co_argcount
        sig = characterise(f, a)
        if sig: res.append((t, a, sig))
    return res


def characterise_templates(tpls):
    st, out, d = run_confined(_char_templates_child, tpls, cpu_s=170)
    assert st == "ok", (st, out)
    return out

# ---------------- harvesting leaves from a verifier ----------------

def load_sat(src):
    g = {"List": List, "__builtins__": builtins}
    exec(src, g)
    return g["sat"]


def harvest_leaves(src, sat):
    tree = ast.parse(src); fn = tree.body[0]
    ansvar = fn.args.args[0].arg
    leaves = []
    if sat.__defaults__:
        leaves += list(sat.__defaults__)
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool) and node.value is not None:
            leaves.append(node.value)
    # closed sub-expressions (no reference to the answer variable or a local)
    params = {a.arg for a in fn.args.args[1:]}
    defaults = dict(zip([a.arg for a in fn.args.args[1:]], sat.__defaults__ or ()))
    for node in ast.walk(fn):
        if isinstance(node, ast.expr) and not isinstance(node, (ast.Constant, ast.Name)):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if ansvar in names: continue
            if any(isinstance(n, (ast.Lambda, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)) for n in ast.walk(node)):
                continue
            free = names - params - set(dir(builtins))
            if free: continue
            try:
                v = call_limited(eval, (compile(ast.Expression(node), "<c>", "eval"), dict(defaults, __builtins__=builtins)), 0.02)
                if vtype(v) and not too_big(v): leaves.append(v)
            except BaseException:
                pass
    return leaves


# ---------------- the composer ----------------

def solve(src, ans_type, lib, B=500, E=60000, seeds=(0, 1, 2, -1), order=None, depth=2):
    """Returns (solved, verifier_calls, op_apps, expr)."""
    sat = load_sat(src)
    leaves = harvest_leaves(src, sat) + list(seeds)
    pool = {}  # type -> list of (value, expr)
    seen = set()
    calls = 0; apps = 0
    want = ans_type

    def add(v, e, d=0):
        nonlocal calls
        vt = vtype(v)
        if vt is None or too_big(v): return False
        k = key(v)
        if k in seen: return False
        seen.add(k)
        pool.setdefault(vt, []).append((v, e, d))
        if compatible(vt, want) or (want == "float" and vt == "int"):
            calls += 1
            try:
                if call_limited(sat, (_clone(v) if want != "float" else float(v),), 0.02) is True:
                    return True
            except BaseException:
                pass
        return False

    for v in leaves:
        if add(v, repr(v)[:40]): return True, calls, apps, repr(v)[:60]
        if calls >= B: return False, calls, apps, None
    ops = lib if order is None else order(lib, src)
    for level in range(1, depth + 1):
        snapshot = {t: list(vs) for t, vs in pool.items()}
        for name, f, a, sigs in ops:
            for in_t, out_t in sigs:
                lists = [snapshot.get(t, []) + (snapshot.get("list", []) if t.startswith("List[") else []) for t in in_t]
                if any(not l for l in lists): continue
                for args in itertools.product(*lists):
                    if max(d for _, _, d in args) != level - 1:
                        continue  # at level L at least one argument comes from level L-1
                    apps += 1
                    if apps > E: return False, calls, apps, None
                    try:
                        v = call_limited(f, tuple(_clone(x) for x, _, _ in args), 0.005)
                    except BaseException:
                        continue
                    e = "%s(%s)" % (name, ",".join(x for _, x, _ in args))
                    if add(v, e, level): return True, calls, apps, e
                    if calls >= B: return False, calls, apps, None
    return False, calls, apps, None


# ---------------- indexer: behavioural de-duplication ----------------

def fingerprint(f, a, sigs):
    fp = []
    for in_t, out_t in sigs:
        for s in list(itertools.islice(itertools.product(*[PROBES[t] for t in in_t]), 60)):
            try:
                fp.append(repr(call_limited(f, tuple(_clone(x) for x in s), 0.01))[:100])
            except BaseException as e:
                fp.append("E")
    return hashlib.sha1(repr((a, sigs, fp)).encode()).hexdigest()


def build_lib(entries, dedupe=True):
    """entries: (name, arity, sigs) -> list of (name, fn, arity, sigs)."""
    out = []; fps = set()
    for name, a, sigs in entries:
        f = compile_template(name) if name.startswith("lambda") else resolve(name)
        sigs = [(tuple(i), o) for i, o in sigs if o != "bool"]   # bool outputs are not composable answers here
        if not sigs: continue
        if dedupe:
            h = fingerprint(f, a, sigs)
            if h in fps: continue
            fps.add(h)
        out.append((name, f, a, sigs))
    return out


# ---------------- representation edit: mutator -> function ----------------

def functionalise(f):
    def g(x, *rest):
        y = _clone(x)
        r = f(y, *rest)
        return y if r is None else r
    return g


class Wrapped:
    """name 'wrap:<inner>' resolves to functionalise(resolve(inner))."""


_resolve0 = resolve


def resolve(name):  # noqa: F811
    if name.startswith("wrap:"):
        return functionalise(_resolve0(name[5:]))
    return _resolve0(name)


def _discover_wrapped_child(policy, max_arity):
    lib = []
    for name, f in candidate_callables(policy):
        for a in range(1, max_arity + 1):
            if characterise(f, a):
                continue
            g = functionalise(f)
            sig = characterise(g, a)
            if sig:
                lib.append(("wrap:" + name, a, sig))
    return lib


def _discover_ext2_child(policy, max_arity, cap=8):
    """criterion v2: admit opaque types with >=3 distinct sample values that are bridges
    (some op maps known->T and some op maps T->known)."""
    _discover_child(policy, max_arity)
    cands = sorted((n for n in UNKNOWN if len(UNKNOWN[n]) >= 3), key=lambda n: (-len(UNKNOWN[n]), n))[:cap]
    for n in cands:
        vals = [UNKNOWN[n][r] for r in sorted(UNKNOWN[n])][:5]
        EXT_TYPES.add(n); PROBES["T:" + n] = vals; TYPES.append("T:" + n)
    lib, _ = _discover_child(policy, max_arity)
    keep = []
    for n in cands:
        t = "T:" + n
        into = any(o == t and all(not i.startswith("T:") for i in it) for _, _, s in lib for it, o in s)
        outof = any(t in it and not o.startswith("T:") and o != "bool" for _, _, s in lib for it, o in s)
        if into and outof: keep.append(n)
    for n in cands:
        if n not in keep:
            EXT_TYPES.discard(n); PROBES.pop("T:" + n); TYPES.remove("T:" + n)
    lib, probes = _discover_child(policy, max_arity)
    return lib, probes, cands, keep


def _discover_ext3_child(policy, max_arity, k=6):
    """criterion v3: score candidate opaque types by the number of NON-UNIVERSAL unary ops that
    consume them into a known type (an op accepting every probe type carries no information)."""
    _discover_child(policy, max_arity)
    cands = sorted(n for n in UNKNOWN if len(UNKNOWN[n]) >= 3)
    base_types = list(TYPES)
    for n in cands:
        EXT_TYPES.add(n); PROBES["T:" + n] = [UNKNOWN[n][r] for r in sorted(UNKNOWN[n])][:5]; TYPES.append("T:" + n)
    lib1, _ = _discover_child(policy, 1)
    nT = len(TYPES)
    score = {}
    for name, a, sigs in lib1:
        ins = {it[0] for it, o in sigs}
        if len(ins) >= 0.8 * nT:   # universal op
            continue
        for it, o in sigs:
            if it[0].startswith("T:") and not o.startswith("T:") and o != "bool":
                score.setdefault(it[0][2:], set()).add(name)
    ranked = sorted(score, key=lambda n: (-len(score[n]), n))
    keep = [n for n in ranked if len(score[n]) >= 2][:k]
    for n in cands:
        if n not in keep:
            EXT_TYPES.discard(n); PROBES.pop("T:" + n); TYPES.remove("T:" + n)
    lib, probes = _discover_child(policy, max_arity)
    return lib, probes, [(n, sorted(score[n])[:6]) for n in ranked[:10]], keep
