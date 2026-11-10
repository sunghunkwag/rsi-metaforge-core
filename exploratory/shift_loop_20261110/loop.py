"""The four-idea loop over the hybrid harness (exploratory, report-only).

At every state the loop tries moves in a fixed order; a move is one generation run of every
task at the per-task budget, and it is accepted only if verified learning-set solves rise.
  compress   L: up to 3 new symbols by description-length gain over the verified programs
  apoptosis  A (idea 1): cut 60% of each space's symbols, least used first
  unused     A': cut only the symbols no verified learning program uses
  entropy    E (idea 2): turn on seeded mutation of near misses
A rejected move goes on the ban list. When no move is accepted the loop rolls back one accepted
step, bans it and branches again (T, idea 3). Fusion (idea 4) is part of the fixed machinery.

Every decision reads the learning partitions only. Held-out partitions are run each time for
the record and never consulted.

    python loop.py <budget> <components> <out.json> <config A|B> [workers] [--moves m1,m2,..]
                   [--max-runs N] [--no-rollback]
"""
from __future__ import annotations

import json
import random
import sys
import time

import hybrid
from hybrid import ALL, Harness, spec_of, summary

import compress
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import Lam, term_from_dict, term_to_dict
from rsi5.dsl.types import INT, arrows
from rsi5.dsl.vocabulary import RESTORED

PER_GENERATION = 3
MAX_ROLLBACKS = 3
CUT = 0.6
CONFIGS = {"A": ("train", "near"),
           "B": ("train", "near", "validation", "far", "far2", "fresh1")}
MOVES = ("compress", "apoptosis", "unused", "entropy")


def base_symbols() -> list:
    return list(RESTORED.primitives) + [f"int:{c}" for c in RESTORED.integer_constants]


def _nodes(term):
    yield term
    for child in term.children:
        yield from _nodes(child)


def symbols_of(term, library) -> list:
    """Symbols a program spends, after folding it with the library."""
    compact = compress.rewrite(term, library) if library else term
    found = []
    for node in _nodes(compact):
        if node.tag == "prim":
            found.append(node.value)
        elif node.tag == "int":
            found.append(f"int:{node.value}")
    return found


def split_spaces(term, route):
    """(element-space part, list-space part) of a verified program, by the route that found it."""
    if route and (route.startswith("map+") or route.startswith("filter+")):
        body = term.children[0]                       # (map|filter) (lambda x. e) xs
        inner = body.children[0].children[1]          # the lambda
        return inner, None
    return None, term


def serialise(library: dict):
    abstractions, constants = [], []
    for name, a in library.items():
        if not a.params:
            value = evaluate(a.witness, ())
            if value.ok and type(value.value) is int and abs(value.value) <= hybrid.CONST_RANGE:
                constants.append(value.value)
            continue
        abstractions.append((name, arrows(*a.params, a.result).to_dict(), term_to_dict(a.witness)))
    return abstractions, constants


class State:
    def __init__(self, library, keep, entropy, parent=None, move=None, signature=None):
        self.library, self.keep, self.entropy = library, keep, entropy
        self.parent, self.move, self.signature = parent, move, signature
        self.learn = self.held_out = 0
        self.counts = {}
        self.usage = {"elem": {}, "list": {}}
        self.programs = {}
        self.record = {}


