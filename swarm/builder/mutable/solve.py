"""The mutable tree's entry points (generation 0; Builder-owned): solve tasks, learn from crossings.

The kernel runs this module in an isolated subprocess (``kernel/snapshot.py``)
from a content-addressed copy of the tree, so Kb and crossing checks see
exactly the substrate that was snapshotted. The Builder agent runs it from
its working copy for the generation's wake. Every function takes one JSON
payload and returns one JSON result; evaluation counts come from the pinned
evaluator's ``METER``.

Public example values are JSON: ints, bools and lists of them. Tasks whose
values the DSL cannot represent (strings, tuples) are reported unsolved.

Own-task exclusion (``exclude`` in ``solve_many``): a solve that excludes
task T runs on the grammar the tree would have if T had never been
learned from. Library entries and forged primitives sourced from T are
dropped, every entry whose body references a dropped name is dropped
with them (to a fixpoint), and the grammar weights are refit on the
learning corpus without T's own solutions. ``library.json`` therefore
keeps that corpus (``fit_solutions``, one rewritten solution per source
task): the stored weights are the fit on the whole corpus, and the
excluded grammar is the fit on the corpus minus the excluded tasks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pickle
import zlib

from . import evaluator
from .abstraction import learn_abstractions
from .compile import PRIMITIVE_MAP, compile_program
from .grammar import Grammar
from .resumable import ResumableSearch
from .terms import Term, pretty, term_from_dict, term_to_dict
from .types import BOOL, FORGED, INT, Arrow, ListOf, PRIMITIVE_TYPES, TVar, infer, substitute, unify

HERE = Path(__file__).resolve().parent
MAX_LIBRARY = 64                 # entries; learn adopts nothing beyond it (params learn.max_library)


def _load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def params() -> dict:
    return _load("params.json")


def library_state() -> dict:
    raw = _load("library.json")
    entries = {name: term_from_dict(item["term"]) for name, item in raw["entries"].items()}
    sources = {name: list(item.get("sources", [])) for name, item in raw["entries"].items()}
    context = {tuple(item["context"]): dict(item["weights"]) for item in raw.get("context_weights", [])}
    corpus = {task_id: term_from_dict(item) for task_id, item in raw.get("fit_solutions", {}).items()}
    return {"entries": entries, "sources": sources, "weights": dict(raw.get("weights", {})),
            "context_weights": context, "fit_solutions": corpus}


def save_library_state(state: dict) -> None:
    raw = {"entries": {name: {"term": term_to_dict(term), "sources": state["sources"].get(name, [])}
                       for name, term in state["entries"].items()},
           "weights": state["weights"],
           "context_weights": [{"context": list(k), "weights": v}
                               for k, v in state["context_weights"].items()],
           "fit_solutions": {task_id: term_to_dict(term)
                             for task_id, term in sorted(state.get("fit_solutions", {}).items())}}
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


def _references(term: Term) -> set:
    """Library entries and forged primitives a term names directly."""
    found = set()
    if term.tag == "ref" or (term.tag == "prim" and term.value in FORGED):
        found.add(term.value)
    for child in term.children:
        found |= _references(child)
    return found


def references_closure(names, entries: dict) -> set:
    """``names`` plus everything the named entries' bodies reference, recursively (the credit chain)."""
    out, stack = set(), list(names)
    while stack:
        name = stack.pop()
        if name in out:
            continue
        out.add(name)
        if name in entries:
            stack.extend(_references(entries[name]))
    return out


def dependents_closure(names, entries: dict) -> set:
    """``names`` plus every entry whose body references a name in the set, to a fixpoint."""
    excluded = set(names)
    changed = True
    while changed:
        changed = False
        for name, term in entries.items():
            if name not in excluded and _references(term) & excluded:
                excluded.add(name)
                changed = True
    return excluded


def excluded_names(state: dict, exclude: set) -> set:
    """Every library entry and forged primitive that descends from the excluded tasks."""
    seeds = {name for name, sources in state["sources"].items() if set(sources) & exclude}
    seeds |= {name for name, entry in FORGED.items() if set(entry.get("sources", [])) & exclude}
    return dependents_closure(seeds, state["entries"])


def fit_weights(library: dict, primitives: dict, corpus: list) -> tuple:
    """Grammar weights refit on the corpus terms expressible in (library, primitives); ({}, {}) when none."""
    available = set(library) | set(primitives)
    usable = [term for term in corpus if _references(term) <= available]
    if not usable:
        return {}, {}
    grammar = Grammar(library=library, primitives=primitives)
    try:
        grammar.fit(usable)
    except Exception:
        return {}, {}
    return dict(grammar.weights), {k: dict(v) for k, v in grammar.context_weights.items()}


