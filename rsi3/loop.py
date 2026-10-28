"""One RSI-3 generation: the closed memory-feedback loop around RSI-2's sleep phase.

    plan (controller + value model) -> execute (resumable pathway searches)
    -> bind (integrator) -> verify (frozen verifier, one query per task)
    -> remember (episodic memory, receipt-guarded) -> refit value model (replay)
    -> RSI-2 sleep (abstraction, grammar fit, dreams, recognition, unchanged)
    -> genesis (new dormant pathways from verified solutions)

Only the wake phase differs from RSI-2. The sleep phase calls RSI-2's own
learners with the same arguments RSI-2's ``wake_sleep`` uses, so arm
differences are attributable to allocation, resumption, genesis, and binding.
This module never touches hidden examples (only ``verifier.py`` does), never
loads VALIDATION or TEST, and makes no decision from any evaluation partition.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
import time

import numpy as np

from rsi2.abstraction import learn_abstractions
from rsi2.grammar import Grammar
from rsi2.learning import State, dream_pairs
from rsi2.recognition import Recognition, task_features

from .continuity import ContinuityGuard, snapshot
from .controller import Controller, Slot, probabilities_for
from .integrator import BindingIntegrator
from .memory import Episode, EpisodicMemory, FailureMemory, SolutionRecord
from .pathways import DESIGNER_KINDS, PathwayRegistry
from .value_model import ValueModel, slot_features
from .verifier import FrozenVerifier, public_view, term_digest


@dataclass(frozen=True)
class ArmConfig:
    name: str
    allocation: str = "learned"        # "learned" | "uniform"
    value_mode: str = "replay"         # "replay" | "latest"
    genesis: bool = True
    designer_kinds: tuple = DESIGNER_KINDS
    failure_memory: bool = False       # carry public failures across grammars/pathways
    continuity: str = "off"            # "off" | "measure" | "restore" (continuity.py)


def standardized_features(public_tasks) -> dict:
    raw = np.stack([task_features(task) for task in public_tasks])
    mean, scale = raw.mean(axis=0), raw.std(axis=0)
    scale[scale < 1e-8] = 1.0
    scaled = np.clip((raw - mean) / scale, -10.0, 10.0)
    return {task.name: scaled[i] for i, task in enumerate(public_tasks)}


def sleep_phase(state, public_train, config, generation, sink=None) -> dict:
    """RSI-2's post-wake learning, with RSI-2's arguments, on public task views.

    ``sink`` (optional dict) receives the dreamed pairs, so a later step can
    refit recognition on exactly the same corpus. It changes nothing here.
    """
    search = config["search"]
    solutions, library, adopted = learn_abstractions(state.solutions, state.grammar.library,
                                                     generation)
    state.solutions = solutions
    state.grammar = Grammar(library=library, weights=state.grammar.weights,
                            context_weights=state.grammar.context_weights)
    state.library_history.extend(adopted)
    lookup = {task.name: task for task in public_train}
    fitting = [(term, lookup[name].request_type) for name, term in state.solutions.items()]
    grammar_metrics = state.grammar.fit(fitting)
    rng = random.Random(state.seed * 1000003 + generation)
    dreams, dream_evaluations = dream_pairs(public_train, state.grammar, rng,
                                            count=config.get("dreams", 16),
                                            max_size=search["max_size"],
                                            step_budget=search["step_budget"])
    if sink is not None:
        sink["dreams"] = list(dreams)
    pairs = [(lookup[name], term) for name, term in state.solutions.items()] + dreams
    model = Recognition(state.seed * 1000003 + generation)
    recognition_metrics = model.fit(pairs, state.grammar)
    state.recognition = model
    state.generation = generation
    state.logical_evaluations += dream_evaluations
    return {"adopted_library": adopted, "library_entries": len(state.grammar.library),
            "grammar_log_likelihood": grammar_metrics["log_likelihood_after"],
            "dreams": len(dreams), "dream_candidate_evaluations": dream_evaluations,
            "recognition_examples": recognition_metrics["examples"]}


class Runtime:
    def __init__(self, seed: int, train_tasks, arm: ArmConfig, config: dict):
        self.arm = arm
        self.config = config
        search = config["search"]
        self.public = [public_view(task) for task in train_tasks]
        # The verifier is the only holder of hidden examples; every other
        # component below receives public views.
        self.verifier = FrozenVerifier(train_tasks, step_budget=search["step_budget"])
        self.state = State(seed)
        self.features = standardized_features(self.public)
        self.memory = EpisodicMemory(self.verifier)
        self.failures = FailureMemory() if arm.failure_memory else None
        controller_config = config["controller"]
        self.registry = PathwayRegistry(
            self.public, self.features, genesis=arm.genesis,
            neighbors=controller_config["analog_neighbors"],
            designer_kinds=arm.designer_kinds, search_config=search,
            failure_memory=self.failures)
        self.value_model = ValueModel()
        self.controller = Controller(chunk=controller_config["chunk"],
                                     exploration=controller_config["exploration"], seed=seed)
        self.integrator = BindingIntegrator(self.public, step_budget=search["step_budget"])
        continuity = config.get("continuity", {})
        self.continuity = ContinuityGuard(
            arm.continuity, budget=continuity.get("audit_budget", config["B_eval"]),
            rehearsal=continuity.get("rehearsal", 3), search_config=search,
            integrator=BindingIntegrator(self.public, step_budget=search["step_budget"]))
        self.budget_debt = 0      # audit work charged to the next wake

    # ---- wake ------------------------------------------------------------
    def _slots(self, unsolved, pending, window) -> list[Slot]:
        slots = []
        for task in unsolved:
            if task in pending:
                continue
            for pid, similarity in self.registry.applicable(task, self.state):
                start, exhausted = self.registry.peek(task, pid, self.state)
                if exhausted:
                    continue
                kind = self.registry.pathways[pid].kind
                slots.append(Slot(task, pid, kind, start, similarity,
                                  slot_features(self.features[task], kind, similarity,
                                                start, window)))
        return slots

    def _run_window(self, task, pid, similarity, budget, generation, pending, log) -> int:
        fingerprint, search = self.registry.search(task, pid, self.state, generation)
        library = self.state.grammar.library
        kind = self.registry.pathways[pid].kind
        features = slot_features(self.features[task], kind, similarity, search.evaluated, budget)
        cpu_started = time.process_time()
        result = search.run(budget, self.integrator.skip_callback(task, library, self.memory))
        outcome, digest, receipt = "none", None, None
        if result.term is not None:
            digest = term_digest(result.term)
            receipt = self.verifier.verify(task, result.term, library, generation)
            pending.add(task)
            pathway = self.registry.pathways[pid]
            if receipt.verdict:
                outcome = "verified"
                self.state.solutions[task] = result.term
                record = SolutionRecord(task, digest, pid, kind, pathway.origin, generation,
                                        receipt.receipt_id)
                self.memory.remember_solution(record, receipt)
                self.integrator.bind_verified(task, result.term, library, record)
                pathway.verified_solves += 1
                pathway.solved_tasks.append(task)
                self.registry.drop_task(task)
            else:
                outcome = "rejected"
                self.integrator.bind_rejected(task, result.term, library, receipt, self.memory)
        episode = Episode(generation, task, pid, kind, fingerprint, result.start,
                          result.evaluated, result.exhausted, outcome, digest,
                          tuple(float(x) for x in features),
                          time.process_time() - cpu_started,
                          None if receipt is None else receipt.receipt_id,
                          result.skipped_matches, result.skipped_known)
        self.memory.record(episode, receipt)
        self.registry.pathways[pid].windows += 1
        log.append(episode.to_record())
        return result.evaluated

    def wake(self, generation) -> dict:
        budget_total = max(0, self.config["B_wake"] * len(self.public) - self.budget_debt)
        self.budget_debt = 0
        unsolved = sorted(task.name for task in self.public if task.name not in self.state.solutions)
        pending, log = set(), []
        spent = 0
        if self.arm.allocation == "uniform":
            for task, budget in Controller.uniform_split(budget_total, unsolved).items():
                spent += self._run_window(task, "prior", 0.0, budget, generation, pending, log)
        elif self.arm.allocation == "learned":
            chunk = self.controller.chunk
            while spent < budget_total:
                slots = self._slots(unsolved, pending, chunk)
                if not slots:
                    break
                probabilities = probabilities_for(self.value_model, slots)
                index = self.controller.choose(slots, probabilities, self.memory.slot_windows,
                                               len(self.memory.episodes))
                slot = slots[index]
                window = min(chunk, budget_total - spent)
                spent += self._run_window(slot.task, slot.pathway, slot.similarity, window,
                                          generation, pending, log)
        else:
            raise ValueError(f"unknown allocation {self.arm.allocation!r}")
        verified = [e for e in log if e["outcome"] == "verified"]
        return {"budget": budget_total, "spent": spent, "windows": len(log),
                "unsolved_at_start": len(unsolved),
                "verified": [{"task": e["task"], "pathway": e["pathway"], "kind": e["kind"],
                              "start": e["start"]} for e in verified],
                "rejected": sum(e["outcome"] == "rejected" for e in log),
                "skipped_equivalent": sum(e["skipped_equivalent"] for e in log),
                "skipped_known": sum(e["skipped_known"] for e in log),
                "exhausted_windows": sum(e["exhausted"] for e in log),
                "spent_by_kind": {kind: sum(e["evaluated"] for e in log if e["kind"] == kind)
                                  for kind in sorted({e["kind"] for e in log})},
                "max_depth": max((e["start"] + e["evaluated"] for e in log), default=0),
                "episodes": log}

    # ---- one generation --------------------------------------------------
    def generation(self) -> dict:
        generation = self.state.generation + 1
        cpu_started, wall_started = time.process_time(), time.perf_counter()
        self.registry.begin_generation()
        wake = self.wake(generation)
        self.state.logical_evaluations += wake["spent"]
        replayed = self.memory.replay(self.arm.value_mode, generation)
        fit = self.value_model.fit([e.features for e in replayed],
                                   [self.memory.label(e) for e in replayed])
        before_rewrite = snapshot(self.state, "old")
        sink = {}
        sleep = sleep_phase(self.state, self.public, self.config, generation, sink=sink)
        continuity = self.continuity.after_sleep(
            self.state, before_rewrite, {t.name: t for t in self.public},
            sink.get("dreams", ()), generation)
        self.budget_debt = continuity["charged"]
        self.state.logical_evaluations += continuity["charged"]
        created = self.registry.genesis(self.state, generation)
        failed = self.failures.sizes() if self.failures is not None else {}
        return {"generation": generation, "wake": wake, "value_fit": fit, "sleep": sleep,
                "continuity": continuity,
                "failure_memory": {"tasks": len(failed), "programs": sum(failed.values()),
                                   "max_per_task": max(failed.values(), default=0)},
                "genesis_created": created, "pathways": self.registry.summary(),
                "train_solved": len(self.state.solutions),
                "verifier_queries": self.verifier.queries,
                "integrator": self.integrator.stats(),
                "cpu_seconds": time.process_time() - cpu_started,
                "wall_seconds": time.perf_counter() - wall_started}
