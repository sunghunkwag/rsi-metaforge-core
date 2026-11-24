"""Chains of self-modification of design s, run on tables of measured runs.

``rsi6/experiments/dev_grid.py`` measures every mechanism of design s's list on a category. With
those tables an improver needs no new runs: an evaluation of a version on a problem (a category
and a seed) is a row that already exists. So a chain can be started from every mechanism of the
list and repeated many times, and what is compared is settled by arithmetic on measured runs.

**The improver is the learner's acquisition.** ``improve`` calls ``design_s.search``, the function
the learner acquires with, on a task of the same shape as an acquisition:

===========================  ==================================  ====================================
                             acquisition (``_WeightTask``)       improvement (``VersionTask``)
===========================  ==================================  ====================================
point                        the weights of the policy           a version: one coordinate per field
                                                                 of the list, in steps of the list
start                        the prior weights                   the incumbent version
training problems            16 instances of the category        16 (category, seed) pairs, the same
                                                                 number from every discovery category
one evaluation               one construction on an instance     one run of the version on the pair
its key (lower is better)    the totals of the construction      minus the acquired score of the run
its cost                     counted units of the construction   CPU-seconds of the incumbent's run
budget                       ``train`` x the cost of every       ``train`` x the cost of every
                             problem once                        problem once
held-back check              start against end, strict           the same: no nominee unless the end
                                                                 beats the incumbent on held-back pairs
===========================  ==================================  ====================================

The fields that govern the search (population, batch, share kept, spread, the two adaptive
steps, the held-back share) are read from the version that is doing the improving. In the
*recursive* arm that is the current version of the chain; in the *frozen* arm it is the version
the chain started from, whatever has been adopted since; the *random* arm nominates a version of
the list drawn uniformly, the *neighbour* arm a uniformly drawn change of one field. Every arm's
nominee goes through the same gate (``Gate``: the registered rule of ``rsi6/meta/rounds.py`` on
categories the improver does not see), and replaces the current version only if it passes.

    python -m rsi6.meta.chain_s simulate DIR --discovery ... --gate ... --test ... --out chains.json
    python -m rsi6.meta.chain_s quality  DIR --discovery ... --gate ... --test ... --out quality.json
    python -m rsi6.meta.chain_s read DIR --chains chains.json ... [--quality quality.json ...] --out reading.json

``simulate`` and ``quality`` do not read the test categories; they only write their names into the
file, so that ``read`` scores each fold on the categories it was promised.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np

from rsi6.learner import design_s
from rsi6.meta.rounds import RULES

ARMS = ("recursive", "frozen", "random", "neighbour")
NAMES = ("untrained", "acquired", "untrained_a", "acquired_a", "untrained_b", "acquired_b", "cpu", "learned", "rounds", "used")


class Tables:
    """The tables of a directory, per category: arrays ``[seed, version]``."""

    def __init__(self, directory: str):
        self.versions = design_s.mechanisms()
        self.shape = tuple(len(design_s.LEVELS[f]) for f in design_s.MECHANISM)
        self.cats = {}
        parts = {}
        for path in sorted(glob.glob(os.path.join(directory, "**", "grid_*.json"), recursive=True)):
            d = json.load(open(path))
            if d.get("smoke"):
                continue
            if d["fields"] != list(design_s.MECHANISM) or len(d["versions"]) != len(self.versions):
                raise ValueError(f"{path}: not a table of this list of mechanisms")
            parts.setdefault(d["category"], []).append(d)
        for category, files in parts.items():
            files.sort(key=lambda d: d["seeds"][0])
            seeds = [s for d in files for s in d["seeds"]]
            if len(set(seeds)) != len(seeds):
                raise ValueError(f"{category}: a seed appears in two files")
            table = {name: np.concatenate([np.asarray(d["table"][name], dtype=float) for d in files]) for name in NAMES}
            table["seeds"] = seeds
            table["file"] = np.concatenate([np.full(len(d["seeds"]), i) for i, d in enumerate(files)])
            self.cats[category] = table

    def number(self, point) -> int:
        """The version a point of the list stands for."""
        return int(np.ravel_multi_index(tuple(int(x) for x in point), self.shape))

    def point(self, k: int) -> np.ndarray:
        return np.array(np.unravel_index(int(k), self.shape), dtype=float)

    def mean(self, categories, name: str = "acquired", seeds=None) -> np.ndarray:
        """Per version: the mean over the categories of the mean over seeds."""
        rows = []
        for c in categories:
            a = self.cats[c][name]
            rows.append(a.mean(axis=0) if seeds is None else a[seeds[c]].mean(axis=0))
        return np.mean(rows, axis=0)


class VersionTask:
    """The improver's task (see the table in the module's docstring)."""

    def __init__(self, tables: Tables, categories, incumbent: int, rng, train: float = 40.0, n_problems: int = 16):
        self.tables, self.shape = tables, np.array(tables.shape)
        per = max(1, n_problems // len(categories))
        self.problems = []
        for c in categories:
            for s in rng.choice(len(tables.cats[c]["seeds"]), size=per, replace=False):
                self.problems.append((c, int(s)))
        self.n, self.dim = len(self.problems), len(tables.shape)
        self.start = tables.point(incumbent)
        self.costs = [float(tables.cats[c]["cpu"][s, incumbent]) for c, s in self.problems]
        self.limit, self.used, self.evaluations = train * sum(self.costs), 0.0, 0

    def cost(self, i) -> float:
        return self.costs[i]

    def left(self) -> float:
        return self.limit - self.used

    def project(self, points):
        return np.clip(np.rint(points), 0, self.shape - 1)

    def evaluate(self, points, problems, rng):
        need = len(points) * sum(self.costs[i] for i in problems)
        if self.left() < need:
            return None
        numbers = np.ravel_multi_index(tuple(points.astype(np.int64).T), self.tables.shape)
        keys = np.zeros((len(points), len(problems), 2))
        for j, i in enumerate(problems):
            c, s = self.problems[i]
            keys[:, j, 1] = -self.tables.cats[c]["acquired"][s, numbers]
        self.used += need
        self.evaluations += len(points) * len(problems)
        return keys


def improve(tables: Tables, categories, improver: int, incumbent: int, rng, train: float = 40.0):
    """One search for a better version than the incumbent, by the mechanism of the version
    ``improver``. Returns the nominee (a version number, or ``None``) and the search's report."""
    task = VersionTask(tables, categories, incumbent, rng, train)
    report = {}
    point, learned = design_s.search(task, tables.versions[improver], rng, report)
    nominee = tables.number(point) if learned else None
    if nominee == incumbent:
        nominee = None
    report["evaluations"] = task.evaluations
    return nominee, report


