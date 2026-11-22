"""Development analysis of the landscape files: does a single-field change chosen on some categories of the
pool carry to a category it was not chosen on?

    python3 -I landscape_loco.py DIR --out FILE.json [--boot 1000]

Input: the ``landscape_<category>_<seed>.json`` files written by ``rsi6.experiments.dev_landscape`` (any
number per category; rows are pooled by seed).

For a change k and a category c, with the runs paired by seed against generation 0:
    d_acq[k][c]  mean change of the acquired score
    d_gain[k][c] mean change of the gain
    cpu[k][c]    mean measured CPU seconds of a run
The choice statistic on a set S of categories is the one the continued process uses (amendment 2,
``rsi6.meta.rounds.breadth``): the change in each category is cut to [-0.03, +0.01] before the mean over
categories is taken, for the acquired score and for the gain, and the smaller of the two means is the value.
A change is eligible if its CPU over S is at most 1.15 times generation 0's (the registered gate's limit).

Leave one category out: for each category c, the eligible change with the largest value on the other
categories is chosen, and what it does on c is read off. The mean over c is the estimate of what a change
chosen this way does on a category it was not chosen on. Its interval is from resampling seeds within every
category and repeating the whole procedure, choice included.

Two further readings guard against one thing. Every change of a category is compared with the same runs of
generation 0, so if generation 0 is unlucky on these seeds in a category, every change looks better there,
whichever is chosen.
  * against the other changes: what the chosen change does on the category left out, minus the mean over all
    common changes there, and its place among them (0 = worst, 1 = best, ties shared). The level of
    generation 0 cancels.
  * a randomisation: the same mean when, for every category left out, a change is drawn at random from the
    eligible ones instead of chosen. The share of draws at or above the chosen mean is the chance that choosing
    on the other categories did no better than drawing.

  * a permutation: within every category the changes are shuffled among themselves (which change has which
    runs), which keeps what the changes of a category do and removes any agreement between categories; the
    whole procedure is repeated. The share of shuffles at or above the chosen mean is the chance of that mean
    if no change carried from one category to another. The randomisation above is too narrow for this
    question, because one change can be chosen for every category left out; the permutation is not.

Nothing here is a registered result: the categories are the pool (source and adoption roles), the seeds are
development seeds, and no rule was fixed before the numbers were seen.
"""
import argparse
import glob
import json
import os
import random
import statistics as st
from collections import defaultdict

NAMES = ("mean_held_out_smaller", "mean_held_out_acquired", "mean_held_out_gain", "mean_held_out_clipped",
         "mean_held_out_top3", "mean_held_out_against_the_others", "mean_held_out_place")
FLOOR, CAP = -0.03, 0.01
CPU_LIMIT = 1.15
MARGIN = 0.005


def clip(x):
    return max(FLOOR, min(CAP, x))


def load(directory):
    """category -> seed -> key -> row, with key = (field, json(value)); generation 0 has key ('', 'null')."""
    data = defaultdict(lambda: defaultdict(dict))
    machines = {}
    for path in sorted(glob.glob(os.path.join(directory, "**", "landscape_*.json"), recursive=True)):
        with open(path) as handle:
            doc = json.load(handle)
        if doc.get("smoke"):
            continue
        machines[os.path.basename(path)] = doc.get("machine")
        for row in doc["rows"]:
            key = (row["field"], json.dumps(row["value"], sort_keys=True))
            data[doc["category"]][row["seed"]][key] = row
    return data, machines


BASE = ("", "null")


def table(data, seeds_of):
    """per category: key -> (d_acq, d_gain, cpu of the change, cpu of generation 0), means over the given seeds."""
    out = {}
    for cat, by_seed in data.items():
        seeds = seeds_of[cat]
        keys = set.intersection(*(set(by_seed[s]) for s in set(seeds))) - {BASE}
        rows = {}
        for key in keys:
            da = st.fmean(by_seed[s][key]["acquired"] - by_seed[s][BASE]["acquired"] for s in seeds)
            dg = st.fmean(by_seed[s][key]["gain"] - by_seed[s][BASE]["gain"] for s in seeds)
            ck = st.fmean(by_seed[s][key]["cpu"] for s in seeds)
            cb = st.fmean(by_seed[s][BASE]["cpu"] for s in seeds)
            rows[key] = (da, dg, ck, cb)
        out[cat] = rows
    return out


def value(tab, key, cats):
    a = st.fmean(clip(tab[c][key][0]) for c in cats)
    g = st.fmean(clip(tab[c][key][1]) for c in cats)
    return min(a, g)


def cpu_ratio(tab, key, cats):
    return sum(tab[c][key][2] for c in cats) / max(sum(tab[c][key][3] for c in cats), 1e-12)


