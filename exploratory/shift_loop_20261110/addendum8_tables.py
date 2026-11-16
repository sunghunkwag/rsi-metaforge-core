"""Tables of Addendum 8, recomputed from the stored report of ``confirm.py``.

Reads the JSON report only (no solver, no audit, no task file). Every comparison is recomputed
here from the rows' own lists of sound and verified solves with a second implementation of the
sign test, and compared with what the driver stored; a difference is printed as MISMATCH.

Usage: python addendum8_tables.py results/confirm.json

Attribution: Intelligence Research Project.
"""
from __future__ import annotations

import json
import sys
from math import comb

EXPECTED = {  # the registered expectations (PREDICTIONS.md, Addendum 8)
    "D1": ("PASS", "high"), "D2": ("PASS", "high"), "D3": ("PASS", "moderate"), "D4": ("PASS", "moderate"),
    "D5": ("PASS", "high"), "D6": ("PASS", "low"), "D7": ("PASS", "moderate"), "D8": ("PASS", "moderate"),
    "D9": ("PASS", "high"), "D10": ("PASS", "low"), "D11": ("PASS", "moderate"), "D12": ("PASS", "moderate"),
    "D13": ("FAIL", "moderate"), "D14": ("FAIL", "moderate")}
WORDING = {
    "D1": "Primary, list outputs: new at 10^5 has more sound solves than generation 0 at any budget",
    "D2": "The sign test of D1 gives p < 0.05",
    "D3": "The lead of D1 is at least 50 sound solves",
    "D4": "Ending 1: outside the routines of the earlier symbols, more with p < 0.05",
    "D5": "Ending 2: more sound solves than old at 10^5 with p < 0.05",
    "D6": "Old at 10^5 has more sound solves than generation 0 at any budget with p < 0.05",
    "D7": "Ending 4: where no dream computed the task or composed its pair, more with p < 0.05",
    "D8": "Ending 5: where not both stage instances are learning tasks, more with p < 0.05",
    "D9": "Ending 3: budget-bound new-only tasks outnumber budget-bound control-only tasks with p < 0.05",
    "D10": "On the list tasks with a routine no learning task has, new has more sound solves",
    "D11": "R1 on FRESH-4", "D12": "R2 on FRESH-4",
    "D13": "R3 on FRESH-4: the final vocabulary at 10^4 has more sound solves than generation 0 at any budget",
    "D14": "All four criteria on FRESH-4"}


def p_value(first_only: int, second_only: int) -> float:
    """Exact one-sided sign test: the chance of at least ``first_only`` heads in that many fair coins."""
    n = first_only + second_only
    return 1.0 if n == 0 else sum(comb(n, k) for k in range(first_only, n + 1)) / 2 ** n


def paired(first: set, second: set) -> dict:
    a, b = len(first - second), len(second - first)
    return {"trained": len(first), "control": len(second), "trained_only": a, "control_only": b,
            "p_one_sided": round(p_value(a, b), 5)}


def same(mine: dict, stored: dict) -> bool:
    return all(mine[k] == stored[k] for k in ("trained", "control", "trained_only", "control_only")) and \
        abs(mine["p_one_sided"] - stored["p_one_sided"]) <= 1e-5


def line(c: dict) -> str:
    return (f"{c['trained']} against {c['control']} ({c['trained_only']} against {c['control_only']}, "
            f"p = {c['p_one_sided']:.4g})")


