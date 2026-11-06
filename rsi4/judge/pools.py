"""J's pools: the continual stages and every pool J evaluates on, from one source file.

    python -m rsi4.judge.pools --source PATH/list_tasks2.json      # build and write
    python -m rsi4.judge.pools --source PATH --check                # rebuild and compare

Source: DreamCoder's ``data/list_tasks2.json`` in ``ellisk42/ec`` at commit
cb0e63f5c33cd2de360b791038b0f5272750270e (MIT), the file and commit FRESH
used (``rsi3/fresh.py``). It holds 174,258 records; the builder refuses any
other count or content hash. The file is fetched once and is not committed.

Rules (OWNER_DIRECTIVE.md §4), applied to names, declared types and example
counts only. No task is run to select anything.

1. **Eligible.** ``rsi3.fresh``'s rules: declared input and output types RSI-2
   supports, at least nine distinct inputs, and a public/hidden split that
   ``rsi3.fresh.to_task`` accepts (the first 8 distinct inputs public, the
   rest hidden). Shapes: two-stage pipelines (exactly two routines, the second
   applied to the first's output) and three-stage pipelines (three routines
   in sequence). Single routines are exhausted (F6) and are not used.
2. **One record per name.** The source repeats names (131,909 distinct names
   in 174,258 records). The first eligible record of a name, in source order,
   is the only one considered, so pools are disjoint by name and not only by
   record.
3. **Exclusions, before any draw.**
   - every name in FRESH-1 or FRESH-2 (``rsi3/data/fresh_tasks.json``);
   - every record whose corpus-style name is a name in RSI-2's corpus,
     matched by name as ``rsi3.fresh`` does (for a pipeline the corpus-style
     name is its stages' corpus-style names joined by " then "; the raw name
     is also checked). RSI-2's corpus holds single routines, so this removes
     no pipeline; the count is recorded;
   - COMPOSE-24 is not a record of this file (``rsi3/compose24.py`` builds it
     from reference oracles), so its exclusion is behavioural: a list-to-list
     record whose every distinct example agrees with one of the 24
     ``reference_oracle(family, k)`` functions is removed.
4. **Stages.** The routine names that occur in eligible two-stage pipelines
   are split by group = int(sha256(name + str(J seed))) mod 3. Stage i
   (i = 1, 2, 3) holds the pipelines whose two routines both lie in group
   i - 1. From each, 136 are drawn: the first 36 drawn are stage-train, the
   next 100 stage-eval. If a group cannot supply 136, every stage shrinks to
   the smallest group's count (stage-train keeps 36/136 of it).
5. **J pools**, drawn after the stages from the remaining eligible two-stage
   records, in this order from one draw: probe 60, then per round r = 1..3
   selection 100 and confirmation 200, then final test 200. The 100
   three-stage final-test tasks come from a separate draw over eligible
   three-stage records.

**Draws.** A draw orders records by sha256(purpose | J seed | name) and takes
the first n. It is a keyed permutation: deterministic on every Python
version, and unpredictable without J's seed.

**Where things go.** Stage-eval, probe, selection, confirmation and final-test
pools go to ``rsi4/judge/pools/`` (judge-only). The stage-train tasks are what
the system learns on, like TRAIN, so they go to ``rsi4/data/stage_train.json``;
their hidden examples, like TRAIN's, reach only ``rsi3.verifier.FrozenVerifier``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rsi3.compose24 import FAMILIES, PARAMETERS, reference_oracle
from rsi3.fresh import (CORPUS as CORPUS_FILE, DATA as FRESH_FILE, SOURCE_COMMIT, _eligible,
                        components, corpus_style_name, to_task)
from rsi2.research.transfer import _distinct_examples

from . import registry

SOURCE_RECORDS = 174_258
SOURCE_SHA256 = "0dce7f8263548ecc796545bf1346e90685b586bc0cbdaf25688ba689fad3c4d0"
FLOWS = {2: [[0], [1]], 3: [[0], [1], [2]]}

# Which J operation may read each pool (evaluate.py enforces it).
USES = {"stage_eval": "evaluate", "probe": "sleep_check", "selection": "select",
        "confirmation": "confirm", "final_test": "final_test"}


def pool_names() -> list[str]:
    names = [f"stage_eval_S{i}" for i in range(1, registry.STAGES + 1)] + ["probe"]
    for r in range(1, registry.ROUNDS + 1):
        names += [f"selection_r{r}", f"confirmation_r{r}"]
    return names + ["final_test_2", "final_test_3"]


def use_of(pool: str) -> str:
    for prefix, use in USES.items():
        if pool.startswith(prefix):
            return use
    raise KeyError(f"unknown pool {pool!r}")


# ---- rules ------------------------------------------------------------------
def shape_of(record):
    """(stages, routines) for an eligible two- or three-stage pipeline, else None."""
    parts = components(record["name"])
    if len(parts) not in FLOWS:
        return None
    flows = [[value for kind, value in args if kind == "dyn"] for _, args in parts]
    if flows != FLOWS[len(parts)]:
        return None
    if not _eligible(record):
        return None
    try:
        to_task(record)
    except ValueError:
        return None
    return len(parts), tuple(routine for routine, _ in parts)


def pipeline_style_name(record) -> str:
    return " then ".join(corpus_style_name(r, a) for r, a in components(record["name"]))


def matches_compose24(record) -> bool:
    declared = record["type"]
    if declared.get("input") != "list-of-int" or declared.get("output") != "list-of-int":
        return False
    examples = _distinct_examples(record)
    for family in FAMILIES:
        for k in PARAMETERS:
            if all(reference_oracle(family, k, list(e["inputs"][0])) == e["output"]
                   for e in examples):
                return True
    return False


def group_of(routine: str, seed: int) -> int:
    return int(hashlib.sha256((routine + str(seed)).encode("utf-8")).hexdigest(), 16) % 3


def draw(records, purpose: str, seed: int, n: int) -> list:
    keyed = sorted(records, key=lambda r: hashlib.sha256(
        f"{purpose}|{seed}|{r['name']}".encode("utf-8")).hexdigest())
    if len(keyed) < n:
        raise ValueError(f"{purpose}: {len(keyed)} records, {n} needed")
    return keyed[:n]


def by_name(records) -> list:
    return sorted(records, key=lambda r: r["name"])


def exclusion_sets():
    fresh = json.loads(FRESH_FILE.read_text(encoding="utf-8"))
    fresh_names = {r["name"] for r in fresh["fresh1"] + fresh["fresh2"]}
    # Names only, as rsi3.fresh reads this file; no example of it is used.
    corpus_names = {t["name"] for t in json.loads(CORPUS_FILE.read_text(encoding="utf-8"))}
    return fresh_names, corpus_names


def build(source_records, seed: int) -> dict:
    """Every pool and the stage-train sets, with the counts behind each rule."""
    if len(source_records) != SOURCE_RECORDS:
        raise ValueError(f"source has {len(source_records)} records, expected {SOURCE_RECORDS}")
    fresh_names, corpus_names = exclusion_sets()
    counts = {"records": len(source_records), "eligible_two_stage_records": 0,
              "eligible_three_stage_records": 0, "duplicate_names_dropped": 0,
              "excluded_fresh": 0, "excluded_corpus_name": 0, "excluded_compose24": 0}
    seen, two, three, routines_of = set(), [], [], {}
    for record in source_records:
        shape = shape_of(record)
        if shape is None:
            continue
        stages, routines = shape
        counts["eligible_two_stage_records" if stages == 2
               else "eligible_three_stage_records"] += 1
        name = record["name"]
        if name in seen:
            counts["duplicate_names_dropped"] += 1
            continue
        seen.add(name)
        if name in fresh_names:
            counts["excluded_fresh"] += 1
            continue
        if name in corpus_names or pipeline_style_name(record) in corpus_names:
            counts["excluded_corpus_name"] += 1
            continue
        if matches_compose24(record):
            counts["excluded_compose24"] += 1
            continue
        (two if stages == 2 else three).append(record)
        routines_of[name] = routines
    counts["eligible_two_stage"] = len(two)
    counts["eligible_three_stage"] = len(three)
    routine_names = sorted({r for rec in two for r in routines_of[rec["name"]]})
    groups = {r: group_of(r, seed) for r in routine_names}
    counts["routines"] = len(routine_names)
    counts["routines_per_group"] = [sum(1 for g in groups.values() if g == i) for i in range(3)]

    candidates = {i: [rec for rec in two
                      if all(groups[r] == i - 1 for r in routines_of[rec["name"]])]
                  for i in range(1, registry.STAGES + 1)}
    counts["stage_candidates"] = {f"S{i}": len(c) for i, c in candidates.items()}
    per_stage = registry.STAGE_TRAIN + registry.STAGE_EVAL
    size = min(per_stage, *(len(c) for c in candidates.values()))
    n_train = registry.STAGE_TRAIN if size == per_stage else round(
        registry.STAGE_TRAIN * size / per_stage)
    counts["stage_size"], counts["stage_train_size"] = size, n_train
    stage_train, pools, used = {}, {}, set()
    for i, cands in candidates.items():
        drawn = draw(cands, f"rsi4-stage-S{i}", seed, size)
        stage_train[f"S{i}"] = by_name(drawn[:n_train])
        pools[f"stage_eval_S{i}"] = by_name(drawn[n_train:])
        used.update(r["name"] for r in drawn)

    remaining = [rec for rec in two if rec["name"] not in used]
    counts["remaining_two_stage"] = len(remaining)
    plan = [("probe", registry.PROBE)]
    for r in range(1, registry.ROUNDS + 1):
        plan += [(f"selection_r{r}", registry.SELECTION),
                 (f"confirmation_r{r}", registry.CONFIRMATION)]
    plan.append(("final_test_2", registry.FINAL_TWO_STAGE))
    ordered = draw(remaining, "rsi4-pools", seed, sum(n for _, n in plan))
    start = 0
    for pool, n in plan:
        pools[pool] = by_name(ordered[start:start + n])
        start += n
    pools["final_test_3"] = by_name(draw(three, "rsi4-final-three", seed,
                                         registry.FINAL_THREE_STAGE))
    counts["two_stage_used"] = len(used) + start
    counts["pool_sizes"] = {p: len(pools[p]) for p in pool_names()}
    return {"stage_train": stage_train, "pools": pools, "counts": counts,
            "groups": groups}


# ---- files ------------------------------------------------------------------
def _source_block() -> dict:
    return {"repository": "ellisk42/ec", "path": "data/list_tasks2.json",
            "commit": SOURCE_COMMIT, "license": "MIT", "records": SOURCE_RECORDS,
            "sha256": SOURCE_SHA256}


def write(built: dict, judge_dir: Path = registry.JUDGE_DIR) -> None:
    pools_dir = Path(judge_dir) / "pools"
    pools_dir.mkdir(parents=True, exist_ok=True)
    for pool in pool_names():
        payload = {"pool": pool, "use": use_of(pool), "source": _source_block(),
                   "public": 8, "records": built["pools"][pool]}
        (pools_dir / f"{pool}.json").write_text(json.dumps(payload, indent=1) + "\n",
                                               encoding="utf-8")
    build_record = {"source": _source_block(), "counts": built["counts"],
                    "groups": built["groups"]}
    (pools_dir / "BUILD.json").write_text(json.dumps(build_record, indent=1) + "\n",
                                          encoding="utf-8")
    stage_file = Path(judge_dir).parent / "data" / registry.STAGE_TRAIN_FILE.name
    stage_file.parent.mkdir(parents=True, exist_ok=True)
    stage_payload = {"source": _source_block(), "public": 8,
                     "rule": "OWNER_DIRECTIVE.md §4; built by rsi4/judge/pools.py",
                     "stages": built["stage_train"]}
    stage_file.write_text(json.dumps(stage_payload, indent=1) + "\n", encoding="utf-8")


def load_records(pool: str, judge_dir: Path = registry.JUDGE_DIR) -> list:
    path = Path(judge_dir) / "pools" / f"{pool}.json"
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def load_pool(pool: str, judge_dir: Path = registry.JUDGE_DIR) -> list:
    """Parsed tasks of a pool, hidden examples included. Judge process only."""
    if pool not in pool_names():
        raise KeyError(f"unknown pool {pool!r}")
    return [to_task(record) for record in load_records(pool, judge_dir)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--check", action="store_true",
                        help="rebuild and compare with the committed files; write nothing")
    args = parser.parse_args(argv)
    if registry.file_sha256(args.source) != SOURCE_SHA256:
        raise SystemExit("source file hash differs from the registered one")
    built = build(json.loads(args.source.read_text(encoding="utf-8")), registry.judge_seed())
    if args.check:
        same = all(load_records(p) == built["pools"][p] for p in pool_names())
        stages = json.loads(registry.STAGE_TRAIN_FILE.read_text(encoding="utf-8"))["stages"]
        same = same and stages == built["stage_train"]
        print(json.dumps({"identical": same}))
        raise SystemExit(0 if same else 1)
    write(built)
    print(json.dumps(built["counts"], indent=1))


if __name__ == "__main__":
    main()