def loco(tab):
    cats = sorted(tab)
    common = set.intersection(*(set(tab[c]) for c in cats))
    per = {}
    for held in cats:
        rest = [c for c in cats if c != held]
        eligible = [k for k in common if cpu_ratio(tab, k, rest) <= CPU_LIMIT]
        ranked = sorted(eligible, key=lambda k: (-value(tab, k, rest), k))
        best = ranked[0]
        da, dg, ck, cb = tab[held][best]
        top3 = ranked[:3]
        others = sorted(min(tab[held][k][0], tab[held][k][1]) for k in common)
        mine = min(da, dg)
        place = (sum(1 for x in others if x < mine) + 0.5 * (sum(1 for x in others if x == mine) - 1)) / max(len(others) - 1, 1)
        per[held] = {
            "chosen": list(best), "value_on_the_rest": value(tab, best, rest),
            "cpu_ratio_on_the_rest": cpu_ratio(tab, best, rest),
            "held_out": {"acquired_change": da, "gain_change": dg, "smaller": min(da, dg), "cpu_ratio": ck / max(cb, 1e-12)},
            "held_out_top3_mean_smaller": st.fmean(min(tab[held][k][0], tab[held][k][1]) for k in top3),
            "eligible": len(eligible),
            "held_out_mean_of_all_changes": st.fmean(others),
            "held_out_against_the_others": mine - st.fmean(others),
            "held_out_place": place,
            "eligible_held_out_values": [min(tab[held][k][0], tab[held][k][1]) for k in sorted(eligible)],
        }
    smaller = [per[c]["held_out"]["smaller"] for c in cats]
    return {
        "per_category": per,
        "mean_held_out_smaller": st.fmean(smaller),
        "mean_held_out_acquired": st.fmean(per[c]["held_out"]["acquired_change"] for c in cats),
        "mean_held_out_gain": st.fmean(per[c]["held_out"]["gain_change"] for c in cats),
        "mean_held_out_clipped": st.fmean(clip(x) for x in smaller),
        "mean_held_out_top3": st.fmean(per[c]["held_out_top3_mean_smaller"] for c in cats),
        "mean_held_out_against_the_others": st.fmean(per[c]["held_out_against_the_others"] for c in cats),
        "mean_held_out_place": st.fmean(per[c]["held_out_place"] for c in cats),
        "categories_at_or_above_margin": sum(1 for x in smaller if x >= MARGIN),
        "categories_below_zero": sum(1 for x in smaller if x < 0),
        "common_changes": len(common),
    }


def all_categories(tab):
    """The change that is best on all categories at once (no category left out): the upper reference."""
    cats = sorted(tab)
    common = set.intersection(*(set(tab[c]) for c in cats))
    rows = []
    for k in common:
        rows.append({"change": list(k), "value": value(tab, k, cats), "cpu_ratio": cpu_ratio(tab, k, cats),
                     "mean_acquired_change": st.fmean(tab[c][k][0] for c in cats),
                     "mean_gain_change": st.fmean(tab[c][k][1] for c in cats),
                     "categories_positive": sum(1 for c in cats if min(tab[c][k][0], tab[c][k][1]) > 0),
                     "categories_negative": sum(1 for c in cats if min(tab[c][k][0], tab[c][k][1]) < 0)})
    rows.sort(key=lambda r: (-r["value"], r["change"]))
    return rows


