"""The budget meter: the sole counter of logical cost (OWNER_DIRECTIVE.md §2, Phase K's K4).

Logical cost has two units: interpreter steps (of the kernel executor and
of the Builder's own evaluator) and candidate evaluations (one per program
checked against a task's public examples). Every module that spends charges
this meter; nothing else keeps a tally (``tests/test_integrity.py``). The
meter is append-only: charges are recorded per generation, agent and
module, and its state is part of every generation summary in the ledger.
"""
from __future__ import annotations


class Meter:
    def __init__(self):
        self.generation = 0
        self._rows: list = []            # (generation, agent, module, steps, evaluations)
        self._totals: dict = {}          # (agent, module) -> [steps, evaluations]

    def mark_generation(self, generation: int) -> None:
        self.generation = int(generation)

    def charge(self, agent: str, module: str, steps: int = 0, evaluations: int = 0) -> None:
        steps, evaluations = int(steps), int(evaluations)
        if steps < 0 or evaluations < 0:
            raise ValueError("charges are nonnegative")
        self._rows.append((self.generation, agent, module, steps, evaluations))
        total = self._totals.setdefault((agent, module), [0, 0])
        total[0] += steps
        total[1] += evaluations

    def total(self, agent: str | None = None) -> dict:
        steps = evaluations = 0
        for (a, _), (s, e) in self._totals.items():
            if agent is None or a == agent:
                steps += s
                evaluations += e
        return {"steps": steps, "evaluations": evaluations}

    def generation_total(self, generation: int, agent: str | None = None) -> dict:
        steps = evaluations = 0
        for g, a, _, s, e in self._rows:
            if g == generation and (agent is None or a == agent):
                steps += s
                evaluations += e
        return {"steps": steps, "evaluations": evaluations}

    def snapshot(self) -> dict:
        return {f"{agent}/{module}": {"steps": s, "evaluations": e}
                for (agent, module), (s, e) in sorted(self._totals.items())}
