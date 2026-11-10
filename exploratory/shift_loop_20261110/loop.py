"""The four-idea loop over the hybrid harness (exploratory, report-only).

At every state the loop tries moves in a fixed order; a move is one generation run of every
task at the per-task budget, and it is accepted only if verified learning-set solves rise.
  compress   L: up to 3 new symbols by description-length gain over the verified programs
  apoptosis  A (idea 1): cut 60% of each space's symbols, least used first
  unused     A': cut only the symbols no verified learning program uses
  entropy    E (idea 2): turn on seeded mutation of near misses
  regrow     restore the full vocabulary and keep the learned symbols
A rejected move goes on the ban list. When no move is accepted the loop rolls back one accepted
step, bans it and branches again (T, idea 3). Fusion (idea 4) is part of the fixed machinery.

With --dreams the driver also composes its verified programs into dream tasks (dream.py): 40
at generation 0 and 20 more after each accepted move, at most 100. Dream solves count in the
acceptance signal and verified dream programs join the compression corpus and usage counts.

Every decision reads the learning partitions only. Held-out partitions are run each time for
the record and never consulted.

Known limits of the signal (measured in the README): a move is one more query of every learning
task's hidden examples, so over a loop a task can be put to them with several programs; with
one or two hidden examples a wrong program can pass. Ties in usage are cut in name order.

    python loop.py <budget> <components> <out.json> <config A|B> [workers] [--moves m1,m2,..]
                   [--max-runs N] [--no-rollback] [--dreams]
"""
from __future__ import annotations

import json
import random
import sys
import time

import hybrid
from hybrid import ALL, Harness, spec_of, summary

import compress
import dream
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


def constant_of(abstraction):
    """The integer a parameterless abstraction stands for, or None."""
    if abstraction.params:
        return None
    value = evaluate(abstraction.witness, ())
    if value.ok and type(value.value) is int and abs(value.value) <= hybrid.CONST_RANGE:
        return value.value
    return None


def symbols_of(term, library) -> list:
    """Symbols a program spends, after folding it with the library. A learned constant is named
    ``int:<value>``, the name the cut knows it by."""
    compact = compress.rewrite(term, library) if library else term
    found = []
    for node in _nodes(compact):
        if node.tag == "prim":
            value = constant_of(library[node.value]) if node.value in library else None
            found.append(node.value if value is None else f"int:{value}")
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
            value = constant_of(a)
            if value is not None and value not in constants:       # two spellings of one value
                constants.append(value)
            continue
        abstractions.append((name, arrows(*a.params, a.result).to_dict(), term_to_dict(a.witness)))
    return abstractions, constants


class State:
    def __init__(self, library, keep, entropy, parent=None, move=None, signature=None):
        self.library, self.keep, self.entropy = library, keep, entropy
        self.parent, self.move, self.signature = parent, move, signature
        self.learn = self.held_out = self.dream = 0
        self.dream_programs = {}
        self.counts = {}
        self.usage = {"elem": {}, "list": {}}
        self.programs = {}
        self.record = {}


DREAM_FIRST, DREAM_MORE, DREAM_CAP = 40, 20, 100


