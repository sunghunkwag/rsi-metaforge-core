"""Tables for the README from the result files (exploratory, report-only).

    python summarise.py loop   <loop report.json>
    python summarise.py expert <expert report.json>
    python summarise.py gen0   <hybrid report.json>

loop:   the accepted chain to the best state, every acceptance, family concentration of the
        learning gains, and the generalisation audit of the first and the best state.
expert: the student at each accepted cycle, the teacher's harvest, the screened symbols.
gen0:   held-out counts of each variant under both configurations' definitions of held-out.
"""
from __future__ import annotations

import collections
import json
import sys

import audit_hybrid
from hybrid import ALL
from loop import CONFIGS
from rsi5 import partitions


def family_of(key: str) -> str:
    return partitions.family(key.split("/", 1)[1])


def family_view(solved, learn) -> dict:
    """Families with a verified learning solve, and the family-normalised score (the sum over
    learning families of the fraction of the family solved)."""
    sizes = collections.Counter()
    for partition in learn:
        for task in partitions.load(partition):
            sizes[partitions.family(task.name)] += 1
    hits = collections.Counter(family_of(key) for key in solved if key.split("/", 1)[0] in learn)
    return {"families": len(sizes), "with_a_solve": len(hits),
            "score": round(sum(hits[f] / n for f, n in sizes.items()), 2)}


def audit_line(programs) -> str:
    result = audit_hybrid.audit(programs)
    return ", ".join(f"{p} {v['generalise']}/{v['verified']}" for p, v in sorted(result.items()))


def loop_summary(report) -> None:
    learn = tuple(report["learn"])
    by_run = {t["run"]: t for t in report["timeline"]}
    first, best = by_run[report["first"]], by_run[report["best_run"]]
    accepted = [t for t in report["timeline"] if t.get("accepted")]
    print(f"runs {report['runs']}, rollbacks {report['rollbacks']}, acceptances {len(accepted)}, "
          f"equal budget per real task {report['equal_budget_per_real_task']}")
    print("| Run | Move | Learning | Held-out | Dream | Symbols | Kept symbols (element, list) |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for t in [first] + accepted:
        keep = t["keep_sizes"]
        mark = " (best)" if t["run"] == best["run"] else ""
        print(f"| {t['run']}{mark} | {t['move'] or 'generation 0'} | {t['learn']} | {t['held_out']} | "
              f"{t.get('dream', 0)}/{t.get('dream_tasks', 0)} | {len(t['library'])} | "
              f"{keep.get('elem', 'all')}, {keep.get('list', 'all')} |")
    for label, state in (("first", first), ("best", best)):
        view = family_view(state["solved"], learn)
        print(f"{label}: counts {state['counts']}; learning families with a solve {view['with_a_solve']} of "
              f"{view['families']}, family-normalised score {view['score']}; audit {audit_line(state['programs'])}")
    gained = sorted(set(best["solved"]) - set(first["solved"]))
    lost = sorted(set(first["solved"]) - set(best["solved"]))
    real = lambda keys: [k for k in keys if not k.startswith("dream")]
    for label, keys in (("gained", real(gained)), ("lost", real(lost))):
        groups = collections.Counter((k.split("/", 1)[0], family_of(k)) for k in keys)
        print(f"{label} {len(keys)}: " + "; ".join(f"{p} {f} x{n}" for (p, f), n in groups.most_common()))
    print("library of the best state:")
    for name, a in report["library"].items():
        print(f"  {name} (depth {a['depth']}): {a['definition']}  | used in learning "
              f"{best['abstraction_use_learn'].get(name, 0)}, in held-out {best['abstraction_use_held_out'].get(name, 0)}")
    if "random_cut" in report:
        print("random 60% cut of generation 0:", report["random_cut"]["learn"], report["random_cut"]["held_out"])


def expert_summary(report) -> None:
    learn = tuple(report["learn"])
    by_run = {t["run"]: t for t in report["timeline"]}
    first, last = by_run[report["student_first"]], by_run[report["student_last"]]
    print(f"cycles with an acceptance {sum(1 for t in report['timeline'] if t.get('accepted'))}, "
          f"executions {report['executions']}, equal budget per real task {report['equal_budget_per_real_task']}, "
          f"screened out {len(report['screened_out'])}")
    print("| Run | State | Budget | Learning | Families with a solve | Family score | Held-out |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for t in report["timeline"]:
        mark = "" if t["label"].startswith("teacher") else (" accepted" if t.get("accepted") else
                                                           ("" if t["label"] == "student0" else " rejected"))
        print(f"| {t['run']} | {t['label']}{mark} | {t['budget']} | {t['learn']} | {t['families_with_a_solve']} of "
              f"{report['families']} | {t['family_score']} | {t['held_out'] if t['held_out'] is not None else ''} |")
    print("harvest (teacher) learning solves", report["harvest_learn"], "families", report["harvest_families"],
          "family score", report["harvest_family_score"])
    for label, state in (("first student", first), ("last student", last)):
        print(f"{label}: counts {state['counts']}; audit {audit_line(state['programs'])}")
    gained = sorted(set(last["solved"]) - set(first["solved"]))
    lost = sorted(set(first["solved"]) - set(last["solved"]))
    for label, keys in (("gained", gained), ("lost", lost)):
        groups = collections.Counter((k.split("/", 1)[0], family_of(k)) for k in keys)
        print(f"{label} {len(keys)}: " + "; ".join(f"{p} {f} x{n}" for (p, f), n in groups.most_common()))
    print("library:")
    for name, a in report["library"].items():
        print(f"  {name} (depth {a['depth']}): {a['definition']}")
    for row in report["screened_out"]:
        print(f"  screened out in cycle {row['cycle']}: {row['definition']}  score {row['score']} tasks {row['tasks']} "
              f"families {row['families']}")


def gen0_summary(report) -> None:
    print(f"budget {report['budget']}")
    for variant, data in report["variants"].items():
        counts = data["counts"]
        line = f"{variant:6s} total {sum(counts.values())}"
        for config, learn in CONFIGS.items():
            line += f" | held-out {config} {sum(counts[p] for p in ALL if p not in learn)}"
        programs = {f"{p}/{r['name']}": [r["program"], r["route"]] for p, rows in data["records"].items()
                    for r in rows if r["solved"]}
        print(line, "|", counts, "| audit", audit_line(programs))


if __name__ == "__main__":
    kind, path = sys.argv[1], sys.argv[2]
    report = json.load(open(path))
    {"loop": loop_summary, "expert": expert_summary, "gen0": gen0_summary}[kind](report)
