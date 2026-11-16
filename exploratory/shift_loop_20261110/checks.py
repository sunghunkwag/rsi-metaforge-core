"""Self-checks of the exploratory tools (not part of the rsi5 test suite).

    python checks.py          about a minute on two cores

1. The harness with every component off reproduces the registered engine task by task, and a
   cut vocabulary with no size-2 program is searched, not abandoned at the first empty level.
2. Every exposed task has a reference function that reproduces all of its examples.
3. The extended audit agrees with the Phase 1 audit on every program both cover.
4. The audit catches known wrong programs and passes the registered corpus programs it should.
"""
from __future__ import annotations

import json
from pathlib import Path

# The harness forks its workers before any task loader is imported, so its check runs first and
# the audit modules (which load the partitions) are imported inside the later checks.


def check_references():
    import oracles
    table = oracles.references()
    missing = [key for key, (_, functions) in table.items() if not functions]
    assert len(table) == 338 and not missing, missing
    return f"338 of 338 tasks have a validated reference ({sum(len(f) > 1 for _, f in table.values())} admit several readings)"


def check_agreement():
    import audit_all
    from rsi5 import audit_p1
    auditor = audit_all.Auditor()
    old = audit_p1.audit(Path("rsi5/results_p1"))
    total = bad = 0
    for (_, partition), rows in old.items():
        for row in rows:
            total += 1
            bad += row["coincidental"]
            assert auditor.sound(f"{partition}/{row['name']}", row["program"]) == (not row["coincidental"]), row["name"]
    assert total == 60 and bad == 4
    return "the two audits agree on 60 programs (4 coincidental)"


def check_known_programs():
    import audit_all
    auditor = audit_all.Auditor()
    wrong = {"near/is-mod-k with k=4": "(lambda x0: list[int]. (is_empty ((filter (lambda x1: int. ((gt ((mod x1) 2)) 0))) x0)))",
             "far/is-odds": "(lambda x0: list[int]. ((eq 1) (head ((map (lambda x1: int. ((mod x1) 2))) x0))))",
             "near/has-k with k=5": "(lambda x0: list[int]. (((fold (lambda x1: bool. (lambda x2: int. ((eq x2) 5)))) false) x0))"}
    for key, text in wrong.items():
        assert auditor.sound(key, text) is False, key
    right = {"near/is-mod-k with k=4": "(lambda x0: list[int]. (is_empty ((filter (lambda x1: int. ((gt ((mod x1) 4)) 0))) x0)))",
             "far/is-odds": "(lambda x0: list[int]. (is_empty ((filter (lambda x1: int. ((eq ((mod x1) 2)) 0))) x0)))"}
    for key, text in right.items():
        assert auditor.sound(key, text) is True, key
    records = json.load(open("rsi5/results_p1/restored_far2.json"))["records"]
    solved = [r for r in records if r["solved"]]
    assert all(auditor.sound(f"far2/{r['name']}", r["program"]) for r in solved) and len(solved) == 18
    return "3 wrong programs flagged, 2 right ones and the 18 registered RESERVE-FAR2 programs passed"


def check_harness_identity(budget=300):
    import hybrid
    harness = hybrid.Harness(2, hybrid.ALL)
    try:
        result = harness.run(hybrid.spec_of("off", budget, ""))
        different = 0
        for partition, rows in result.items():
            registered = {r["name"]: r for r in json.load(open(f"rsi5/results_p1/restored_{partition}.json"))["records"]}
            for row in rows:
                want = registered[row["name"]]
                solved = bool(want["solved"] and want["candidates_to_solution"] <= budget)
                if row["solved"] != solved or (solved and row["program"] != want["program"]):
                    different += 1
        assert different == 0, different
        # a cut with no size-2 program in the element space: add, sub, mod and three constants
        keep = {"elem": ["add", "sub", "mod", "int:1", "int:2", "int:3"], "list": None}
        cut = harness.run(hybrid.spec_of("cut", budget, "S", keep=keep), partition_names=["near"])
        lifted = [r for r in cut["near"] if r["solved"] and (r["route"] or "").startswith("map+")]
        assert any("add" in r["program"] or "sub" in r["program"] or "mod" in r["program"] for r in lifted), \
            "the cut element space was abandoned at the first empty level"
        return (f"harness with everything off equals the registered engine on 338 tasks at {budget}; "
                f"a cut element space without size-2 programs still solves {len(lifted)} RESERVE-NEAR tasks by the lift")
    finally:
        harness.close()


if __name__ == "__main__":
    for check in (check_harness_identity, check_references, check_agreement, check_known_programs):
        print("ok:", check())
