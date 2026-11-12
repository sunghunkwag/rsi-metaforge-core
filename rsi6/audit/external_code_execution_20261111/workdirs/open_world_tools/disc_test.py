import sys,os,time; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import owt
for pol in [{"builtins":1},{"typeattrs":1},{"modules":["math","operator","itertools","string"]}]:
    t=time.time(); lib,probes,den=owt.discover(pol,2)
    print(list(pol), "callables kept",len(lib),"signatures",sum(len(s) for _,_,s in lib),"probe type-combos",probes,"denied",len(den),"%.1fs"%(time.time()-t))
    print("   e.g.",[ (n,a,s[:2]) for n,a,s in lib[:3]])
