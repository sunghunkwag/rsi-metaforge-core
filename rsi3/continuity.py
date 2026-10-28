"""Self-continuity: does the rewritten self still have the previous self's abilities?

Every sleep phase rewrites the system: RSI-2 refits the grammar on the
solution set, may adopt library entries, and refits the recognition model on
real and dreamed tasks. The stored solutions survive the rewrite as records,
but a record is not an ability. The question this module asks after every
rewrite is the ship-of-Theseus question in operational form: can the new self,
searching from scratch, still re-derive what the old self could?

Definitions (all on TRAIN public data; hidden examples are never read here):

* The SELF is the pair (grammar, recognition model). It is what VALIDATION
  measures: RSI-2's ``assess`` searches each task with the recognition-
  conditioned grammar at B_eval.
* A task is RETAINED by a self if a fresh, heuristic-free RSI-2 search under
  that self, with budget B_audit, finds a program that matches the task's
  public examples AND behaves like the stored verified solution on the
  binding integrator's probe inputs (same probe signature). A different
  program with the same public outputs but different behaviour is a different
  ability and does not count.
* LOST abilities = tasks the old self retained and the new self does not.

Modes (``ArmConfig.continuity``):

* ``off``      nothing is audited.
* ``measure``  the new self is audited after every rewrite and the result is
               recorded. Nothing is changed and no budget is charged; the run
               is otherwise identical to the same arm without auditing.
* ``restore``  the old and new selves are both audited. If the new self lost
               abilities, it is repaired once by rehearsal: grammar and
               recognition are refit with each lost task's solution repeated
               ``rehearsal`` extra times (same seed, same dreams). The
               candidate selves (new, rehearsed, old weights with the current
               library) are ranked by retained count; ties keep the new self,
               then the rehearsed one, so the old self returns only by
               retaining strictly more. Every audit evaluation is charged to
               the next generation's wake budget, so total logical work per
               generation is unchanged.

This is a gate on a discrete self-rewrite, which is where the regulation
study and RSI-3's first study place gates (ARCHITECTURE.md, D2); it never
pulls continuous parameters toward a reference.

It is a functional, measurable self-continuity check. It does not make the
system conscious and makes no claim about subjective experience.
"""
from __future__ import annotations

from dataclasses import dataclass

from rsi2.grammar import Grammar
from rsi2.recognition import Recognition
from rsi2.search import solve

MODES = ("off", "measure", "restore")


@dataclass(frozen=True)
class SelfSnapshot:
    label: str
    grammar: Grammar
    recognition: object | None

    def grammar_for(self, task):
        if self.recognition is None:
            return self.grammar
        return self.recognition.grammar_for(task, self.grammar)


def snapshot(state, label: str) -> SelfSnapshot:
    grammar = Grammar(library=dict(state.grammar.library), weights=state.grammar.weights,
                      context_weights=state.grammar.context_weights)
    return SelfSnapshot(label, grammar, state.recognition)


def audit(self_snapshot: SelfSnapshot, tasks: dict, solutions: dict, integrator,
          budget: int, search_config: dict, library: dict) -> dict:
    """Re-derive every solved task from scratch under one self.

    ``library`` is the current library. Library entries are only ever added,
    so it contains every entry any earlier self could reference; both the
    rediscovered program and the stored solution are evaluated against it.
    """
    retained, details, spent = set(), {}, 0
    for name in sorted(solutions):
        task = tasks[name]
        grammar = self_snapshot.grammar_for(task)
        result = solve(task.examples, task.request_type, budget, grammar, heuristic=None,
                       step_budget=search_config["step_budget"],
                       max_size=search_config["max_size"],
                       max_expansions=search_config["max_expansions"])
        spent += result.candidates
        same = False
        if result.term is not None:
            found = integrator.signature(name, result.term, library)
            stored = integrator.signature(name, solutions[name], library)
            same = found == stored
        if same:
            retained.add(name)
        details[name] = {"found": result.term is not None, "retained": same,
                         "candidates": result.candidates}
    return {"self": self_snapshot.label, "retained": sorted(retained),
            "count": len(retained), "audited": len(solutions), "spent": spent,
            "tasks": details}


