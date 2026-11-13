import sys, json, time, random, cProfile, pstats
sys.argv=[sys.argv[0]]
t=time.time()
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))
print('harvest', round(time.time()-t,2), len(POOL), flush=True)
data=json.load(open('../p3_development.json'))
rng=random.Random(0)
for inst in data[:3]+data[40:43]:
    t=time.time()
    c,x=run_M(M0,inst,300,rng)
    print(inst['name'], round(time.time()-t,2), c, x is not None and repr(x)[:40], flush=True)
