"""Acceleration readouts: does a generation's growth raise the next generation's gain?

Every RSI-3 arm so far reaches a plateau: TRAIN rises for a few
generations, then stops. "Recursive" improvement would show as the
opposite: growth of the system's own language in generation g (library
entries adopted by RSI-2's MDL learner, concepts the self-model invented
and the verifier confirmed, or a self-curriculum pool) raising the gain
in generation g + 1, and a gain curve whose slope does not decay. This
module turns a run record into that readout, so every results file can
state it from the same arithmetic. It reads run files only and executes
no task.

Readouts, per run (``readout``):

- ``gains``: TRAIN solves gained per generation (generation 1 counts from
  zero).
- ``growth``: library entries added per generation (RSI-2's MDL
  adoptions plus adopted concepts; the library size is read from the
  sleep record, so a removed entry would count negative).
- ``slope``: mean gain over the first and second halves of the run, and
  ``decays``: whether the second half's mean gain is lower.
- ``plateau``: generations since the last gain.
- ``growth_then_gain``: the 2 x 2 table over generation pairs (g, g + 1):
  did the library grow in g, and was there a gain in g + 1. ``after_growth``
  and ``after_none`` are the mean next-generation gains in the two rows.
  ``raises`` is True when the mean gain after a growth generation exceeds
  the mean gain after a generation without growth, with at least one pair
  in each row; None when a row is empty. Growth is mostly caused by the
  same generation's solves and solves cluster early, so ``given_no_gain``
  and ``given_gain`` repeat the comparison with the gain in g held fixed.
- ``accelerates``: the last quarter's mean gain exceeds the previous
  quarter's.

With 16 generations these are descriptive, not tests of significance;
a results file that cites them must say so.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _series(record: dict) -> dict:
    generations = record["generations"]
    solved = [int(g["train_solved"]) for g in generations]
    library = [int(g["sleep"]["library_entries"]) for g in generations]
    previous = 0
    gains = []
    for value in solved:
        gains.append(value - previous)
        previous = value
    growth = [library[0]] + [b - a for a, b in zip(library, library[1:])]
    curriculum = [int((g["sleep"].get("curriculum") or {}).get("pool", 0)) for g in generations]
    return {"solved": solved, "library": library, "gains": gains, "growth": growth,
            "curriculum_pool": curriculum}


def _mean(values) -> float | None:
    values = list(values)
    return sum(values) / len(values) if values else None


def readout(record: dict) -> dict:
    """The readouts listed in the module docstring, from one run record."""
    series = _series(record)
    gains, growth = series["gains"], series["growth"]
    n = len(gains)
    half = n // 2
    first, second = _mean(gains[:half]), _mean(gains[half:])
    last_gain = max((i + 1 for i, g in enumerate(gains) if g > 0), default=0)
    table = {"grew_then_gain": 0, "grew_then_none": 0, "flat_then_gain": 0, "flat_then_none": 0}
    after_growth, after_none = [], []
    for g in range(n - 1):
        grew = growth[g] > 0
        gained = gains[g + 1] > 0
        key = ("grew" if grew else "flat") + "_then_" + ("gain" if gained else "none")
        table[key] += 1
        (after_growth if grew else after_none).append(gains[g + 1])
    # Growth is mostly caused by the same generation's solves (RSI-2's MDL
    # learner compresses new solutions), and solves cluster early, so the
    # table above is confounded by the gain in g itself. The conditioned
    # rows hold the gain in g fixed: pairs where g gained nothing, split by
    # whether the library still grew, and pairs where g gained.
    conditioned = {}
    for label, select in (("given_no_gain", lambda g: gains[g] == 0),
                          ("given_gain", lambda g: gains[g] > 0)):
        rows = [(growth[g] > 0, gains[g + 1]) for g in range(n - 1) if select(g)]
        grew = _mean(v for flag, v in rows if flag)
        flat = _mean(v for flag, v in rows if not flag)
        conditioned[label] = {"after_growth": grew, "after_none": flat,
                              "pairs": (sum(1 for flag, _ in rows if flag),
                                        sum(1 for flag, _ in rows if not flag)),
                              "raises": None if grew is None or flat is None else grew > flat}
    quarter = max(n // 4, 1)
    last_quarter = _mean(gains[-quarter:])
    previous_quarter = _mean(gains[-2 * quarter:-quarter]) if n >= 2 * quarter else None
    mean_after_growth, mean_after_none = _mean(after_growth), _mean(after_none)
    raises = (None if mean_after_growth is None or mean_after_none is None
              else mean_after_growth > mean_after_none)
    return {
        "arm": record.get("arm"), "seed": record.get("seed"), "generations": n,
        "solved": series["solved"], "gains": gains, "library": series["library"],
        "growth": growth, "curriculum_pool": series["curriculum_pool"],
        "slope": {"first_half": first, "second_half": second,
                  "decays": (None if first is None or second is None else second < first)},
        "plateau": n - last_gain,
        "growth_then_gain": {**table, "after_growth": mean_after_growth,
                             "after_none": mean_after_none, "raises": raises,
                             **conditioned},
        "accelerates": (None if previous_quarter is None else last_quarter > previous_quarter),
    }


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def markdown(readouts: list[dict]) -> str:
    """One table row per run, for a results file."""
    lines = ["| Arm | Seed | TRAIN gains g1..gN | Library growth g1..gN | Slope first/second half "
             "| Plateau (gens) | Next gain after growth / after none (pairs) "
             "| Same, given no gain in g | Last quarter accelerates |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in readouts:
        t = r["growth_then_gain"]
        pairs = (f"{t['grew_then_gain']}+{t['grew_then_none']} / "
                 f"{t['flat_then_gain']}+{t['flat_then_none']}")
        c = t["given_no_gain"]
        lines.append(
            f"| {r['arm']} | {r['seed']} | {' '.join(map(str, r['gains']))} | "
            f"{' '.join(map(str, r['growth']))} | {_fmt(r['slope']['first_half'])} / "
            f"{_fmt(r['slope']['second_half'])} | {r['plateau']} | "
            f"{_fmt(t['after_growth'])} / {_fmt(t['after_none'])} ({pairs}) | "
            f"{_fmt(c['after_growth'])} / {_fmt(c['after_none'])} "
            f"({c['pairs'][0]} / {c['pairs'][1]}) | {_fmt(r['accelerates'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", type=Path, nargs="+", help="run record JSON files")
    parser.add_argument("--json", action="store_true", help="print the readouts as JSON")
    args = parser.parse_args(argv)
    readouts = [readout(json.loads(path.read_text(encoding="utf-8"))) for path in args.runs]
    if args.json:
        print(json.dumps(readouts, indent=1))
    else:
        print(markdown(readouts), end="")


if __name__ == "__main__":
    main()
