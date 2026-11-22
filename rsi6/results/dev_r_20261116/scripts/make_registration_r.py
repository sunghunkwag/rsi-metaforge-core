"""Write rsi6/registry/registration_r.json and amendment_6.json (run from the repository root).

    python3 make_registration_r.py <dev.json>

dev.json (written by make_dev_r.py) holds what the development checks fixed by their pre-written
rules: J, S, the CPU model (D4), the test (D6), the relay settings and the arms (D2), the
predictions' expected values (D3), and the development record. Nothing else is chosen here, and
nothing is written unless the development rules say to register and D6 was run at the final
layout.
"""
import hashlib
import json
import math
import sys
import time

import numpy as np

sys.path.insert(0, ".")
from rsi6.learner import design_r, designs, dispatch_extra

dispatch_extra.install()
dev = json.load(open(sys.argv[1]))
if not dev["register"]:
    raise SystemExit("development rule D2 (e) says: do not register")
if not dev["d6_done"]:
    raise SystemExit("D6 has not been run at the final J, S and tau*")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
fresh = json.load(open("rsi6/registry/fresh.json"))
held = sorted(k for k, v in fresh["categories"].items() if v["admitted"])
meta_cats = ["jobshop", "quadassign", "pmedian", "knapsack", "binpacking"]
files = ["rsi6/learner/design_r.py", "rsi6/learner/design_q.py", "rsi6/learner/design_o.py", "rsi6/learner/designs.py",
         "rsi6/learner/dispatch_extra.py", "rsi6/learner/learner.py", "rsi6/learner/version.py", "rsi6/learner/design_b.py",
         "rsi6/open/edits.py", "rsi6/open/discovery.py", "rsi6/open/evaluate.py", "rsi6/open/relay.py", "rsi6/open/relay_report.py",
         "rsi6/kernel/run.py", "rsi6/kernel/problem.py", "rsi6/kernel/environment.py", "rsi6/kernel/ledger.py", "rsi6/kernel/roles.py",
         "rsi6/experiments/guard.py", "rsi6/experiments/report.py", "rsi6/environments/__init__.py", "rsi6/environments/fresh.py",
         "rsi6/registry/fresh.json", "rsi6/registry/roles.json", "rsi6/tests/test_design_r.py", "rsi6/tests/test_relay.py"] + \
        [f"rsi6/environments/{c}.py" for c in meta_cats + held] + [f"rsi6/environments/manifests/{c}.json" for c in meta_cats + held]
v = design_r.default()
# relay.py requires the registered version to be design_r.default(): a setting the development
# rules change (the rule, beta) is changed in design_r.RELAY0, whose file the registration pins
for key, value in (dev.get("relay") or {}).items():
    assert v["relay"][key] == value, f"set {key} = {value!r} in design_r.RELAY0 before registering"