def run_loop(harness, budget, components, learn, moves=MOVES, max_runs=24, rollback=True, log=print):
    held = tuple(p for p in ALL if p not in learn)
    timeline, tabu_keys, tabu_moves = [], set(), set()
    rollbacks = 0

    def measure(state, label):
        abstractions, constants = serialise(state.library)
        switches = components + ("E" if state.entropy else "")
        started = time.perf_counter()
        result = harness.run(spec_of(label, budget, switches, abstractions, constants, keep=state.keep))
        state.counts = summary(result)
        state.learn = sum(state.counts[p] for p in learn)
        state.held_out = sum(state.counts[p] for p in held)
        usage = {"elem": {}, "list": {}}
        programs, held_usage, routes = {}, {}, {}
        for partition, rows in result.items():
            for row in rows:
                if not row["solved"]:
                    continue
                routes[row["route"]] = routes.get(row["route"], 0) + 1
                term = term_from_dict(row["term"])
                if partition in learn:
                    programs[f"{partition}/{row['name']}"] = term
                    elem, whole = split_spaces(term, row["route"])
                    for space, part in (("elem", elem), ("list", whole)):
                        if part is not None:
                            for symbol in symbols_of(part, state.library):
                                usage[space][symbol] = usage[space].get(symbol, 0) + 1
                else:
                    for symbol in symbols_of(term, state.library):
                        if symbol in state.library:
                            held_usage[symbol] = held_usage.get(symbol, 0) + 1
        state.usage, state.programs = usage, programs
        state.record = {
            "run": harness.runs, "label": label, "move": state.move, "counts": state.counts,
            "learn": state.learn, "held_out": state.held_out, "library": list(state.library),
            "keep_sizes": {s: (len(k) if k is not None else None) for s, k in (state.keep or {}).items()},
            "entropy": state.entropy, "routes": routes,
            "abstraction_use_learn": {n: usage["elem"].get(n, 0) + usage["list"].get(n, 0) for n in state.library},
            "abstraction_use_held_out": {n: held_usage.get(n, 0) for n in state.library},
            "rejected_by_verifier": sum(1 for rows in result.values() for r in rows
                                        if r["term"] is not None and not r["solved"]),
            "solved": sorted(f"{p}/{r['name']}" for p, rows in result.items() for r in rows if r["solved"]),
            "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                         for p, rows in result.items() for r in rows if r["solved"]},
            "seconds": round(time.perf_counter() - started)}
        timeline.append(state.record)
        log(f"run {harness.runs:2d} {label:22s} learn {state.learn:3d} held-out {state.held_out:3d} {state.counts} "
            f"lib {len(state.library)} keep {state.record['keep_sizes']} E {int(state.entropy)} | {state.record['seconds']} s",
            )
        return state

    def symbols(state, space):
        if state.keep and state.keep.get(space) is not None:
            return list(state.keep[space])
        learned = [n for n, a in state.library.items() if a.params] + \
                  [f"int:{evaluate(a.witness, ()).value}" for n, a in state.library.items() if not a.params]
        return base_symbols() + learned

    def cut(state, mode, rng=None):
        keep = {}
        for space in ("elem", "list"):
            current = symbols(state, space)
            use = state.usage[space]
            if mode == "unused":
                kept = [s for s in current if use.get(s, 0) > 0]
            elif mode == "random":
                kept = sorted(rng.sample(sorted(current), max(1, round(len(current) * (1 - CUT)))))
            else:
                ranked = sorted(current, key=lambda s: (use.get(s, 0), s))
                kept = ranked[int(len(ranked) * CUT):]
            keep[space] = sorted(kept)
        return keep

    def candidate(state, move):
        if move == "compress":
            proposals = compress.propose(state.programs, state.library, tabu=frozenset(tabu_keys),
                                         max_new=PER_GENERATION, name_prefix=f"s{len(timeline)}_")
            if not proposals:
                return None
            library = dict(state.library)
            library.update({a.name: a for a in proposals})
            keep = None
            if state.keep:                              # new symbols are born in both spaces
                keep = {space: sorted(set(kept) | {a.name for a in proposals if a.params}
                                      | {f"int:{evaluate(a.witness, ()).value}" for a in proposals if not a.params})
                        for space, kept in state.keep.items()}
            new = State(library, keep, state.entropy, state, move, tuple(compress.key(a) for a in proposals))
            new.proposals = proposals
            return new
        if move in ("apoptosis", "unused"):
            keep = cut(state, move)
            signature = (move, tuple(keep["elem"]), tuple(keep["list"]))
            if signature in tabu_moves or all(set(keep[s]) == set(symbols(state, s)) for s in keep):
                return None
            return State(dict(state.library), keep, state.entropy, state, move, signature)
        if move == "entropy":
            signature = ("entropy", id(state))
            if state.entropy or signature in tabu_moves:
                return None
            return State(dict(state.library), state.keep, True, state, move, signature)
        raise ValueError(move)

    current = measure(State({}, None, False), "gen0")
    best = current
    while harness.runs < max_runs:
        accepted = False
        for move in moves:
            if harness.runs >= max_runs:
                break
            new = candidate(current, move)
            if new is None:
                continue
            if move == "compress":
                for a in new.proposals:
                    log(f"     propose {a.name}: {a.definition}  score {a.score} tasks {len(a.tasks)} depth {a.depth}")
            measure(new, f"{move}@{current.record['run']}")
            new.record["accepted"] = new.learn > current.learn
            if move == "compress":
                new.record["proposed"] = [{"name": a.name, "definition": str(a.definition), "score": a.score,
                                           "tasks": len(a.tasks), "depth": a.depth, "params": [str(p) for p in a.params],
                                           "result": str(a.result)} for a in new.proposals]
            if new.learn > current.learn:
                log(f"     accepted {move}: learn {current.learn} -> {new.learn}, held-out {current.held_out} -> {new.held_out}")
                current = new
                if current.learn > best.learn:
                    best = current
                accepted = True
                break
            if move == "compress":
                tabu_keys.update(new.signature)
            else:
                tabu_moves.add(new.signature)
        if accepted:
            continue
        if not rollback or rollbacks >= MAX_ROLLBACKS or current.parent is None:
            log("no move accepted: stop")
            break
        rollbacks += 1
        if current.move == "compress":
            tabu_keys.update(current.signature)
        else:
            tabu_moves.add(current.signature)
        log(f"     rollback {rollbacks}: no move accepted after {current.move}@run{current.record['run']}; "
            f"banned it and returned to run {current.parent.record['run']}")
        current = current.parent
    report = {"budget": budget, "components": components, "learn": list(learn), "held_out": list(held),
              "moves": list(moves), "timeline": timeline, "rollbacks": rollbacks, "runs": harness.runs,
              "best_run": best.record["run"], "first": timeline[0]["run"],
              "library": {n: {"definition": str(a.definition), "witness": str(a.witness), "depth": a.depth,
                              "params": [str(p) for p in a.params], "result": str(a.result)}
                          for n, a in best.library.items()},
              "best_keep": best.keep}
    return report, best