class Gate:
    """The registered adoption rule (``rounds.gate``, then ``rounds.confirm`` above zero) on tables.

    The gate reads the first half of a category's seeds and the first half of its fresh
    instances; the confirmation reads the other seeds and the other instances. The resampling is
    that of ``rounds.gate``: runs within a category, then the mean over categories."""

    def __init__(self, tables: Tables, categories, rules: dict = RULES, seed: int = 700):
        self.tables, self.categories, self.rules, self.memo = tables, list(categories), rules, {}
        self.gate_seeds = {c: np.arange(len(tables.cats[c]["seeds"]) // 2) for c in self.categories}
        self.conf_seeds = {c: np.arange(len(tables.cats[c]["seeds"]) // 2, len(tables.cats[c]["seeds"])) for c in self.categories}
        rng = np.random.default_rng(seed)
        self.draws = {c: [] for c in self.categories}
        for _ in range(rules["bootstrap"]):
            for c in self.categories:
                n = len(self.gate_seeds[c])
                self.draws[c].append(rng.choice(n, size=n))
        self.draws = {c: np.array(rows) for c, rows in self.draws.items()}

    def _changes(self, incumbent, nominee, seeds, half):
        acquired, gain = [], []
        for c in self.categories:
            t = self.tables.cats[c]
            a = t["acquired_" + half][seeds[c]]
            u = t["untrained_" + half][seeds[c]]
            d_acq = a[:, nominee] - a[:, incumbent]
            acquired.append(d_acq)
            gain.append(d_acq - (u[:, nominee] - u[:, incumbent]))
        return acquired, gain

    def decide(self, incumbent: int, nominee: int) -> dict:
        key = (int(incumbent), int(nominee))
        if key not in self.memo:
            rules = self.rules
            acquired, gain = self._changes(incumbent, nominee, self.gate_seeds, "a")
            both = min(float(np.mean([x.mean() for x in acquired])), float(np.mean([x.mean() for x in gain])))
            means = np.mean([g[self.draws[c]].mean(axis=1) for c, g in zip(self.categories, gain)], axis=0)
            low = float(np.quantile(means, 1.0 - rules["level"]))
            cpu = [self.tables.cats[c]["cpu"][self.gate_seeds[c]] for c in self.categories]
            ratio = float(sum(x[:, nominee].sum() for x in cpu) / max(sum(x[:, incumbent].sum() for x in cpu), 1e-9))
            c_acq, c_gain = self._changes(incumbent, nominee, self.conf_seeds, "b")
            confirmation = min(float(np.mean([x.mean() for x in c_acq])), float(np.mean([x.mean() for x in c_gain])))
            conditions = {"improvement": both >= rules["margin"], "gain_interval": low > 0.0, "cpu": ratio <= rules["cpu_ratio"],
                          "confirmation": confirmation > 0.0}
            self.memo[key] = {"mean_min": both, "gain_lower_bound": low, "cpu_ratio": ratio, "confirmation": confirmation,
                              "conditions": conditions, "adopted": bool(all(conditions.values()))}
        return self.memo[key]


def nominate(tables: Tables, arm: str, discovery, start: int, current: int, rng, train: float = 40.0):
    if arm == "recursive":
        return improve(tables, discovery, current, current, rng, train)[0]
    if arm == "frozen":
        return improve(tables, discovery, start, current, rng, train)[0]
    if arm == "random":
        k = int(rng.integers(len(tables.versions) - 1))
        return k + (k >= current)
    if arm == "neighbour":
        point = tables.point(current)
        f = int(rng.integers(len(point)))
        others = [x for x in range(tables.shape[f]) if x != int(point[f])]
        point[f] = others[int(rng.integers(len(others)))]
        return tables.number(point)
    raise ValueError(arm)


def chain(tables: Tables, gate: Gate, arm: str, discovery, start: int, generations: int, seed: tuple, train: float = 40.0):
    """One chain: per generation one nominee and one gate. Returns the current version after every
    generation and the nominees. Generation ``g`` of repetition ``seed`` uses the same random stream in
    every arm, so the recursive and the frozen arm are the same chain until their improvers differ."""
    current, path, nominees = start, [start], []
    for g in range(generations):
        rng = np.random.default_rng(list(seed) + [g])
        nominee = nominate(tables, arm, discovery, start, current, rng, train)
        nominees.append(-1 if nominee is None else nominee)
        if nominee is not None and gate.decide(current, nominee)["adopted"]:
            current = nominee
        path.append(current)
    return path, nominees


def simulate(tables: Tables, discovery, gate_categories, starts, reps: int, generations: int, seed: int, arms=ARMS,
             train: float = 40.0, progress=None) -> dict:
    gate = Gate(tables, gate_categories)
    out = {arm: {"paths": [], "nominees": []} for arm in arms}
    for n, start in enumerate(starts):
        for arm in arms:
            paths, noms = [], []
            for r in range(reps):
                path, nominees = chain(tables, gate, arm, discovery, start, generations, (seed, start, r), train)
                paths.append(path)
                noms.append(nominees)
            out[arm]["paths"].append(paths)
            out[arm]["nominees"].append(noms)
        if progress and (n + 1) % progress == 0:
            print(f"{n + 1} of {len(starts)} starts", flush=True)
    return {"discovery": list(discovery), "gate": list(gate_categories), "starts": [int(s) for s in starts], "reps": reps,
            "generations": generations, "seed": seed, "train": train, "arms": out,
            "gates_decided": len(gate.memo), "gates_passed": int(sum(1 for d in gate.memo.values() if d["adopted"]))}


def quality(tables: Tables, discovery, gate_categories, incumbents, reps: int, seed: int, train: float = 40.0, progress=None):
    """For every version of the list as improver: what one generation of it yields from each of the
    given incumbents. Returns ``after[improver, incumbent, rep]``, the version after the gate."""
    gate = Gate(tables, gate_categories)
    n = len(tables.versions)
    after = np.zeros((n, len(incumbents), reps), dtype=np.int64)
    for i in range(n):
        for j, incumbent in enumerate(incumbents):
            for r in range(reps):
                rng = np.random.default_rng([seed, incumbent, r])
                nominee, _ = improve(tables, discovery, i, incumbent, rng, train)
                ok = nominee is not None and gate.decide(incumbent, nominee)["adopted"]
                after[i, j, r] = nominee if ok else incumbent
        if progress and (i + 1) % progress == 0:
            print(f"{i + 1} of {n} improvers", flush=True)
    return after


def _ranks(x) -> np.ndarray:
    """Ranks with ties sharing their mean rank."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x))
    ranks[order] = np.arange(len(x), dtype=float)
    for value in np.unique(x):
        same = x == value
        if same.sum() > 1:
            ranks[same] = ranks[same].mean()
    return ranks


def spearman(x, y) -> float:
    a, b = _ranks(x), _ranks(y)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def read(tables: Tables, folds: list, boot: int = 2000, seed: int = 900) -> dict:
    """What the chains came to on the test categories, which no improver and no gate read.

    ``folds``: one entry per assignment of the categories to roles: ``{"result": the output of
    simulate, "test": the test categories, and optionally "after" and "incumbents" from quality}``.

    Per arm and generation: the mean, over every start and repetition, of the acquired score of the
    chain's current version minus that of its start (mean over the test categories of the mean over
    seeds). The differences between arms are differences of these means. A statistic of several
    folds is the mean of the folds' statistics. The points given with them come from resampling the
    seeds of the test categories (every version shares a seed's instances, so a category's seeds are
    resampled together for all versions); the chains themselves are kept as they ran."""
    pairs = (("recursive", "frozen"), ("recursive", "random"), ("recursive", "neighbour"), ("frozen", "random"))
    prepared = []
    for fold in folds:
        result = fold["result"]
        if set(fold["test"]) & (set(result["discovery"]) | set(result["gate"])):
            raise ValueError("a test category was read by the chains")
        prepared.append({"test": list(fold["test"]), "paths": {arm: np.array(result["arms"][arm]["paths"]) for arm in result["arms"]},
                         "after": None if fold.get("after") is None else np.asarray(fold["after"]),
                         "incumbents": None if fold.get("incumbents") is None else np.asarray(fold["incumbents"])})

    def stats(fold, score):
        paths = fold["paths"]
        out = {arm: (score[p] - score[p[:, :, :1]]).mean(axis=(0, 1)) for arm, p in paths.items()}
        for x, y in pairs:
            if x in paths and y in paths:
                out[f"{x}-{y}"] = out[x] - out[y]
        if fold["after"] is not None:
            gain = (score[fold["after"]] - score[fold["incumbents"]][None, :, None]).mean(axis=(1, 2))
            order = np.argsort(-score, kind="stable")
            third = len(order) // 3
            out["alignment"] = np.array([spearman(score, gain)])
            out["yield_of_best_third_as_improvers"] = np.array([gain[order[:third]].mean()])
            out["yield_of_worst_third_as_improvers"] = np.array([gain[order[-third:]].mean()])
            out["yield_best_minus_worst_third"] = out["yield_of_best_third_as_improvers"] - out["yield_of_worst_third_as_improvers"]
        return out

    def every(chosen=None):
        per = [stats(fold, tables.mean(fold["test"], seeds=chosen)) for fold in prepared]
        return per, {name: np.mean([x[name] for x in per], axis=0) for name in per[0]}

    per_point, point = every()
    rng = np.random.default_rng(seed)
    categories = sorted({c for fold in prepared for c in fold["test"]})
    draws, per_draws = {name: [] for name in point}, [{name: [] for name in point} for _ in prepared]
    for _ in range(boot):
        chosen = {c: rng.choice(len(tables.cats[c]["seeds"]), size=len(tables.cats[c]["seeds"])) for c in categories}
        per, mean = every(chosen)
        for name in point:
            draws[name].append(mean[name])
            for k in range(len(prepared)):
                per_draws[k][name].append(per[k][name])

    def row(value, d):
        d = np.array(d)
        return {"mean": [round(float(x), 5) for x in value], "q05": [round(float(x), 5) for x in np.quantile(d, 0.05, axis=0)],
                "q95": [round(float(x), 5) for x in np.quantile(d, 0.95, axis=0)],
                "share_at_or_below_zero": [round(float(x), 4) for x in (d <= 0).mean(axis=0)]}

    first = folds[0]["result"]
    reading = {"folds": len(folds), "reps": first["reps"], "generations": first["generations"], "starts": len(first["starts"]),
               "bootstrap": boot, "statistics": {name: row(point[name], draws[name]) for name in point}, "per_fold": []}
    named = {"generation 0 of the first design": {"model.batch": 4}, "the version process d adopted": {"model.batch": 2}}
    for k, (fold, raw) in enumerate(zip(prepared, folds)):
        result, paths = raw["result"], fold["paths"]
        score = tables.mean(fold["test"])
        entry = {"test": fold["test"], "discovery": result["discovery"], "gate": result["gate"],
                 "statistics": {name: row(per_point[k][name], per_draws[k][name]) for name in point},
                 # not resampled: how often a generation nominated and adopted, and the same means on the categories the chains read
                 "nominated_per_generation": {arm: [round(float(x), 4) for x in (np.array(result["arms"][arm]["nominees"]) >= 0).mean(axis=(0, 1))]
                                              for arm in paths},
                 "adopted_per_generation": {arm: [round(float(x), 4) for x in (p[:, :, 1:] != p[:, :, :-1]).mean(axis=(0, 1))]
                                            for arm, p in paths.items()},
                 "score_of_list_on_test": {"best": round(float(score.max()), 5), "mean": round(float(score.mean()), 5),
                                           "worst": round(float(score.min()), 5)},
                 "named_starts": {}}
        for label, categories_ in (("on_discovery", result["discovery"]), ("on_gate", result["gate"])):
            other = tables.mean(categories_)
            entry[label] = {arm: [round(float(x), 5) for x in (other[p] - other[p[:, :, :1]]).mean(axis=(0, 1))] for arm, p in paths.items()}
        for label, change in named.items():
            number = tables.number(design_s.index_of(design_s.validate(dict(design_s.default(), **change))))
            if number in result["starts"]:
                at = result["starts"].index(number)
                entry["named_starts"][label] = {
                    "version": number, "score": round(float(score[number]), 5), "rank_in_list": int((score > score[number]).sum()) + 1,
                    **{arm: [round(float(x), 5) for x in (score[p[at]] - score[number]).mean(axis=0)] for arm, p in paths.items()},
                    "changed_by_the_end": {arm: round(float((p[at][:, -1] != number).mean()), 4) for arm, p in paths.items()}}
        reading["per_fold"].append(entry)
    return reading


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("simulate", "quality"):
        cmd = sub.add_parser(name)
        cmd.add_argument("directory")
        cmd.add_argument("--discovery", nargs="+", required=True)
        cmd.add_argument("--gate", nargs="+", required=True)
        cmd.add_argument("--test", nargs="+", required=True)
        cmd.add_argument("--train", type=float, default=40.0)
        cmd.add_argument("--out", required=True)
        if name == "simulate":
            cmd.add_argument("--reps", type=int, default=30)
            cmd.add_argument("--generations", type=int, default=4)
            cmd.add_argument("--seed", type=int, default=1)
        else:
            cmd.add_argument("--incumbents", type=int, default=40)
            cmd.add_argument("--reps", type=int, default=6)
            cmd.add_argument("--seed", type=int, default=2)
    rd = sub.add_parser("read")
    rd.add_argument("directory")
    rd.add_argument("--chains", nargs="+", required=True)
    rd.add_argument("--quality", nargs="*", default=[])
    rd.add_argument("--boot", type=int, default=2000)
    rd.add_argument("--out", required=True)
    args = parser.parse_args()
    tables = Tables(args.directory)
    if args.command == "read":
        if args.quality and len(args.quality) != len(args.chains):
            raise SystemExit("one quality file per chains file, in the same order, or none")
        folds = []
        for k, path in enumerate(args.chains):
            result = json.load(open(path))
            fold = {"result": result, "test": result["test"]}
            if args.quality:
                q = json.load(open(args.quality[k]))
                if (q["discovery"], q["gate"], q["test"]) != (result["discovery"], result["gate"], result["test"]):
                    raise SystemExit(f"{args.quality[k]} is not of the fold of {path}")
                fold.update(after=q["after"], incumbents=q["incumbents"])
            folds.append(fold)
        reading = read(tables, folds, boot=args.boot)
        json.dump(reading, open(args.out, "w"), indent=1)
        for name, row in reading["statistics"].items():
            print(f"{name:36s} mean {row['mean']}  q05 {row['q05']}")
        return 0
    missing = [c for c in args.discovery + args.gate + args.test if c not in tables.cats]
    if missing:
        raise SystemExit(f"no table for {missing}")
    sets = [set(args.discovery), set(args.gate), set(args.test)]
    if sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2]:
        raise SystemExit("a category has one role in a fold: discovery, gate or test")
    if args.command == "simulate":
        result = simulate(tables, args.discovery, args.gate, range(len(tables.versions)), args.reps, args.generations, args.seed,
                          train=args.train, progress=36)
    else:
        rng = np.random.default_rng([args.seed, 0])
        incumbents = sorted(int(k) for k in rng.choice(len(tables.versions), size=args.incumbents, replace=False))
        after = quality(tables, args.discovery, args.gate, incumbents, args.reps, args.seed, train=args.train, progress=36)
        result = {"discovery": args.discovery, "gate": args.gate, "incumbents": incumbents, "reps": args.reps, "seed": args.seed,
                  "train": args.train, "after": after.tolist()}
    result["test"] = list(args.test)
    result["seeds"] = {c: tables.cats[c]["seeds"] for c in sorted(tables.cats)}
    json.dump(result, open(args.out, "w"))
    print("written", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
