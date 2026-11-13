import sys, json, time, random
sys.argv=[sys.argv[0]]
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))
data=json.load(open('../p3_development.json'))
rng=random.Random(0); slow=[]
t0=time.time()
for inst in data[::4]:
    t=time.time()
    try: c,x=run_M(M0,inst,300,rng)
    except BaseException as e: c,x=-1,None
    slow.append((time.time()-t,inst['name'],c,x is not None))
print('total',round(time.time()-t0,1),'n',len(slow),'solved',sum(s[3] for s in slow))
for s in sorted(slow)[-8:]: print(s)