def run_loop(harness, budget, components, learn, moves=MOVES, max_runs=24, rollback=True, log=print,
             dreams=False):
    held = tuple(p for p in ALL if p not in learn)
    timeline, tabu_keys, tabu_moves = [], set(), set()
    rollbacks = 0
    bank, signatures, executions = [], set(), [0]        # dream tasks; their signatures; task runs

    def signal(state):
        return state.learn + state.dream

    def measure(state, label):
        abstractions, constants = serialise(state.library)
        switches = components + ("E" if state.entropy else "")
        started = time.perf_counter()
        result = harness.run(spec_of(label, budget, switches, abstractions, constants, keep=state.keep),
                             dreams=[(task, check) for task, check, _ in bank])
        executions[0] += sum(len(rows) for rows in result.values())
        state.counts = summary(result)
        state.learn = sum(state.counts[p] for p in learn)
        state.held_out = sum(state.counts[p] for p in held)
        usage = {"elem": {}, "list": {}}
        programs, learn_usage, held_usage, routes = {}, {}, {}, {}
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
                if partition != "dream":                 # solutions the search built with the symbol
                    counter = learn_usage if partition in learn else held_usage
                    for symbol in row.get("used") or ():
                        counter[symbol] = counter.get(symbol, 0) + 1
        state.dream_programs = {}
        for row in result.get("dream", ()):
            if row["solved"]:
                term = term_from_dict(row["term"])
                state.dream_programs[row["name"]] = term
                elem, whole = split_spaces(term, row["route"])
                for space, part in (("elem", elem), ("list", whole)):
                    if part is not None:
                        for symbol in symbols_of(part, state.library):
                            usage[space][symbol] = usage[space].get(symbol, 0) + 1
        state.dream = len(state.dream_programs)
        state.usage, state.programs = usage, programs
        state.record = {
            "run": harness.runs, "label": label, "move": state.move, "counts": state.counts,
            "learn": state.learn, "held_out": state.held_out, "library": list(state.library),
            "dream": state.dream, "dream_tasks": len(bank),
            "keep_sizes": {s: (len(k) if k is not None else None) for s, k in (state.keep or {}).items()},
            "entropy": state.entropy, "routes": routes,
            "abstraction_use_learn": {n: learn_usage.get(n, 0) for n in state.library},
            "abstraction_use_held_out": {n: held_usage.get(n, 0) for n in state.library},
            "rejected_by_verifier": sum(1 for rows in result.values() for r in rows
                                        if r["term"] is not None and not r["solved"]),
            "solved": sorted(f"{p}/{r['name']}" for p, rows in result.items() for r in rows if r["solved"]),
            "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                         for p, rows in result.items() for r in rows if r["solved"]},
            "rejected": {f"{p}/{r['name']}": [r["program"], r["route"]]          # public match, verifier said no
                         for p, rows in result.items() for r in rows if r["term"] is not None and not r["solved"]},
            "seconds": round(time.perf_counter() - started)}
        timeline.append(state.record)
        log(f"run {harness.runs:2d} {label:22s} learn {state.learn:3d} held-out {state.held_out:3d} "
            f"dream {state.dream:3d}/{len(bank):3d} {state.counts} "
            f"lib {len(state.library)} keep {state.record['keep_sizes']} E {int(state.entropy)} | {state.record['seconds']} s",
            )
        return state

    def grow_bank(state, count):
        """Compose new dream tasks from the state's verified programs and score the state on them."""
        if not dreams or len(bank) >= DREAM_CAP:
            return
        source = dict(state.programs)
        source.update(state.dream_programs)
        new = dream.make(source, min(count, DREAM_CAP - len(bank)), signatures, len(timeline))
        if not new:
            return
        bank.extend(new)
        abstractions, constants = serialise(state.library)
        switches = components + ("E" if state.entropy else "")
        result = harness.run(spec_of(f"dreams@{state.record['run']}", budget, switches, abstractions, constants,
                                     keep=state.keep), partition_names=[], dreams=[(t, c) for t, c, _ in new])
        executions[0] += len(new)
        for row in result["dream"]:
            if row["solved"]:
                state.dream_programs[row["name"]] = term_from_dict(row["term"])
        state.dream = len(state.dream_programs)
        state.record["dream"], state.record["dream_tasks"] = state.dream, len(bank)
        log(f"     {len(new)} new dream tasks (bank {len(bank)}); the current state solves {state.dream} of the bank")

    def symbols(state, space):
        if state.keep and state.keep.get(space) is not None:
            return list(state.keep[space])
        learned = [n for n, a in state.library.items() if a.params]
        for a in state.library.values():
            value = constant_of(a)
            if value is not None and f"int:{value}" not in learned and f"int:{value}" not in base_symbols():
                learned.append(f"int:{value}")
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
        if move == "regrow":
            signature = ("regrow", tuple(sorted(state.library)))
            if state.keep is None or signature in tabu_moves:
                return None
            return State(dict(state.library), None, state.entropy, state, move, signature)
        if move == "compress":
            corpus = dict(state.programs)
            corpus.update(state.dream_programs)
            proposals = compress.propose(corpus, state.library, tabu=frozenset(tabu_keys),
                                         max_new=PER_GENERATION, name_prefix=f"s{len(timeline)}_")
            if not proposals:
                return None
            library = dict(state.library)
            library.update({a.name: a for a in proposals})
            keep = None
            if state.keep:                              # new symbols are born in both spaces
                keep = {space: sorted(set(kept) | {a.name for a in proposals if a.params}
                                      | {f"int:{constant_of(a)}" for a in proposals if constant_of(a) is not None})
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
    grow_bank(current, DREAM_FIRST)
    best = current
    stop = "run cap"
    while harness.runs < max_runs:
        accepted = False
        for move in moves:
            if harness.runs >= max_runs:
                break                                   # moves left untried: not a saturation
            new = candidate(current, move)
            if new is None:
                continue
            if move == "compress":
                for a in new.proposals:
                    log(f"     propose {a.name}: {a.definition}  score {a.score} tasks {len(a.tasks)} depth {a.depth}")
            measure(new, f"{move}@{current.record['run']}")
            new.record["accepted"] = signal(new) > signal(current)
            if move == "compress":
                new.record["proposed"] = [{"name": a.name, "definition": str(a.definition), "score": a.score,
                                           "tasks": len(a.tasks), "depth": a.depth, "params": [str(p) for p in a.params],
                                           "result": str(a.result)} for a in new.proposals]
            if signal(new) > signal(current):
                log(f"     accepted {move}: learn {current.learn} -> {new.learn}, dream {current.dream} -> {new.dream}, "
                    f"held-out {current.held_out} -> {new.held_out}")
                current = new
                grow_bank(current, DREAM_MORE)
                if signal(current) > signal(best) or (dreams and current.learn >= best.learn):
                    best = current
                accepted = True
                break
            if move == "compress":
                tabu_keys.update(new.signature)
            else:
                tabu_moves.add(new.signature)
        if accepted:
            continue
        if harness.runs >= max_runs:
            log(f"run cap reached at the state of run {current.record['run']} with moves untried: stop")
            break
        if not rollback or rollbacks >= MAX_ROLLBACKS or current.parent is None:
            log("no move accepted: stop")
            stop = "no move accepted"
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
              "stopped_by": stop,
              "dreams": dreams, "dream_tasks": [task.name for task, _, _ in bank], "task_executions": executions[0],
              "equal_budget_per_real_task": round(executions[0] * budget / 338),
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
                            rollback="--no-rollback" not in sys.argv, dreams="--dreams" in sys.argv)
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
          f"held-out {first['held_out']} -> {last['held_out']}, dream {first.get('dream', 0)} -> {last.get('dream', 0)}; "
          f"runs {report['runs']}, rollbacks {report['rollbacks']}, symbols learned {len(report['library'])}, "
          f"equal budget per real task {report['equal_budget_per_real_task']}")
    harness.close()
