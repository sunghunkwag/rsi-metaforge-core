"""Generalisation audit over every exposed partition (report-only; verdicts are not changed).

A verified program is *sound* here when, for some validated reading of its task's name
(``oracles.py``), it agrees with that reading on 200 fresh inputs inside the task's own input
range, spread over the reading's outputs. Otherwise it is *coincidental*: it passed the
task's public and hidden examples and computes something else.

    python audit_all.py loop     <loop report.json>      every state: verified and sound counts
    python audit_all.py expert   <expert report.json>
    python audit_all.py gen0     <hybrid report.json>    every variant
    python audit_all.py frontier <frontier report.json>
    python audit_all.py ablate   <expert_ablate output.json>
    python audit_all.py state    <state_run output.json>
    python audit_all.py registered <budget>              the registered engine's files

Add --list to print the coincidental programs of the last (or best) state.
"""
from __future__ import annotations

import collections
import json
import sys

import oracles
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

ALL = oracles.ALL
STEPS = 2000


class Auditor:
    def __init__(self):
        self.table = oracles.references()
        self.cache = {}
        self.inputs = {}
        self.counterexample = {}             # (key, program) -> (input, reference output, program output)

    def _fresh(self, key, index):
        if (key, index) not in self.inputs:
            task, functions = self.table[key]
            self.inputs[(key, index)] = oracles.fresh_inputs(key, task, [functions[index]])
        return self.inputs[(key, index)]

    def sound(self, key: str, text: str):
        """True, False, or None when the task has no validated reference."""
        if (key, text) in self.cache:
            return self.cache[(key, text)]
        entry = self.table.get(key)
        if entry is None or not entry[1]:
            verdict = None
        else:
            term = parse(text)
            verdict = False
            for index, function in enumerate(entry[1]):
                agrees = True
                for xs in self._fresh(key, index):
                    want = function(list(xs))
                    if want is None:
                        continue
                    got = evaluate(term, (list(xs),), step_budget=STEPS)
                    if not got.ok or got.value != want or type(got.value) is not type(want):
                        agrees = False
                        self.counterexample.setdefault((key, text), (list(xs), want, got.value if got.ok else "error"))
                        break
                if agrees:
                    verdict = True
                    break
        self.cache[(key, text)] = verdict
        return verdict

    def counts(self, programs: dict) -> dict:
        """programs: 'partition/name' -> [text, ...]. Per partition (verified, sound), dreams skipped."""
        out = {p: [0, 0] for p in ALL}
        for key, value in programs.items():
            partition = key.split("/", 1)[0]
            if partition not in out:
                continue
            out[partition][0] += 1
            if self.sound(key, value[0]):
                out[partition][1] += 1
        return out

    def coincidental(self, programs: dict) -> list:
        return sorted((key, value[0]) for key, value in programs.items()
                      if key.split("/", 1)[0] in ALL and self.sound(key, value[0]) is False)


def _line(counts, learn) -> str:
    held = [p for p in ALL if p not in learn]
    learn_v, learn_s = (sum(counts[p][i] for p in learn) for i in (0, 1))
    held_v, held_s = (sum(counts[p][i] for p in held) for i in (0, 1))
    per = " ".join(f"{p} {counts[p][1]}/{counts[p][0]}" for p in ALL)
    return f"learning {learn_s}/{learn_v} held-out {held_s}/{held_v} | {per}"


def _listing(auditor, programs) -> None:
    for key, text in auditor.coincidental(programs):
        xs, want, got = auditor.counterexample[(key, text)]
        print(f"    coincidental {key[:70]} | {text[:150]} | on {xs}: reference {want}, program {got}")


def loop_audit(auditor, report, listing) -> dict:
    learn = tuple(report["learn"])
    by_run = {t["run"]: t for t in report["timeline"]}
    chain = {report["first"], report["best_run"]} | {t["run"] for t in report["timeline"] if t.get("accepted")}
    print("sound/verified, every state of the timeline (* accepted or first, B best):")
    out = {}
    for t in report["timeline"]:
        counts = auditor.counts(t["programs"])
        mark = "B" if t["run"] == report["best_run"] else ("*" if t["run"] in chain else " ")
        print(f" {mark} run {t['run']:2d} {t['label']:16s} {_line(counts, learn)}")
        out[t["run"]] = counts
    if listing:
        _listing(auditor, by_run[report["best_run"]]["programs"])
    return out


def expert_audit(auditor, report, listing) -> dict:
    learn = tuple(report["learn"])
    out = {}
    for t in report["timeline"]:
        counts = auditor.counts(t["programs"])
        mark = "*" if t.get("accepted") or t["label"] == "student0" else " "
        print(f" {mark} run {t['run']:2d} {t['label']:14s} budget {t['budget']:>6} {_line(counts, learn)}")
        out[t["run"]] = counts
    if listing:
        last = {t["run"]: t for t in report["timeline"]}[report["student_last"]]
        _listing(auditor, last["programs"])
    return out


def gen0_audit(auditor, report, listing) -> None:
    for variant, data in report["variants"].items():
        programs = {f"{p}/{r['name']}": [r["program"]] for p, rows in data["records"].items()
                    for r in rows if r["solved"]}
        print(f"{variant:6s} A: {_line(auditor.counts(programs), ('train', 'near'))}")
        if listing:
            _listing(auditor, programs)


def frontier_audit(auditor, report, listing) -> None:
    for row in report["rows"]:
        counts = auditor.counts(row["programs"])
        held = report["held_out"]
        print(f"{row['state']:8s} budget {row['budget']:>7} held-out sound {sum(counts[p][1] for p in held)} "
              f"verified {sum(counts[p][0] for p in held)} | " + " ".join(f"{p} {counts[p][1]}/{counts[p][0]}" for p in held))
        if listing:
            _listing(auditor, row["programs"])


def ablate_audit(auditor, report, listing) -> None:
    for row in report["rows"]:
        counts = auditor.counts(row["programs"])
        cells = " ".join(f"{p} {counts[p][1]}/{counts[p][0]}" for p in report["partitions"])
        print(f"{row['label']:14s} budget {row['budget']:>7} {report.get('components', '')} sound "
              f"{sum(counts[p][1] for p in report['partitions'])} verified {sum(counts[p][0] for p in report['partitions'])} | {cells}")
        if listing:
            _listing(auditor, row["programs"])


def registered_audit(auditor, budget: int, listing) -> None:
    programs = {}
    for partition in ALL:
        records = json.load(open(f"rsi5/results_p1/restored_{partition}.json"))["records"]
        for r in records:
            if r["solved"] and r["candidates_to_solution"] <= budget:
                programs[f"{partition}/{r['name']}"] = [r["program"]]
    print(f"registered restored at {budget}: A: {_line(auditor.counts(programs), ('train', 'near'))}")
    if listing:
        _listing(auditor, programs)


if __name__ == "__main__":
    kind, target = sys.argv[1], sys.argv[2]
    listing = "--list" in sys.argv
    auditor = Auditor()
    if kind == "registered":
        registered_audit(auditor, int(target), listing)
    else:
        report = json.load(open(target))
        if kind == "state":
            counts = auditor.counts(report["programs"])
            print(f"{report['label']} budget {report['budget']}: A: {_line(counts, ('train', 'near'))}")
            if listing:
                _listing(auditor, report["programs"])
        else:
            {"loop": loop_audit, "expert": expert_audit, "gen0": gen0_audit,
             "frontier": frontier_audit, "ablate": ablate_audit}[kind](auditor, report, listing)
