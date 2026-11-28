import sys, json, time
sys.setrecursionlimit(50000)
from rsi6.experiments.dev_proof_depth import pool_text, SETMM
from rsi6.kernel.metamath import Database, Rejected
from rsi6.kernel.problem import Meter
from rsi6.learner.prover import Entry, Library, Prover
db = Database.read(pool_text(open(SETMM).read()))
rows = {r['label']: r for r in json.load(open('rsi6/runs/dev-proof-depth-B.json'))['rows']}
target = sys.argv[1]; budgets = [float(x) for x in sys.argv[2].split(',')]
lib = Library()
for l in db.order:
    a = db.assertions[l]
    if l == target: break
    if a.typecode != '|-': continue
    try: e = Entry(db, l)
    except Exception: continue
    if a.kind == 'a' or (rows.get(l) or {}).get('proved'): lib.add(e)
print(target, 'library', len(lib), flush=True)
for b in budgets:
    t = time.time(); m = Meter(b); pr = Prover(db, lib, max_depth=int(sys.argv[3]) if len(sys.argv)>3 else 8).prove(target, m)
    ok = False
    if pr is not None:
        try: ok = db.verify(target, pr)
        except Rejected as e: print('rejected', e)
    print(f"{target} budget {b:.0f}: {'PROVED' if ok else 'no'} used {m.used:.0f} in {time.time()-t:.1f}s", flush=True)
    if ok: break
