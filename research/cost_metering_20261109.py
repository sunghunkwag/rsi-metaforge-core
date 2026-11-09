"""Synthetic compute-accounting calibration. NOT an RSI or held-out task audit."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import time

SEEDS=range(40)
ARMS=("reference","same_work","extra_training_call","extra_generator_cpu")
COUNTERS=("candidate_evaluations","public_vm_calls","training_vm_calls","verification_vm_calls")
CAPS=dict(candidate_evaluations=48,public_vm_calls=384,training_vm_calls=16,verification_vm_calls=72)
CPU_CAP_NS=1_000_000_000

class BudgetExceeded(RuntimeError):
    pass

class Meter:
    def __init__(self):
        self.count=defaultdict(int)
        self.cpu=defaultdict(int)
        self.start=time.process_time_ns()
        self.wall=time.perf_counter_ns()
    def check(self,key):
        if self.count[key]>CAPS[key]:
            raise BudgetExceeded(key)
        if time.process_time_ns()-self.start>CPU_CAP_NS:
            raise BudgetExceeded("cpu")
    def candidate(self):
        self.count["candidate_evaluations"]+=1
        self.check("candidate_evaluations")
    def call(self,kind,fn,*args):
        key=kind+"_vm_calls"
        if key not in CAPS:
            raise ValueError(kind)
        self.count[key]+=1
        self.check(key)
        t=time.process_time_ns()
        try:
            return fn(*args)
        finally:
            self.cpu[kind+"_vm_cpu_ns"]+=time.process_time_ns()-t
    def measured(self,kind,fn,*args):
        t=time.process_time_ns()
        try:
            return fn(*args)
        finally:
            self.cpu[kind+"_cpu_ns"]+=time.process_time_ns()-t
    def receipt(self):
        total=time.process_time_ns()-self.start
        vm=sum(self.cpu[k+"_vm_cpu_ns"] for k in ("public","training","verification"))
        return {**{k:self.count[k] for k in COUNTERS},
                **{k:self.cpu[k] for k in ("generator_cpu_ns","support_update_cpu_ns",
                    "public_vm_cpu_ns","training_vm_cpu_ns","verification_vm_cpu_ns")},
                "non_vm_cpu_ns":total-vm,"total_cpu_ns":total,
                "wall_ns":time.perf_counter_ns()-self.wall,
                "cpu_cap_breached":total>CPU_CAP_NS}

def vm_fixture(x,k):
    return ((x*k+17)^(x>>2))%997

def proposal(rng,extra):
    value=rng.randrange(1,10000)
    if extra:
        acc=1
        for i in range(200000):
            acc=(acc*33+i)&0xffffffff
        value^=acc&0x7fff
    return value

def run_arm(seed,arm):
    rng=random.Random(seed)
    m=Meter()
    checksum=0
    for generation in range(3):
        for i in range(16):
            x=m.measured("generator",proposal,rng,
                arm=="extra_generator_cpu" and generation==0 and i==0)
            m.candidate()
            for j in range(8):
                checksum^=m.call("public",vm_fixture,x+j,generation+1)
        for j in range(4+int(arm=="extra_training_call")):
            checksum^=m.call("training",vm_fixture,seed+generation*7+j,3)
        checksum^=m.measured("support_update",lambda z:(z*5+1)%997,checksum)
        for j in range(24):
            checksum^=m.call("verification",vm_fixture,j+seed*13,generation+2)
    return dict(seed=seed,arm=arm,fixture_checksum=checksum,**m.receipt())

def compare(a,b):
    equal=all(a[k]==b[k] for k in COUNTERS)
    ratio=max(a["total_cpu_ns"],b["total_cpu_ns"])/max(1,min(a["total_cpu_ns"],b["total_cpu_ns"]))
    cpu_ok=ratio<=1.10
    return dict(seed=a["seed"],arm=b["arm"],counts_equal=equal,cpu_ratio=ratio,
                cpu_within_ten_percent=cpu_ok,strict_parity=equal and cpu_ok)

def wilson(s,n):
    z=1.959963984540054
    p=s/n
    d=1+z*z/n
    center=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0,center-h),6),round(min(1,center+h),6)]

def calibrate():
    rows=[]
    pairs=[]
    for seed in SEEDS:
        batch={arm:run_arm(seed,arm) for arm in ARMS}
        rows.extend(batch.values())
        pairs.extend(compare(batch["reference"],batch[arm]) for arm in ARMS[1:])
    totals={}
    for arm in ARMS:
        group=[r for r in rows if r["arm"]==arm]
        totals[arm]={k:sum(r[k] for r in group) for k in
                     (*COUNTERS,"generator_cpu_ns","support_update_cpu_ns",
                      "public_vm_cpu_ns","training_vm_cpu_ns","verification_vm_cpu_ns",
                      "non_vm_cpu_ns","total_cpu_ns","wall_ns")}
    paired={}
    for arm in ARMS[1:]:
        group=[r for r in pairs if r["arm"]==arm]
        rejected=sum(not r["strict_parity"] for r in group)
        paired[arm]=dict(paired_seeds=40,rejected=rejected,accepted=40-rejected,
                         count_mismatches=sum(not r["counts_equal"] for r in group),
                         cpu_mismatches=sum(not r["cpu_within_ten_percent"] for r in group),
                         rejection_rate_wilson_95=wilson(rejected,40),
                         min_cpu_ratio=min(r["cpu_ratio"] for r in group),
                         max_cpu_ratio=max(r["cpu_ratio"] for r in group))
    gates=dict(extra_training_rejected_40_of_40=paired["extra_training_call"]["rejected"]==40,
               extra_generator_cpu_rejected_at_least_38_of_40=paired["extra_generator_cpu"]["rejected"]>=38,
               all_receipts_under_cpu_cap=all(not r["cpu_cap_breached"] for r in rows))
    return dict(schema="synthetic-cost-metering-preflight-v1",is_rsi_audit=False,
                seeds=list(SEEDS),generations=3,candidates_per_generation=16,
                public_calls_per_candidate=8,training_calls_per_generation=4,
                verification_calls_per_generation=24,cpu_parity_tolerance=0.10,
                rows=rows,paired_comparisons=pairs,summary=totals,paired_summary=paired,
                preregistered_gates=gates,preregistered_success=all(gates.values()),
                limitations=["Synthetic fixture only; no task-solving, transfer, or RSI result.",
                             "Measured CPU depends on hardware and scheduling.",
                             "A wrapper cannot detect calls that bypass it.",
                             "No original TEST, J, or spent audit tasks were accessed."])

def selftest():
    m=Meter()
    m.candidate()
    m.call("public",lambda x:x+1,2)
    m.call("public",lambda x:x+1,3)
    m.call("training",lambda x:x,2)
    assert (m.receipt()["candidate_evaluations"],m.receipt()["public_vm_calls"],
            m.receipt()["training_vm_calls"])==(1,2,1)
    try:
        m.call("public",lambda:1//0)
    except ZeroDivisionError:
        pass
    assert m.receipt()["public_vm_calls"]==3
    for _ in range(47):
        m.candidate()
    try:
        m.candidate()
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("cap not enforced")
    a=run_arm(3,"reference")
    b=run_arm(3,"extra_training_call")
    assert not compare(a,b)["strict_parity"] and b["training_vm_calls"]-a["training_vm_calls"]==3
    c=run_arm(3,"same_work")
    assert compare(a,c)["counts_equal"]
    d=run_arm(3,"extra_generator_cpu")
    assert compare(a,d)["counts_equal"] and d["generator_cpu_ns"]>a["generator_cpu_ns"]
    assert wilson(0,40)[0]==0 and wilson(40,40)[1]==1
    print("PASS: 7 synthetic accounting assertions")

def report(result):
    p=result["paired_summary"]
    s=result["summary"]
    def ms(arm,key):
        return f'{s[arm][key]/1e6:.3f}'
    return f"""# Cost-metering calibration, 2026-11-09

