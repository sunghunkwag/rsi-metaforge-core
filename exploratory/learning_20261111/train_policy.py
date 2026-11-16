"""Train the search policy from the system's own experience (development script).

Experience, all from the learning partitions of configuration B and from programs the engine
runs itself:
  real    verified programs of generation 0 on learning tasks (its student and first teacher run)
  real2   compositions of two such programs on public inputs of the learning tasks
  pool    programs of the engine's own enumeration, alone and composed
  lift    element functions mapped or filtered over the input

    python train_policy.py <out.json> [--seed N] [--runs R] [--steps S]

Prints, for held-out experience of each kind and for the solved tasks of FRESH-4 (a development
set), how often every item of the program is among the K most likely items.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

import numpy as np

import dreams
import features
from policy import Policy, Replay, learn
from rsi5 import partitions
from rsi5.dsl.pretty_parse import parse
from rsi5.dsl.vocabulary import VOCABULARIES

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(HERE, "..", "shift_loop_20261110", "results")
LEARN = ("train", "near", "validation", "far", "far2", "fresh1")
KS = (10, 14, 18, 22)


def real_experience(labels=("student0", "teacher1")) -> tuple:
    """(programs: key -> term, experience: [(examples, items, key)]) of generation 0's own
    verified programs on the learning tasks, from the stored loop report of Addendum 8."""
    loop = json.load(open(os.path.join(STUDY, "confirm.json")))["loop"]
    texts = {}
    for run in loop["timeline"]:
        if run["label"] in labels:
            for key, entry in run["programs"].items():
                if key.split("/")[0] in LEARN:
                    texts.setdefault(key, entry[0])
    tasks = {f"{p}/{task.name}": task for p in LEARN for task in partitions.load(p)}
    names = set(VOCABULARIES["restored"].primitives)
    programs = {key: parse(text) for key, text in texts.items()}
    experience = [(tasks[key].examples, sorted(dreams.items_of(text, names)), key) for key, text in texts.items()]
    return programs, experience


def coverage(policy: Policy, rows) -> dict:
    """For each K: the share of rows whose items are all among the K most likely."""
    out = {}
    if not rows:
        return out
    ranks = []
    for x, items in rows:
        order = policy.ranked(x)
        position = {name: i for i, name in enumerate(order)}
        ranks.append(max((position[i] for i in items if i in position), default=0))
    for k in KS:
        out[k] = round(sum(1 for r in ranks if r < k) / len(ranks), 3)
    return out


def main() -> None:
    out_path = sys.argv[1]
    option = lambda flag, default: type(default)(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default
    seed, runs, steps = option("--seed", 0), option("--runs", 120), option("--steps", 6000)
    vocabulary = VOCABULARIES["restored"]
    names = list(vocabulary.primitives)
    rng = random.Random(seed)
    started = time.perf_counter()
    pool = dreams.input_pool(LEARN)
    programs, real = real_experience()
    real2 = dreams.composed_programs(programs, pool, rng, 40 * runs, set(names))
    pooled = dreams.make(vocabulary, pool, runs, seed + 1, budget=20_000, singles=40, pairs=40, names=names)
    lift = []
    for _ in range(runs):
        lift.extend(dreams.lifted(vocabulary, rng.sample(pool, 8), 3000, rng, 40, set(names)))
    print(f"experience: real {len(real)}, real2 {len(real2)}, pool {len(pooled)}, lift {len(lift)} | "
          f"{round(time.perf_counter() - started)} s", flush=True)
    replay, held = Replay(seed=seed), {}
    for tag, rows in (("real", real), ("real2", real2), ("pool", pooled), ("lift", lift)):
        rng.shuffle(rows)
        cut = max(1, len(rows) // 10) if tag != "real" else 0
        held[tag] = [(features.featurize(r[0]), r[1]) for r in rows[:cut]]
        for r in rows[cut:]:
            replay.add(features.featurize(r[0]), r[1], tag)
    policy = Policy(features.SIZE, names, seed)
    mix = {"real": 0.15, "real2": 0.35, "pool": 0.25, "lift": 0.25}
    for chunk in range(steps // 1000):
        loss = learn(policy, replay, 1000, mix=mix)
        print(f"step {1000 * (chunk + 1)} loss {loss:.3f} | held-out all-in-top-K " +
              "; ".join(f"{tag} {coverage(policy, rows)}" for tag, rows in held.items() if rows), flush=True)
    json.dump({"policy": policy.to_json(), "seed": seed, "runs": runs, "steps": steps, "mix": mix,
               "experience": {"real": len(real), "real2": len(real2), "pool": len(pooled), "lift": len(lift)}},
              open(out_path, "w"))
    # development check on tasks that are not learning tasks: the solved tasks of FRESH-4
    import fresh4
    stored = json.load(open(os.path.join(STUDY, "confirm.json")))["rows"]
    tasks = {f"fresh4/{task.name}": task for task in fresh4.make()}
    solved = {}
    for label, row in stored.items():
        if label.endswith(":fresh4"):
            for key in row["sound"]:
                solved.setdefault(key, row["programs"][key][0])
    rows = [(features.featurize(tasks[key].examples), sorted(dreams.items_of(text, set(names))))
            for key, text in solved.items()]
    print(f"FRESH-4 (development): {len(rows)} tasks some arm solves soundly; all items among the top K: "
          f"{coverage(policy, rows)}")
    gen0 = {key for label, row in stored.items() if label.startswith("gen0@") and label.endswith(":fresh4")
            for key in row["sound"]}
    rows0 = [(features.featurize(tasks[key].examples), sorted(dreams.items_of(solved[key], set(names)))) for key in gen0]
    print(f"  of them generation 0 solves at some budget: {len(rows0)}; coverage {coverage(policy, rows0)}")
    sizes = sorted(len(items) for _, items in rows)
    print(f"  items per solved program: median {sizes[len(sizes) // 2]}, max {sizes[-1]}")


if __name__ == "__main__":
    main()
