"""Readings of the registered run of Addendum 8 that its own script does not print.

An independent verification of the run (README, Reviews, the seventh) found that the criteria
R1 and R3 and several strata read differently under measures the registration names but
``confirm.py`` applies only to the primary comparison. This script recomputes those readings
from ``results/confirm.json`` and the regenerated FRESH-4 tasks. Nothing here is part of the
registered protocol and nothing here changes a registered verdict: the registered output is
printed first in every block and the other readings beside it. The symbol-stage stratum was
chosen after the data had been read.

    python addendum8_checks.py results/confirm.json
"""
from __future__ import annotations

import json
import sys
from math import comb

import confirm
import fresh4
from rsi5 import partitions
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

STEPS = confirm.STEPS
GEN0 = ("gen0@student", "gen0@deploy", "gen0@C2old", "gen0@C2new", "gen0@top")
# A stage that equals a symbol of the final library on every input it is defined on (checked by
# two reviewers against the symbols' definitions): reverse = s3_1; append-k = s23_1 k;
# take-k 3 = s2_1 xs 3; remove-mod-k = s15_1 k; keep-mod-k 2 = s17_1; replace-all-k-with-n (k, -2) = s18_1 k.
SYMBOL_STAGE = (lambda routine, parameters:
                routine in ("reverse", "append-k", "remove-mod-k")
                or (routine == "take-k" and tuple(parameters) == (3,))
                or (routine == "keep-mod-k" and tuple(parameters) == (2,))
                or (routine == "replace-all-k-with-n" and len(parameters) == 2 and parameters[1] == -2))


def p_one_sided(a: int, b: int) -> float:
    n = a + b
    return sum(comb(n, k) for k in range(a, n + 1)) / 2 ** n if n else 1.0


def line(x, y, scope=None, two_sided=False) -> str:
    x, y = set(x), set(y)
    if scope is not None:
        x, y = x & scope, y & scope
    a, b = len(x - y), len(y - x)
    p = min(1.0, 2 * min(p_one_sided(a, b), p_one_sided(b, a))) if two_sided else p_one_sided(a, b)
    return f"{len(x)} against {len(y)} ({a} against {b}, {'two-sided ' if two_sided else ''}p = {p:.4g})"


