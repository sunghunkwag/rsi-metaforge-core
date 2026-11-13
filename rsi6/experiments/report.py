"""Every reported number, recomputed from the ledger.

    python -m rsi6.experiments.report [--ledger PATH] [--json OUT]

Prints, in this order: the registered predictions scored (misses first), the rounds (what each
improver found, what the gate decided, what the confirmation half measured), the comparison in
which only the improver differs, and the test on the target categories with its controls.
Nothing here is typed by hand: a table that cannot be computed from the ledger is not printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.learner import designs
from rsi6.learner import version as versions

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration.json")


def both_interval(acquired: dict, gain: dict, rng, draws: int = 5000, level: float = 0.95):
    """The smaller of the mean change in acquired and the mean change in gain (means over seeds
    within a category, then over categories), with an interval that resamples categories and,
    within each, seeds, and recomputes the statistic."""
    names = sorted(acquired)

    def statistic(pick):
        a = np.mean([np.mean(acquired[n][idx]) for n, idx in pick])
        g = np.mean([np.mean(gain[n][idx]) for n, idx in pick])
        return min(a, g)

    point = statistic([(n, np.arange(len(acquired[n]))) for n in names])
    values = []
    for _ in range(draws):
        chosen = [names[k] for k in rng.choice(len(names), size=len(names))]
        values.append(statistic([(n, rng.choice(len(acquired[n]), size=len(acquired[n]))) for n in chosen]))
    low, high = np.quantile(values, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(point), float(low), float(high)


def by_key(ledger) -> dict:
    return {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}


def blocked_interval(values: dict, rng, draws: int = 5000, level: float = 0.95):
    """``values``: category -> array over seeds. Mean over categories of the mean over seeds,
    with an interval that resamples categories and, within each, seeds."""
    names = sorted(values)
    point = float(np.mean([np.mean(values[n]) for n in names]))
    means = []
    for _ in range(draws):
        chosen = rng.choice(len(names), size=len(names))
        means.append(np.mean([np.mean(rng.choice(values[names[k]], size=len(values[names[k]]))) for k in chosen]))
    low, high = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return point, float(low), float(high)


def changes_by_function(changes: dict) -> dict:
    out = {}
    for name, change in (changes or {}).items():
        out.setdefault(change["function"], []).append(f"{name}: {change['from']} -> {change['to']}")
    return out


def rounds_section(ledger) -> dict:
    out = {"rounds": []}
    for done in ledger.select(type="round_done"):
        g = done["round"]
        entry = {"round": g, "searches": {}, "gates": {}, "confirmations": {}, "adopted": {}}
        for record in ledger.select(type="search", round=g):
            entry["searches"][record["name"]] = {
                "improver": record["improver"], "evaluated": record["evaluated"], "improving": record["improving"],
                "best_cost": record["best_cost"], "cpu_used": round(record["cpu_used"], 1), "cpu_limit": record["cpu_limit"],
                "nominee": record["nominee"], "changes": changes_by_function(record["nominee_changes"]),
                "brier": record["brier"]}
        for record in ledger.select(type="gate", round=g):
            entry["gates"][record["name"]] = {k: record[k] for k in ("adopted", "conditions", "mean_min", "mean_gain_change",
                                                                    "mean_acquired_change", "gain_lower_bound", "cpu_ratio", "per_env")}
        for record in ledger.select(type="confirm", round=g):
            entry["confirmations"][record["name"]] = {k: record[k] for k in ("mean_min", "mean_gain_change", "mean_acquired_change", "runs")}
        for record in ledger.select(type="adopt", round=g):
            entry["adopted"][record["lineage"]] = {"digest": record["digest"], "changes": changes_by_function(record["changes"])}
        out["rounds"].append(entry)
    return out


def search_section(ledger) -> dict:
    """Two diagnostics of every search, from its runs in the ledger.

    Reliability: every candidate was measured with two seeds; the improvement over the starting
    version is computed from each seed alone, and the two are correlated over the candidates. A
    low value means the search ranked noise.

    Transfer: what the search measured for its nominee on the source pool, beside what the gate
    and the confirmation measured for the same version on categories the search never saw."""
    runs = [r for r in ledger.records if r.get("type") == "run"]
    out = {}
    for record in ledger.select(type="search"):
        tag, envs, seeds = record["tag"], record["envs"], record["seeds"]
        if any(other["tag"] != tag and other["nominee"] == record["nominee"] and other["start"] == record["start"]
               and other["round"] == record["round"] and other["tag"] in out for other in ledger.select(type="search")):
            continue                                  # the same search under another name (lineages that had not diverged)
        table = {}
        for r in runs:
            if r["budget"] == ledger.select(type="registration")[0]["registration"]["budgets"]["search"] and r["env"] in envs \
                    and r["seed"] in seeds:
                table.setdefault(r["version"], {})[(r["env"], r["seed"])] = r
        candidates = []
        for r in runs:
            if r["purpose"] == tag and r["version"] != record["start"] and r["version"] not in candidates:
                candidates.append(r["version"])
        base = table.get(record["start"], {})

        def improvement(digest, use):
            a = np.mean([table[digest][(e, s)]["acquired"] - base[(e, s)]["acquired"] for e in envs for s in use])
            g = np.mean([table[digest][(e, s)]["gain"] - base[(e, s)]["gain"] for e in envs for s in use])
            return float(min(a, g))

        complete = [d for d in candidates if all((e, s) in table[d] and (e, s) in base for e in envs for s in seeds)]
        entry = {"candidates": len(complete)}
        if len(complete) > 2 and len(seeds) == 2:
            first = np.array([improvement(d, seeds[:1]) for d in complete])
            second = np.array([improvement(d, seeds[1:]) for d in complete])
            both = np.array([improvement(d, seeds) for d in complete])
            entry.update({"correlation_between_seeds": float(np.corrcoef(first, second)[0, 1]),
                          "sd_between_candidates": float(np.std(both)), "sd_of_seed_difference": float(np.std(first - second)),
                          "share_of_candidates_measured_better": float(np.mean(both > 0))})
        if len(complete) > 2:
            # does a modification that helps acquisition in one category help in the others?
            change = np.array([[np.mean([table[d][(e, s)]["acquired"] - base[(e, s)]["acquired"] for s in seeds]) for e in envs]
                               for d in complete])
            moved = [j for j in range(len(envs)) if change[:, j].std() > 1e-9]
            between = np.corrcoef(change[:, moved].T)[np.triu_indices(len(moved), 1)] if len(moved) > 1 else np.array([])
            better, worse = (change > 0.005).sum(axis=1), (change < -0.005).sum(axis=1)
            entry["per_category"] = {e: {"mean_change": float(change[:, j].mean()), "share_better": float(np.mean(change[:, j] > 0.005)),
                                         "share_worse": float(np.mean(change[:, j] < -0.005))} for j, e in enumerate(envs)}
            entry["mean_correlation_between_categories"] = float(between.mean()) if len(between) else None
            entry["candidates_by_categories_improved"] = {int(k): int((better == k).sum()) for k in range(len(envs) + 1)}
            entry["candidates_improving_two_or_more_and_harming_none"] = int(((better >= 2) & (worse == 0)).sum())
        entry["nominee_on_source_pool"] = None if record["best_cost"] is None else -record["best_cost"]
        gate = ledger.select(type="gate", tag=tag.replace("search", "gate"))
        confirm = ledger.select(type="confirm", tag=tag.replace("search", "confirm"))
        entry["nominee_on_adoption_set"] = gate[-1]["mean_min"] if gate else None
        entry["nominee_on_confirmation_half"] = confirm[-1]["mean_min"] if confirm else None
        out[tag] = entry
    return out


def generation0_section(ledger) -> dict:
    """What generation 0 of each design did on every category it was run on, over all its recorded
    runs outside the target test: scores on fresh instances, how often its own check accepted what
    it had learned, and how many rounds of learning (or tests) fitted in the budget."""
    out = {}
    for design in ("a", "b"):
        digest = designs.digest(designs.default(design))
        rows = [r for r in ledger.records if r.get("type") == "run" and r["version"] == digest
                and not r["purpose"].startswith(("target", "memory")) and r.get("memory_in", 0) == 0]
        table = {}
        for env in sorted({r["env"] for r in rows}):
            sel = [r for r in rows if r["env"] == env]
            table[env] = {"runs": len(sel), "untrained": float(np.mean([r["untrained"] for r in sel])),
                          "acquired": float(np.mean([r["acquired"] for r in sel])), "gain": float(np.mean([r["gain"] for r in sel])),
                          "threshold": float(np.mean([r["threshold"] for r in sel])),
                          "share_of_runs_that_kept_what_was_learned": float(np.mean([bool(r["report"].get("learned")) for r in sel])),
                          "rounds_of_learning": float(np.mean([r["report"].get("iterations", 0) for r in sel])),
                          "cpu_per_run": float(np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in sel]))}
        if table:
            out[design] = table
    return out


def targets_section(ledger, reg) -> dict | None:
    done = ledger.select(type="target_done")
    if not done:
        return None
    done, runs = done[-1], by_key(ledger)
    arms = {arm: [runs[k] for k in keys] for arm, keys in done["arms"].items()}
    rng = np.random.default_rng(0)
    table = {}
    for arm, records in arms.items():
        envs = sorted({r["env"] for r in records})
        table[arm] = {"per_env": {}, "cpu_per_run": float(np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in records]))}
        for env in envs:
            rows = [r for r in records if r["env"] == env]
            table[arm]["per_env"][env] = {
                "untrained": float(np.mean([r["untrained"] for r in rows])), "acquired": float(np.mean([r["acquired"] for r in rows])),
                "gain": float(np.mean([r["gain"] for r in rows])), "train_acquired": float(np.mean([r["train_acquired"] for r in rows])),
                "threshold": rows[0]["threshold"],
                "reached": bool(np.mean([r["acquired"] for r in rows]) >= rows[0]["threshold"] > np.mean([r["untrained"] for r in rows]))}
        for field in ("untrained", "acquired", "gain"):
            table[arm][field] = float(np.mean([v[field] for v in table[arm]["per_env"].values()]))
        table[arm]["categories_reached"] = int(sum(v["reached"] for v in table[arm]["per_env"].values()))
    comparisons = {}
    base = arms["frozen"]

    def compare(name, other, reference=base):
        acquired, gain = {}, {}
        for env in sorted({r["env"] for r in reference}):
            b = sorted((r for r in reference if r["env"] == env), key=lambda r: r["seed"])
            o = sorted((r for r in other if r["env"] == env), key=lambda r: r["seed"])
            acquired[env] = np.array([y["acquired"] - x["acquired"] for x, y in zip(b, o)])
            gain[env] = np.array([y["gain"] - x["gain"] for x, y in zip(b, o)])
        comparisons[name] = {"min_change": both_interval(acquired, gain, rng), "acquired_change": blocked_interval(acquired, rng),
                             "gain_change": blocked_interval(gain, rng)}

    for arm in arms:                                   # every arm against generation 0 of its own design
        if arm.startswith("b:"):
            if arm != "b:frozen":
                compare(f"{arm} minus b:frozen", arms[arm], arms["b:frozen"])
        elif arm not in ("frozen", "compute@b", "c:frozen", "c:skills"):       # the last two are the arms frozen and skills
            compare(f"{arm} minus frozen", arms[arm])
    primary = done["primary_arm"]
    for arm in ("fixed", "random", "skills", "compute", "search"):
        if arm in arms and primary in arms and primary != "frozen":
            compare(f"{primary} minus {arm}", arms[primary], arms[arm])
    primary_b = done.get("primary_arm_b")
    if primary_b:
        for arm in ("b:fixed", "b:random", "b:skills", "b:compute", "b:search"):
            if arm in arms and primary_b != "b:frozen":
                compare(f"{primary_b} minus {arm}", arms[primary_b], arms[arm])
        compare("b:frozen minus frozen", arms["b:frozen"])                     # the two designs at equal counted units
        if "compute@b" in arms:
            compare("b:frozen minus compute@b", arms["b:frozen"], arms["compute@b"])     # and at equal measured CPU
            if primary_b != "b:frozen":
                compare(f"{primary_b} minus compute@b", arms[primary_b], arms["compute@b"])
    primary_c = done.get("primary_arm_c")
    if primary_c and primary_c != "c:frozen":
        for arm in ("skills", "c:memory", "c:compute", "c:search"):
            if arm in arms:
                compare(f"{primary_c} minus {arm}", arms[primary_c], arms[arm])
    gen0 = {env: np.array([r["gain"] for r in base if r["env"] == env]) for env in sorted({r["env"] for r in base})}
    matched = {r["arm"]: {"share_per_run": r["share_per_run"], "reached": int(sum(r["reached"])), "of": len(r["reached"])}
               for r in ledger.select(type="matched")}
    out = {"arms": table, "comparisons": comparisons, "primary_arm": primary, "generation0_gain": blocked_interval(gen0, rng),
           "matched": matched, "targets": done["targets"], "seeds": done["seeds"], "primary_arm_b": primary_b,
           "primary_arm_c": primary_c}
    if primary_b:
        base_b = arms["b:frozen"]
        out["generation0_gain_b"] = blocked_interval({env: np.array([r["gain"] for r in base_b if r["env"] == env])
                                                      for env in sorted({r["env"] for r in base_b})}, rng)
    return out


def process_c_section(ledger, targets) -> dict | None:
    """Process c (amendment 3) from its records: what every technique named in every generation,
    what the gate on the categories set aside decided, the adoptions, the external gate on the
    reserves, the recursion check (amendment 4), and the three parts of the registered success
    condition."""
    registered = ledger.select(type="registration_c")
    if not registered:
        return None
    reg = registered[-1]["registration"]
    out = {"generations": [], "planned": reg["generations_planned"]}
    for done in ledger.select(type="c_generation_done"):
        g = done["generation"]
        screen = ledger.select(type="c_screen", generation=g)
        entry = {"generation": g, "searched": done["searched"], "set_aside": done["set_aside"], "adopted_by": done["adopted_by"],
                 "version": done["version"], "techniques": {},
                 "single_field_changes_measured": screen[-1]["candidates"] if screen else None,
                 "positive_on_the_light_categories": screen[-1]["positive_on_light"] if screen else None}
        for nominee in ledger.select(type="c_nominee", generation=g):
            name = nominee["technique"]
            row = {"nominee": nominee["nominee"], "changes": changes_by_function(nominee["changes"])}
            gate = ledger.select(type="gate", tag=f"gate:c{g}:{name}")
            check = ledger.select(type="confirm", tag=f"confirm:c{g}:{name}")
            if gate:
                row["gate"] = {k: gate[-1][k] for k in ("adopted", "mean_min", "gain_lower_bound", "cpu_ratio", "per_env")}
            if check:
                row["confirmation"] = check[-1]["mean_min"]
            entry["techniques"][name] = row
        entry["distinct_nominees"] = len({r["nominee"] for r in entry["techniques"].values() if r["nominee"]})
        out["generations"].append(entry)
    adoptions = ledger.select(type="adopt", process="c")
    out["adoptions"] = [{"generation": a["round"], "technique": a["technique"], "digest": a["digest"],
                         "changes": changes_by_function(a["changes"])} for a in adoptions]
    out["nominees_tested"] = int(sum(e["distinct_nominees"] for e in out["generations"]))
    mine = [r for r in ledger.records if r.get("type") == "run" and r.get("purpose", "").startswith(("search:c", "gate:c", "confirm:c"))
            and not r["purpose"].startswith(("gate:c:external", "confirm:c:external"))]
    out["runs"], out["cpu_seconds"] = len(mine), float(sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in mine))
    frozen = ledger.select(type="freeze", process="c")
    out["finished"] = bool(frozen)
    if frozen:
        out["final"] = {"digest": frozen[-1]["digest"], "changes_from_generation_0": changes_by_function(frozen[-1]["changes_from_generation_0"])}
    external = ledger.select(type="external_gate", process="c")
    if external:
        gate = ledger.select(type="gate", tag="gate:c:external")
        check = ledger.select(type="confirm", tag="confirm:c:external")
        out["external_gate"] = {"run": external[-1]["run"], "passed": external[-1]["passed"], "why": external[-1].get("why"),
                                "gate": {k: gate[-1][k] for k in ("adopted", "conditions", "mean_min", "mean_gain_change",
                                                                 "mean_acquired_change", "gain_lower_bound", "cpu_ratio", "per_env")} if gate else None,
                                "confirmation": {k: check[-1][k] for k in ("mean_min", "mean_gain_change", "mean_acquired_change", "runs")} if check else None}
    recursion = ledger.select(type="recursion_done")
    if recursion:
        out["recursion_check"] = {k: recursion[-1][k] for k in ("generations", "compared", "better_than_gen0", "better_than_random")}
    # ---- the registered success condition, part by part (None: not decided yet)
    parts = {"two_adopting_generations": (len(adoptions) >= 2) if frozen else (True if len(adoptions) >= 2 else None),
             "external_gate_passed": external[-1]["passed"] if external else None, "targets": None}
    if targets and targets.get("primary_arm_c"):
        c = targets["comparisons"]
        primary = c.get("c:self minus frozen")
        if primary is None:
            parts["targets"] = False
        else:
            point, low, _ = primary["min_change"]
            behind = c["c:self minus c:compute"]["min_change"][0] < 0.0 if "c:self minus c:compute" in c else None
            parts["targets"] = None if behind is None else bool(point >= 0.01 and low > 0.0 and not behind)
            out["targets"] = {"min_change": primary["min_change"], "against_compute": c.get("c:self minus c:compute", {}).get("min_change")}
    out["success_parts"] = parts
    out["success"] = False if any(v is False for v in parts.values()) else (True if all(parts.values()) else None)
    return out


def score_predictions_c(section, ledger) -> list:
    """Predictions C1 to C4 (registration_c.json) and C5, C6 (amendment_4.json)."""
    out = []
    texts = {p["id"]: p for p in ledger.select(type="registration_c")[-1]["registration"]["predictions"]}
    path = os.path.join(os.path.dirname(HERE), "registry", "amendment_4.json")
    if os.path.exists(path):
        texts.update({p["id"]: p for p in json.load(open(path))["predictions"]})

    def add(pid, outcome, detail):
        if pid in texts:
            out.append({"id": pid, "text": texts[pid]["text"], "criterion": texts[pid]["criterion"], "holds": outcome, "detail": detail})

    count = len(section["adoptions"])
    add("C1", True if count >= 1 else (False if section["finished"] else None), count)
    if section["finished"]:
        single = sum(1 for a in section["adoptions"] if a["technique"] in ("single", "remeasure", "combine"))
        add("C2", bool(single > count - single), {"single-field techniques": single, "climb": count - single})
    else:
        add("C2", None, "the process has not ended")
    external = section.get("external_gate")
    add("C3", None if external is None else bool(not external["passed"]), external and (external["gate"] or external["why"]))
    add("C4", None if section["success"] is None else bool(not section["success"]), section["success_parts"])
    recursion = section.get("recursion_check")
    if recursion is None or not recursion["compared"]:
        add("C5", None, "no generation compared" if recursion else "the recursion check has not been run")
    else:
        add("C5", bool(recursion["better_than_gen0"] <= recursion["compared"] / 2),
            {"compared": recursion["compared"], "climb better than generation 0 as improver": recursion["better_than_gen0"]})
    listed = os.path.join(os.path.dirname(HERE), "registry", "targets.json")
    add("C6", bool(len(json.load(open(listed))["admitted"]) == 4) if os.path.exists(listed) else None,
        json.load(open(listed))["admitted"] if os.path.exists(listed) else "the list of admitted targets is not written yet")
    return out


def score_predictions(reg, rounds, targets, ledger) -> list:
    out = []
    by_round = {r["round"]: r for r in rounds["rounds"]}

    def add(pid, outcome, detail):
        text = next(p for p in reg["predictions"] if p["id"] == pid)
        out.append({"id": pid, "text": text["text"], "criterion": text["criterion"], "holds": outcome, "detail": detail})

    if 1 in by_round:
        s = by_round[1]["searches"].get("self")
        add("R1", None if s is None else bool(s["best_cost"] is not None and s["best_cost"] <= -0.005), s and s["best_cost"])
        g = by_round[1]["gates"].get("self")
        add("R2", (s is not None and s["nominee"] is None) or (g is not None and not g["adopted"]), g and g["mean_min"])
    if sum(1 for g in by_round if isinstance(g, int)) >= reg["rounds_planned"]:
        count = len(ledger.select(type="adopt", lineage="self"))
        add("R3", count <= 1, count)
        seen = []
        for g, entry in by_round.items():
            if not isinstance(g, int):               # rounds of the continued process have their own predictions
                continue
            a, b = entry["searches"].get("self"), entry["searches"].get("random")
            if a and b and a["best_cost"] is not None and b["best_cost"] is not None:
                seen.append(b["best_cost"] <= a["best_cost"])
        add("R4", any(seen) if seen else None, seen)
    if targets:
        primary = targets["comparisons"].get(f"{targets['primary_arm']} minus frozen")
        if primary:
            point, low, high = primary["min_change"]
            add("R5", bool(point < 0.01 or low <= 0.0), [point, low, high])
        else:
            add("R5", True, "no version was adopted by the self lineage, so there is nothing to compare")
        if "skills minus frozen" in targets["comparisons"]:
            point = targets["comparisons"]["skills minus frozen"]["acquired_change"][0]
            add("R6", bool(point < 0.005), point)
        reached = targets["arms"]["frozen"]["categories_reached"]
        add("R7", bool(1 <= reached <= len(targets["targets"]) - 1), reached)
        point, low, high = targets["generation0_gain"]
        add("R8", bool(point > 0 and low > 0), [point, low, high])
    return out


def score_predictions_b(reg_b, rounds, searches, targets) -> list:
    out = []
    by_round = {r["round"]: r for r in rounds["rounds"]}

    def add(pid, outcome, detail):
        text = next(p for p in reg_b["predictions"] if p["id"] == pid)
        out.append({"id": pid, "text": text["text"], "criterion": text["criterion"], "holds": outcome, "detail": detail})

    first = by_round.get("b1")
    if first:
        s = first["searches"].get("self")
        g = first["gates"].get("self")
        add("B1", None if s is None else bool(s["best_cost"] is not None and s["best_cost"] < 0), s and s["best_cost"])
        add("B2", (s is not None and s["nominee"] is None) or (g is not None and not g["adopted"]), g and g["mean_min"])
        r = searches.get("search:b1:self", {}).get("correlation_between_seeds")
        add("B3", None if r is None else bool(r >= 0.3), r)
    if targets and targets.get("primary_arm_b"):
        c = targets["comparisons"]
        add("B4", bool(c["b:frozen minus frozen"]["acquired_change"][0] > 0), c["b:frozen minus frozen"]["acquired_change"])
        if "b:frozen minus compute@b" in c:
            point, low, high = c["b:frozen minus compute@b"]["acquired_change"]
            add("B5", bool(low <= 0.0), [point, low, high])
        if "b:skills minus b:frozen" in c:
            add("B6", bool(c["b:skills minus b:frozen"]["acquired_change"][0] < 0.005), c["b:skills minus b:frozen"]["acquired_change"][0])
        primary = c.get(f"{targets['primary_arm_b']} minus b:frozen")
        if primary:
            point, low, high = primary["min_change"]
            add("B7", bool(point < 0.01 or low <= 0.0), [point, low, high])
        else:
            add("B7", True, "no version was adopted by the b:self lineage, so there is nothing to compare")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    reg = json.load(open(REGISTRATION))
    rounds = rounds_section(ledger)
    targets = targets_section(ledger, reg)
    predictions = score_predictions(reg, rounds, targets, ledger)
    searches = search_section(ledger)
    registered_b = ledger.select(type="registration_b")
    if registered_b:
        predictions += score_predictions_b(registered_b[-1]["registration"], rounds, searches, targets)
    process_c = process_c_section(ledger, targets)
    if process_c:
        predictions += score_predictions_c(process_c, ledger)
    runs = [r for r in ledger.records if r.get("type") == "run"]
    report = {"ledger_head": ledger.head(), "records": len(ledger.records), "runs": len(runs),
              "cpu_seconds": round(float(sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in runs)), 1),
              "predictions": predictions, **rounds, "searches": searches, "generation0": generation0_section(ledger),
              "process_c": process_c, "targets": targets}
    if args.json:
        json.dump(report, open(args.json, "w"), indent=1)
    print(f"ledger: {len(ledger.records)} records, {len(runs)} runs, {report['cpu_seconds']} CPU-seconds, head {ledger.head()[:16]}")
    print("\nPREDICTIONS (misses first)")
    for p in sorted(predictions, key=lambda p: (p["holds"] is not False, p["id"])):
        mark = {True: "held", False: "MISSED", None: "not scored"}[p["holds"]]
        print(f"  {p['id']} {mark:10s} {p['text']} | {p['criterion']} | measured: {p['detail']}")
    for entry in rounds["rounds"]:
        print(f"\nROUND {entry['round']}")
        for name, s in entry["searches"].items():
            print(f"  search {name:12s} evaluated {s['evaluated']:3d} improving {s['improving']:3d} best {s['best_cost']} cpu {s['cpu_used']} "
                  f"changes {s['changes'] if s['changes'] else None}")
        for name, g in entry["gates"].items():
            print(f"  gate   {name:12s} adopted {g['adopted']} | min-change {g['mean_min']:+.4f} gain {g['mean_gain_change']:+.4f} "
                  f"acquired {g['mean_acquired_change']:+.4f} lower bound {g['gain_lower_bound']:+.4f} cpu x{g['cpu_ratio']:.2f} {g['conditions']}")
            for env, v in g["per_env"].items():
                print(f"           {env:12s} gain {v['gain_change']:+.4f} acquired {v['acquired_change']:+.4f}")
        for name, c in entry["confirmations"].items():
            print(f"  confirm {name:11s} min-change {c['mean_min']:+.4f} gain {c['mean_gain_change']:+.4f} acquired {c['mean_acquired_change']:+.4f} ({c['runs']} runs)")
        for name, a in entry["adopted"].items():
            print(f"  ADOPTED by {name}: {a['changes']}")
    if process_c:
        number = lambda x: "none" if x is None else f"{x:+.4f}"
        print(f"\nPROCESS C: {len(process_c['generations'])} of {process_c['planned']} generations recorded, {len(process_c['adoptions'])} "
              f"adoptions (provisional), {process_c['nominees_tested']} distinct nominees tested, {process_c['runs']} runs, "
              f"{process_c['cpu_seconds']:.0f} CPU-seconds")
        for e in process_c["generations"]:
            print(f"  generation {e['generation']}: searched on {e['searched']}; set aside {e['set_aside']}; "
                  f"{e['single_field_changes_measured']} single-field changes measured, {e['positive_on_the_light_categories']} positive; "
                  f"adopted by {e['adopted_by']}; version {e['version'][:12]}")
            for name, row in e["techniques"].items():
                if row["nominee"] is None:
                    print(f"      {name:10s} no nominee")
                    continue
                g = row.get("gate")
                print(f"      {name:10s} {row['nominee'][:12]} gate {number(g and g['mean_min'])} lower bound {number(g and g['gain_lower_bound'])} "
                      f"cpu x{g['cpu_ratio']:.2f} passes {g['adopted']} | confirmation {number(row.get('confirmation'))} | {row['changes']}"
                      if g else f"      {name:10s} {row['nominee'][:12]} not gated yet | {row['changes']}")
                if g:
                    print("                 per category (acquired):", "; ".join(f"{env} {v['acquired_change']:+.4f}" for env, v in g["per_env"].items()))
        if process_c.get("final"):
            print(f"  frozen at {process_c['final']['digest'][:12]}: {process_c['final']['changes_from_generation_0']}")
        external = process_c.get("external_gate")
        if external:
            if not external["run"]:
                print(f"  external gate: not run ({external['why']})")
            else:
                g, c = external["gate"], external["confirmation"]
                print(f"  external gate on the reserves: passed {external['passed']} | gate min-change {g['mean_min']:+.4f} gain {g['mean_gain_change']:+.4f} "
                      f"acquired {g['mean_acquired_change']:+.4f} lower bound {g['gain_lower_bound']:+.4f} cpu x{g['cpu_ratio']:.2f} {g['conditions']} "
                      f"| confirmation {c['mean_min']:+.4f} ({c['runs']} runs)")
                for env, v in g["per_env"].items():
                    print(f"           {env:12s} gain {v['gain_change']:+.4f} acquired {v['acquired_change']:+.4f}")
        recursion = process_c.get("recursion_check")
        if recursion:
            print(f"  recursion check: {recursion['compared']} generations compared; the climb's nominee better at the gate than that of "
                  f"generation 0 as improver in {recursion['better_than_gen0']}, than the random proposer's in {recursion['better_than_random']}")
            for row in recursion["generations"]:
                print(f"      generation {row['generation']}: " + "; ".join(
                    f"{who} found {number(row[who]['found'])} gate {row[who]['gate']:+.4f} confirmation {row[who]['confirmation']:+.4f}"
                    for who in ("self", "gen0", "random")))
        print(f"  success condition, part by part: {process_c['success_parts']} -> {process_c['success']}")
    for design, table in report["generation0"].items():
        print(f"\nGENERATION 0 of design {design}: every recorded run outside the target test (fresh instances)")
        for env, e in table.items():
            print(f"  {env:13s} runs {e['runs']:3d} untrained {e['untrained']:.4f} acquired {e['acquired']:.4f} gain {e['gain']:+.4f} "
                  f"threshold {e['threshold']:.3f} | kept what was learned in {e['share_of_runs_that_kept_what_was_learned']:.2f} of runs | "
                  f"rounds of learning {e['rounds_of_learning']:.1f} | cpu/run {e['cpu_per_run']:.1f}")
    print("\nSEARCHES: reliability between the two seeds, and what the nominee did where the search never looked")
    for tag, e in searches.items():
        number = lambda x: "none" if x is None else f"{x:+.4f}"
        print(f"  {tag:16s} candidates {e['candidates']:3d} correlation between seeds {number(e.get('correlation_between_seeds'))} "
              f"measured better {number(e.get('share_of_candidates_measured_better'))} | nominee: source pool "
              f"{number(e['nominee_on_source_pool'])}, adoption set {number(e['nominee_on_adoption_set'])}, "
              f"confirmation half {number(e['nominee_on_confirmation_half'])}")
        if "per_category" in e:
            print("      change of the acquired score per category over the candidates (mean; share better by 0.005; share worse):",
                  "; ".join(f"{name} {v['mean_change']:+.4f} {v['share_better']:.2f} {v['share_worse']:.2f}" for name, v in e["per_category"].items()))
            print(f"      mean correlation between categories {number(e['mean_correlation_between_categories'])}; candidates by number of "
                  f"categories improved {e['candidates_by_categories_improved']}; improving two or more and harming none "
                  f"{e['candidates_improving_two_or_more_and_harming_none']}")
    if targets:
        print(f"\nTARGETS {targets['targets']}, seeds {targets['seeds']}; primary arm {targets['primary_arm']}; of the continued process "
              f"{targets.get('primary_arm_b')}; of process c {targets.get('primary_arm_c')}")
        for arm, t in targets["arms"].items():
            print(f"  {arm:10s} untrained {t['untrained']:.4f} acquired {t['acquired']:.4f} gain {t['gain']:+.4f} "
                  f"categories reached {t['categories_reached']} cpu/run {t['cpu_per_run']:.1f}")
            for env, v in t["per_env"].items():
                print(f"      {env:14s} untrained {v['untrained']:.4f} acquired {v['acquired']:.4f} gain {v['gain']:+.4f} "
                      f"(training instances {v['train_acquired']:.4f}) threshold {v['threshold']:.3f} reached {v['reached']}")
        for name, c in targets["comparisons"].items():
            print(f"  {name:28s} min-change {c['min_change'][0]:+.4f} [{c['min_change'][1]:+.4f}, {c['min_change'][2]:+.4f}] "
                  f"acquired {c['acquired_change'][0]:+.4f} [{c['acquired_change'][1]:+.4f}, {c['acquired_change'][2]:+.4f}] "
                  f"gain {c['gain_change'][0]:+.4f} [{c['gain_change'][1]:+.4f}, {c['gain_change'][2]:+.4f}]")
        print("  generation 0 gain on targets: %+.4f [%+.4f, %+.4f]" % tuple(targets["generation0_gain"]))
        if targets.get("generation0_gain_b"):
            print("  generation 0 of the second design, gain on targets: %+.4f [%+.4f, %+.4f]" % tuple(targets["generation0_gain_b"]))
        print("  compute matching:", targets["matched"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
