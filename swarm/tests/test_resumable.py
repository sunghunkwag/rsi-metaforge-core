"""The Builder's search checkpoint: a restored frontier continues exactly where the previous process stopped."""
import pickle
import zlib

import pytest

from swarm.builder.mutable import solve as solve_module
from swarm.builder.mutable.enumeration import Frontier, enumerate_programs
from swarm.builder.mutable.resumable import ResumableSearch
from swarm.builder.mutable import grammar as grammar_module
from swarm.builder.mutable import types as types_module


EXAMPLES = tuple((([x],), [v + 1 for v in x]) for x in ([1, 2], [3], [0, 4, 5], [7, 7, 7, 7]))


def shape(term):
    """A term without its lambda parameter types (fresh variable names differ between processes)."""
    value = term.value if term.tag in ("prim", "ref", "var", "int", "bool") else None
    return term.tag, value, tuple(shape(child) for child in term.children)


def fresh_search():
    request = solve_module.request_type(EXAMPLES)
    grammar = solve_module.grammar_for(solve_module.library_state(), set())
    return ResumableSearch(EXAMPLES, request, grammar, step_budget=2000, max_size=12,
                           max_expansions=20000, near_misses=lambda *a: None)


def trace(search, budget):
    seen = []
    search.near_misses = lambda term, matched, total: seen.append(shape(term))
    result = search.run(budget)
    return seen, result


def test_frontier_matches_generator_order():
    request = solve_module.request_type(EXAMPLES)
    grammar = solve_module.grammar_for(solve_module.library_state(), set())
    generated = [(shape(c.term), round(c.log_probability, 9)) for _, c in zip(range(300), enumerate_programs(
        request, grammar=grammar, max_size=12, max_expansions=20000, partial_heuristic=None,
        partial_features_only=True))]
    frontier = Frontier(request, grammar, 12, None, 20000, None, None, True)
    direct = [(shape(c.term), round(c.log_probability, 9)) for _, c in zip(range(300), frontier)]
    assert generated == direct


def test_checkpoint_continues_identically():
    whole, result_whole = trace(fresh_search(), 500)
    first = fresh_search()
    head, _ = trace(first, 200)
    blob = zlib.compress(pickle.dumps(first.state(), protocol=pickle.HIGHEST_PROTOCOL), 1)
    resumed = fresh_search().restore(pickle.loads(zlib.decompress(blob)))
    assert resumed.position == first.position == 200
    tail, result_tail = trace(resumed, 300)
    assert head + tail == whole
    assert resumed.position == 500 and result_tail.evaluated == 300
    # the position-based fallback (re-enumeration) gives the same continuation
    skipped = fresh_search()
    skipped.fast_forward(200)
    tail_fallback, _ = trace(skipped, 300)
    assert tail_fallback == tail


def test_checkpoint_advances_fresh_name_counters():
    search = fresh_search()
    search.run(50)
    state = search.state()
    assert state["frontier"]["fresh"]["types"] == types_module._fresh_ids.value
    assert state["frontier"]["fresh"]["grammar"] == grammar_module._fresh.value
    # a process that restores the checkpoint never reuses a name the checkpoint may hold
    types_module._fresh_ids.value = 0
    grammar_module._fresh.value = 0
    fresh_search().restore(state)
    assert types_module._fresh_ids.value >= state["frontier"]["fresh"]["types"]
    assert grammar_module._fresh.value >= state["frontier"]["fresh"]["grammar"]


def test_heuristic_frontier_cannot_be_checkpointed():
    request = solve_module.request_type(EXAMPLES)
    grammar = solve_module.grammar_for(solve_module.library_state(), set())
    frontier = Frontier(request, grammar, 12, None, 20000, None, lambda term: 0.0, True)
    with pytest.raises(ValueError):
        frontier.state()


def test_solve_many_resumes_from_checkpoint(tmp_path):
    task = {"id": "t-plus-one", "examples": [{"inputs": [list(x[0])], "output": y} for x, y in EXAMPLES]}
    state_path = tmp_path / "state.pkl"
    first = solve_module.solve_many({"tasks": [task], "budget": 120, "state_path": str(state_path)})
    persisted = pickle.loads(state_path.read_bytes())
    assert any(key[0] == "t-plus-one" for key in persisted["frontiers"])
    assert first["results"][0]["candidates"] == 120 or first["results"][0]["program"] is not None
    second = solve_module.solve_many({"tasks": [task], "budget": 120, "state_path": str(state_path)})
    whole = solve_module.solve_many({"tasks": [task], "budget": 240})
    found = [r["results"][0]["program"] is not None for r in (first, second, whole)]
    # two windows of 120 with a checkpoint between them reach the same verdict as one window of 240
    assert (found[0] or found[1]) == found[2]
    if found[2]:
        solved_in = first if found[0] else second
        assert solved_in["results"][0]["dsl"] == whole["results"][0]["dsl"]
    else:
        assert first["results"][0]["candidates"] + second["results"][0]["candidates"] == whole["results"][0]["candidates"]