def rehearse(state, public_tasks: dict, lost, dreams, generation: int, repeats: int):
    """Refit grammar and recognition with each lost ability rehearsed ``repeats`` more times."""
    grammar = Grammar(library=dict(state.grammar.library))
    fitting = [(term, public_tasks[name].request_type) for name, term in state.solutions.items()]
    fitting += [(state.solutions[name], public_tasks[name].request_type)
                for name in sorted(lost) for _ in range(repeats)]
    grammar.fit(fitting)
    pairs = [(public_tasks[name], term) for name, term in state.solutions.items()]
    pairs += [(public_tasks[name], state.solutions[name]) for name in sorted(lost)
              for _ in range(repeats)]
    pairs += list(dreams)
    model = Recognition(state.seed * 1000003 + generation)
    model.fit(pairs, grammar)
    return SelfSnapshot("rehearsed", grammar, model)


class ContinuityGuard:
    def __init__(self, mode: str, *, budget: int, rehearsal: int, search_config: dict,
                 integrator):
        if mode not in MODES:
            raise ValueError(f"unknown continuity mode {mode!r}")
        self.mode = mode
        self.budget = int(budget)
        self.rehearsal = int(rehearsal)
        self.search_config = dict(search_config)
        self.integrator = integrator          # a private instance: audit probes only

    def after_sleep(self, state, old: SelfSnapshot, public_tasks: dict, dreams,
                    generation: int) -> dict:
        """Audit the rewrite; in ``restore`` mode, possibly replace the new self."""
        if self.mode == "off" or not state.solutions:
            return {"mode": self.mode, "charged": 0}
        solutions = dict(state.solutions)
        library = state.grammar.library
        new = SelfSnapshot("new", state.grammar, state.recognition)
        new_audit = audit(new, public_tasks, solutions, self.integrator, self.budget,
                          self.search_config, library)
        if self.mode == "measure":
            return {"mode": "measure", "charged": 0, "new": new_audit,
                    "retained": new_audit["count"], "audited": new_audit["audited"]}

        old_audit = audit(old, public_tasks, solutions, self.integrator, self.budget,
                          self.search_config, library)
        charged = new_audit["spent"] + old_audit["spent"]
        lost = sorted(set(old_audit["retained"]) - set(new_audit["retained"]))
        record = {"mode": "restore", "old": old_audit, "new": new_audit, "lost": lost,
                  "decision": "accept_new"}
        winner, winner_audit = new, new_audit
        if lost:
            rehearsed = rehearse(state, public_tasks, lost, dreams, generation,
                                 self.rehearsal)
            rehearsed_audit = audit(rehearsed, public_tasks, solutions, self.integrator,
                                    self.budget, self.search_config, library)
            charged += rehearsed_audit["spent"]
            # Reverting keeps the current library (entries are never removed)
            # and restores the old self's weights and recognition model. With
            # an unchanged library that is exactly the old self, so its audit
            # is reused; otherwise it is audited separately.
            restored_old = SelfSnapshot("old", Grammar(library=dict(library),
                                                       weights=old.grammar.weights,
                                                       context_weights=old.grammar.context_weights),
                                        old.recognition)
            restored_audit = old_audit
            if set(library) != set(old.grammar.library):
                restored_audit = audit(restored_old, public_tasks, solutions, self.integrator,
                                       self.budget, self.search_config, library)
                charged += restored_audit["spent"]
            # Ties keep the unmodified new self, then the rehearsed one; the old
            # self wins only by retaining strictly more.
            candidates = [(new, new_audit), (rehearsed, rehearsed_audit),
                          (restored_old, restored_audit)]
            winner, winner_audit = max(candidates, key=lambda pair: pair[1]["count"])
            record["rehearsed"] = rehearsed_audit
            record["decision"] = {"rehearsed": "rehearse", "new": "accept_new",
                                  "old": "revert"}[winner.label]
            state.grammar = winner.grammar
            state.recognition = winner.recognition
        record.update({"charged": charged, "retained": winner_audit["count"],
                       "audited": winner_audit["audited"]})
        return record