if __name__ == "__main__":
    budget = int(sys.argv[1])
    components = "" if sys.argv[2] == "-" else sys.argv[2]
    out_path = sys.argv[3]
    learn = CONFIGS[sys.argv[4]]
    workers = int(sys.argv[5]) if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else 4
    moves = tuple(sys.argv[sys.argv.index("--moves") + 1].split(",")) if "--moves" in sys.argv else MOVES
    max_runs = int(sys.argv[sys.argv.index("--max-runs") + 1]) if "--max-runs" in sys.argv else 24
    harness = Harness(workers, ALL)
    report, best = run_loop(harness, budget, components, learn, moves=moves, max_runs=max_runs,
                            rollback="--no-rollback" not in sys.argv)
    if "--random-control" in sys.argv:                 # idea 1 taken literally: a random 60% cut of generation 0
        start = State({}, None, False)
        start.usage = {"elem": {}, "list": {}}
        rng = random.Random(20261110)
        keep = {space: sorted(rng.sample(sorted(base_symbols()), round(len(base_symbols()) * (1 - CUT))))
                for space in ("elem", "list")}
        result = harness.run(spec_of("random-cut", budget, components, keep=keep))
        counts = summary(result)
        report["random_cut"] = {"counts": counts, "learn": sum(counts[p] for p in learn),
                                "held_out": sum(counts[p] for p in ALL if p not in learn), "keep": keep}
        print("random 60% cut of generation 0:", report["random_cut"]["learn"], report["random_cut"]["held_out"], counts)
    json.dump(report, open(out_path, "w"), indent=1)
    first, last = report["timeline"][0], best.record
    print(f"\nbest state (run {last['run']}): learn {first['learn']} -> {last['learn']}, "
          f"held-out {first['held_out']} -> {last['held_out']}; runs {report['runs']}, rollbacks {report['rollbacks']}, "
          f"symbols learned {len(report['library'])}")
    harness.close()
