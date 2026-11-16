import sys, json, time, random, cProfile, pstats
sys.argv=[sys.argv[0]]
exec(open('inv1.py').read().split('if __name__ == "__main__":')[0].replace('__file__','"inv1.py"'))
data=json.load(open('../p3_development.json'))
rng=random.Random(0)
inst=[d for d in data if d['name']=='ArithmeticSequence:1'][0]
cProfile.run('run_M(M0,inst,300,rng)','pr.out')
pstats.Stats('pr.out').sort_stats('cumtime').print_stats(12)
