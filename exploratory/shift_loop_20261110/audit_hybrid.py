"""Generalisation audit of verified programs (report-only): each program on 200 seeded random
inputs against the family oracle of rsi5.audit_p1 (FRESH-1, RESERVE-FAR2, COMPOSE-24 only).

Superseded by audit_all.py, which covers every exposed partition and tests boolean tasks on
both answers. Kept because the first numbers of this study were produced with it."""
import json, random, sys
from rsi5 import audit_p1
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

AUDITED = ("fresh1", "far2", "compose24")


def audit(programs: dict) -> dict:
    """programs: 'partition/task name' -> [program text, route, ...]. Returns per partition
    {'verified', 'generalise', 'coincidental': [(name, route, program)]}."""
    out = {}
    for key in sorted(programs):
        partition, name = key.split("/", 1)
        if partition not in AUDITED:
            continue
        text, route = programs[key][0], programs[key][1]
        oracle = audit_p1.ORACLES[partition](name)
        if oracle is None:
            continue
        rng = random.Random(f"{audit_p1.SEED}:{key}")
        term = parse(text)
        bad = None
        for _ in range(audit_p1.TRIALS):
            xs = audit_p1.random_inputs(rng, partition)
            want = oracle(xs)
            got = evaluate(term, (xs,), step_budget=2000)
            if want is None:
                continue                 # outside the task's domain, as in rsi5.audit_p1
            if not got.ok or got.value != want:
                bad = xs
                break
        row = out.setdefault(partition, {"verified": 0, "generalise": 0, "coincidental": []})
        row["verified"] += 1
        if bad is None:
            row["generalise"] += 1
        else:
            row["coincidental"].append((name, route, text))
    return out


if __name__ == "__main__":
    report = json.load(open(sys.argv[1]))
    if "variants" in report:
        for variant, data in report["variants"].items():
            programs = {f"{p}/{r['name']}": [r["program"], r["route"]] for p, rows in data["records"].items()
                        for r in rows if r["solved"]}
            result = audit(programs)
            print(variant, {p: (v["verified"], v["generalise"], len(v["coincidental"])) for p, v in result.items()})
            for p, v in result.items():
                for name, route, text in v["coincidental"]:
                    print("    coincidental", p, name[:44], route, text[:90])
    else:
        for state in report["timeline"]:
            result = audit(state["programs"])
            print(state["run"], state["label"], {p: (v["verified"], v["generalise"], len(v["coincidental"])) for p, v in result.items()})
