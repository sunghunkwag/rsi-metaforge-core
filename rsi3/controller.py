"""The processor controller: allocates the wake phase's logical candidate budget.

In RSI-2 the measurable processor resource is the candidate-evaluation budget.
RSI-2 spends it uniformly: B_wake per TRAIN task per generation, retrying every
unsolved task from the start of an unchanged enumeration. The recorded failure
analysis found that always-unsolved tasks consumed 99.1% of wake candidates.

This controller spends the same per-generation total differently:

1. Hard rules from memory, no learning involved. Solved tasks receive no
   budget. A slot (task, pathway) never re-evaluates its searched prefix under
   an unchanged grammar; it resumes. Exhausted slots receive nothing. A task
   with a pending verification receives nothing more this generation.
2. Learned allocation. Each chunk of ``chunk`` candidates goes to the slot with
   the highest UCB score: value-model probability of a verified solve in the
   next window plus ``exploration * sqrt(log(1 + N) / (1 + n_slot))``, where N
   counts all windows in memory and n_slot the slot's own windows. Dormant
   pathways have n_slot = 0, so they are woken by the exploration term, and
   keep budget only if the value model, fit on their replayed outcomes, says so.

``allocation="uniform"`` is the control arm: the same resumption rules, the
budget split evenly over unsolved tasks, prior pathway only, no value model.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np


@dataclass
class Slot:
    task: str
    pathway: str
    kind: str
    start: int
    similarity: float
    features: np.ndarray


class Controller:
    def __init__(self, *, chunk: int, exploration: float, seed: int):
        if chunk < 1:
            raise ValueError("chunk must be positive")
        self.chunk = int(chunk)
        self.exploration = float(exploration)
        self.seed = int(seed)

    def _tiebreak(self, slot: Slot) -> str:
        return hashlib.sha256(f"{self.seed}|{slot.task}|{slot.pathway}".encode()).hexdigest()

    def scores(self, slots, probabilities, slot_windows, total_windows):
        log_term = math.log(1.0 + total_windows)
        result = []
        for slot, p in zip(slots, probabilities):
            n = slot_windows.get((slot.task, slot.pathway), 0)
            result.append(float(p) + self.exploration * math.sqrt(log_term / (1.0 + n)))
        return result

    def choose(self, slots, probabilities, slot_windows, total_windows) -> int:
        if not slots:
            raise ValueError("no slots to choose from")
        scores = self.scores(slots, probabilities, slot_windows, total_windows)
        best = max(range(len(slots)),
                   key=lambda i: (round(scores[i], 12), self._tiebreak(slots[i])))
        return best

    @staticmethod
    def uniform_split(total: int, tasks: list[str]) -> dict[str, int]:
        if not tasks:
            return {}
        base, remainder = divmod(int(total), len(tasks))
        return {task: base + (1 if index < remainder else 0)
                for index, task in enumerate(sorted(tasks))}


def probabilities_for(value_model, slots) -> np.ndarray:
    if not slots:
        return np.zeros(0)
    return value_model.predict(np.stack([slot.features for slot in slots]))
