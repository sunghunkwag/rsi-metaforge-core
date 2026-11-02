"""The mutable tree's entry points (generation 0; Builder-owned): solve tasks, learn from crossings.

The kernel runs this module in an isolated subprocess (``kernel/snapshot.py``)
from a content-addressed copy of the tree, so Kb and crossing checks see
exactly the substrate that was snapshotted. The Builder agent runs it from
its working copy for the generation's wake. Every function takes one JSON
payload and returns one JSON result; evaluation counts come from the pinned
evaluator's ``METER``.

Public example values are JSON: ints, bools and lists of them. Tasks whose
values the DSL cannot represent (strings, tuples) are reported unsolved.
"""
from __future__ import annotations

import json
from pathlib import Path
import pickle

from . import evaluator
from .abstraction import learn_abstractions
from .compile import compile_program
from .grammar import Grammar
from .memory import FailureMemory
from .resumable import ResumableSearch
from .terms import Term, pretty, term_from_dict, term_to_dict
from .types import BOOL, FORGED, INT, Arrow, ListOf, PRIMITIVE_TYPES, TVar, substitute, unify

HERE = Path(__file__).resolve().parent


def _load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def params() -> dict:
    return _load("params.json")


def library_state() -> dict:
    raw = _load("library.json")
    entries = {name: term_from_dict(item["term"]) for name, item in raw["entries"].items()}
    sources = {name: list(item.get("sources", [])) for name, item in raw["entries"].items()}
    context = {tuple(item["context"]): dict(item["weights"]) for item in raw.get("context_weights", [])}
    return {"entries": entries, "sources": sources, "weights": dict(raw.get("weights", {})),
            "context_weights": context}


def save_library_state(state: dict) -> None:
    raw = {"entries": {name: {"term": term_to_dict(term), "sources": state["sources"].get(name, [])}
                       for name, term in state["entries"].items()},
           "weights": state["weights"],
           "context_weights": [{"context": list(k), "weights": v}
                               for k, v in state["context_weights"].items()]}
    (HERE / "library.json").write_text(json.dumps(raw, indent=1, sort_keys=True) + "\n",
                                       encoding="utf-8")


def value_type(value):
    if type(value) is bool:
        return BOOL
    if type(value) is int:
        return INT
    if type(value) is list:
        element = TVar("e")
        constraints = {}
        for item in value:
            constraints = unify(element, value_type(item), constraints)
            element = substitute(element, constraints)
        return ListOf(element)
    raise TypeError("value outside the DSL")


def request_type(examples):
    request = None
    for inputs, output in examples:
        if len(inputs) != 1:
            raise TypeError("one input per task")
        signature = Arrow(value_type(inputs[0]), value_type(output))
        request = signature if request is None else substitute(request, unify(request, signature))
    return request


def grammar_for(state: dict, exclude: set) -> Grammar:
    """The current grammar without entries and forged primitives sourced from excluded tasks."""
    library = {name: term for name, term in state["entries"].items()
               if not set(state["sources"].get(name, [])) & exclude}
    primitives = {name: type_ for name, type_ in PRIMITIVE_TYPES.items()
                  if name not in FORGED or not set(FORGED[name]["sources"]) & exclude}
    weights = {k: v for k, v in state["weights"].items()}
    context = {k: dict(v) for k, v in state["context_weights"].items()}
    return Grammar(library=library, primitives=primitives, weights=weights or None,
                   context_weights=context or None)


def _references(term: Term) -> set:
    found = set()
    if term.tag == "ref" or (term.tag == "prim" and term.value in FORGED):
        found.add(term.value)
    for child in term.children:
        found |= _references(child)
    return found


