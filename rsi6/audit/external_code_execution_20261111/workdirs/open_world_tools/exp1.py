"""Dev experiment 1: what each acquisition source adds. usage: exp1.py ARM B E"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import owt
from sandbox import run_confined
W = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/review17/work"
P = json.load(open(W + "/p3_development.json"))
arm, B, E = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fam = lambda x: x["name"].split(":")[0]

def lexical(lib, src):
    toks = set(re.findall(r"[A-Za-z_]+", src))
    def sc(o):
        n = o[0]
        short = n.split(".")[-1] if not n.startswith("lambda") else ""
        return 0 if (short.strip("_") in toks or n.startswith("lambda")) else 1
    return sorted(lib, key=sc)

def run():
    t0 = time.time()
    entries = []
    if arm != "A0":
        pol = {"builtins": 1}
        if arm != "A1": pol["typeattrs"] = 1
        if arm.startswith("A3"): pol["modules"] = ["math", "operator", "itertools", "string"]
        if "X" in arm[2:]:
            entries, probes, ranked, kept = owt._discover_ext3_child(pol, 2)
            print("admitted types", kept)
        else:
            entries, probes = owt._discover_child(pol, 2)
        if "W" in arm:
            entries = entries + owt._discover_wrapped_child(pol, 2)
    base = owt.build_lib(entries)
    tcache = {}
    def tpl_entries(srcs):
        out = []
        for s in srcs:
            if s not in tcache:
                tcache[s] = owt._char_templates_child(owt.lift_templates(s))
            out += tcache[s]
        return out
    res = []
    fams = sorted({fam(x) for x in P})
    for x in P:
        lib = base
        if arm.rstrip("LWX") in ("A4", "A6"):
            lib = owt.build_lib(tpl_entries([x["sat"]]), dedupe=False) + lib
        if arm.rstrip("LWX") in ("A5", "A6"):
            others = sorted({y["sat"] for y in P if fam(y) != fam(x) and y["name"].endswith(":0")})
            pooled = sorted({tuple(map(str, e))[0]: e for e in tpl_entries(others)}.values())
            lib = lib + owt.build_lib(pooled, dedupe=True)
        order = lexical if "L" in arm[2:] else None
        st, o, d = run_confined(owt.solve, x["sat"], x["ans_type"], lib, B, E, (0, 1, 2, -1), order, cpu_s=4)
        ok, calls, apps, expr = o if st == "ok" else (False, B, E, "child:" + st)
        res.append((x["name"], x["module"], ok, calls, apps, expr))
    return {"arm": arm, "libsize": len(base), "res": res, "secs": time.time() - t0}

out = run(); den = []
R = out["res"]
by = {}
for n, m, ok, c, a, e in R:
    by.setdefault(m, [0, 0]); by[m][0] += ok; by[m][1] += 1
fams_solved = len({n.split(":")[0] for n, m, ok, *_ in R if ok})
print("arm", arm, "B", B, "E", E, "baselib", out["libsize"], "solved", sum(r[2] for r in R), "/", len(R),
      "families", fams_solved, "/97", {k: "%d/%d" % tuple(v) for k, v in by.items()},
      "mean_calls_solved %.1f" % (sum(r[3] for r in R if r[2]) / max(1, sum(r[2] for r in R))),
      "%.0fs" % out["secs"], "denied", len(den))
json.dump(out, open("exp1_%s_%d_%d.json" % (arm, B, E), "w"))
