"""Did a cycle's symbols depend on what the cycle before added? (report-only, post hoc)

For each accepted cycle k >= 2 of an expert-iteration report, the screened proposal step is
replayed twice with the library the cycle started from: once on the corpus the loop really had
(every verified learning program up to that cycle's teacher run), and once on the corpus as it
stood when cycle k - 1 proposed, before that cycle's symbols had added any program to it.
A symbol that the older corpus proposes too, in any of its attempts, was already waiting
there. For each symbol the report also counts the supporting programs the older corpus lacks.

No search is run: only compression in the driver.

    python expert_dependence.py <expert report.json>
"""
from __future__ import annotations

import json
import sys

import compress
from expert import MIN_FAMILIES, PER_CYCLE
from rsi5 import partitions
from rsi5.dsl.pretty_parse import parse


def absorb(corpus, programs, learn):
    for key, value in programs.items():
        if key.split("/", 1)[0] not in learn:
            continue
        term = parse(value[0])
        if key not in corpus or compress.size(term) < compress.size(corpus[key]):
            corpus[key] = term


def proposals(corpus, library, tabu, family_of, cycle, attempts=2):
    """The batches ``expert.run`` would propose in ``attempts`` tries. ``tabu`` is extended in
    place with the screened symbols, as in the loop; a batch is banned for the next try only."""
    batches, tried = [], set()
    for _ in range(attempts):
        tabu |= tried
        kept, trial, banned = [], dict(library), set(tabu)
        for _ in range(60):
            if len(kept) >= PER_CYCLE:
                break
            found = compress.propose(corpus, trial, tabu=frozenset(banned), max_new=1, name_prefix=f"c{cycle}_")
            if not found:
                break
            a = found[0]
            families = {family_of[t] for t in a.tasks if t in family_of}
            if len(families) < MIN_FAMILIES:
                banned.add(compress.key(a))
                tabu.add(compress.key(a))
                continue
            kept.append(a)
            trial[a.name] = a
        batches.append(kept)
        tried = {compress.key(a) for a in kept}
    return batches


if __name__ == "__main__":
    report = json.load(open(sys.argv[1]))
    learn = tuple(report["learn"])
    family_of = {f"{p}/{task.name}": partitions.family(task.name) for p in learn for task in partitions.load(p)}
    timeline = report["timeline"]
    # rebuild, cycle by cycle, the corpus and the library the loop held
    corpus, library, tabu = {}, {}, set()
    absorb(corpus, timeline[0]["programs"], learn)                 # student0
    snapshots = []                                                 # corpus before each cycle's teacher run
    index, cycle = 1, 0
    while index < len(timeline) and timeline[index]["label"].startswith("teacher") \
            and timeline[index]["label"] != "teacher_final":
        cycle += 1
        before = dict(corpus)
        absorb(corpus, timeline[index]["programs"], learn)         # this cycle's teacher
        index += 1
        students = []
        while index < len(timeline) and timeline[index]["label"].startswith(f"student{cycle}."):
            students.append(timeline[index])
            index += 1
        snapshots.append((cycle, before, dict(corpus), dict(library), set(tabu), students))
        snapshot_tabu = set(tabu)
        real = proposals(corpus, library, tabu, family_of, cycle, attempts=len(students))
        snapshots[-1] = (cycle, before, dict(corpus), dict(library), snapshot_tabu, students)
        for batch, student in zip(real, students):
            recorded = [p["definition"] for p in student["proposed"]]
            assert [str(a.definition) for a in batch] == recorded, (cycle, recorded, [str(a.definition) for a in batch])
            if student.get("accepted"):
                library.update({a.name: a for a in batch})
                absorb(corpus, student["programs"], learn)
                break
            tabu.update(compress.key(a) for a in batch)
    print(f"the replay reproduces the recorded proposals of {cycle} cycles")
    for (cycle, before, after, lib, tab, students), previous in zip(snapshots[1:], snapshots):
        accepted = [s for s in students if s.get("accepted")]
        if not accepted:
            continue
        frozen = previous[2]                                        # the corpus cycle k - 1 proposed from
        real = proposals(after, lib, set(tab), family_of, cycle, attempts=len(students))[len(students) - 1]
        # On the older corpus the greedy order differs, so a symbol can come up in another attempt:
        # the comparison is with everything the older corpus proposes in as many attempts.
        older = {compress.key(a) for batch in proposals(frozen, lib, set(tab), family_of, cycle, attempts=len(students))
                 for a in batch}
        same = {compress.key(a) for a in real} & older
        print(f"cycle {cycle}: accepted symbols {[str(a.definition)[:70] for a in real]}")
        print(f"   corpus then {len(after)} programs; frozen one cycle earlier {len(frozen)} programs; "
              f"{len(same)} of {len(real)} symbols are proposed from the older corpus too")
        for a in real:
            changed = [t for t in a.tasks if t not in frozen or frozen[t] != after[t]]
            where = "proposed from the older corpus too" if compress.key(a) in same else "only with the newer programs"
            print(f"   {where}: {a.definition}  (tasks {len(a.tasks)}, of them {len(changed)} with a program "
                  f"the older corpus does not hold)")
