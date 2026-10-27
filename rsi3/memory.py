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