def solve_many(payload: dict) -> dict:
    """Search each task's public examples; return compiled programs and the meter.

    payload: {"tasks": [{"id", "examples": [{"inputs": [x], "output": y}]}],
              "budget": int, "exclude": {task_id: [task ids]} (optional),
              "state_path": optional path of persisted search state (live wake only)}
    """
    settings = params()
    search = settings["search"]
    state = library_state()
    persisted = {}
    state_path = payload.get("state_path")
    if state_path and Path(state_path).exists():
        persisted = pickle.loads(Path(state_path).read_bytes())
    results = []
    before = dict(evaluator.METER)
    candidates = 0
    for task in payload["tasks"]:
        task_id = task["id"]
        exclude = set(payload.get("exclude", {}).get(task_id, []))
        try:
            examples = tuple((tuple(e["inputs"]), e["output"]) for e in task["examples"])
            request = request_type(examples)
        except (TypeError, ValueError, Exception):
            results.append({"id": task_id, "program": None, "reason": "outside the DSL",
                            "evaluations": 0, "best_public": 0.0})
            continue
        grammar = grammar_for(state, exclude)
        failures = persisted.setdefault("failures", {}).setdefault(task_id, set()) if state_path else None
        best = {"matched": 0, "total": len(examples)}

        def near_miss(term, matched, total, best=best):
            if matched > best["matched"]:
                best["matched"] = matched

        searcher = ResumableSearch(examples, request, grammar, step_budget=search["step_budget"],
                                   max_size=search["max_size"],
                                   max_expansions=search["max_expansions"],
                                   known_failures=failures, near_misses=near_miss)
        position = persisted.setdefault("positions", {}).get((task_id, grammar_key(grammar)), 0) if state_path else 0
        if position:
            searcher.fast_forward(position, 0, 0, 0)
        start = evaluator.METER["evaluations"]
        result = searcher.run(int(payload["budget"]))
        if state_path:
            persisted["positions"][(task_id, grammar_key(grammar))] = searcher.position
        record = {"id": task_id, "program": None, "dsl": None, "fragments": [],
                  "evaluations": evaluator.METER["evaluations"] - start,
                  "candidates": result.evaluated,
                  "best_public": (1.0 if result.term is not None
                                  else best["matched"] / max(best["total"], 1)),
                  "exhausted": result.exhausted}
        if result.term is not None:
            record["program"] = compile_program(result.term, state["entries"])
            record["dsl"] = pretty(result.term)
            record["fragments"] = sorted(_references(result.term))
        candidates += result.evaluated
        results.append(record)
    if state_path:
        Path(state_path).write_bytes(pickle.dumps(persisted))
    after = dict(evaluator.METER)
    # "candidates" is the logical unit (one program checked against a
    # task's public examples); "evaluations" counts evaluator calls.
    return {"results": results,
            "meter": {"candidates": candidates,
                      "evaluations": after["evaluations"] - before["evaluations"],
                      "steps": after["steps"] - before["steps"]}}


def grammar_key(grammar: Grammar) -> str:
    import hashlib
    blob = json.dumps({"library": sorted((n, pretty(t)) for n, t in grammar.library.items()),
                       "weights": sorted(grammar.weights.items()),
                       "primitives": sorted(grammar.primitives)}, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def learn(payload: dict) -> dict:
    """Adopt library entries from crossed solutions (DSL text) and refit the grammar.

    payload: {"solutions": {task_id: dsl term dict}, "generation": int}
    Only the entries the adoption rule admits are written to library.json.
    """
    state = library_state()
    solutions = {task_id: term_from_dict(item) for task_id, item in payload["solutions"].items()}
    settings = params()["learn"]
    before = len(state["entries"])
    rewritten, library, adopted = learn_abstractions(solutions, state["entries"], int(payload["generation"]))
    for record in adopted[:int(settings.get("max_adoptions", 8))]:
        state["sources"][record["name"]] = sorted(record["source_tasks"])
    state["entries"] = library
    grammar = Grammar(library=library)
    fitting = [(term, None) for term in rewritten.values()]
    try:
        grammar.fit([term for term, _ in fitting])
        state["weights"] = dict(grammar.weights)
        state["context_weights"] = {k: dict(v) for k, v in grammar.context_weights.items()}
    except Exception:
        pass
    save_library_state(state)
    return {"adopted": [r["name"] for r in adopted], "library_size": len(library),
            "before": before}


def inventory(payload: dict) -> dict:
    """Public facts about the tree: library and forged names with sources, parameters."""
    state = library_state()
    return {"library": {name: {"dsl": pretty(term), "sources": state["sources"].get(name, [])}
                        for name, term in state["entries"].items()},
            "forged": {name: {"type": str(entry["type"]), "sources": entry["sources"]}
                       for name, entry in FORGED.items()},
            "params": params()}
