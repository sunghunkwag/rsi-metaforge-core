"""Episodic memory used as a control input, not as an archive.

An ``Episode`` is one search window: which pathway searched which task, from
which depth of its enumeration, at what cost, and what happened. Three
consumers read it:

* the controller reads exact frontier state (how deep each task/pathway/grammar
  combination has been searched, and whether it is exhausted), so no budget is
  spent re-running a prefix whose outcome is already known;
* the value model is refit every generation by replaying episodes
  (``replay`` = all generations; ``latest`` = most recent generation only);
* pathway genesis reads verified solutions to create new dormant pathways.

``FailureMemory`` (optional, per arm) is a fourth record: for each task, the
programs that failed its public examples. It needs no verifier receipt because
it is computed from the public examples the search already sees, and a public
failure is final under any enumeration order. Searches consult it so that no
pathway, and no grammar after a sleep phase, pays to evaluate a known failure
again.

Contamination guard: an episode labeled ``verified`` or ``rejected`` must carry
an authentic verifier receipt for the same task and program digest whose
verdict matches the label. Self-reported success raises ``ContaminationError``
and never reaches the value model. Accumulation alone is not adaptation; what
counts is that the next generation's allocation changes because of these
records, which the experiment measures.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict

OUTCOMES = ("none", "verified", "rejected")


class ContaminationError(ValueError):
    """An outcome label that the frozen verifier did not issue."""


class FailureMemory:
    """Per-task sets of programs that failed the task's public examples."""

    def __init__(self):
        self._sets: dict[str, set] = {}

    def for_task(self, task: str) -> set:
        return self._sets.setdefault(task, set())

    def sizes(self) -> dict[str, int]:
        return {task: len(failed) for task, failed in sorted(self._sets.items())}


class NearMissMemory:
    """Per task, the failed programs that matched the most public examples.

    Recorded at evaluation time by a search that evaluates every public
    example of a failed candidate instead of stopping at the first mismatch.
    The match decision, and therefore the logical budget, is unchanged.
    """

    def __init__(self, keep: int = 4):
        self.keep = int(keep)
        self._best: dict[str, list] = {}
        self._serial = 0

    def record(self, task: str, term, matched: int, total: int) -> None:
        if matched <= 0 or matched >= total:
            return
        entries = self._best.setdefault(task, [])
        if any(entry[3] == term for entry in entries):
            return
        self._serial += 1
        entries.append((matched / total, -self._serial, matched, term))
        entries.sort(key=lambda entry: (-entry[0], -entry[1]))
        del entries[self.keep:]

    def best(self, task: str) -> list[tuple[int, object]]:
        return [(entry[2], entry[3]) for entry in self._best.get(task, [])]

    def recorder(self, task: str) -> "NearMissRecorder":
        return NearMissRecorder(self, task)


class NearMissRecorder:
    """A picklable callback bound to one task."""

    def __init__(self, memory: NearMissMemory, task: str):
        self.memory, self.task = memory, task

    def __call__(self, term, matched: int, total: int) -> None:
        self.memory.record(self.task, term, matched, total)


@dataclass(frozen=True)
class Episode:
    generation: int
    task: str
    pathway: str
    kind: str
    fingerprint: str
    start: int
    evaluated: int
    exhausted: bool
    outcome: str
    digest: str | None
    features: tuple[float, ...]
    cpu_seconds: float
    receipt_id: int | None = None
    skipped_equivalent: int = 0
    skipped_known: int = 0

    def to_record(self) -> dict:
        record = asdict(self)
        record.pop("features")
        return record


@dataclass(frozen=True)
class SolutionRecord:
    task: str
    digest: str
    pathway: str
    kind: str
    origin: str
    generation: int
    receipt_id: int


class EpisodicMemory:
    def __init__(self, verifier):
        self._verifier = verifier
        self.episodes: list[Episode] = []
        self.solutions: dict[str, SolutionRecord] = {}
        self.rejected_signatures: dict[str, set] = {}
        self.slot_windows: Counter = Counter()

    def record(self, episode: Episode, receipt=None) -> None:
        if episode.outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {episode.outcome!r}")
        if episode.outcome == "none":
            if receipt is not None:
                raise ContaminationError("a window without a match cannot carry a receipt")
        else:
            if receipt is None or not self._verifier.is_authentic(receipt):
                raise ContaminationError("outcome label lacks an authentic verifier receipt")
            if receipt.task != episode.task or receipt.digest != episode.digest:
                raise ContaminationError("receipt does not certify this task and program")
            if receipt.verdict != (episode.outcome == "verified"):
                raise ContaminationError("outcome label disagrees with the verifier's verdict")
            if receipt.receipt_id != episode.receipt_id:
                raise ContaminationError("episode cites a different receipt")
        self.episodes.append(episode)
        self.slot_windows[(episode.task, episode.pathway)] += 1

    def remember_solution(self, record: SolutionRecord, receipt) -> None:
        if (not self._verifier.is_authentic(receipt) or not receipt.verdict
                or receipt.task != record.task or receipt.digest != record.digest
                or receipt.receipt_id != record.receipt_id):
            raise ContaminationError("only verifier-certified programs enter the solution store")
        self.solutions[record.task] = record

    def reject_signature(self, task: str, signature, receipt) -> None:
        if not self._verifier.is_authentic(receipt) or receipt.verdict or receipt.task != task:
            raise ContaminationError("only verifier-rejected behaviour can be marked rejected")
        self.rejected_signatures.setdefault(task, set()).add(signature)

    def is_rejected_behaviour(self, task: str, signature) -> bool:
        return signature in self.rejected_signatures.get(task, ())

    def replay(self, mode: str, generation: int) -> list[Episode]:
        """Episodes used to refit the value model after ``generation``."""
        if mode == "replay":
            return list(self.episodes)
        if mode == "latest":
            return [e for e in self.episodes if e.generation == generation]
        raise ValueError(f"unknown replay mode {mode!r}")

    @staticmethod
    def label(episode: Episode) -> int:
        return int(episode.outcome == "verified")
