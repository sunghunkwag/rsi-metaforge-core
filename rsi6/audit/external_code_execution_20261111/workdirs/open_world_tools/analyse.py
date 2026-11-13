import json, re, keyword, builtins, collections, math, sys
sys.set_int_max_str_digits(0)
W="/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/review17/work"
P={x["name"]:x for x in json.load(open(W+"/p3_development.json"))}
R={a:{x[0]:x for x in json.load(open('exp1_%s_300_5000.json'%a))['res']} for a in ['A0','A1','A2','A3','A4','A5','A6','A6L','A6W','A6WL']}
def mcn(a,b,mod):
    n=[k for k in P if P[k]['module']==mod]
    w=sum(1 for k in n if R[b][k][2] and not R[a][k][2]); l=sum(1 for k in n if R[a][k][2] and not R[b][k][2])
    p=sum(math.comb(w+l,i) for i in range(w,w+l+1))/2**(w+l) if w+l else 1.0
    return w,l,round(p,4)
for mod in ['trivial_inverse.py','basic.py','study.py','tutorial.py']:
    print(mod, {b:mcn('A2',b,mod) for b in ['A3','A4','A5','A6','A6W']})
# family-level: solved all instances
for a in R:
    fam=collections.defaultdict(list)
    for k,x in R[a].items(): fam[k.split(':')[0]].append(x[2])
    print(a,'families all-instances',sum(all(v) for v in fam.values()),'any',sum(any(v) for v in fam.values()))
# diagnostic: identifier tokens of unsolved verifiers that name no library op
lib=json.load(open('exp1_A6_300_5000.json'))
names=set()
import owt
ent,_=owt._discover_child({"builtins":1,"typeattrs":1},2)
names={n.split('.')[-1] for n,a,s in ent}
cnt=collections.Counter()
for k,x in R['A6'].items():
    if x[2]: continue
    src=P[k]['sat']; toks=set(re.findall(r'\.([A-Za-z_]+)\(|\b([A-Za-z_]+)\(',src))
    for t in {a or b for a,b in toks}:
        if t not in names and t!='sat': cnt[t]+=1
print('called names in unsolved verifiers with no library op:',cnt.most_common(20))
# where do they live in the environment? search attribute names over loaded modules + types
where={}
mods=['builtins','math','itertools','string','operator','functools','collections','re','statistics','heapq','bisect']
import importlib
for t,_ in cnt.most_common(20):
    hits=[]
    for m in mods:
        mo=importlib.import_module(m)
        if hasattr(mo,t): hits.append(m)
    for T in (int,str,list,float,dict,set,tuple):
        if hasattr(T,t): hits.append(T.__name__)
    where[t]=hits
print('environment locations by introspection:',where)
