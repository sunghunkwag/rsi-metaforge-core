#!/usr/bin/env python3
"""Preregistered external-task meta-learning experiment (three generations).

The external task manifest and the full preregistration were committed in
separate earlier commits BEFORE this implementation and BEFORE the first run.
No unmerged PR code is loaded. No sealed TEST/J dataset is opened.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import time

BASE_SHA = "c4f0a8627a1c9f37dd3aa6291b0eee0c78648210"
SOURCE_BLOB = "2816d1ee51ff2f523704c1930d8736eb99711036"
SPLIT_BLOB = "afac5b3f2dc346027caaba36f308f2b1e078ebda"
MANIFEST_BLOB = "c27b1c6431ab9d836c94f9ddc66269fd4216a1e0"
ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "rsi2/data/source_list_tasks.json"
SPLIT_FILE = ROOT / "rsi2/data/split_manifest.json"
MANIFEST_FILE = ROOT / "research/external_metacontrol_task_manifest.json"

ARMS = (
    "dedup_uniform", "frozen_mutation", "untrained_no_memory",
    "memory_wiped", "one_generation_equal_compute",
    "adaptive_persistent", "negative_inverted",
)
CONTROL_ARMS = ARMS[:5]
ACTIONS = ("uniform", "parameter_mutation", "family_mutation",
           "novelty", "failure_memory")
GENERATIONS = 3
SEEDS = 40
CANDIDATES = 48
TRAIN_N = 12
SHIFT_N = 32
CPU_CAP = 0.5
CPU_PARITY_TOLERANCE = 0.10
BOOTS = 2000
BOOT_SEED = 909113
ETA = 3.0
FAMILIES = (
    "add-k", "mult-k", "count-k", "drop-k", "take-k",
    "pow-k", "append-k", "rotate-k", "keep-mod-k",
    "remove-mod-k", "modulo-k",
)
FAMILY_LABELS = ("append-k", "keep-mod-k", "modulo-k",
                 "remove-mod-k", "rotate-k")
INT_EXTRA = ("len", "sum", "min", "max", "head", "last", "product")


def sha_git(path):
    return subprocess.check_output(
        ["git", "hash-object", str(path)], text=True, cwd=ROOT,
    ).strip()


def stable_seed(*v):
    s = "|".join(map(str, v)).encode()
    return int.from_bytes(hashlib.sha256(s).digest()[:8], "big")


def external_meta(name):
    if name in INT_EXTRA:
        return name, None
    hit = re.fullmatch(r"(.+?) with k=(\d+)", name)
    if not hit or hit.group(1) not in FAMILIES:
        raise ValueError(f"Unsupported external task name: {name}")
    return hit.group(1), int(hit.group(2))


def output_type(name):
    family, _ = external_meta(name)
    return "int" if family in ("count-k", *INT_EXTRA) else "list-of-int"


def external_oracle(name, raw):
    """Independently reconstruct publicly named operations; validate vs source."""
    f, k = external_meta(name)
    x = list(raw)
    if f == "add-k":
        return [v + k for v in x]
    if f == "mult-k":
        return [v * k for v in x]
    if f == "pow-k":
        return [v ** k for v in x]
    if f == "append-k":
        return x + [k]
    if f == "drop-k":
        return x[k:]
    if f == "take-k":
        return x[:k]
    if f == "rotate-k":
        steps = k % len(x) if x else 0
        return x[-steps:] + x[:-steps] if steps else x
    if f == "keep-mod-k":
        return [v for v in x if v % k == 0]
    if f == "remove-mod-k":
        return [v for v in x if v % k != 0]
    if f == "modulo-k":
        return [v % k for v in x]
    if f == "count-k":
        return sum(v == k for v in x)
    if f == "len":
        return len(x)
    if f == "sum":
        return sum(x)
    if f == "min":
        return min(x, default=0)
    if f == "max":
        return max(x, default=0)
    if f == "head":
        return x[0] if x else 0
    if f == "last":
        return x[-1] if x else 0
    if f == "product":
        result = 1
        for v in x:
            result *= v
        return result
    raise ValueError(name)


def vocabulary(target_type):
    all_names = []
    for family in FAMILIES:
        if family == "count-k" and target_type != "int":
            continue
        if family != "count-k" and target_type == "int":
            continue
        allowed = range(1, 6) if family in ("modulo-k", "keep-mod-k", "remove-mod-k") else range(6)
        for k in allowed:
            all_names.append(f"{family} with k={k}")
    if target_type == "int":
        all_names += list(INT_EXTRA)
    return tuple(all_names)


def load_external():
    assert sha_git(SOURCE_FILE) == SOURCE_BLOB, "external task blob mismatch"
    assert sha_git(SPLIT_FILE) == SPLIT_BLOB, "protected split blob mismatch"
    assert sha_git(MANIFEST_FILE) == MANIFEST_BLOB, "pre-frozen audit manifest modified"
    source = {r["name"]: r for r in json.loads(SOURCE_FILE.read_text())}
    old = json.loads(SPLIT_FILE.read_text())
    excluded = set(old["train"] + old["validation"] + old["test"])
    manifest = json.loads(MANIFEST_FILE.read_text())
    support = sum(manifest["support_rounds"], [])
    dev = sum(manifest["development_rounds"], [])
    audit = manifest["audit_tasks"]
    assert len(support) == 16 and len(dev) == 15 and len(audit) == 19
    assert len(set(support+dev+audit)) == 50
    assert set(support+dev+audit).isdisjoint(excluded)
    for name in support+dev+audit:
        assert name in source
        assert source[name]["type"]["input"] == "list-of-int"
        assert source[name]["type"]["output"] == output_type(name)
    assert set(n.split(" with k=")[0] for n in audit) == set(FAMILY_LABELS)
    assert not ({n.split(" with k=")[0] for n in support+dev} & set(FAMILY_LABELS))
    return source, manifest


def verify_external(source, task_names):
    """Only invoke for support/dev before the audit; audit after freeze."""
    checked = 0
    for name in task_names:
        for ex in source[name]["examples"]:
            if external_oracle(name, ex["i"]) != ex["o"]:
                raise AssertionError(
                    f"External semantics discrepancy: {name}; abort without tuning"
                )
            checked += 1
    return checked


def input_pairs(name, seed, stage):
    rng = random.Random(stable_seed("published-fresh-input-v1", name, seed, stage))
    if stage == "public":
        lengths = (0, 1, 2, 3, 4, 5, 7, 8, 9, 11, 13, 16)
        assert len(lengths) == TRAIN_N
        inputs = [tuple(rng.randint(0, 16) for _ in range(length))
                  for length in lengths]
    else:
        lengths = (0, 1, 2, 3, 5, 8, 13, 21, 34)
        inputs = [
            tuple(rng.randint(-17, 31) for _ in range(lengths[i % len(lengths)]))
            for i in range(SHIFT_N)
        ]
        assert len(inputs) == SHIFT_N and len(set(map(len, inputs))) >= 8
    return [(x, external_oracle(name, x)) for x in inputs]


def accuracy(output, target):
    if output == target:
        return 1.0
    if isinstance(target, list):
        if not isinstance(output, list):
            return 0.0
        diff = abs(len(output)-len(target))
        diff += sum(min(100, abs(a-b)) for a, b in zip(output,target)) / max(1,len(target))
    elif isinstance(output,int):
        diff = min(1000, abs(output-target))
    else:
        return 0.0
    return 1.0/(1.0+diff)


def mutate_candidate(rng, vocab, best, action, history, zero_failures):
    if action == "uniform" or best is None:
        return rng.choice(vocab)
    fam, k = external_meta(best)
    if action == "parameter_mutation":
        if k is None:
            return rng.choice(vocab)
        nearest = [p for p in vocab if external_meta(p)[0] == fam
                   and external_meta(p)[1] is not None and
                   abs(external_meta(p)[1]-k) <= 1]
        return rng.choice(nearest or vocab)
    if action == "family_mutation":
        same_k = [p for p in vocab if external_meta(p)[1] == k
                  and external_meta(p)[0] != fam]
        return rng.choice(same_k or vocab)
    pool = [rng.choice(vocab) for _ in range(6)]
    if action == "novelty":
        return min(pool, key=lambda x: (history.get(x, 0), x))
    return min(pool, key=lambda x: (zero_failures.get(external_meta(x)[0], 0), x))


class Learner:
    def __init__(self, arm):
        self.arm = arm
        self.weights = {a: 1.0 for a in ACTIONS}
        self.rewards = {a: 0.0 for a in ACTIONS}
        self.n = {a: 0 for a in ACTIONS}
        self.cumulative_rewards = {a: 0.0 for a in ACTIONS}
        self.cumulative_n = {a: 0 for a in ACTIONS}
        self.history = []

    def draw_action(self, rng):
        if self.arm == "dedup_uniform":
            return "uniform"
        if self.arm == "frozen_mutation":
            return "parameter_mutation"
        if self.arm == "untrained_no_memory":
            return rng.choice(ACTIONS)
        return rng.choices(
            ACTIONS,[self.weights[a] for a in ACTIONS],k=1,
        )[0]

    def reward(self, action, value):
        if self.arm in ("dedup_uniform", "frozen_mutation", "untrained_no_memory"):
            return
        if self.arm == "negative_inverted":
            value = 1.0-value
        self.rewards[action] += value
        self.n[action] += 1
        self.cumulative_rewards[action] += value
        self.cumulative_n[action] += 1

    def finish_generation(self, index):
        if self.arm in ("dedup_uniform", "frozen_mutation", "untrained_no_memory"):
            pass
        else:
            if self.arm == "one_generation_equal_compute":
                r,n = self.cumulative_rewards,self.cumulative_n
            else:
                r,n = self.rewards,self.n
            mean = {a:r[a]/max(1,n[a]) for a in ACTIONS}
            avg = sum(mean.values())/len(ACTIONS)
            next_w = {}
            for a in ACTIONS:
                prior = 1.0 if self.arm in ("memory_wiped","one_generation_equal_compute") else self.weights[a]
                next_w[a] = max(0.25,min(4.0,prior*math.exp(ETA*(mean[a]-avg))))
            self.weights = next_w
        self.history.append({
            "generation":index+1,
            "weights":dict(self.weights),
            "updates":sum(self.n.values()),
            "cumulative_updates":sum(self.cumulative_n.values()),
        })
        self.rewards = {a:0.0 for a in ACTIONS}
        self.n = {a:0 for a in ACTIONS}
        if self.arm == "memory_wiped":
            self.weights = {a:1.0 for a in ACTIONS}
        if self.arm == "one_generation_equal_compute":
            # After evaluation snapshot, support proposals remain the untrained
            # fixed policy; all support compute is aggregated into ONE update.
            self.weights = {a:1.0 for a in ACTIONS}

    def checkpoint(self, generation):
        weights = self.history[generation]["weights"]
        return dict(weights)


def episode(task, replicate, checkpoint, arm, learner, stage, learn=False, weights=None):
    public = input_pairs(task,replicate, "public")
    shifted = input_pairs(task,replicate, "shift")
    vocab = vocabulary(output_type(task))
    rng = random.Random(stable_seed("proposal-tape-v1", task, replicate))
    # The same RNG seed is used for all checkpoints, to prevent
    # fake learning from resampling a more favorable random trajectory.
    action_rng = random.Random(stable_seed("action-tape-v1", task, replicate))
    draws = []
    used = set()
    history = {}
    zero_failures = {}
    best = None
    best_fitness = -1.0
    winner = None
    score_seq = []
    action_seq = []
    start = time.process_time()
    for step in range(CANDIDATES):
        action = learner.draw_action(action_rng) if weights is None else (
            action_rng.choices(ACTIONS,[weights[a] for a in ACTIONS],k=1)[0]
            if arm not in ("dedup_uniform","frozen_mutation","untrained_no_memory")
            else learner.draw_action(action_rng)
        )
        if arm == "dedup_uniform":
            action = "uniform"
        elif arm == "frozen_mutation":
            action = "parameter_mutation"
        proposed = mutate_candidate(rng,vocab,best,action,history,zero_failures)
        if proposed in used and len(used)<len(vocab):
            # Deduplicate all arms by the same deterministic fallback policy.
            for j in range(len(vocab)):
                fallback = vocab[(stable_seed(task,replicate,step)+j)%len(vocab)]
                if fallback not in used:
                    proposed = fallback
                    break
        used.add(proposed)
        score_total = 0.0
        exact = True
        for xs,y in public:
            output = external_oracle(proposed,xs)
            score_total += accuracy(output,y)
            if output != y:
                exact=False
        fitness = score_total/TRAIN_N
        if fitness > best_fitness:
            prev = best_fitness
            best_fitness, best = fitness, proposed
        else:
            prev = best_fitness
        if exact and winner is None:
            winner = proposed
        action_seq.append(action)
        score_seq.append(round(fitness,6))
        history[proposed] = history.get(proposed,0)+1
        if fitness < 0.05:
            family = external_meta(proposed)[0]
            zero_failures[family] = zero_failures.get(family,0)+1
        if learn:
            learning_reward = max(0.0,fitness-max(0.0,prev))
            if exact:
                learning_reward = min(1.0,learning_reward+0.2)
            learner.reward(action,learning_reward)
    assert len(score_seq)==CANDIDATES
    # Exactly SHIFT_N VM calls for every arm, even without a train-perfect
    # candidate, so total interpreter call counts are not success-dependent.
    checked = winner or best
    shift_outputs = [external_oracle(checked,x) for x,_ in shifted]
    shift_pass = winner is not None and all(
        output==y for output,(_,y) in zip(shift_outputs,shifted)
    )
    elapsed=time.process_time()-start
    return {
        "task":task,"replicate":replicate,"checkpoint":checkpoint,
        "arm":arm,"phase":stage,
        "train_exact":winner is not None,"shift_correct":bool(shift_pass),
        "spurious_fit":bool(winner is not None and not shift_pass),
        "winner":winner,"best":best,
        "candidate_evaluations":CANDIDATES,
        "actual_public_vm_calls":CANDIDATES*TRAIN_N,
        "actual_shift_vm_calls":SHIFT_N,
        "public_fitness_per_candidate":score_seq,
        "actions_per_candidate":action_seq,
        "cpu_seconds":elapsed,
        "cpu_cap_breached":elapsed>CPU_CAP,
    }


def bootstrap_seed_delta(rows, candidate, baseline):
    # One independent unit = one seed trajectory, not each task within it.
    diffs=[]
    for seed in range(SEEDS):
        cs=[r["shift_correct"] for r in rows if r["replicate"]==seed and r["arm"]==candidate]
        bs=[r["shift_correct"] for r in rows if r["replicate"]==seed and r["arm"]==baseline]
        assert len(cs)==len(bs) and len(cs)>0
        diffs.append((sum(cs)-sum(bs))/len(cs))
    rng=random.Random(BOOT_SEED)
    vals=[]
    for _ in range(BOOTS):
        samples=[diffs[rng.randrange(SEEDS)] for _ in range(SEEDS)]
        vals.append(sum(samples)/SEEDS)
    vals.sort()
    return {"paired_effect":sum(diffs)/SEEDS,
            "ci95":[vals[int(0.025*BOOTS)],vals[int(0.975*BOOTS)-1]],
            "independent_seed_trajectories":SEEDS}


def compare_pairs(rows,candidate,baseline):
    c={(r["task"],r["replicate"]):r for r in rows if r["arm"]==candidate}
    b={(r["task"],r["replicate"]):r for r in rows if r["arm"]==baseline}
    assert c.keys()==b.keys()
    win=sum(x["shift_correct"] and not b[k]["shift_correct"] for k,x in c.items())
    loss=sum(not x["shift_correct"] and b[k]["shift_correct"] for k,x in c.items())
    tie=len(c)-win-loss
    return {"wins":win,"losses":loss,"ties":tie,"cases":len(c),
            "paired_seed_bootstrap":bootstrap_seed_delta(rows,candidate,baseline)}


def summary(rows):
    s={}
    for arm in ARMS:
        r=[x for x in rows if x["arm"]==arm]
        s[arm]={
            "train_exact":sum(x["train_exact"] for x in r),
            "shift_correct":sum(x["shift_correct"] for x in r),
            "spurious_fit":sum(x["spurious_fit"] for x in r),
            "spurious_fraction_given_train_fit":(
                sum(x["spurious_fit"] for x in r)/max(1,sum(x["train_exact"] for x in r))
            ),
            "candidate_evaluations":sum(x["candidate_evaluations"] for x in r),
            "actual_public_vm_calls":sum(x["actual_public_vm_calls"] for x in r),
            "actual_shift_vm_calls":sum(x["actual_shift_vm_calls"] for x in r),
            "cpu_seconds":round(sum(x["cpu_seconds"] for x in r),6),
            "cpu_cap_breaches":sum(x["cpu_cap_breached"] for x in r),
        }
    for field in ("candidate_evaluations","actual_public_vm_calls","actual_shift_vm_calls"):
        assert len({v[field] for v in s.values()})==1
    return s


def evaluate_checkpoint(tasks,replica_controllers,checkpoint,phase):
    rows=[]
    for task in tasks:
        for rep in range(SEEDS):
            for arm in ARMS:
                learner=replica_controllers[rep][arm]
                rows.append(episode(
                    task,rep,checkpoint,arm,learner,phase,
                    learn=False,weights=learner.checkpoint(checkpoint)
                ))
    return rows


def run():
    source,manifest=load_external()
    support=sum(manifest["support_rounds"],[])
    dev=sum(manifest["development_rounds"],[])
    external_checks=verify_external(source,support+dev)
    assert external_checks==31*15
    replicas={
        seed:{a:Learner(a) for a in ARMS}
        for seed in range(SEEDS)
    }
    generation_history=[]
    for g in range(GENERATIONS):
        support_rows=[]
        for task in manifest["support_rounds"][g]:
            for rep in range(SEEDS):
                for arm in ARMS:
                    support_rows.append(episode(
                        task,rep,g,arm,replicas[rep][arm],"support",learn=True
                    ))
        for rep in range(SEEDS):
            for arm in ARMS:
                replicas[rep][arm].finish_generation(g)
        dev_rows=evaluate_checkpoint(
            manifest["development_rounds"][g],replicas,g,"development",
        )
        generation_history.append({
            "generation":g+1,
            "support_summary":summary(support_rows),
            "development_summary":summary(dev_rows),
            "support_rows":support_rows,
            "development_rows":dev_rows,
        })
    # Strictly AFTER the three controller snapshots are frozen, validate and
    # independently evaluate the externally committed audit tasks.
    audit_verified_examples=verify_external(source,manifest["audit_tasks"])
    assert audit_verified_examples==19*15
    audit_checkpoints=[]
    for g in range(GENERATIONS):
        rows=evaluate_checkpoint(manifest["audit_tasks"],replicas,g,"audit")
        audit_checkpoints.append({
            "generation":g+1,
            "summary":summary(rows),
            "rows":rows,
        })
    last=audit_checkpoints[-1]
    metrics=last["summary"]
    peers={arm:compare_pairs(last["rows"],"adaptive_persistent",arm)
           for arm in ARMS if arm!="adaptive_persistent"}
    family_deltas={}
    for family in FAMILY_LABELS:
        target=[r for r in last["rows"] if r["task"].startswith(family+" with k=")]
        family_deltas[family]={
            arm:(
                sum(r["shift_correct"] for r in target if r["arm"]=="adaptive_persistent")-
                sum(r["shift_correct"] for r in target if r["arm"]==arm)
            ) for arm in CONTROL_ARMS
        }
    fixed=max(("dedup_uniform","frozen_mutation"),
              key=lambda a:metrics[a]["shift_correct"])
    comparisons=["dedup_uniform","frozen_mutation","untrained_no_memory",
                 "memory_wiped","one_generation_equal_compute"]
    n=SEEDS*len(manifest["audit_tasks"])
    final_effects={
        a:(metrics["adaptive_persistent"]["shift_correct"]-metrics[a]["shift_correct"])/n
        for a in comparisons
    }
    audit_margins=[]
    for row in audit_checkpoints:
        v=row["summary"]
        audit_margins.append(
            (v["adaptive_persistent"]["shift_correct"]-
             v[fixed]["shift_correct"])/n
        )
    positive_curve=(
        audit_margins[0]<=audit_margins[1]<=audit_margins[2]
        and audit_margins[2]-audit_margins[0]>=0.05
    )
    cpu_ratio=max(
        metrics["adaptive_persistent"]["cpu_seconds"]/max(1e-9,metrics[fixed]["cpu_seconds"]),
        metrics[fixed]["cpu_seconds"]/max(1e-9,metrics["adaptive_persistent"]["cpu_seconds"]),
    )
    negative_effect=(
        metrics["negative_inverted"]["shift_correct"]-
        metrics[fixed]["shift_correct"]
    )/n
    gate_components={
        "min_eight_pp_over_strongest_fixed":final_effects[fixed]>=0.08,
        "min_five_pp_over_every_memory_and_total_compute_control":all(
            final_effects[a]>=0.05 for a in ("memory_wiped","one_generation_equal_compute","untrained_no_memory")
        ),
        "paired_seed_cluster_bootstrap_lower95_positive":all(
            peers[a]["paired_seed_bootstrap"]["ci95"][0]>0 for a in comparisons
        ),
        "no_negative_external_audit_family":all(
            all(x>=0 for x in family_deltas[f].values()) for f in FAMILY_LABELS
        ),
        "positive_unseen_family_multigeneration_growth":positive_curve,
        "inverted_feedback_negative_control_fails":negative_effect<0.08,
        "no_cpu_cap_breach":all(v["cpu_cap_breaches"]==0 for v in metrics.values()),
        "actual_cpu_within_ten_percent":cpu_ratio<=1+CPU_PARITY_TOLERANCE,
        "evaluations_matched":all(
            len({v[f] for v in metrics.values()})==1
            for f in ("candidate_evaluations","actual_public_vm_calls","actual_shift_vm_calls")
        ),
    }
    passed=all(gate_components.values())
    return {
        "schema":"external-preregistered-meta-controller-v1",
        "source_blob":SOURCE_BLOB,
        "manifest_blob":MANIFEST_BLOB,
        "old_split_exclusion_blob":SPLIT_BLOB,
        "root_main_sha":BASE_SHA,
        "preregistration_files":[
            "research/PREREG_EXTERNAL_METACONTROL_20261108.md",
            "research/PREREG_ADDENDUM_AUDIT_CURVE_20261108.md",
        ],
        "validated_upstream_examples":{
            "support_and_development":external_checks,
            "audit_checked_only_after_all_controller_states_frozen":audit_verified_examples,
        },
        "seeds_independent":SEEDS,
        "generation_history":generation_history,
        "controller_snapshots":{
            str(rep):{arm:learner.history for arm,learner in arms.items()}
            for rep,arms in replicas.items()
        },
        "audit_checkpoints":audit_checkpoints,
        "final_paired_vs_every_baseline":peers,
        "audit_family_deltas_vs_controls":family_deltas,
        "strongest_fixed_baseline":fixed,
        "final_ood_absolute_effects":final_effects,
        "unseen_audit_family_learning_curve_margins":audit_margins,
        "cpu_ratio_vs_strongest_fixed":cpu_ratio,
        "negative_control_effect":negative_effect,
        "gate_components":gate_components,
        "preregistered_success":passed,
        "general_rsi_proven":False,
        "production_eligible":False,
        "limitations":[
            "Published external benchmark tasks, but only list-of-int substrate.",
            "32 independently generated shifted-input checks per task trajectory, not formal correctness.",
            "Controller changes action probabilities but does not rewrite its own source or verifier.",
            "Not all task families or CPU costs are equally represented.",
            "No sealed TEST/J data, unmerged PR source, or prior audit outcomes were used.",
            "The audit and its three checkpoints are single-use and are spent.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("research/results/external_metacontrol_raw.json"))
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        source,manifest=load_external()
        assert verify_external(source,sum(manifest["support_rounds"],[]))==16*15
        assert verify_external(source,sum(manifest["development_rounds"],[]))==15*15
        for name in sum(manifest["support_rounds"],[])+sum(manifest["development_rounds"],[]):
            assert len(input_pairs(name,7,"shift"))==SHIFT_N
        a=Learner("adaptive_persistent")
        a.reward("parameter_mutation",0.9)
        a.reward("uniform",0.0)
        a.finish_generation(0)
        assert a.weights["parameter_mutation"]>a.weights["uniform"]
        for action in ACTIONS:
            vocab=vocabulary("list-of-int")
            candidate=mutate_candidate(random.Random(909),vocab,vocab[0],action,{}, {})
            assert candidate in vocab
        x=episode(manifest["support_rounds"][0][0],0,0,"dedup_uniform",Learner("dedup_uniform"),"smoke")
        assert x["actual_public_vm_calls"]==CANDIDATES*TRAIN_N
        assert x["actual_shift_vm_calls"]==SHIFT_N
        print("PASS: source hashes, protected TEST exclusion, external support/dev semantics, "
              "32 OOD probes, controller update, exact counted VM evaluations")
        return
    result=run()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "strongest_fixed":result["strongest_fixed_baseline"],
        "final_audit":result["audit_checkpoints"][-1]["summary"],
        "paired":result["final_paired_vs_every_baseline"],
        "curve":result["unseen_audit_family_learning_curve_margins"],
        "gate":result["gate_components"],
        "preregistered_success":result["preregistered_success"],
        "general_rsi_proven":result["general_rsi_proven"],
        "raw_json":str(args.out),
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