This is a **synthetic instrumentation test, NOT an RSI audit**. No external
task labels, protected TEST, J or prior spent audits were opened.

Preregistration: [PREREG_COST_METERING_20261109.md](PREREG_COST_METERING_20261109.md).
40 independent paired seeds, three generations, 16 candidate evaluations per
generation, four arms. All results are preserved in
[complete raw JSON](results/cost_metering_raw_20261109.json).

| Arm | Candidates | Public VM | Support VM | Verify VM | Total CPU ms | Generator CPU ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
"""+"".join(f'| {arm} | {s[arm]["candidate_evaluations"]} | {s[arm]["public_vm_calls"]} | {s[arm]["training_vm_calls"]} | {s[arm]["verification_vm_calls"]} | {ms(arm,"total_cpu_ns")} | {ms(arm,"generator_cpu_ns")} |\n' for arm in ARMS)+f"""
Paired strict parity rejections (out of 40): same-work **{p["same_work"]["rejected"]}**;
extra-training-call **{p["extra_training_call"]["rejected"]}**;
extra-generator-CPU **{p["extra_generator_cpu"]["rejected"]}**.
The predeclared negative-control gates: **{result["preregistered_success"]}**.
The same-work false rejections show that a per-seed 10% CPU gate is noisy
even for identical work; report both per-seed and aggregate CPU, never infer
CPU parity from matching proposal/VM counts. This is not evidence of learning.

All arms have an identical nominal candidate budget. The extra-training
negative control has 120 additional **actually counted** support VM calls.
The extra-generator control has matched VM calls but charged extra CPU.
OS timing, bypassed wrappers, external substrate validity, and future
held-out transfer remain unverified. No RSI adoption is warranted.
"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path)
    ap.add_argument("--selftest",action="store_true")
    args=ap.parse_args()
    if args.selftest:
        selftest()
        return
    if args.output is None:
        ap.error("--output required unless --selftest")
    result=calibrate()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    Path("research/RESULTS_COST_METERING_20261109.md").write_text(report(result),encoding="utf-8")
    readme=Path("README.md")
    content=readme.read_text(encoding="utf-8")
    anchor="## Results at a glance"
    note=("**2026-11-09 research calibration (not an RSI result):** "
          "40-seed instrumented compute-parity preflight, synthetic fixtures only. "
          "See [preregistration](research/PREREG_COST_METERING_20261109.md), "
          "[full raw results](research/results/cost_metering_raw_20261109.json), "
          "and [report](research/RESULTS_COST_METERING_20261109.md). "
          f"Preregistered instrumentation gates: {result['preregistered_success']}. "
          f"Identical-work CPU false rejections: {result['paired_summary']['same_work']['rejected']}/40. "
          "No RSI claim.\n\n")
    assert anchor in content
    assert "2026-11-09 research calibration" not in content
    readme.write_text(content.replace(anchor,note+anchor,1),encoding="utf-8")
    print(json.dumps({"gates":result["preregistered_gates"],
                      "paired":result["paired_summary"]},indent=2))

if __name__=="__main__":
    main()