def same(a, b) -> bool:
    """Equality with the element types compared too: [True] is not [1]."""
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def main(path: str) -> None:
    data = json.load(open(path))
    rows = data["rows"]
    tasks = fresh4.make()
    task_of = {f"fresh4/{task.name}": task for task in tasks}
    every = set(task_of)
    listed = {key for key, task in task_of.items() if task.kind == "list"}
    sound = confirm.Sound({"fresh4": tasks})

    def arm(labels, measure):
        out = set()
        for label in labels:
            row = rows[f"{label}:fresh4"]
            if measure == "sound":
                out |= set(row["sound"])
            elif measure == "verified":
                out |= set(row["programs"])
            else:                                   # sound by the audit and right on the whole input pool
                out |= {key for key in row["sound"] if sound.on_pool(key, row["programs"][key][0])}
        return out

    print("R1 to R3 on FRESH-4 (800 tasks, 10^4 candidates per task) under three measures")
    for measure in ("sound", "verified", "pool"):
        zero, one, two = arm(["gen0@student"], measure), arm(["cycle1@student"], measure), arm(["new@student"], measure)
        union = arm(GEN0, measure)
        gains = (two - one) - zero
        print(f"  {measure:8s} R1 by generation {len(zero)}, {len(one)}, {len(two)}; second step "
              f"{len(two - one)} gained, {len(one - two)} lost | R2 gains after cycle 1: {len(gains)} | "
              f"R3 {line(two, union)}; list outputs {line(two, union, listed)}")
    for measure in ("sound", "verified", "pool"):
        two = arm(["new@student"], measure)
        print(f"  R3 against the single runs of generation 0 ({measure}): " + "; ".join(
            f"{label.split('@')[1]} {line(two, arm([label], measure))}" for label in GEN0))

    print("\nThe task that decides R3, and the step budget of the evaluator")
    key = "fresh4/fresh4::((identify-geq-k (dyn . 0) (static . 2)) (replace-all-k-with-n (dyn . 1) (static . 1) (static . 5)))"
    task, text = task_of[key], rows["new@student:fresh4"]["programs"][key][0]
    values = [x for example in list(task.examples) + list(task.hidden) for x in example[0][0]]
    lengths = [len(example[0][0]) for example in list(task.examples) + list(task.hidden)]
    print(f"  program of new@student: {text}")
    print(f"  the task's examples: lengths {min(lengths)} to {max(lengths)}, values {min(values)} to {max(values)}")
    for xs in ([max(values)] * max(lengths), [14, 12, 2, 16, 14, 14, 9, 13, 16, 7]):
        got, far = evaluate(parse(text), (xs,), step_budget=STEPS), evaluate(parse(text), (xs,), step_budget=200_000)
        print(f"  on {xs}: with {STEPS} steps ok = {got.ok}; with 200,000 steps equal to the reference: "
              f"{far.ok and same(far.value, task.reference(list(xs)))}")
    print(f"  sound in: new@student {key in rows['new@student:fresh4']['sound']}, "
          f"generation 0 at some budget {key in arm(GEN0, 'sound')}, cycle 1 {key in rows['cycle1@student:fresh4']['sound']}")

    def stress(key):
        task = task_of[key]
        inputs = [list(example[0][0]) for example in list(task.examples) + list(task.hidden)]
        values = [x for xs in inputs for x in xs] or [0]
        low, high, longest = min(values), max(values), max(len(xs) for xs in inputs)
        return [[high] * longest, [low] * longest, ([high, low] * longest)[:longest]]

    def survives(key, text):
        """False when the program fails an in-range input of the stress set (step budget or value)."""
        task, term = task_of[key], parse(text)
        for xs in stress(key):
            want = task.reference(list(xs))
            if want is None or sound.kind(want) is None:
                continue
            got = evaluate(term, (list(xs),), step_budget=STEPS)
            if not got.ok or not same(got.value, want):
                return False
        return True

    def stressed(labels):
        out = set()
        for label in labels:
            row = rows[f"{label}:fresh4"]
            out |= {key for key in row["sound"] if survives(key, row["programs"][key][0])}
        return out
    zero, one, two, union = stressed(["gen0@student"]), stressed(["cycle1@student"]), stressed(["new@student"]), stressed(GEN0)
    print("  two rules for a program that runs out of steps, each applied to every row")
    print("  rule 1, it fails: sound, and right within the step budget on three more in-range inputs per task (the "
          "longest list of the largest value, of the smallest value, alternating):")
    print(f"    R1 by generation {len(zero)}, {len(one)}, {len(two)} | R3 {line(two, union)} | primary "
          f"{line(stressed(['new@deploy']), union, listed)}")
    lost = {label: sorted(set(rows[f'{label}:fresh4']['sound']) - stressed([label]))
            for label in ("new@student", "cycle1@student", "new@deploy", "old@deploy") + GEN0}
    print("    sound programs that fail one of them: " + ", ".join(f"{label} {len(keys)}" for label, keys in lost.items()))

    def patient(labels):
        """Rule 2: running out of steps on an audit input is not a disagreement (200,000 steps)."""
        out = set()
        for label in labels:
            row = rows[f"{label}:fresh4"]
            out |= set(row["sound"])
            for key, (text, _, _) in row["programs"].items():
                if key in row["sound"]:
                    continue
                task, term, agree, checked = task_of[key], parse(text), True, 0
                if key not in sound.inputs:
                    sound.inputs[key] = sound.oracles.fresh_inputs(key, task, [task.reference])
                for xs in sound.inputs[key]:
                    want = task.reference(list(xs))
                    if want is None or sound.kind(want) is None:
                        continue
                    checked += 1
                    got = evaluate(term, (list(xs),), step_budget=200_000)
                    if not got.ok or not same(got.value, want):
                        agree = False
                        break
                if agree and checked >= confirm.MIN_EVIDENCE:
                    out.add(key)
        return out
    zero, one, two, union = patient(["gen0@student"]), patient(["cycle1@student"]), patient(["new@student"]), patient(GEN0)
    print("  rule 2, it does not: the audit's own inputs with 200,000 steps where a program was called not sound:")
    print(f"    R1 by generation {len(zero)}, {len(one)}, {len(two)} | R3 {line(two, union)} | primary "
          f"{line(patient(['new@deploy']), union, listed)} | new against old {line(patient(['new@deploy']), patient(['old@deploy']), listed)}")

    key = "fresh4/fresh4::((remove-mod-k (dyn . 0) (static . 2)) (identify-geq-k (dyn . 1) (static . 7)))"
    text = rows["new@deploy:fresh4"]["programs"][key][0]
    got, far = evaluate(parse(text), ([15] * 10,), step_budget=STEPS), evaluate(parse(text), ([15] * 10,), step_budget=200_000)
    print(f"  the other way round, new@deploy on remove-mod-k 2 then identify-geq-k 7: stored sound "
          f"{key in rows['new@deploy:fresh4']['sound']}; on [15] * 10 with {STEPS} steps ok = {got.ok}; with 200,000 "
          f"steps equal to the reference: {far.ok and same(far.value, task_of[key].reference([15] * 10))}")

    print("\nThe primary comparison and the endings where a stage equals a learned symbol, and where none does "
          "(a stratum chosen after the data were read)")
    with_symbol = {key for key in listed if any(SYMBOL_STAGE(routine, list(parameters)) for routine, parameters in task_of[key].stages)}
    without = listed - with_symbol
    new, old, control = arm(["new@deploy"], "sound"), arm(["old@deploy"], "sound"), arm(GEN0, "sound")
    earlier = {key for key in listed if task_of[key].modulo or confirm.EARLIER_FAMILY in (task_of[key].stages[0][0], task_of[key].stages[1][0])}
    provenance = fresh4.provenance(tasks)
    print(f"  list tasks with such a stage: {len(with_symbol)}; without: {len(without)}")
    print(f"  new-only tasks of the primary comparison with such a stage: {len((new - control) & with_symbol)} of "
          f"{len((new - control) & listed)}; control-only: {len((control - new) & with_symbol)} of {len((control - new) & listed)}")
    print(f"  with such a stage:    new against generation 0 at any budget {line(new, control, with_symbol)}")
    print(f"  without such a stage: new against generation 0 at any budget {line(new, control, without)}; "
          f"{line(new, control, without, two_sided=True)}")
    print(f"                        new against generation 0 at 10^5 {line(new, arm(['gen0@deploy'], 'sound'), without)}")
    print(f"                        new against old {line(new, old, without)}")
    breadth = listed - earlier
    print(f"  ending 1 (neither slice-k-n nor a divisibility routine, {len(breadth)} tasks): {line(new, control, breadth)}; "
          f"without a symbol stage ({len(breadth & without)} tasks) {line(new, control, breadth & without, two_sided=True)}")
    beyond = listed - {f"fresh4/{name}" for name, entry in provenance.items() if entry["stages"] == 2}
    print(f"  ending 5 (not both stage instances are learning tasks, {len(beyond)} tasks): {line(new, control, beyond)}; "
          f"without a symbol stage ({len(beyond & without)} tasks) {line(new, control, beyond & without)}")
    print(f"  new against old with a routine of the earlier symbols ({len(earlier)} tasks): "
          f"{line(new, old, earlier, two_sided=True)}; without one ({len(listed - earlier)}): "
          f"{line(new, old, listed - earlier, two_sided=True)}")

    print("\nEnding 4 with element types compared (a dream that returns booleans does not compute a task of 0s and 1s)")
    report = data["loop"]
    dreams = [entry for cycle in report["cycles"] for group in cycle["dream_programs"].values() for entry in group]
    parsed = [parse(text) for text in sorted({text for text, _, _ in dreams})]
    family_of_key = lambda key: partitions.family(key.split("/", 1)[1])
    dream_pairs = {(family_of_key(f), family_of_key(g)) for _, f, g in dreams}

    def dreamt(task, strict) -> bool:
        examples = list(task.examples) + list(task.hidden)
        for term in parsed:
            for inputs, want in examples:
                got = evaluate(term, tuple(inputs), step_budget=STEPS)
                agree = got.ok and (same(got.value, want) if strict else
                                    (got.value == want and type(got.value) is type(want)))
                if not agree:
                    break
            else:
                return True
        return False
    pair = {key for key, task in task_of.items() if (task.stages[0][0], task.stages[1][0]) in dream_pairs}
    for strict in (False, True):
        exact = {key for key, task in task_of.items() if dreamt(task, strict)}
        undreamt = listed - (exact | pair)
        print(f"  {'element types compared' if strict else 'as stored (top-level type only)'}: a dream computes "
              f"{len(exact)} tasks; no dream computes the task or composes its pair: {len(undreamt)} list tasks, "
              f"new against generation 0 at any budget {line(new, control, undreamt)}; new against old {line(new, old, undreamt)}")

    print("\nThe primary comparison under the other measures")
    for measure in ("sound", "verified", "pool"):
        print(f"  {measure:8s} new at 10^5 against generation 0 at any budget, list outputs: "
              f"{line(arm(['new@deploy'], measure), arm(GEN0, measure), listed)}; new against old: "
              f"{line(arm(['new@deploy'], measure), arm(['old@deploy'], measure), listed)}")


if __name__ == "__main__":
    main(sys.argv[1])
