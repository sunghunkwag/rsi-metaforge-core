from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import json,time,hashlib
from pathlib import Path

@dataclass(frozen=True)
class SolverView:
    train_pairs: tuple[tuple[tuple[int,...],int],...]

def rref(A,b):
    if not A: return True,[],[]
    m,n=len(A),len(A[0]); M=[row[:] + [b[i]] for i,row in enumerate(A)]
    piv=[]; r=0
    for c in range(n):
        p=next((i for i in range(r,m) if M[i][c] != 0),None)
        if p is None: continue
        M[r],M[p]=M[p],M[r]
        q=M[r][c]; M[r]=[x/q for x in M[r]]
        for i in range(m):
            if i != r and M[i][c] != 0:
                q=M[i][c]; M[i]=[M[i][j]-q*M[r][j] for j in range(n+1)]
        piv.append(c); r+=1
        if r==m: break
    for row in M:
        if all(row[c]==0 for c in range(n)) and row[n] != 0: return False,M,piv
    return True,M,piv

def reconstruct(view):
    pairs=view.train_pairs
    if not pairs:return ()
    s=list(map(int,pairs[0][0]))
    for xs,y in pairs:
        xs=tuple(map(int,xs))
        if tuple(s[-len(xs):]) != xs: raise ValueError('noncontiguous')
        s.append(int(y))
    return tuple(s)

def fit(view,maxk):
    s=reconstruct(view)
    W=len(view.train_pairs[0][0])
    # faithful degree-0 detector: increasing k, full rank, integral exact coefficients.
    for k in range(1,maxk+1):
        A=[];b=[]
        for xs,y in view.train_pairs:
            A.append([Fraction(int(xs[-i])) for i in range(1,k+1)])
            b.append(Fraction(int(y)))
        ok,M,piv=rref(A,b)
        if not ok or len(piv)!=k: continue
        vals=[Fraction(0) for _ in range(k)]
        for ri,pc in enumerate(piv): vals[pc]=M[ri][k]
        if all(x.denominator==1 for x in vals):
            return tuple(int(x) for x in vals)
    return None

def predict(xs,c): return sum(c[i-1]*int(xs[-i]) for i in range(1,len(c)+1))

def run_one(terms,W):
    if len(terms)<2*W+16: return None
    train=tuple((tuple(terms[n-W:n]),int(terms[n])) for n in range(W,2*W))
    view=SolverView(train)
    c=fit(view,W//2)
    if c is None:return {'pass':False,'coeffs':None,'order':None,'trivial':None}
    hold=tuple((tuple(terms[n-W:n]),int(terms[n])) for n in range(2*W,2*W+16))
    if not all(predict(xs,c)==y for xs,y in hold):
        return {'pass':False,'coeffs':c,'order':len(c),'trivial':None}
    pairs=train+hold
    ys=[predict(xs,c) for xs,_ in pairs]
    trivial=(len(set(ys))==1 or any(all(y==xs[j] for y,(xs,_) in zip(ys,pairs)) for j in range(W)))
    return {'pass':not trivial,'coeffs':c,'order':len(c),'trivial':trivial}

def load_stripped(path):
    d={}
    with open(path,'rt',encoding='utf-8',errors='strict') as f:
        for line in f:
            if not line.startswith('A'): continue
            aid,rest=line.split(' ',1)
            vals=[]
            for z in rest.strip().strip(',').split(','):
                if z: vals.append(int(z))
            d[aid]=vals
    return d

def main():
    rows=json.load(open('/mnt/data/evidence_curve/oeis_window_400_raw_results.json'))
    aids=[r['aid_internal'] for r in rows]
    sd=load_stripped('/mnt/data/evidence_curve/stripped')
    out={}
    for W in (12,24,48,96):
        t0=time.process_time(); eligible=[]; passes=[]
        for slot,aid in enumerate(aids):
            terms=sd[aid]
            rr=run_one(terms,W)
            if rr is None: continue
            eligible.append(slot)
            if rr['pass']: passes.append((slot,aid,rr['order'],rr['coeffs']))
        cpu=time.process_time()-t0
        out[W]={'eligible':len(eligible),'excluded':400-len(eligible),'passes':passes,'count':len(passes),'cpu':cpu}
        print(W,len(eligible),len(passes),cpu)
        print(passes)
    json.dump(out,open('/mnt/data/evidence_curve/stripped_only_curve.json','w'),indent=2)
if __name__=='__main__':main()
