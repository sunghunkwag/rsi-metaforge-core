import sys, json
sys.setrecursionlimit(20000)
from rsi6.experiments.dev_proof_depth import pool_text, SETMM
from rsi6.experiments.dev_proof_learn import run_pass
from rsi6.kernel.metamath import Database
text = pool_text(open(SETMM).read())
db = Database.read(text)
k = text.find("\n  Logical conjunction\n"); until = len(Database.read(text[:text.rfind("$(", 0, k)]).order)
k2 = text.find("\n  Logical equivalence\n"); eq_from = len(Database.read(text[:text.rfind("$(", 0, k2)]).order)
p = run_pass(db, 200000, None, True, until, count_from=0)
eq = [r for r in p['rows'] if db.assertions[r['label']].index >= eq_from]
print('learned order, sections 1-2: proved', len(p['proved']), 'equivalence section', sum(r['proved'] for r in eq), 'of', len(eq), 'rejected', p['rejected'], 'seconds', p['seconds'])
json.dump({'proved': p['proved'], 'eq_from': eq_from, 'until': until}, open('rsi6/runs/dev-proof-learned-order-probe.json', 'w'))
