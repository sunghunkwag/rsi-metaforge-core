"""Behavioral novelty search for an opt-in RSI-4 research pilot.

Lehman and Stanley (2011), doi:10.1162/EVCO_a_00025:
novelty is mean distance to k nearest behaviors in the current generation
and an accumulating archive. This module ranks imagined PUBLIC behaviors,
not proximity to a target or held-out performance.

The experiment reuses RSI-3's exact candidate generator, one-chunk
minimal-criterion test, verifier-backed solver, library learning, and budgets.
It never changes the live RSI-4 registered phases or their instruments.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from rsi2.terms import pretty
from rsi3.curriculum import Pool, imagine, select_hard, solve
from rsi3.loop import Runtime
from rsi3.metarl import shape_features


def _numbers(value):
    """List-valued and scalar public behaviors; nonnumeric entries use zero."""
    seq = value if isinstance(value, (tuple, list)) else (value,)
    nums = [float(v) if isinstance(v, (int, float, bool)) else 0.0 for v in seq]
    return nums, tuple(repr(v) for v in seq)


def behavior_descriptor(task) -> tuple[float, ...]:
    """Fixed-size phenotype based EXCLUSIVELY on public input/output examples.

    The existing 17-dimensional RSI-3 relation signature is augmented by
    continuous behavior statistics so distinct transformations within the
    same Boolean shape are not automatically collapsed. Task names and
    the program that produced the examples are deliberately ignored.
    """
    examples = tuple(task.examples)
    if not examples:
        raise ValueError("A behavior needs at least one public example")
    flags = [float(v) for v in shape_features(
        examples, extended=True, fixed_length=True)]
    rows = []
    for inputs, output in examples:
        source = inputs[0] if len(inputs) == 1 else inputs
        x, x_repr = _numbers(source)
        y, y_repr = _numbers(output)
        n_x, n_y = len(x), len(y)
        x_sum, y_sum = sum(x), sum(y)
        overlaps = sum(1 for value in y_repr if value in x_repr)
        rows.append((
            math.tanh(n_y / 8.0),
            math.tanh((n_y - n_x) / 8.0),
            math.tanh(y_sum / (8.0 + n_y)),
            math.tanh((y_sum - x_sum) / (8.0 + n_x + n_y)),
            len(set(y_repr)) / max(1, n_y),
            overlaps / max(1, n_y),
            float(x_repr == y_repr),
            sum(v > 0 for v in y) / max(1, n_y),
        ))
    extras = [sum(r[i] for r in rows) / len(rows) for i in range(8)]
    result = tuple(round(v, 8) for v in flags + extras)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("Non-finite behavior descriptor")
    return result


def distance(a, b) -> float:
    """Scale-independent Euclidean distance averaged across feature axes."""
    if len(a) != len(b) or not a:
        raise ValueError("Behavior dimensions must match and be nonempty")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def novelty_scores(vectors, archived=(), k: int = 10) -> list[float]:
    """Mean k-nearest-neighbor sparseness (the current item excludes itself).

    Comparison set = other candidates in the same generation + prior archive.
    Sparse startup populations use however many neighbors exist. A singleton
    without history has novelty 0 rather than an invented infinite reward.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    vectors = [tuple(v) for v in vectors]
    archived = [tuple(v) for v in archived]
    scores = []
    for i, current in enumerate(vectors):
        neighbors = [
            distance(current, other)
            for j, other in enumerate(vectors) if j != i
        ]
        neighbors.extend(distance(current, other) for other in archived)
        neighbors.sort()
        closest = neighbors[:k]
        scores.append(sum(closest) / len(closest) if closest else 0.0)
    return scores


@dataclass
class NoveltyArchive:
    """FIFO archive of distinct, public behavior vectors with bounded memory."""

    capacity: int = 256

    def __post_init__(self):
        if self.capacity <= 0:
            raise ValueError("Archive capacity must be positive")
        self.items: list[tuple[float, ...]] = []

    def add(self, vector) -> bool:
        vector = tuple(float(x) for x in vector)
        if not vector or not all(math.isfinite(x) for x in vector):
            raise ValueError("Invalid archive vector")
        if vector in self.items:
            return False
        if self.items and len(vector) != len(self.items[0]):
            raise ValueError("Archive vector dimensions differ")
        self.items.append(vector)
        if len(self.items) > self.capacity:
            self.items.pop(0)
        return True


class NoveltyCurriculumRuntime(Runtime):
    """Opt-in replacement for RSI-3's curriculum ordering, not its verifier.

    The sole change is the order of eligible imagined tasks sent to the
    existing solver. This preserves the self-curriculum arm's sleep-phase
    integration and isolates the algorithm from all RSI-4 registered runs.
    """

    def _curriculum(self, generation: int) -> dict:
        settings = self.config.get("curriculum", {})
        novelty = self.config.get("novelty", {})
        k = int(novelty.get("k", 10))
        if not hasattr(self, "curriculum_pool"):
            self.curriculum_pool = Pool(int(settings.get("pool", 48)))
            self.curriculum_record = []
        if not hasattr(self, "novelty_archive"):
            self.novelty_archive = NoveltyArchive(int(novelty.get("archive", 256)))

        tasks = imagine(self, generation, int(settings.get("count", 48)))
        vectors = [behavior_descriptor(task) for task in tasks]
        scores = novelty_scores(vectors, self.novelty_archive.items, k=k)
        by_name = {task.name: score for task, score in zip(tasks, scores)}
        by_vector = {task.name: vector for task, vector in zip(tasks, vectors)}

        # Identical minimal-criterion probe and exactly the same solver
        # budget as the incumbent curriculum arm. Novelty does not get
        # to bypass the authentic verification performed by solve().
        hard, probe_spent = select_hard(
            self, tasks, int(settings.get("hard_chunk", 16)))
        ranked = sorted(hard, key=lambda task: (-by_name[task.name], task.name))
        chosen = ranked[:int(settings.get("solve", 24))]
        programs, solve_spent = solve(self, chosen, generation)

        added = 0
        for task in chosen:
            added += self.novelty_archive.add(by_vector[task.name])
            if task.name in programs:
                self.curriculum_pool.add(task, programs[task.name])

        self.curriculum_record.append({
            "generation": generation, "imagined": len(tasks),
            "hard_candidates": len(hard), "hard": len(chosen),
            "selected": [task.name for task in chosen],
            "novelty_scores": {task.name: round(by_name[task.name], 8)
                               for task in chosen},
            "archive_size": len(self.novelty_archive.items),
            "solved": sorted(programs),
            "programs": {name: pretty(term) for name, term in programs.items()},
        })
        return {
            "imagined": len(tasks), "hard_candidates": len(hard),
            "hard": len(chosen), "solved": len(programs),
            "pool": len(self.curriculum_pool.items),
            "novelty_archive": len(self.novelty_archive.items),
            "novelty_archive_added": added,
            "novelty_mean": round(sum(scores) / len(scores), 8) if scores else 0.0,
            "novelty_max": round(max(scores), 8) if scores else 0.0,
            "curriculum_evaluations": probe_spent + solve_spent,
        }
