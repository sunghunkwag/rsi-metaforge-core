"""Apply the development rules written in the synthesis (D1 to D6) to the development results and
write dev.json for make_registration_r.py. Every decision is computed here from the D-files; none
is typed by hand. Run from the repository root after D1, D2, D3 and D4 (D6 is run with the J, S
and tau* this script chooses, then this script is run again to fold D6 in).

    python3 make_dev_r.py
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, "<repo>")
from rsi6.learner import design_r
from rsi6.open import evaluate, relay
from rsi6.open.relay_report import t_quantile, t_sf

S_DIR = os.path.dirname(os.path.abspath(__file__))
load = lambda name: json.load(open(os.path.join(S_DIR, name))) if os.path.exists(os.path.join(S_DIR, name)) else None
D1, D3, D4, D6 = load("dev_r_d1h.json"), load("dev_r_d3.json"), load("dev_r_d4.json"), load("dev_r_d6.json")
D1_FIRST = load("dev_r_d1_rank.json")                       # the first D1, with the acceptance rule the design then had
D2 = {f: load(f"dev_r_d2n_{f}.json") for f in ("quadassign", "jobshop", "pmedian")}
assert D1 and D3 and D4 and all(D2.values()), "D1, D2 (three categories), D3 and D4 must be done"
FRESH = ["clique", "projects", "quadratic", "tardiness"]
ORDER = ["jobshop"] * 3 + ["quadassign"] * 3 + ["pmedian"] * 3 + ["knapsack"] * 2 + ["binpacking"]
decisions, record = [], {}

# ---- D1 ----------------------------------------------------------------------------------------
from rsi6.kernel import ledger as ledgers
runs = {arm: {(x["env"], x["seed"]): x for x in xs} for arm, xs in D1["runs"].items()}
pairs = lambda a, b: [runs[a][k]["acquired"] - runs[b][k]["acquired"] for k in runs[a] if k in runs[b]]
cpu = lambda arm: sum(x["cpu"] for x in runs[arm].values())
ratio_d1 = cpu("r0") / cpu("o0")
l2 = pairs("r0@800", "r0")
L2_dev = float(np.mean(l2))
record["D1, first run (acceptance rule rank, the design as it then was)"] = {
    "seeds": "9201 to 9206 (the specification named 600001 to 600006; the development seeds differ, nothing else)",
    "r0 minus o0 at train 200": D1_FIRST["r0 minus o0"], "r0@800 minus r0 (L2_dev)": D1_FIRST["r0@800 minus r0"],
    "r0 over o0 CPU": D1_FIRST["r0 minus o0"]["cpu_ratio"],
    "diagnosis": "the loss at budget 800 is carried by instances scored 0: design o's mean-rank batch fitness takes copies of the programs that "
                 "break a hard constraint on a minority of problems (one run repeated with its constructions recorded: 4.6% of the acquisition's "
                 "constructions broke one; the kept programs broke one on 3 of 10 training problems and on 3 of 10 fresh instances). Over instances "
                 "scoring above 0 in both arms r0@800 minus r0 was +0.0066",
    "change": "design r's generation 0 judges a batch hard constraints first (accept: hard_first); D1 was run again and D2 was run in full on the "
              "changed design. The first-rule D2 had been stopped after 56 chain acquisitions, before any arm on a left-out category ran"}
record["D1"] = {"acceptance rule": D1["accept"], "seeds": "9201 to 9206",
                "r0 minus o0 at train 200": {e: D1["paired r0 minus o0 by category"][e] for e in D1["paired r0 minus o0 by category"]},
                "r0 minus o0, all": D1["r0 minus o0"], "r0 minus o0@r0 (o0 raised to r0's CPU)": D1["r0 minus o0@r0"],
                "L2_dev r0@800 minus r0": {"mean": L2_dev, "sd": float(np.std(l2, ddof=1)), "n": len(l2), "per_env": D1["r0@800 minus r0"]["per_env"]},
                "r0 over o0 CPU": ratio_d1, "per arm": {k: D1[k] for k in ("r0", "o0", "o0@r0", "r0@800")}}
first_ratio = D1_FIRST["r0 minus o0"]["cpu_ratio"]
decisions.append({"rule": "D1 (a)", "condition": f"r0/o0 CPU ratio above 1.25: {first_ratio:.3f} in the first D1, {ratio_d1:.3f} in the repeated D1",
                  "prescribed": "add a behaviour-neutral compile cache, re-run T1, before D2",
                  "done": "not added. In the first D1 the condition held; a profile of one run of each design (dev_r_profile_*_quadassign.txt) shows that "
                          "compilation and sensor construction are not where design r spends its extra CPU: it is spent running the longer edited programs "
                          "inside design o's constructions (design_o.py, pinned by the open registration), so a compile cache would not change the ratio. "
                          + ("In the repeated D1 the condition does not hold." if ratio_d1 <= 1.25 else "In the repeated D1 it still holds.")
                          + " The measured ratio is carried into the plan (rule b) and the matched-CPU controls carry the comparison"})
decisions.append({"rule": "D1 (b)", "done": f"the measured r0/o0 CPU ratio replaces 1.1 in the held-out plan: {D4['r0_over_o0']:.3f} (D1's pairs at train 200)"})

# ---- D2: every rule on the 24 development chains pooled ------------------------------------------
RF = "relay minus frozen"
sigma_hat = float(math.sqrt(np.mean([D2[f][RF]["sigma_hat"] ** 2 for f in D2])))
tau_hat = float(math.sqrt(np.mean([D2[f][RF]["tau_hat"] ** 2 for f in D2])))
sigma_s, tau_s = max(sigma_hat, 0.025), max(tau_hat, 0.008)
chain_means = [x for f in D2 for x in D2[f][RF]["chain_means"]]
dev_mean = float(np.mean(chain_means))
dev_se = float(np.std(chain_means, ddof=1) / math.sqrt(len(chain_means)))
dev_interval80 = [dev_mean - t_quantile(0.1, len(chain_means) - 1) * dev_se, dev_mean + t_quantile(0.1, len(chain_means) - 1) * dev_se]
dev_upper80 = dev_interval80[1]                                # rule (e)'s bound: the upper end of the 80% interval D2 reports
libs = [x for f in D2 for x in D2[f]["library_sizes"]]
tops = [x for f in D2 for x in D2[f]["prior_top3_mass"]]
rho = {k: [x for f in D2 for x in D2[f]["prospective_spearman"][k]] for k in ("dplus", "dmean")}
lib_median, top3_median = float(np.median(libs)), (float(np.median(tops)) if tops else None)
rho_plus = float(np.mean(rho["dplus"])) if rho["dplus"] else None
rho_mean = float(np.mean(rho["dmean"])) if rho["dmean"] else None
cpu_ratios = {f: D2[f]["cpu_ratio_relay_over_frozen"] for f in D2}
record["D2"] = {"acceptance rule": sorted({D2[f]["accept"] for f in D2}), "sigma_hat": sigma_hat, "tau_hat": tau_hat, "sigma_star": sigma_s, "tau_star": tau_s,
                "per left-out category": {f: {"relay minus frozen": D2[f][RF]["mean"], "se": D2[f][RF]["se"], "sigma_hat": D2[f][RF]["sigma_hat"],
                                              "tau_hat": D2[f][RF]["tau_hat"], "shuffled minus frozen": D2[f]["shuffled minus frozen"]["mean"],
                                              "relay over frozen CPU": D2[f]["cpu_ratio_relay_over_frozen"], "instances scored 0": D2[f]["instances_scored_0"]}
                                          for f in D2},
                "development effect relay minus frozen": {"mean": dev_mean, "se": dev_se, "upper_80": dev_upper80, "interval_80": dev_interval80,
                                                          "chains": len(chain_means)},
                "library sizes (24 chains)": {"median": lib_median, "min": int(min(libs)), "max": int(max(libs))},
                "prior top-3 mass (24 chains)": {"median": top3_median},
                "prospective Spearman (per acquisition)": {"dplus": rho_plus, "dmean": rho_mean, "n": [len(rho["dplus"]), len(rho["dmean"])]},
                "productivity": {f: D2[f]["productivity"] for f in D2}}


def power(J, S, delta=0.007, sigma=sigma_s, tau=tau_s, alpha=0.01):
    se = math.sqrt((tau ** 2 + sigma ** 2 / (4 * S)) / J)
    return t_sf(t_quantile(alpha, J - 1) - delta / se, J - 1), se


def mde(J, S, level=0.8, sigma=sigma_s, tau=tau_s, alpha=0.01):
    se = math.sqrt((tau ** 2 + sigma ** 2 / (4 * S)) / J)
    return se * (t_quantile(alpha, J - 1) + t_quantile(1 - level, J - 1))


# CPU of the layouts. The chain acquisitions cost what D2's chains cost (bin packing, which D2 leaves out, the mean of the
# others); a held-out run costs the specification's planning value, 39 s for o0 at train 200, times the measured r0/o0
# ratio. No held-out category is read here.
r0_ratio = D4["r0_over_o0"]
PLAN_O0 = 39.0
held_r0 = PLAN_O0 * r0_ratio
meta_cpu = D4["fits"]["r0"]["meta_run_cpu"]
mean_meta = float(np.mean(list(meta_cpu.values())))
c_of = lambda e: meta_cpu.get(e, mean_meta)
per_chain = sum(c_of(e) for e in ORDER)
layouts = {}
for J, S in ((48, 2), (64, 2), (48, 3)):
    pw, se = power(J, S)
    layouts[f"{J}x{S}"] = {"J": J, "S": S, "power_at_0.007": pw, "se": se, "mde80": mde(J, S), "cpu": J * per_chain + 2 * J * S * 4 * held_r0}
ok = [v for v in layouts.values() if v["power_at_0.007"] >= 0.85]
choice = min(ok, key=lambda v: v["cpu"]) if ok else layouts["64x2"]
decisions.append({"rule": "D2 (a)", "done": f"(J, S) = ({choice['J']}, {choice['S']}): the cheapest layout with power at least 0.85 at 0.007"
                  if ok else "no layout reaches 0.85; (64, 2) with its MDE registered", "layouts": layouts})
J, S = choice["J"], choice["S"]
relay_changes, dropped_arms = {}, []
if lib_median < 2:
    dropped_arms = ["libonly", "prioronly"]
    relay_changes["lib_per_run"] = 0                           # no block ever enters a memory: prior only equals relay, library only equals frozen
    decisions.append({"rule": "D2 (b)", "done": f"median library size {lib_median} < 2: the library is dropped from design r (lib_per_run 0); libonly, prioronly and E-R5 are removed"})
else:
    decisions.append({"rule": "D2 (b)", "done": f"median library size {lib_median} >= 2 over the 24 chains: the library and its arms stay"})
if rho_plus is not None and rho_mean is not None and rho_mean - rho_plus >= 0.15 and rho_plus < 0.10:
    relay_changes["rule"] = "dmean"
decisions.append({"rule": "D2 (c)", "done": f"rho(dplus) {rho_plus}, rho(dmean) {rho_mean}: rule {relay_changes.get('rule', 'dplus')}"})
if top3_median is not None and top3_median > 0.5:
    relay_changes["beta"] = 0.5
decisions.append({"rule": "D2 (d)", "done": f"median top-3 prior mass {top3_median} over the 24 chains: beta {relay_changes.get('beta', 1.0)}"})
stop = L2_dev < 0.003 and dev_upper80 < 0.003
decisions.append({"rule": "D2 (e)", "done": ("do not register: L2_dev %.4f < 0.003 and the development effect's upper 80%% bound %.4f < 0.003" % (L2_dev, dev_upper80))
                  if stop else ("register: L2_dev %.4f (the stop needs it below 0.003), upper 80%% bound of the development effect %.4f" % (L2_dev, dev_upper80))})
matched_all = any(v > 1.10 for v in cpu_ratios.values())
decisions.append({"rule": "D2 (f)", "done": ("relay/frozen CPU above 1.10 on %s: frozen raised to relay's CPU on every held-out category"
                                             % [f for f, v in cpu_ratios.items() if v > 1.10]) if matched_all
                  else "relay/frozen CPU within 1.10 on every development category: %s" % {f: round(v, 3) for f, v in cpu_ratios.items()}})

# ---- D3 ----------------------------------------------------------------------------------------
L4 = D3["pooled over the D2 ledgers"]["mean_pairwise_spearman"]
fail = bool(L4 is not None and L4 <= 0.1)
record["D3"] = {"L4 on the D2 chains": L4, "pairs": D3["pooled over the D2 ledgers"]["pairs"], "transfer_predicted_to_fail": fail}
decisions.append({"rule": "D3", "done": f"P3's expected value is {L4}" + ("; at most 0.1: transfer is predicted to fail, P7 and P10 lowered" if fail else "")})

# ---- D4: the cap, with the planning cost of the held-out categories -------------------------------
seen_keys, dev_cpu = set(), 0.0                 # every development run of design r, in every scratch ledger, each run once
for name in sorted(os.listdir(S_DIR)):
    if name.startswith("dev_r") and name.endswith(".jsonl"):
        for r in ledgers.Ledger(os.path.join(S_DIR, name)).records:
            if r.get("type") == "run" and str(r.get("purpose", "")).startswith(("dev:r:", "dev-d2:", "relay-")) and r["key"] not in seen_keys:
                seen_keys.add(r["key"])
                dev_cpu += evaluate.cpu(r)


def projected(J):
    meta = ((J + 32) * per_chain - 32 * c_of(ORDER[0])                           # on- and off-policy chains; position 0 is shared
            + 32 * (3 * c_of("jobshop") + 3 * c_of("quadassign")))               # retention: depths 0, 3, 12 and 0, 6, 12
    H = {"cpu_model": {"o0": {"a": 0.0, "b": 1.0, "d": 0.0}, "r0_over_o0": r0_ratio}, "train_grid": [200, 160, 120, 80, 40], "max_cpu_per_run": 60.0,
         "machine_factor": 1.15, "matched_levels": 2, "ceiling_cost": 3.8, "dropped_arms": dropped_arms, "frozen_matched_everywhere": matched_all}
    U = {c: {"train": PLAN_O0 / 200.0, "test": 0.0} for c in FRESH}              # planning units: o0 at 39 s per run at train 200
    h_cap = 300000.0 - 1.15 * (dev_cpu + meta) - 15000.0
    plan = relay.plan_of(H, FRESH, U, J, S, 32, 16, h_cap)
    return meta, plan, 1.15 * (dev_cpu + meta) + plan["projection"] + 15000.0


meta_planned, plan, total = projected(J)
if total > 300000.0 or plan["kept"] == [1, 2] and 1.15 * sum(float(plan["cost"][k]) for k in ("1", "2")) > plan["h_cap"]:
    lower = sorted((v for v in layouts.values() if v["J"] < J and v["S"] == S and power(v["J"], v["S"])[0] >= 0.8), key=lambda v: -v["J"])
    decisions.append({"rule": "D4", "done": f"projected total {total:.0f} > 300000 after the drops: " + (f"J falls to {lower[0]['J']}" if lower else "no smaller J keeps power 0.8")})
    if lower:
        J = lower[0]["J"]
        meta_planned, plan, total = projected(J)
else:
    decisions.append({"rule": "D4", "done": f"projected total {total:.0f} of 300000 (development {dev_cpu:.0f}, meta {meta_planned:.0f}, held-out "
                                            f"{plan['projection']:.0f} with items {plan['kept']} at the planning cost); MDE80 {mde(J, S):.4f} at (J, S) = ({J}, {S})"})
record["D4"] = {"fits": D4["fits"], "r0_over_o0": r0_ratio, "r0_over_o0_by_category": D4["r0_over_o0_by_category"], "development_cpu": dev_cpu,
                "meta_cpu_planned": meta_planned, "planning cost of a held-out run": {"o0": PLAN_O0, "r0": held_r0},
                "plan at the planning cost": {k: plan[k] for k in ("kept", "projection", "h_cap", "cost")}, "projected_total": total}

# ---- D5 ----------------------------------------------------------------------------------------
record["D5"] = load("dev_r_d5_record.json")

# ---- D6 ----------------------------------------------------------------------------------------
test = "t"
if D6 and (D6["J"], D6["S"]) == (J, S) and abs(D6["tau"] - tau_s) < 1e-12:
    record["D6"] = D6
    switch = D6["switch_to_permutation_test"]
    test = "signflip" if switch else "t"
    decisions.append({"rule": "D6", "done": ("rejection rate %.4f > 0.013: E-R1 to E-R5 use the sign-flip permutation test (10,000 seeded flips)" if switch
                                             else "rejection rate %.4f <= 0.013: the t-test stays") % D6["deciding (the specification's pool)"]["rejection_rate"]})
    d6_done = True
else:
    d6_done = False
    print(f"run D6 now: python3 {S_DIR}/dev_r_d6.py {J} {S} {tau_s}")

out = {"J": J, "S": S, "relay": relay_changes, "dropped_arms": dropped_arms, "frozen_matched_everywhere": matched_all, "test": test,
       "cpu_model": {"o0": {k: D4["fits"]["o0"][k] for k in ("a", "b", "d")}, "r0_over_o0": r0_ratio}, "cpu_development": dev_cpu,
       "power": {"layouts": layouts, "chosen": [J, S], "power_at_0.007": power(J, S)[0], "mde80": mde(J, S), "mde90": mde(J, S, 0.9),
                 "sigma_star": sigma_s, "tau_star": tau_s, "formula": "one-sided t at 0.01 on J chain means; Var(chain mean) = tau*^2 + sigma*^2/(4 S); "
                                                                     "power by the shifted central t"},
       "register": not stop, "d6_done": d6_done, "L4_dev": L4, "transfer_predicted_to_fail": fail,
       "development": {"record": record, "decisions": decisions}}
json.dump(out, open(os.path.join(S_DIR, "dev.json"), "w"), indent=1, default=float)
print(json.dumps({k: out[k] for k in ("J", "S", "relay", "dropped_arms", "frozen_matched_everywhere", "test", "register", "d6_done", "L4_dev")}, default=float))
for d in decisions:
    print("-", d["rule"], ":", d["done"])