def grammar_for(state: dict, exclude: set, boost: dict | None = None) -> Grammar:
    """The current grammar with everything learned from the excluded tasks removed.

    ``boost`` (name -> factor) multiplies the weight of retrieved fragments:
    how the Builder's latent retrieval reaches the search order.
    """
    excluded = excluded_names(state, set(exclude)) if exclude else set()
    library = {name: term for name, term in state["entries"].items() if name not in excluded}
    primitives = {name: type_ for name, type_ in PRIMITIVE_TYPES.items() if name not in excluded}
    corpus = state.get("fit_solutions", {})
    tainted = bool(exclude) and (bool(excluded) or bool(set(corpus) & set(exclude)))
    if tainted:
        weights, context = fit_weights(library, primitives,
                                       [term for task_id, term in corpus.items() if task_id not in exclude])
    else:
        weights = {k: v for k, v in state["weights"].items()}
        context = {k: dict(v) for k, v in state["context_weights"].items()}
    for name, factor in (boost or {}).items():
        if name in library or name in primitives:
            weights[name] = max(float(weights.get(name, 1.0)) * float(factor), 1e-6)
    return Grammar(library=library, primitives=primitives, weights=weights or None,
                   context_weights=context or None)


def grammar_key(grammar: Grammar, search: dict | None = None) -> str:
    """Identity of an enumeration order: library, primitives, every weight table and the search limits."""
    blob = json.dumps({"library": sorted((n, pretty(t)) for n, t in grammar.library.items()),
                       "weights": sorted(grammar.weights.items()),
                       "context": sorted((list(k), sorted(v.items())) for k, v in grammar.context_weights.items()),
                       "primitives": sorted(grammar.primitives),
                       "search": dict(search or {})}, default=str, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _unsolved(task_id: str, reason: str) -> dict:
    return {"id": task_id, "program": None, "dsl": None, "fragments": [], "reason": reason,
            "evaluations": 0, "candidates": 0, "best_public": 0.0, "best_dsl": None, "exhausted": False}


def solve_many(payload: dict) -> dict:
    """Search each task's public examples; return compiled programs and the meter.

    payload: {"tasks": [{"id", "examples": [{"inputs": [x], "output": y}]}],
              "budget": int or {task_id: int}, "exclude": {task_id: [task ids]} (optional),
              "boost": {task_id: {name: factor}} (optional),
              "skip": {task_id: [term dicts]} (optional: public matches to pass over, counted),
              "state_path": optional path of persisted search state (live wake only)}
    """
    settings = params()
    search = settings["search"]
    state = library_state()
    persisted, state_reset = {}, False
    state_path = payload.get("state_path")
    if state_path and Path(state_path).exists():
        try:
            persisted = pickle.loads(Path(state_path).read_bytes())
        except Exception:
            persisted, state_reset = {}, True
    active = {t["id"] for t in payload["tasks"]}
    if state_path:
        # A task absent from the wake is crossed, mined or retired; the live
        # wake never returns to it, so its search state is dropped here.
        for key in ("positions", "frontiers"):
            persisted[key] = {k: v for k, v in persisted.get(key, {}).items() if k[0] in active}
        persisted["failures"] = {k: v for k, v in persisted.get("failures", {}).items() if k in active}
    skip = {task_id: {term_from_dict(item) for item in items}
            for task_id, items in (payload.get("skip") or {}).items()}
    results = []
    before = dict(evaluator.METER)
    candidates = 0
    for task in payload["tasks"]:
        task_id = task["id"]
        exclude = set(payload.get("exclude", {}).get(task_id, []))
        try:
            examples = tuple((tuple(e["inputs"]), e["output"]) for e in task["examples"])
            request = request_type(examples)
        except Exception:
            results.append(_unsolved(task_id, "outside the DSL"))
            continue
        try:
            grammar = grammar_for(state, exclude, payload.get("boost", {}).get(task_id))
        except Exception as exc:
            results.append(_unsolved(task_id, f"grammar failed: {type(exc).__name__}"))
            continue
        failures = persisted.setdefault("failures", {}).setdefault(task_id, set()) if state_path else None
        best = {"matched": 0, "total": len(examples), "term": None}

        def near_miss(term, matched, total, best=best):
            if matched > best["matched"]:
                best["matched"] = matched
                best["term"] = term

        searcher = ResumableSearch(examples, request, grammar, step_budget=search["step_budget"],
                                   max_size=search["max_size"],
                                   max_expansions=search["max_expansions"],
                                   known_failures=failures, near_misses=near_miss)
        key = (task_id, grammar_key(grammar, search))
        # SWARM addition: the search frontier is checkpointed per task and
        # grammar order (compressed pickle in the Builder's state file), so
        # a wake resumes where the last one stopped instead of
        # re-enumerating its prefix, whose cost grew with every
        # generation. The position-based fast-forward remains the
        # fallback when no checkpoint can be restored.
        frontiers = persisted.setdefault("frontiers", {}) if state_path else {}
        restored = False
        if key in frontiers:
            try:
                searcher.restore(pickle.loads(zlib.decompress(frontiers[key])))
                restored = True
            except Exception:
                restored = False
        position = persisted.setdefault("positions", {}).get(key, 0) if state_path else 0
        if position and not restored:
            searcher.fast_forward(position)
        start = evaluator.METER["evaluations"]
        budget = payload["budget"]
        budget = int(budget[task_id]) if isinstance(budget, dict) else int(budget)
        rejected = skip.get(task_id)
        result = searcher.run(budget, skip_match=(lambda term, s=rejected: term in s) if rejected else None)
        if state_path:
            persisted["positions"][key] = searcher.position
            frontiers[key] = zlib.compress(pickle.dumps(searcher.state(), protocol=pickle.HIGHEST_PROTOCOL), 1)
        record = {"id": task_id, "program": None, "dsl": None, "fragments": [],
                  "evaluations": evaluator.METER["evaluations"] - start,
                  "candidates": result.evaluated,
                  "skipped": result.skipped_matches,
                  "best_public": (1.0 if result.term is not None
                                  else best["matched"] / max(best["total"], 1)),
                  "best_dsl": None if best["term"] is None else pretty(best["term"]),
                  "exhausted": result.exhausted}
        if result.term is not None:
            record["program"] = compile_program(result.term, state["entries"])
            record["dsl"] = pretty(result.term)
            record["term"] = term_to_dict(result.term)
            # The credit chain: direct references closed through the library entries' own bodies.
            record["fragments"] = sorted(references_closure(_references(result.term), state["entries"]))
        candidates += result.evaluated
        results.append(record)
    if state_path:
        tmp = Path(state_path).with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(persisted))
        tmp.replace(state_path)
    after = dict(evaluator.METER)
    # "candidates" is the logical unit (one program checked against a
    # task's public examples); "evaluations" counts evaluator calls.
    return {"results": results,
            "state_reset": state_reset,
            "meter": {"candidates": candidates,
                      "evaluations": after["evaluations"] - before["evaluations"],
                      "steps": after["steps"] - before["steps"]}}


