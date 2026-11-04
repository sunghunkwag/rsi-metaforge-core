"""Self-curriculum: the system makes tasks for itself, solves them, and learns its library from them.

**Why.** Every learning signal in RSI-3 comes from the 36 TRAIN tasks.
The library compresses their solutions, the policy trains on them and on
one-chunk practice, and nothing else. Once the TRAIN tasks the search can
reach are solved, growth stops. Across a dozen arms the plateau is the
same: 29 of 36.

**What.** Each generation, after the wake:

1. **Generate.** The system imagines tasks from its own programs. A task
   is ``lambda x. S[h] (f x)`` or ``S[h]`` alone: ``f`` one of the
   system's list programs (a library concept, ``tail``, or a verified
   solution; ``chain.stage_candidates``), ``S`` a decomposition skeleton,
   ``h`` a hole sampled from the current grammar. The program runs on a
   TRAIN task's public inputs for the public examples, and on another
   TRAIN task's inputs for the hidden ones, so an imagined task has a
   verifier of its own. Constant, identity and stage-only outcomes are
   dropped.
2. **Select.** A task is kept only when the prior does not find it in one
   chunk. Tasks the system already solves at a glance teach nothing.
3. **Solve.** Each kept task is given to the system's own held-out solver
   (``longrun.agent_validation``: the policy applied, never trained; the
   prior unconditioned, so TRAIN stays seed-independent; ``B_eval``
   candidates; one verifier query). A solve is a program the system
   found, not the generating program.
4. **Learn.** The solved tasks join a bounded pool. In the sleep, RSI-2's
   abstraction learner compresses TRAIN's solutions and the pool's
   together, the grammar is fitted on both, and recognition trains on
   both. TRAIN's count and solutions are kept apart: nothing imagined
   counts as a TRAIN solve.

The random stream depends on the generation only. Candidate evaluations
spent here are reported as ``curriculum_evaluations``; they are not wake
budget and are disclosed as extra compute. Nothing here reads a hidden
example of any corpus task.
"""
from __future__ import annotations

import random

from rsi2.corpus import Task
from rsi2.evaluator import evaluate
from rsi2.terms import App, Lam, Var
from rsi2.types import INT, ListOf

LIST = ListOf(INT)


def imagine(runtime, generation: int, count: int) -> list:
    """Imagined tasks with their own hidden examples (module docstring, step 1)."""
    from rsi2.sampling import sample_program
    from .chain import stage_candidates
    from .decompose import ALL_SKELETONS, skeletons_for
    from .selfmodel import canonical_types, normalize
    rng = random.Random(f"rsi3-curriculum-{generation}")
    family = [sk for sk in ALL_SKELETONS
              if runtime.arm.decomposition_fold or not sk.name.startswith("fold")]
    templates = [t for t in sorted(runtime.public, key=lambda t: t.name)
                 if all(len(i) == 1 and isinstance(i[0], (list, tuple)) for i, _ in t.examples)]
    library = runtime.registry.library(runtime.state)
    types = {t.name: t.request_type for t in runtime.public}
    stages = list(stage_candidates(runtime.state.solutions, types, library).values())
    step_budget = runtime.config["search"]["step_budget"]
    made, seen = [], set()
    for attempt in range(4 * count):
        if len(made) >= count:
            break
        skeleton = family[rng.randrange(len(family))]
        hole = sample_program(skeleton.hole_type, runtime.state.grammar, rng, max_size=8,
                              max_attempts=20)
        if hole is None:
            continue
        stage = stages[rng.randrange(len(stages))] if stages and rng.random() < 0.5 else None
        try:
            body = skeleton.compose(hole)
            program = body if stage is None else canonical_types(normalize(
                Lam(LIST, App(body, App(stage, Var(0))))))
        except Exception:
            continue
        public_template = templates[rng.randrange(len(templates))]
        hidden_template = templates[rng.randrange(len(templates))]
        rows = []
        for template in (public_template, hidden_template):
            examples, middle = [], []
            for inputs, _ in template.examples:
                result = evaluate(program, inputs, library=library, step_budget=step_budget)
                if not result.ok:
                    break
                examples.append((inputs, result.value))
                if stage is not None:
                    first = evaluate(stage, inputs, library=library, step_budget=step_budget)
                    middle.append(first.value if first.ok else None)
            if len(examples) != len(template.examples):
                break
            rows.append((examples, middle))
        if len(rows) != 2:
            continue
        examples, middle = rows[0]
        outputs = [repr(o) for _, o in examples]
        if len(set(outputs)) == 1 or all(repr(o) == repr(i[0]) for i, o in examples):
            continue
        if stage is not None and all(repr(o) == repr(m) for (_, o), m in zip(examples, middle)):
            continue
        public_inputs = {repr(i) for i, _ in examples}
        hidden = tuple((i, o) for i, o in rows[1][0] if repr(i) not in public_inputs)
        if not hidden:
            continue
        try:
            from rsi2.corpus import infer_request_type
            request = infer_request_type(examples + list(hidden))
        except Exception:
            continue
        key = repr(outputs)
        if key in seen:
            continue
        seen.add(key)
        name = f"imagined_g{generation}_{len(made)}"
        made.append(Task(name, request, tuple(examples), hidden))
    return made


def select_hard(runtime, tasks: list, chunk: int) -> tuple[list, int]:
    """Tasks the prior does not find within one chunk; returns them and the units spent."""
    from .resumable import ResumableSearch
    search = runtime.config["search"]
    kept, spent = [], 0
    for task in tasks:
        probe = ResumableSearch(task.examples, task.request_type,
                                runtime.registry.base_grammar(runtime.state),
                                step_budget=search["step_budget"], max_size=search["max_size"],
                                max_expansions=search["max_expansions"])
        result = probe.run(chunk)
        spent += result.evaluated
        if result.term is None:
            kept.append(task)
    return kept, spent


def solve(runtime, tasks: list, generation: int) -> tuple[dict, int]:
    """The system's held-out solver on its imagined tasks; returns solutions and units spent."""
    from .longrun import agent_validation
    from .verifier import FrozenVerifier
    if not tasks:
        return {}, 0
    config = {"B_eval": runtime.config["B_eval"], "search": runtime.config["search"],
              "meta": runtime.config.get("meta", {}), "behave": runtime.config.get("behave", {}),
              "analogy": runtime.config.get("analogy", {}),
              "chain": runtime.config.get("chain", {})}
    verifier = FrozenVerifier(tasks, step_budget=runtime.config["search"]["step_budget"])
    programs = {}
    record = agent_validation(runtime, None, tasks, config, verifier, generation,
                              programs=programs)
    spent = sum(sum(t["spent"].values()) for t in record["tasks"])
    return programs, spent


class Pool:
    """A bounded, most-recent-first pool of imagined tasks the system solved."""

    def __init__(self, limit: int):
        self.limit = int(limit)
        self.items: dict = {}        # name -> (Task, program)

    def add(self, task: Task, program) -> None:
        self.items[task.name] = (task, program)
        while len(self.items) > self.limit:
            del self.items[next(iter(self.items))]

    def rewrite(self, solutions: dict) -> None:
        """Keep the abstraction learner's rewrites of the pool's programs."""
        for name in list(self.items):
            if name in solutions:
                task, _ = self.items[name]
                self.items[name] = (task, solutions[name])

    def tasks(self) -> dict:
        return {name: task for name, (task, _) in self.items.items()}

    def programs(self) -> dict:
        return {name: program for name, (_, program) in self.items.items()}