def quantile(xs, q):
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--out", required=True)
    parser.add_argument("--boot", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261123)
    args = parser.parse_args()

    data, machines = load(args.directory)
    seeds_of = {c: sorted(data[c]) for c in data}
    tab = table(data, seeds_of)
    point = loco(tab)
    ranking = all_categories(tab)

    rng = random.Random(args.seed)
    boots = defaultdict(list)
    chosen_counts = defaultdict(int)
    for _ in range(args.boot):
        resampled = {c: [rng.choice(seeds_of[c]) for _ in seeds_of[c]] for c in seeds_of}
        result = loco(table(data, resampled))
        for name in NAMES:
            boots[name].append(result[name])
        for c, r in result["per_category"].items():
            chosen_counts[tuple(r["chosen"])] += 1
    cats = sorted(tab)
    draws, at_or_above = 20000, 0
    observed = point["mean_held_out_smaller"]
    null = []
    for _ in range(draws):
        t = st.fmean(rng.choice(point["per_category"][c]["eligible_held_out_values"]) for c in cats)
        null.append(t)
        at_or_above += t >= observed
    randomisation = {"draws": draws, "observed": observed, "mean_of_draws": st.fmean(null),
                     "q95_of_draws": quantile(null, 0.95), "share_at_or_above_observed": at_or_above / draws}
    common = sorted(set.intersection(*(set(tab[c]) for c in cats)))
    shuffles, perm = 2000, []
    for _ in range(shuffles):
        shuffled = {}
        for c in cats:
            order = common[:]
            rng.shuffle(order)
            shuffled[c] = {k: tab[c][j] for k, j in zip(common, order)}
        perm.append(loco(shuffled)["mean_held_out_smaller"])
    permutation = {"shuffles": shuffles, "observed": observed, "mean_of_shuffles": st.fmean(perm),
                   "q95_of_shuffles": quantile(perm, 0.95), "q99_of_shuffles": quantile(perm, 0.99),
                   "share_at_or_above_observed": sum(1 for t in perm if t >= observed) / shuffles}
    for c in cats:
        del point["per_category"][c]["eligible_held_out_values"]
    intervals = {name: {"q05": quantile(v, 0.05), "q10": quantile(v, 0.10), "q50": quantile(v, 0.50),
                        "q90": quantile(v, 0.90), "q95": quantile(v, 0.95),
                        "share_at_or_below_zero": sum(1 for x in v if x <= 0) / len(v)}
                 for name, v in boots.items()}
    total = sum(chosen_counts.values())
    doc = {
        "what": "development: leave one category of the pool out, choose a single-field change of generation 0 on the "
                "rest by the continued process's statistic, read what it does on the category left out",
        "registered": False,
        "categories": {c: {"seeds": seeds_of[c], "changes": len(tab[c])} for c in sorted(tab)},
        "rules": {"floor": FLOOR, "cap": CAP, "cpu_limit": CPU_LIMIT, "margin": MARGIN},
        "leave_one_out": point,
        "bootstrap": {"draws": args.boot, "seed": args.seed, "intervals": intervals,
                      "chosen_share": sorted(([list(k), n / total] for k, n in chosen_counts.items()),
                                             key=lambda kv: -kv[1])[:12]},
        "randomisation": randomisation,
        "permutation": permutation,
        "all_categories_top": ranking[:15],
        "all_categories_bottom": ranking[-5:],
        "generation_0": {c: {"untrained": st.fmean(data[c][s][BASE]["untrained"] for s in seeds_of[c]),
                             "acquired": st.fmean(data[c][s][BASE]["acquired"] for s in seeds_of[c]),
                             "gain": st.fmean(data[c][s][BASE]["gain"] for s in seeds_of[c]),
                             "cpu": st.fmean(data[c][s][BASE]["cpu"] for s in seeds_of[c])} for c in sorted(tab)},
        "machines": machines,
    }
    with open(args.out, "w") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")

    print(f"categories {len(tab)}: " + ", ".join(f"{c}({len(seeds_of[c])})" for c in sorted(tab)))
    print(f"common changes {point['common_changes']}")
    for c, r in point["per_category"].items():
        h = r["held_out"]
        print(f"  left out {c:13s} chosen {r['chosen'][0]:22s} {r['chosen'][1]:>18s} value on rest {r['value_on_the_rest']:+.4f}"
              f" cpu x{r['cpu_ratio_on_the_rest']:.2f} | held out: acq {h['acquired_change']:+.4f} gain {h['gain_change']:+.4f}"
              f" cpu x{h['cpu_ratio']:.2f} | all changes there {r['held_out_mean_of_all_changes']:+.4f}, place {r['held_out_place']:.2f}")
    for name in NAMES:
        i = intervals[name]
        print(f"{name:26s} {point[name]:+.4f}   bootstrap q05 {i['q05']:+.4f} q50 {i['q50']:+.4f} q95 {i['q95']:+.4f}"
              f"   share <= 0: {i['share_at_or_below_zero']:.3f}")
    print(f"categories at or above the margin {MARGIN}: {point['categories_at_or_above_margin']}/{len(tab)};"
          f" below zero: {point['categories_below_zero']}/{len(tab)}")
    print(f"randomisation: chosen {randomisation['observed']:+.4f}; drawn at random: mean {randomisation['mean_of_draws']:+.4f},"
          f" q95 {randomisation['q95_of_draws']:+.4f}; share of draws at or above the chosen: {randomisation['share_at_or_above_observed']:.4f}")
    print(f"permutation: shuffled within categories: mean {permutation['mean_of_shuffles']:+.4f}, q95 {permutation['q95_of_shuffles']:+.4f},"
          f" q99 {permutation['q99_of_shuffles']:+.4f}; share of shuffles at or above the chosen: {permutation['share_at_or_above_observed']:.4f}")
    print("best on all categories at once:")
    for r in ranking[:8]:
        print(f"  {r['change'][0]:22s} {r['change'][1]:>18s} value {r['value']:+.4f} cpu x{r['cpu_ratio']:.2f}"
              f" acq {r['mean_acquired_change']:+.4f} gain {r['mean_gain_change']:+.4f}"
              f" +{r['categories_positive']}/-{r['categories_negative']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