def learn(payload: dict) -> dict:
    """Adopt library entries from verified solutions (DSL term dicts) and refit the grammar.

    payload: {"solutions": {task_id: dsl term dict}, "generation": int}
    Every offered solution that type-checks against the current library
    joins the learning corpus under its source task; the grammar weights
    are the fit on the whole corpus. Adoption is capped by ``learn.max_adoptions``
    per call and ``learn.max_library`` in total, and every adopted entry
    records its source tasks.
    """
    state = library_state()
    settings = params()["learn"]
    offered = {task_id: term_from_dict(item) for task_id, item in payload["solutions"].items()}
    usable, dropped = {}, []
    for task_id, term in offered.items():
        try:
            infer(term, library=state["entries"])
            usable[task_id] = term
        except Exception:
            dropped.append(task_id)
    before = len(state["entries"])
    cap = int(settings.get("max_adoptions", 8))
    room = max(0, int(settings.get("max_library", MAX_LIBRARY)) - before)
    if usable:
        rewritten, library, adopted = learn_abstractions(usable, state["entries"], int(payload["generation"]),
                                                         max_adoptions=min(cap, room))
    else:
        rewritten, library, adopted = {}, dict(state["entries"]), []
    for record in adopted:
        state["sources"][record["name"]] = sorted(record["source_tasks"])
    state["entries"] = library
    corpus = state.setdefault("fit_solutions", {})
    for task_id, term in rewritten.items():
        corpus[task_id] = term
    state["weights"], state["context_weights"] = fit_weights(library, dict(PRIMITIVE_TYPES), list(corpus.values()))
    save_library_state(state)
    return {"adopted": [r["name"] for r in adopted], "library_size": len(library),
            "before": before, "dropped": sorted(dropped), "corpus": len(corpus)}


def inventory(payload: dict) -> dict:
    """Public facts about the tree: library and forged names with sources and references, parameters."""
    state = library_state()
    unsourced = sorted(name for name in state["entries"] if not state["sources"].get(name))
    if unsourced:
        raise ValueError(f"library entries without source tasks: {unsourced}")
    return {"library": {name: {"dsl": pretty(term), "sources": state["sources"].get(name, []),
                               "references": sorted(_references(term))}
                        for name, term in state["entries"].items()},
            "forged": {name: {"type": str(entry["type"]), "sources": entry["sources"]}
                       for name, entry in FORGED.items()},
            "params": params(),
            "corpus": sorted(state.get("fit_solutions", {})),
            "primitive_heads": sorted(set(PRIMITIVE_MAP.values()))}