now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def predictions(dev) -> list:
    """The synthesis's predictions P1 to P18 with their registered scoring: a prediction is met when
    every check holds; a point prediction without a stated interval is scored within +-0.003 (the
    width the synthesis stated for its other secondary differences); D3 sets P3, and when L4 is at
    most 0.1 lowers P7 and P10."""
    fail = dev["transfer_predicted_to_fail"]
    L4 = dev["L4_dev"]
    # expected outcomes at the chosen layout, under a predictive effect distribution N(mu, s^2):
    # N(0.002, 0.003^2) as in the synthesis, or N(0, 0.002^2) when D3 predicts that transfer fails
    from rsi6.open.relay_report import t_quantile, t_sf
    J, S = dev["J"], dev["S"]
    sig, tau = dev["power"]["sigma_star"], dev["power"]["tau_star"]
    se = math.sqrt((tau ** 2 + sig ** 2 / (4 * S)) / J)
    mu, sd = (0.0, 0.002) if fail else (0.002, 0.003)
    grid = np.linspace(mu - 5 * sd, mu + 5 * sd, 2001)
    wts = np.exp(-0.5 * ((grid - mu) / sd) ** 2)
    wts /= wts.sum()
    crit, t95 = t_quantile(0.01, J - 1), t_quantile(0.05, J - 1)
    p_met = float(sum(w * t_sf(crit - th / se, J - 1) for th, w in zip(grid, wts)))
    p_neg = float(sum(w * (1 - t_sf((0.007 - t95 * se - th) / se, J - 1)) for th, w in zip(grid, wts)))
    se_half = se * math.sqrt(2.0)
    p_fut = float(sum(w * (1 - t_sf(0.5 - th / se_half, J // 2 - 1)) for th, w in zip(grid, wts)))
    dist = f"N({mu}, {sd}^2)"
    half = 1.645 * math.sqrt(sd ** 2 + se ** 2)                 # the 90% predictive interval of the measured mean
    p3 = L4 if L4 is not None else 0.45
    Q = lambda q, lo=None, hi=None, expected=None: {"quantity": q, "lo": lo, "hi": hi, "expected": expected}
    E = "endpoints / "
    Dg = "diagnostics / "
    out = [
        {"id": "P1", "text": "Meta, source categories, per on-policy acquisition at train 200: median program rounds 25 (90% range 15 to 45); median informative-variant share 0.7 (0.45 to 0.85); 0.22 confirmed switches per program round (0.12 to 0.35), as the median over acquisitions",
         "checks": [Q("meta per acquisition (on-policy) / median_program_rounds", 15, 45, 25), Q("meta per acquisition (on-policy) / median_informative_share", 0.45, 0.85, 0.7),
                    Q("meta per acquisition (on-policy) / median_switches_per_round", 0.12, 0.35, 0.22)]},
        {"id": "P2", "text": "In at least 75% of on-policy chains (expected 85%), at least two of score/replace, score/mutop, score/swap and pick/swap are among the four lowest-weight cells of the final memory's prior",
         "checks": [Q("final memories / share_with_two_named_destructive_cells_among_four_lowest", 0.75, None, 0.85)]},
        {"id": "P3", "text": f"L4: the mean pairwise Spearman correlation over source categories of the per-cell m_c/ubar (pooled per category over the on-policy chains) is {p3:.3f} (set by D3 on the development chains), and at least {p3 - 0.15:.3f}; carried by the destructive cells (reported, not scored)",
         "checks": [Q("L4 cross-category correlation of the learned per-cell statistics / mean_pairwise_spearman", p3 - 0.15, None, p3)]},
        {"id": "P4", "text": "L7: on-policy minus off-policy mean d+ per informative variant over positions 1 to 11 is +15% relative with a 95% chain-bootstrap interval excluding 0; at the category-switch positions +10% with an interval including 0",
         "checks": [Q("L7 discovery efficiency over generations (on- minus off-policy) / positions 1 to 11 / lower_95", 1e-12, None, 0.15),
                    Q("L7 discovery efficiency over generations (on- minus off-policy) / category-switch positions / lower_95", None, 0.0, 0.10),
                    Q("L7 discovery efficiency over generations (on- minus off-policy) / category-switch positions / upper_95", 0.0, None, 0.10)]},
        {"id": "P5", "text": "The median library size of the final memories is 8 blocks (2 to 16); at most 10% of held-out relay acquisitions keep a program with a spliced block",
         "checks": [Q("final memories / library_size_median", 2, 16, 8), Q(Dg + "L3 inner productivity / relay / all / kept_spliced_block", None, 0.10)]},
        {"id": "P6", "text": "L3 held-out: relay's confirmed switches per program round are at least 1.15 times frozen's on at least 3 of the 4 categories; relay's informative share is within 0.05 of frozen's on every category",
         "checks": [Q(Dg + "categories where relay's switches per round are at least 1.15 times frozen's", 3, None), Q(Dg + "largest informative-share difference, relay minus frozen", None, 0.05)]},
        {"id": "P7", "text": ("L6: the Spearman correlation between w(M_j) and frozen's realized per-cell d+ is 0.0 on average (transfer predicted to fail by D3; scored within +-0.15); the shuffled placebo's is 0.0 +- 0.1; among the 10 cells of highest prior weight, 0 +- 0.3"
                              if fail else "L6: the Spearman correlation between w(M_j) and frozen's realized per-cell d+ is +0.3 on average (scored within +-0.15) and positive on at least 3 of 4 categories; the shuffled placebo's is 0.0 +- 0.1; among the 10 cells of highest prior weight, 0 +- 0.3"),
         "checks": ([Q(Dg + "L6 prospective transfer of discovery knowledge / mean", -0.15, 0.15, 0.0)] if fail else
                    [Q(Dg + "L6 prospective transfer of discovery knowledge / mean", 0.15, 0.45, 0.3), Q(Dg + "L6 prospective transfer of discovery knowledge / categories_positive", 3, None)])
                   + [Q(Dg + "L6 prospective transfer of discovery knowledge / shuffled_mean", -0.1, 0.1, 0.0), Q(Dg + "L6 prospective transfer of discovery knowledge / top10_mean", -0.3, 0.3, 0.0)]},
        {"id": "P8", "text": "L1: frozen minus o0@relay = -0.003 (90% predictive interval -0.012 to +0.006)", "checks": [Q(Dg + "L1 frozen minus o0@relay / mean", -0.012, 0.006, -0.003)]},
        {"id": "P9", "text": "L2: frozen at four times the budget minus frozen = +0.005 (-0.002 to +0.012)", "checks": [Q(Dg + "L2 frozen@ceiling minus frozen / mean", -0.002, 0.012, 0.005)]},
        {"id": "P10", "text": ((f"E-R1: relay minus frozen = 0.000 (transfer predicted to fail by D3; 90% predictive interval -{half:.4f} to +{half:.4f})" if fail else
                                "E-R1: relay minus frozen = +0.002 (90% predictive interval -0.003 to +0.007)")
                               + f"; under the predictive distribution {dist} at (J, S) = ({J}, {S}) and SE {se:.5f}: E-R1 met with probability {p_met:.2f}, the decisive negative (95% upper bound below 0.007) with probability {p_neg:.2f}"),
         "checks": [Q(E + "E-R1 relay minus frozen / mean", -round(half, 4), round(half, 4), 0.0) if fail else Q(E + "E-R1 relay minus frozen / mean", -0.003, 0.007, 0.002)],
         "events": [{"quantity": "gate / E-R1", "probability": round(p_met, 3)}, {"quantity": E + "E-R1 relay minus frozen / decisive_negative", "probability": round(p_neg, 3)}]},
        {"id": "P11", "text": f"The held-out stage stops for futility at J/2 chains with probability {p_fut:.2f} (the same distribution)", "events": [{"quantity": "futility look / stop", "probability": round(p_fut, 3)}]},
        {"id": "P12", "text": "Secondaries (chains below 32, two seeds): relay - shuffled +0.003; relay - offpolicy 0.000 (absolute value below 0.003); relay - libonly +0.002; relay - prioronly 0.000 (absolute value below 0.003); relay - o0@relay -0.001; points without a stated interval scored within +-0.003",
         "checks": [Q(E + "E-R2 relay minus shuffled / mean", 0.0, 0.006, 0.003), Q(E + "E-R4 relay minus offpolicy / mean", -0.003, 0.003, 0.0)]
                   + ([] if "libonly" in dev["dropped_arms"] else [Q(E + "E-R5 relay minus libonly / mean", -0.001, 0.005, 0.002), Q(Dg + "relay minus prioronly / mean", -0.003, 0.003, 0.0)])
                   + [Q(E + "E-R3 relay minus o0@relay (matched CPU) / mean", -0.004, 0.002, -0.001)]},
        {"id": "P13", "text": "m_net = -0.001, at most 0, with its lower bound below 0", "checks": [Q("m_net / value", None, 0.0, -0.001), Q("m_net / lower_bound", None, -1e-12)]},
        {"id": "P14", "text": "L8: the slope of relay(M^(k)) minus frozen over k = 4, 8, 12 is within +-0.0005 per acquisition", "checks": [Q(Dg + "L8 depth curve / slope", -0.0005, 0.0005, 0.0)]},
        {"id": "P15", "text": "Retention, source part B: R_JS within +-0.004; the within-category benefit on job shop +0.001 (-0.004 to +0.006); R_QAP within +-0.006",
         "checks": [Q("retention / R_jobshop: depth 12 minus depth 3 / mean", -0.004, 0.004, 0.0), Q("retention / within_jobshop: depth 3 minus no memory / mean", -0.004, 0.006, 0.001),
                    Q("retention / R_quadassign: depth 12 minus depth 6 / mean", -0.006, 0.006, 0.0)]},
        {"id": "P16", "text": "Cost: the relay/frozen CPU ratio is in [0.95, 1.10] on every held-out category; o0@relay reaches relay's CPU within 2 levels in at least 90% of pairs; no comparison is void",
         "checks": [Q(Dg + "relay over frozen CPU, smallest", 0.95, None), Q(Dg + "relay over frozen CPU, largest", None, 1.10), Q(Dg + "o0@relay reached within 2 levels", 0.9, None),
                    Q(Dg + "void comparisons", None, 0)]},
        {"id": "P17", "text": "Capability held: the share of runs at or above the category threshold differs between relay and frozen by less than 0.03 on every category",
         "checks": [Q(Dg + "largest threshold-share difference, relay minus frozen", None, 0.03 - 1e-12)]},
        {"id": "P18", "text": "The success condition T3 is not met (probability at least 0.95). If E-R1 fails, the diagnostics name the limit: L2 < 0.004 an object-level ceiling; L2 >= 0.007 with L6 about 0 discovery knowledge that does not transfer; an L3 gain without an acquired gain inner discoveries that overfit training problems; L1 < 0 inner discovery harmful at equal CPU (reported, not scored)",
         "checks": [Q("tiers / T3", None, 0.0)], "events": [{"quantity": "tiers / T3", "probability": 0.05}]},
    ]
    return out

order = ["jobshop"] * 3 + ["quadassign"] * 3 + ["pmedian"] * 3 + ["knapsack"] * 2 + ["binpacking"]
meta_b = {"train": 200.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24, "part": "A"}
test_text = ("a one-sided sign-flip permutation test on the chain means (10,000 flips seeded by the CRC-32 of the comparison's label; development check D6 found the "
             "t-test's null rejection rate above 0.013)" if dev["test"] == "signflip" else "Student's t, one-sided, on the chain means")
reg = {
 "what": "amendment 6: design r, a learner whose discovery machinery (operator prior, edit-size prior, library of instruction blocks) is rebuilt at every acquisition from its own record of earlier discoveries, relayed across categories; decided once on four categories no process had used",
 "amendment": 6,
 "registered_utc": now,
 "why": "the Owner's instruction 14. Measured failures that this attempt does not repackage: the open design's registered discovery accepted nothing (0 of 18 confirmations; every final mechanism is generation 0), and design q's search over its programs inside acquisition gained nothing at training budget 40 in development (q0 minus o0 -0.003 and -0.002; rsi6/results/dev_20261116). The design was proposed by an independent panel of five designers, scored by three independent judges (all three ranked it first) and specified by a synthesis (rsi6/audit/design_panel_20261116). Its development check D1 then found a defect in the inner search's acceptance (a batch judged by mean rank takes programs that break hard constraints on some problems), which generation 0 of design r repairs (accept: hard_first); D1 and D2 were run again on the repaired design (development record below; rsi6/results/dev_r_20261116)",
 "design": "r",
 "version": v,
 "version_digest": designs.digest(v),
 "placebo_seed": 29,
 "files": {f: sha(f) for f in files},
 "budgets": {"meta": meta_b, "retention": dict(meta_b, part="B"),
             "heldout": {"train": 200.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}},
 "meta": {"chains": dev["J"], "chains_off": 32, "order": order, "seed_base": 250000,
          "retention": {"chains": 32, "seed_base": 265000, "plan": {"jobshop": [0, 3, 12], "quadassign": [0, 6, 12]}},
          "rule": "on-policy chain j: acquisition k on order[k], seed 250000 + 100 j + k, with the memory the chain's earlier acquisitions left (their reports' relay.new_entries); off-policy chain j < 32: the same acquisitions each with no memory (at k = 0 the two share one run); the on- and off-policy runs of a position are submitted side by side; retention, chains j < 32, seed 265000 + 10 j, the confirming half: job shop with no memory and the memories of depth 3 and 12, quadratic assignment with no memory and the memories of depth 6 and 12"},
 "heldout": {"categories": held, "role": "fresh", "seed_base": 260000, "seeds": dev["S"], "secondary_chains": 32, "depths": [8, 4],
             "reference_chains": 16, "cpu_model": dev["cpu_model"], "train_grid": [200, 160, 120, 80, 40], "max_cpu_per_run": 60.0,
             "machine_factor": 1.15, "cpu_total": 300000.0, "cpu_development": dev["cpu_development"], "cpu_reserve": 15000.0,
             "matched_levels": 2, "ceiling_cost": 3.8, "cpu_tolerance": 1.10, "futility_t": 0.5, "ceiling_factor": 4,
             "frozen_matched_everywhere": dev["frozen_matched_everywhere"], "dropped_arms": dev["dropped_arms"], "test": dev["test"],
             "alpha": {"primary": 0.01},
             "priority": ["1 relay and frozen, chains below J/2 (primary-a), then the futility look and the CPU rule",
                          "2 relay and frozen, chains from J/2 (primary-b)", "3 shuffled", "4 o0 raised to relay's CPU (o0@relay; its runs at the registered budget are the arm o0)",
                          "5 offpolicy", "6 library only", "7 frozen at four times the training budget", "8 prior only",
                          "9 depth 8", "10 depth 4", "11 references o0 and a0 at the run budget of the earlier processes",
                          "12 a0 raised to relay's CPU (a0@relay; its runs at the registered budget are the arm a0)"],
             "pairs": "seeds 260000 + 10 j + s; items 1 and 2: s below S; items 3, 4, 5, 6, 8: chains below 32, s below 2; items 7, 9, 10: chains below 32, s = 0; items 11, 12: chains below 16, s = 0. The arms of an item that are compared (relay and frozen; o0 and a0 at the reference budget) are submitted as one batch interleaved pair by pair",
             "futility": "non-binding: after item 1, if the t of the J/2 chain means of relay minus frozen (at the registered budget) is below 0.5, items 2, 3, 5, 6, 8, 9 and 10 are not run; E-R1 is then measured on J/2 of its J chains and is not met; items 4, 7, 11 and 12 still run, on the chains below J/2 that the primary holds (at most 32, at most 16 for the references). It spends no alpha",
             "cpu_rule": "over item 1, on a category where relay's CPU over frozen's exceeds 1.10 (on every category when frozen_matched_everywhere: development rule f), frozen is raised pair by pair to relay's CPU (the schedule of evaluate.raise_until: the training budget doubled, then the factor the measured CPU asks for, until the run's CPU reaches relay's), in both halves of the primary. The same rule applies to shuffled, offpolicy, libonly and prioronly against relay, each over its own pairs, raised with its own memory. o0 is raised to relay's CPU on every category. A comparison then uses the raised comparator on those categories AND the comparator at the registered budget on every category: both tests must hold (a comparator is not weakened by being given more CPU; in development a doubled budget did not always help)",
             "size_rule": "the training budget of a held-out category is the largest of 200, 160, 120, 80, 40 at which the CPU model predicts at most 60 s per run of o0, computed from the construction units of its problems (built with a dummy meter, no learner) at the start of the stage; no development step read a held-out category's sizes",
             "plan_rule": "H_cap = cpu_total - machine_factor x (cpu_development + the recorded CPU of the registered meta and retention runs) - cpu_reserve. Projection = machine_factor x the sum over items of runs x predicted recorded CPU: an r0 run costs the CPU model's o0 times r0_over_o0 at the category's budget; a matched item (o0@relay, a0@relay) matched_levels runs at relay's CPU per pair; frozen at the ceiling ceiling_cost runs; a reference o0's model at the run budget, for o0 and for a0; where frozen is raised on every category (frozen_matched_everywhere) the primary counts matched_levels - 1 further runs per pair. Items are dropped from the end of the list until the projection is at most H_cap; if the primary alone exceeds it, the costliest category's budget is lowered by one grid step and the plan recomputed. Before each item the projection is recomputed from the CPU spent and the measured CPU per r0 run (the raise of frozen in primary-b from the measured CPU of primary-a's raise, scaled by the chains); items are dropped from the end until it fits, and if the item itself does not fit the stage stops (r_cap). The raises of the later r0 arms depend on their own measured CPU and are not projected"},
 "statistic": "per chain: the mean over the held-out categories of the mean over seeds of the paired difference (same category, seed and chain) of the acquired score. Within the arms of design r and against o0 the untrained answers are identical (same programs and constants before acquisition, same apply stream), so the change of the gain equals it; the report checks this over every arm of designs r and o and, if it fails, no endpoint is met. Against a0 the smaller of the mean change of the acquired score and the mean change of the gain. Test: " + test_text,
 "endpoints": {"E-R1": "relay minus frozen, all J chains, at 0.01" + (" (critical t(0.99, J-1))" if dev["test"] == "t" else "") + "; against frozen as the CPU rule leaves it and, where frozen was raised, also against frozen at the registered budget: both tests",
               "gate": "E-R2 relay minus shuffled at 0.01 only if E-R1 is met; then Holm at 0.01 over E-R3 relay minus o0 (against o0 raised to relay's CPU, void and so not met if any pair is unreached or got less CPU than relay, and against o0 at the registered budget: the larger of the two p-values enters Holm), E-R4 relay minus offpolicy and E-R5 relay minus libonly (each by the same both-tests rule where the CPU rule raised its comparator), only if E-R2 is met; chains below 32, seeds 0 and 1. An arm that was not measured on its registered chains fails its endpoint" + ("" if "libonly" not in dev["dropped_arms"] else ". Development rule (b) dropped the library: E-R5 is not an endpoint and Holm is over E-R3 and E-R4"),
               "tiers": "T1 = E-R1 and E-R2 (the record carries information that helps on these unseen categories); T2 = T1 and E-R4 and E-R5 (recursive, beyond accumulation and beyond retained blocks); T3 = T2 and E-R3 (useful at matched compute). 'Recursive improvement observed' only at T3; 'established' only after replication on an independent set at 0.05"},
 "m_net": "the smallest, over the comparators frozen, shuffled, offpolicy, libonly and o0, each both as the CPU rule leaves it and at the registered budget, of the mean over chains below 32 (seeds 0 and 1) of the chain-mean difference relay minus that comparator, in acquired-score units; with its Bonferroni lower bound (the smallest of mean minus t(0.99, chains - 1) se) and relative to frozen's gain. It has no value unless every one of these comparators was measured on all 32 chains. The Owner's term has no definition in the record; this one is registered here",
 "diagnostics": ["L1 frozen minus o0, both with at least relay's CPU (frozen as the CPU rule leaves it, o0 raised), and both at the registered budget", "L2 frozen at four times the budget minus frozen",
                 "L3 inner productivity per arm and category", "L4 cross-category Spearman correlation of the per-cell learned statistics (m_c over ubar, pooled per category over the on-policy chains)",
                 "L5 shuffled minus frozen", "L6 Spearman between the relayed prior, fixed before any held-out run, and frozen's realized per-cell positive margins (cells with at least 5 informative variants), with the shuffled prior as placebo and among the 10 cells of highest prior weight",
                 "L7 discovery efficiency over generations: on- minus off-policy positive margin per informative variant at positions 1 to 11, and at the category-switch positions, with a 95% chain bootstrap",
                 "L8 the depth curve: memories of depth 4, 8 and 12 each minus frozen (chains below 32, seed 0), and its slope, given only if all three depths were measured",
                 "the 2x2 of prior and library", "retention (R_JS, the within-category benefit on job shop, R_QAP)", "CPU, units, constructions and the share of runs at or above the threshold per arm",
                 "E-R1 with bootstraps over chains and seeds and over categories and seeds; per-category signs; negative transfer below -0.005", "the references"],
 "predictions": predictions(dev),
 "prediction_scoring": "a prediction is met when every one of its checks holds (the measured quantity within its bounds), missed when one fails, not scored when a quantity was not measured; events are reported with their registered probabilities. The report lists the misses first",
 "power": dev["power"],
 "alpha_spending": "0.05 in total over all further registered success claims of this programme; 0.01 spent here by E-R1; at most 0.01 per later attempt, each judged on categories no earlier attempt evaluated on (the four fresh categories are used here)",
 "family_risk": "earlier attempts: the registered rounds of designs a and b, process c (in progress), the open design (no acceptance), design q (development only). Trying techniques until one passes at 0.05 gives a false-success probability of 1 - 0.95^K (0.23 after 5 attempts); the alpha-spending rule bounds it",
 "development": dev["development"],
 "development_deviations": ["D1's seeds are 9201 to 9206, not 600001 to 600006",
                            "D1 rule (a)'s compile cache was not added (a profile shows the extra CPU is not compilation)",
                            "after the first D1 the design was changed (accept: hard_first) and D1 and D2 were run again in full; the first-rule D2 was stopped after 56 chain acquisitions, before any arm on a left-out category ran, so no development effect of the first rule was seen",
                            "development runs shared the machine, at low priority, with the registered held-out stage of the open experiment (16 November, about 13:50 to 16:37 UTC), against the specification's rule that development waits for registered drivers; the driver and the development scripts now wait",
                            "an independent review of the driver, the report and the placebo found defects that were corrected before registration (commit c84cf75); the specification's 'reviewed twice' is recorded in rsi6/audit/relay_review_20261116"],
 "heldout_caveats": ["thresholds are operating points that plain non-learning procedures reach or approach on all four categories (audit/adapters_fresh_20261116): no threshold crossing counts as an acquired capability; the endpoints are paired differences between arms",
                     "quadratic: computation on the exposed arrays is not metered; a gain counts only between answers produced with at least equal CPU, which the CPU rule and the raised controls enforce",
                     "quadratic: the be files of one generator seed share stretches of the generator's stream across the split; the rule bin packing is held to is not met; the auditor found no exploitable relation",
                     "projects: the score scale is compressed at the top (random lists score 0.970 on the fresh split); its paired differences are small next to other categories'",
                     "tardiness: on the deciding half 9 of 14 instances are at the ceiling of the due-date order (the held-out stage uses both halves)",
                     "the comparison with o0 is between two designs: design r's generation 0 has the inner program search and the hard-first acceptance, o0 has neither; it is the equal-compute control of the Owner's instruction, not a test of the relay alone (that is relay against frozen, shuffled, offpolicy and libonly, which share everything but the memory)"],
 "what_cannot_be_shown": ["the discovery of new learning principles: the init, propose and update programs and the split between representation search and parameter learning are fixed; the recursion is one level deep and its update rule is written by the experimenter",
                          "radical novelty: credit-assigned operator selection, probability matching and block reuse are known components; what is new is the test and its controls",
                          "generalisation beyond these four categories (fixed-effect inference)", "effects below the minimum detectable effect",
                          "verification of every generation (held-out memories of depth 4, 8 and 12 only)",
                          "retention of capabilities: no capability is carried across categories; only the retention of discovery knowledge is measured",
                          "anything at the earlier processes' training budget or without the shared test-time local improvement"],
 "not_claimed": ["that the instruction set, the sensors or the edit operators are free of human design", "anything about artificial general intelligence"],
 "reproduction": {"install": "relay.py installs designs q and r in the dispatch and the fresh categories in the registry at run time",
                  "meta": "python -m rsi6.open.relay --stage meta", "heldout": "python -m rsi6.open.relay --stage heldout",
                  "report": "python -m rsi6.open.relay_report --json rsi6/results/relay_report.json",
                  "replay": "a stopped stage replays from its start, every run served from the ledger and every record checked; runs are submitted 16 at a time, so a stop repeats at most one submission (tests: rsi6/tests/test_relay.py, T10)",
                  "resampling": "every bootstrap and the sign-flip test are seeded by the CRC-32 of the comparison's label; the placebo by seed 29 and the chain"},
}
json.dump(reg, open("rsi6/registry/registration_r.json", "w"), indent=1)
amend = {"amendment": 6, "what": reg["what"], "registration": "rsi6/registry/registration_r.json",
         "registration_sha256": sha("rsi6/registry/registration_r.json"), "utc": now,
         "order_of_work": "after the open experiment's held-out stage and before process c resumes; process c, the external gate, the recursion check, the sealed target test and the open experiment's later held-out stage keep their registrations and follow"}
json.dump(amend, open("rsi6/registry/amendment_6.json", "w"), indent=1)
print("registration_r", sha("rsi6/registry/registration_r.json")[:16], "held-out", held, "J", dev["J"], "S", dev["S"], "test", dev["test"])