def main(path: str) -> int:
    out = json.load(open(path))
    rows, fourth, mismatches = out["rows"], out["fresh4"], []
    kind = {f"fresh4/{name}": k for name, k in zip(fourth["names"], fourth["kinds"])}
    scope = {key for key, k in kind.items() if k == "list"}
    sound = lambda label: set(rows[label]["sound"])
    verified = lambda label: set(rows[label]["programs"])

    def check(name, mine, stored):
        if not same(mine, stored):
            mismatches.append(name)
            print(f"MISMATCH {name}: recomputed {mine} stored {stored}")

    print(f"FRESH-4 digest {fourth['digest'][:16]}, {len(kind)} tasks, {len(scope)} with a list output")
    print(f"loop: {out['accepted_symbols']} symbols, library digest {out['library_digest'][:16]}, "
          f"as in development: {out['loop_as_in_development']}; training ceilings {out['training_candidates']}")
    print(f"control budgets: {out['control_budgets']}; resumed: {out.get('resumed')}")

    # ---- the loop -----------------------------------------------------------------------------------
    loop = out["loop"]
    by_run = {t["run"]: t for t in loop["timeline"]}
    held = {entry["label"]: entry for entry in out["criteria"]["R1_held_out_B_by_cycle"]}
    print("\n| Cycle | Learning tasks the student does not solve | Teacher budget per such task | Taught | "
          "Trials | Symbols accepted | Student at 10^4 on learning (verified) | Held-out B at 10^4 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    first = by_run[1]
    zero = held.get("report0", {})
    print(f"| 0 | | | | | | {first['learn']} | {zero.get('sound')}/{zero.get('verified')} |")
    for cycle in loop["cycles"]:
        report = held.get(f"report{cycle['cycle']}", {})
        student = by_run.get(cycle["student_run"], {})
        accepted = cycle["accepted"] if isinstance(cycle["accepted"], int) else len(cycle["accepted"])
        taught = cycle["taught"] if isinstance(cycle["taught"], int) else len(cycle["taught"])
        trials = cycle["trials"] if isinstance(cycle["trials"], int) else len(cycle["trials"])
        print(f"| {cycle['cycle']} | {cycle['unsolved_before']} | {cycle['teacher_share']:,} | {taught} | {trials} | "
              f"{accepted} | {student.get('learn', '')} | "
              f"{str(report['sound']) + '/' + str(report['verified']) if report else 'no symbol accepted'} |")
    seconds = loop["driver_seconds"] if isinstance(loop["driver_seconds"], (int, float)) else sum(loop["driver_seconds"])
    print(f"training ceiling {loop['training_ceiling']:,}, spent {loop['training_spent']:,}; verdicts read on learning "
          f"tasks {loop['verdicts_read']:,}; seconds in compression and dreaming {seconds:.0f}")

    # ---- the evaluation table -------------------------------------------------------------------------
    def cell(label, keys=None):
        if label not in rows:
            return ""
        s, v = sound(label), verified(label)
        if keys is not None:
            s, v = s & keys, v & keys
        return f"{len(s)}/{len(v)}"

    budgets = out["control_budgets"]
    student, deploy = out["protocol"]["student"], out["protocol"]["deploy"]
    table = [("generation 0", student, "gen0@student"), ("new", student, "new@student"), ("old", student, "old@student"),
             ("generation 0", deploy, "gen0@deploy"), ("new", deploy, "new@deploy"), ("old", deploy, "old@deploy")]
    rungs = sorted({(b, r) for name in budgets for r, b in budgets[name].items()})
    print(f"\n| State | Budget per task | Held-out B ({out['set_sizes']['heldB']}) | FRESH-4 ({len(kind)}) | "
          f"FRESH-4, list outputs ({len(scope)}) |")
    print("| --- | --- | --- | --- | --- |")
    for state, budget, label in table:
        print(f"| {state} | {budget:,} | {cell(label + ':heldB')} | {cell(label + ':fresh4')} | "
              f"{cell(label + ':fresh4', scope)} |")
    for budget, rung in rungs:
        print(f"| generation 0 | {budget:,} ({rung}) | {cell(f'gen0@{rung}:heldB')} | {cell(f'gen0@{rung}:fresh4')} | "
              f"{cell(f'gen0@{rung}:fresh4', scope)} |")

    def union(name, measure):
        labels = [f"gen0@student:{name}", f"gen0@deploy:{name}"] + [f"gen0@{rung}:{name}" for rung in budgets[name]]
        return set().union(*(measure(label) for label in labels))

    any4, anyB = union("fresh4", sound), union("heldB", sound)
    print(f"| generation 0, everything solved at any budget above | | {len(anyB)} sound | {len(any4)} sound | "
          f"{len(any4 & scope)} sound |")
    for label in ("new@deploy:fresh3", "new@student:fresh3"):
        if label in rows:
            print(f"{label}: {cell(label)} of {out['set_sizes']['fresh3']} (a development set)")
    print("budgets spent, share of ceiling:", ", ".join(
        f"{label} {rows[label]['spent'] / rows[label]['ceiling']:.0%}" for label in rows))

    # ---- the primary comparison ----------------------------------------------------------------------
    new, old = sound("new@deploy:fresh4"), sound("old@deploy:fresh4")
    primary = paired(new & scope, any4 & scope)
    check("primary", primary, out["primary"])
    check("new_vs_old", paired(new & scope, old & scope), out["new_vs_old"])
    check("old_vs_any", paired(old & scope, any4 & scope), out["old_vs_any"])
    check("other_outputs", paired(new - scope, any4 - scope), out["other_outputs"])
    print(f"\nPRIMARY, list outputs, new at {deploy:,} against generation 0 at any budget: {line(primary)}")
    v_new, v_any = verified("new@deploy:fresh4") & scope, union("fresh4", verified) & scope
    print(f"  on verified counts: {line(paired(v_new, v_any))}")
    print(f"  other outputs ({len(kind) - len(scope)} tasks): {line(out['other_outputs'])}")
    print(f"  new against old at {deploy:,}: {line(out['new_vs_old'])}")
    print(f"  old against generation 0 at any budget: {line(out['old_vs_any'])}")
    for name, stored in out["comparisons"].items():
        if not name.startswith(("heldB", "fresh4")):
            continue
        part, rest = name.split(": ", 1)
        arm, control = rest.split(" vs ")
        first_set = sound(f"{arm}:{part}")
        if control == "gen0 up to C2old":
            labels = [f"gen0@student:{part}", f"gen0@deploy:{part}"] + [
                f"gen0@{rung}:{part}" for rung, b in budgets[part].items() if b <= budgets[part]["C2old"]]
            second_set = set().union(*(sound(label) for label in labels))
        elif control == "gen0@any":
            second_set = union(part, sound)
        elif control == "gen0@equal":
            second_set = sound(f"gen0@deploy:{part}")
        else:
            second_set = sound(f"{control}:{part}")
        check(name, paired(first_set, second_set), stored)
    print("\nComparisons on all tasks of a set (sound):")
    for name, stored in out["comparisons"].items():
        print(f"  {name}: {line(stored)}")

    # ---- endings and strata ----------------------------------------------------------------------------
    flags = out["flags"]
    print("\n| Ending | Tasks | New against the other arm | Grade |")
    print("| --- | --- | --- | --- |")
    for title, key in (("1 breadth: neither slice-k-n nor a divisibility routine", "outside_earlier"),
                       ("2 against the old vocabulary at the same deployment budget", "over_old"),
                       ("3 budget: tasks where the other arm found no public match", "budget_bound"),
                       ("4 dreams: no dream computes the task or composes its pair", "undreamt"),
                       ("5 learning tasks: not both stage instances are learning tasks", "beyond_learning_tasks")):
        grade = flags[key]
        print(f"| {title} | {grade['tasks']} | {line(grade)} | {grade['reading']} |")
    print("\n| Stratum (list outputs) | Tasks | New against generation 0 at any budget | Grade | New against old | Grade |")
    print("| --- | --- | --- | --- | --- | --- |")
    for name, grade in out["strata"].items():
        other = out["strata_new_vs_old"][name]
        print(f"| {name} | {grade['tasks']} | {line(grade)} | {grade['reading']} | {line(other)} | {other['reading']} |")
    # ending 1 once more, from the stored stage names alone
    earlier = {f"fresh4/{name}" for name, stages, modulo in zip(fourth["names"], fourth["stages"], fourth["modulo"])
               if modulo or "slice-k-n" in stages}
    check("ending 1 from the stage names", paired(new & scope - earlier, any4 & scope - earlier), flags["outside_earlier"])
    print("more than re-pairing of trained instances:", out["more_than_re_pairing_of_trained_instances"])
    print("kinds:", {k: v for k, v in out["kinds"]["fresh4, list outputs: new@deploy vs gen0@any"].items() if k != "tasks"})
    print("dreamt:", out["dreamt"])
    print("provenance:", out["provenance"])
    print("routines removed until the lead is not separated:", out["lead_carried_by"])
    print("leave one routine out: largest p", out["leave_one_routine_out"]["largest_p"], "without",
          out["leave_one_routine_out"]["routine"])
    print("clusters:", out["clusters"])
    print("standardised to the mix of FRESH-2, per 100 tasks:", out["lead_standardised_to_the_mix_of_fresh2_per_100_tasks"])
    print("sound and right on the whole pool:", line(out["fresh4_sound_and_on_whole_pool"]))
    print("thin evidence (programs not counted as sound for fewer than 20 fresh inputs):", out["thin_evidence"])
    print("new-only tasks by learned symbol:", out["new_only_by_symbol"], "| with a symbol built on a symbol:",
          out["new_only_with_a_symbol_built_on_a_symbol"], "| with a symbol no learning program uses:",
          out["new_only_with_a_symbol_no_learning_program_uses"])
    print("\n| Routine | List tasks | New | Old | Generation 0, any budget |")
    print("| --- | --- | --- | --- | --- |")
    for routine, entry in out["by_routine"].items():
        print(f"| `{routine}` | {entry['tasks']} | {entry['new']} | {entry['old']} | {entry['gen0_any']} |")

    # ---- the four criteria ----------------------------------------------------------------------------
    fourth_criteria, recursion = out["criteria_on_fresh4"], out["recursion"]
    print("\ncriteria on FRESH-4 (all tasks, sound, at the student budget):")
    print("  R1 by generation:", fourth_criteria["R1_sound_by_generation"], "->", fourth_criteria["R1"])
    print("  R2:", fourth_criteria["R2_detail"], "->", fourth_criteria["R2"])
    r3 = fourth_criteria["R3_new_student_vs_gen0_any"]
    check("R3 on FRESH-4", paired(sound("new@student:fresh4"), any4), r3)
    print("  R3:", line(r3), "->", fourth_criteria["R3"], "| separated:", fourth_criteria["R3_separated"])
    print("  R4:", fourth_criteria["R4"], "| all four:", fourth_criteria["all_four"])
    print("  recursive symbols:", recursion["recursive_symbols"], "| with those defined through them:",
          recursion["with_the_symbols_defined_through_them"])
    for cycle, found in recursion["discovery_by_cycle"].items():
        print(f"  discoveries in cycle {cycle} (budget {found['budget']:,}, {found['tasks']} tasks): "
              f"{len(found['teacher_sound_with_a_symbol_where_generation_0_has_no_match'])} for the teacher, "
              f"{len(found['generation_0_sound_where_the_teacher_has_no_match'])} the other way")
    for name, ablation in recursion["ablations"].items():
        print(f"  {name}: {len(ablation['symbols_removed'])} symbols removed; FRESH-4 sound solves lost "
              f"{ablation['fresh4_sound_solves_lost']}, gained {ablation['fresh4_sound_solves_gained']}")
    print("criteria on held-out B (a development set):", {k: v for k, v in out["criteria"].items()
                                                         if k in ("R1", "R2", "R3", "R4")},
          "| R3:", line(out["criteria"]["R3_new_student_vs_gen0_any_on_held_out_B"]))

    # ---- predictions, misses first --------------------------------------------------------------------
    scores = out["predictions"]
    marks = {}
    for name, (expected, confidence) in EXPECTED.items():
        got = scores[name]
        marks[name] = "not scored" if got.startswith("not scored") else ("hit" if got == expected else "miss")
    order = sorted(EXPECTED, key=lambda n: ({"miss": 0, "not scored": 1, "hit": 2}[marks[n]], int(n[1:])))
    print(f"\npredictions: {sum(1 for m in marks.values() if m == 'miss')} missed, "
          f"{sum(1 for m in marks.values() if m == 'not scored')} not scored, "
          f"{sum(1 for m in marks.values() if m == 'hit')} hit, of {len(marks)}")
    print("| ID | Prediction | Expected | Outcome | Score |")
    print("| --- | --- | --- | --- | --- |")
    for name in order:
        expected, confidence = EXPECTED[name]
        print(f"| {name} | {WORDING[name]} | {expected} ({confidence}) | {scores[name]} | "
              f"{'**miss**' if marks[name] == 'miss' else marks[name]} |")
    print("\nOUTCOME:", out["outcome"])
    print("on verified counts:", out["outcome_on_verified_counts"])
    print("\nrecomputed comparisons that differ from the stored ones:", mismatches or "none")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
