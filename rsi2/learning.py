"""Wake–sleep training using only explicitly supplied development tasks."""
from __future__ import annotations

from dataclasses import dataclass, field
import random
import time

from .abstraction import learn_abstractions
from .corpus import Task
from .evaluator import evaluate
from .grammar import Grammar
from .measurement import assess
from .recognition import Recognition
from .sampling import sample_program
from .search import solve, verify
from .terms import pretty


@dataclass
class State:
    seed: int
    grammar: Grammar = field(default_factory=Grammar)
    solutions: dict = field(default_factory=dict)
    recognition: object | None = None
    heuristic: object | None = None
    generation: int = 0
    library_history: list = field(default_factory=list)
    heuristic_history: list = field(default_factory=list)
    logical_evaluations: int = 0

    def condition(self, task, grammar=None):
        base = self.grammar if grammar is None else grammar
        return self.recognition.grammar_for(task, base) if self.recognition is not None else base


def dream_pairs(train, grammar, rng, count=16, attempts=256, max_size=12, step_budget=2000):
    """Labels come from seeded grammar samples evaluated on public inputs."""
    pairs = []
    attempted = 0
    for index in range(attempts):
        template = train[rng.randrange(len(train))]
        term = sample_program(template.request_type, grammar, rng,
                              max_size=max_size, max_attempts=20)
        if term is None:
            continue
        attempted += 1
        examples = []
        for inputs, _ in template.examples:
            result = evaluate(term, inputs, library=grammar.library, step_budget=step_budget)
            if not result.ok:
                break
            examples.append((inputs, result.value))
        if len(examples) == len(template.examples):
            task = Task(f"dream_{index}", template.request_type, tuple(examples), ())
            pairs.append((task, term))
            if len(pairs) >= count:
                break
    return pairs, attempted


def wake_sleep(state, train, config, *, library_learning=True, recognition_learning=True):
    """One generation; every training task is retried, including unsolved ones."""
    if not train:
        raise ValueError("training tasks cannot be empty")
    started, cpu_started = time.perf_counter(), time.process_time()
    generation = state.generation + 1
    searchconfig = dict(config["search"])
    evaluations = 0
    wake_records = []
    for task in train:
        grammar = state.condition(task)
        result = solve(task.examples, task.request_type, config["B_wake"], grammar,
                       heuristic=state.heuristic, **searchconfig)
        evaluations += result.candidates
        accepted = verify(result.term, task.hidden, library=grammar.library,
                          step_budget=searchconfig["step_budget"])
        if accepted:
            previous = state.solutions.get(task.name)
            if previous is None or result.log_probability > grammar.log_probability(
                    previous, request_type=task.request_type):
                state.solutions[task.name] = result.term
        wake_records.append({"name": task.name, "hidden_verified": accepted,
                             "candidates": result.candidates,
                             "has_solution": task.name in state.solutions})
    adopted = []
    if library_learning:
        solutions, library, adopted = learn_abstractions(
            state.solutions, state.grammar.library, generation)
        state.solutions = solutions
        state.grammar = Grammar(library=library, weights=state.grammar.weights,
                                context_weights=state.grammar.context_weights)
        state.library_history.extend(adopted)
    lookup = {task.name: task for task in train}
    fitting = [(term, lookup[name].request_type) for name, term in state.solutions.items()]
    grammar_metrics = state.grammar.fit(fitting)
    recognition_metrics = None
    dream_count = dream_evaluations = 0
    if recognition_learning:
        rng = random.Random(state.seed * 1000003 + generation)
        dreams, dream_evaluations = dream_pairs(
            train, state.grammar, rng, count=config.get("dreams", 16),
            max_size=searchconfig["max_size"], step_budget=searchconfig["step_budget"])
        dream_count = len(dreams)
        pairs = [(lookup[name], term) for name, term in state.solutions.items()] + dreams
        model = Recognition(state.seed * 1000003 + generation)
        recognition_metrics = model.fit(pairs, state.grammar)
        state.recognition = model
    state.generation = generation
    state.logical_evaluations += evaluations + dream_evaluations
    return {"generation": generation, "wake": wake_records,
            "training_solutions": len(state.solutions), "library_entries": len(state.grammar.library),
            "adopted_library": adopted, "grammar": grammar_metrics,
            "recognition": recognition_metrics, "dreams": dream_count,
            "wake_candidate_evaluations": evaluations,
            "dream_candidate_evaluations": dream_evaluations,
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu_started}


def assess_development(state, tasks, budget, searchconfig):
    return assess(tasks, state.grammar, state.heuristic, budget, searchconfig,
                  conditioner=state.condition)


def state_summary(state):
    return {"seed": state.seed, "generation": state.generation,
            "solutions": {name: pretty(term) for name, term in state.solutions.items()},
            "library_history": state.library_history,
            "heuristic_history": state.heuristic_history,
            "logical_evaluations": state.logical_evaluations,
            "grammar_weights": state.grammar.weights,
            "grammar_context_weights": [{"parent": parent, "argument": arg, "weights": weights}
                                        for (parent, arg), weights in state.grammar.context_weights.items()]}


def main():
    import argparse
    import json
    from pathlib import Path
    from .calibrate import load_calibration
    from .corpus import load_train, load_validation

    parser = argparse.ArgumentParser(description="One reproducible development-partition wake–sleep smoke run")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = {**load_calibration(), "dreams": 16}
    state = State(args.seed)
    generation = wake_sleep(state, load_train(), config)
    validation = assess_development(state, load_validation(), config["B_eval"], config["search"])
    artifact = {"purpose": "Stage 3 development smoke, outside final experiment",
                "seed": args.seed, "generation": generation,
                "validation": validation, "state": state_summary(state)}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"training_solutions": generation["training_solutions"],
                      "library_entries": generation["library_entries"],
                      "dreams": generation["dreams"],
                      "validation_solved": validation["solved"],
                      "validation_tasks": validation["tasks"],
                      "candidate_evaluations": state.logical_evaluations + validation["candidate_evaluations"]}, indent=2))


if __name__ == "__main__":
    main()
