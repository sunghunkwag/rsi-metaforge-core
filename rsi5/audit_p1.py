"""Post-hoc generalisation audit of the Phase 1 solutions (report-only; verdicts unchanged).

    python -m rsi5.audit_p1 --results rsi5/results_p1

A task counts as *solved* when the frozen verifier accepted the engine's program on every
public and hidden example (the registered protocol, the same as rsi3's). FRESH tasks have
eight public and one or two hidden examples, so a 10^6-candidate enumeration can find a
program that fits all of them by coincidence. This audit measures how often: for the
families whose semantics are known (every FRESH-1 and RESERVE-FAR2 family, and COMPOSE-24
through `rsi3.compose24.reference_oracle`), each verified program is run with the reference
interpreter on 200 fresh random inputs (seeded) and compared with a reference oracle. A
program that disagrees anywhere is *coincidental*. The registered counts are not changed by
this audit; it is reported beside them. FRESH-2, RESERVE-NEAR, RESERVE-FAR, VALIDATION and
TRAIN are not audited (their routines are not all re-implemented here).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import re

from rsi3.compose24 import reference_oracle
from .dsl.evaluator import evaluate
from .dsl.terms import term_from_dict
from .partitions import family

SEED = 20261109
TRIALS = 200


def _is_prime(n):
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


def _params(name):
    return [int(v) for v in re.findall(r"\(static \. (-?\d+)\)", name)]


def _corpus_params(name):
    return [int(v) for v in re.findall(r"=(-?\d+)", name)]


# FRESH-1 single routines (DreamCoder list_tasks2 semantics, read from the examples).
def fresh1_oracle(name):
    fam = family(name)
    p = _params(name)
    if fam == "add-k":
        return lambda xs: [x + p[0] for x in xs]
    if fam == "mult-k":
        return lambda xs: [x * p[0] for x in xs]
    if fam == "prepend-k":
        return lambda xs: [p[0]] + xs
    if fam == "append-k":
        return lambda xs: xs + [p[0]]
    if fam == "has-k":
        return lambda xs: p[0] in xs
    if fam == "identify-k":
        return lambda xs: [1 if x == p[0] else 0 for x in xs]
    if fam == "identify-geq-k":
        return lambda xs: [1 if x >= p[0] else 0 for x in xs]
    if fam == "identify-is-mod-k":
        return lambda xs: [1 if x % p[0] == 0 else 0 for x in xs]
    if fam == "identify-is-prime":
        return lambda xs: [1 if _is_prime(x) else 0 for x in xs]
    if fam == "replace-all-k-with-n":
        return lambda xs: [p[1] if x == p[0] else x for x in xs]
    if fam == "replace-index-k-with-n":
        def f(xs):
            if len(xs) <= p[0] - 1:
                return None
            ys = list(xs)
            ys[p[0] - 1] = p[1]
            return ys
        return f
    if fam == "intersperse-k":
        def f(xs):
            out = []
            for i, x in enumerate(xs):
                if i:
                    out.append(p[0])
                out.append(x)
            return out
        return f
    if fam == "positions":
        return lambda xs: [i for i, x in enumerate(xs) if x != 0]
    if fam == "uniq":
        def f(xs):
            out = []
            for x in xs:
                if x not in out:
                    out.append(x)
            return out
        return f
    if fam == "rotate-k":
        def f(xs):
            if not xs:
                return []
            k = p[0] % len(xs)
            return xs[k:] + xs[:k]
        return f
    return None


def far2_oracle(name):
    fam = family(name)
    p = _corpus_params(name)
    if fam == "drop-k":
        return lambda xs: xs[p[0]:] if len(xs) >= p[0] else None   # the corpus never drops past the end
    if fam == "take-k":
        return lambda xs: xs[:p[0]] if len(xs) >= p[0] else None
    if fam == "count-k":
        return lambda xs: sum(1 for x in xs if x == p[0])
    if fam == "remove-mod-k":
        return lambda xs: [x for x in xs if x % p[0] != 0]
    if fam == "remove-index-k":
        return lambda xs: (xs[:p[0] - 1] + xs[p[0]:]) if len(xs) >= p[0] else None
    return None


def compose_oracle(name):
    fam = name.split("::")[1]
    k = int(name.split("::p")[1])
    return lambda xs: reference_oracle(fam, k, xs)


ORACLES = {"fresh1": fresh1_oracle, "far2": far2_oracle, "compose24": compose_oracle}


def random_inputs(rng, partition):
    if partition == "fresh1":
        n = rng.randint(0, 8)
        return [rng.randint(0, 16) for _ in range(n)]          # list_tasks2 value range
    if partition == "far2":
        n = rng.randint(1, 10)
        return [rng.randint(0, 12) for _ in range(n)]
    n = rng.randint(4, 12)
    return [rng.randint(-8, 9) for _ in range(n)]


def audit_record(record, partition, program_dict, rng):
    oracle = ORACLES[partition](record["name"])
    if oracle is None:
        return None
    term = term_from_dict(program_dict)
    disagreements = 0
    tried = 0
    for _ in range(TRIALS):
        xs = random_inputs(rng, partition)
        expected = oracle(xs)
        if expected is None:
            continue                     # outside the task's domain (too short a list)
        tried += 1
        result = evaluate(term, (xs,), step_budget=2000)
        if not result.ok or result.value != expected:
            disagreements += 1
    return {"tried": tried, "disagreements": disagreements,
            "coincidental": disagreements > 0}


def audit(results: Path) -> dict:
    out = {}
    for path in sorted(Path(results).glob("*_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("partition") not in ORACLES:
            continue
        rng = random.Random(SEED)
        rows = []
        for record in data["records"]:
            if not record["solved"]:
                continue
            program_dict = record.get("program_dict")
            if program_dict is None:
                from .dsl.terms import Term  # noqa: F401
                program_dict = _parse(record["program"])
            verdict = audit_record(record, data["partition"], program_dict, rng)
            if verdict is not None:
                rows.append({"name": record["name"], "family": record["family"],
                             "program": record["program"], **verdict})
        out[(data["vocabulary"], data["partition"])] = rows
    return out


def _parse(pretty: str):
    """Rebuild a term from the result file's pretty form (the files keep the pretty string)."""
    from .dsl.pretty_parse import parse
    return parse(pretty).to_dict()


def table(out: dict) -> str:
    lines = ["| Partition | Vocabulary | Verified solves audited | Generalise to 200 fresh inputs | Coincidental | Coincidental tasks |",
             "| --- | --- | --- | --- | --- | --- |"]
    for (vocabulary, partition), rows in sorted(out.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        bad = [r for r in rows if r["coincidental"]]
        names = ", ".join(f"`{r['name']}`" for r in bad)
        lines.append(f"| {partition} | {vocabulary} | {len(rows)} | {len(rows) - len(bad)} | {len(bad)} | {names} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results_p1")
    args = parser.parse_args(argv)
    out = audit(args.results)
    print(table(out))
    for key, rows in sorted(out.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        for r in rows:
            if r["coincidental"]:
                print(f"- {key[1]} / {key[0]}: `{r['name']}` disagrees on {r['disagreements']} of {r['tried']}: `{r['program']}`")


if __name__ == "__main__":
    main()
