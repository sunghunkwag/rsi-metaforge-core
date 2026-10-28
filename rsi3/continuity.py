"""Self-continuity: does the rewritten self still have the previous self's abilities?

Every sleep phase rewrites the system: RSI-2 refits the grammar on the
solution set, may adopt library entries, and refits the recognition model on
real and dreamed tasks. The stored solutions survive the rewrite as records,
but a record is not an ability. The question this module asks after every
rewrite is the ship-of-Theseus question in operational form: can the new self,
searching from scratch, still do what the old self could?

Definitions (TRAIN public data and self-generated problems only; hidden
examples, VALIDATION and TEST are never read here):

* The SELF is the pair (grammar, recognition model). It is what VALIDATION
  measures: RSI-2's ``assess`` searches each task with the recognition-
  conditioned grammar at B_eval.
* TRAIN RETENTION. A solved TRAIN task is retained by a self if a fresh,
  heuristic-free RSI-2 search under that self, with budget B_audit, finds a
  program that matches the task's public examples AND behaves like the stored
  verified solution on the binding integrator's probe inputs (same probe
  signature). A different program with the same public outputs but different
  behaviour is a different ability and does not count.
* SELF-EXAM. Re-deriving already-solved tasks cannot show a loss of
  generality: a development run (seed 44, PREDICTIONS_SELF_CONTINUITY.md)
  retained 100% of TRAIN at every generation while a VALIDATION task flipped
  between solved and unsolved. So the system also writes itself exam
  problems with known answers. An exam is a program sampled from the
  author grammar, run on the public inputs of a TRAIN task (the template);
  its outputs on those inputs are the exam's examples and the program is the
  answer key. A self passes an exam if its search at B_audit finds a program
  that matches the examples and has the answer key's probe signature on the
  template's probe inputs: a held-out generalization check, like VALIDATION's
  hidden examples, on inputs the search never saw. Exams are never used to
  fit anything: not the grammar, not the recognition model, not the value
  model, not rehearsal.
* Exam authorship (``exam_author``): ``"neutral"`` samples from the system's
  own productions and library with RSI-2's uniform prior weights, so neither
  the old nor the new self's weights shaped the question; ``"self"`` samples
  from the old self's grammar and keeps only exams the old self passes. An
  exam written at generation g joins the bank after generation g's
  comparison, so it first judges the rewrite of generation g+1.
* The CONTINUITY SCORE of a self = TRAIN tasks retained + exams passed.
  LOST abilities = TRAIN tasks or exams the old self has and the new self
  does not.

Modes (``ArmConfig.continuity``):

* ``off``      nothing is audited.
* ``measure``  the old and new selves are both audited after every rewrite
               and the result is recorded, including whether ``restore`` would
               have considered the rewrite a loss. Nothing is changed and no
               budget is charged; the run is otherwise identical to the same
               arm without auditing.
* ``restore``  the same audits. If the new self lost any ability, candidates
               are formed: the new self; if TRAIN tasks were lost, a rehearsed
               self (grammar and recognition refit with each lost TRAIN
               solution repeated ``rehearsal`` extra times, same seed, same
               dreams; exams are never rehearsed); and the old self's weights
               and recognition model with the current library. The candidate
               with the highest continuity score is kept; ties keep the new
               self, then the rehearsed one, so the old self returns only by
               scoring strictly more. Every audit and exam-writing evaluation
               is charged to the next generation's wake budget, so total
               logical work per generation is unchanged.

This is a gate on a discrete self-rewrite, which is where the regulation
study and RSI-3's first study place gates (ARCHITECTURE.md, D2); it never
pulls continuous parameters toward a reference.

It is a functional, measurable self-continuity check. It does not make the
system conscious and makes no claim about subjective experience.
"""
from __future__ import annotations

from dataclasses import dataclass
import random

from rsi2.corpus import Task
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.recognition import Recognition
from rsi2.sampling import sample_program
from rsi2.search import solve

MODES = ("off", "measure", "restore")
AUTHORS = ("neutral", "self")


@dataclass(frozen=True)
class SelfSnapshot:
    label: str
    grammar: Grammar
    recognition: object | None

    def grammar_for(self, task):
        if self.recognition is None:
            return self.grammar
        return self.recognition.grammar_for(task, self.grammar)


@dataclass(frozen=True)
class Exam:
    name: str
    template: str          # TRAIN task whose public inputs and probes are used
    task: Task             # examples = answer key's outputs on the public inputs
    answer: object         # the answer key (never shown to the searching self)
    signature: str         # answer key's behaviour on the template's probes
    written: int           # generation whose comparison preceded it joining the bank


def snapshot(state, label: str) -> SelfSnapshot:
    grammar = Grammar(library=dict(state.grammar.library), weights=state.grammar.weights,
                      context_weights=state.grammar.context_weights)
    return SelfSnapshot(label, grammar, state.recognition)


def _search(self_snapshot: SelfSnapshot, task, budget: int, search_config: dict):
    return solve(task.examples, task.request_type, budget, self_snapshot.grammar_for(task),
                 heuristic=None, step_budget=search_config["step_budget"],
                 max_size=search_config["max_size"],
                 max_expansions=search_config["max_expansions"])


def audit(self_snapshot: SelfSnapshot, tasks: dict, solutions: dict, integrator,
          budget: int, search_config: dict, library: dict) -> dict:
    """Re-derive every solved TRAIN task from scratch under one self.

    ``library`` is the current library. Library entries are only ever added,
    so it contains every entry any earlier self could reference; both the
    rediscovered program and the stored solution are evaluated against it.
    """
    retained, details, spent = set(), {}, 0
    for name in sorted(solutions):
        result = _search(self_snapshot, tasks[name], budget, search_config)
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


def sit_exams(self_snapshot: SelfSnapshot, exams, integrator, budget: int,
              search_config: dict, library: dict) -> dict:
    """One self takes every exam in the bank; only the examples are visible to it."""
    passed, details, spent = [], {}, 0
    for exam in exams:
        result = _search(self_snapshot, exam.task, budget, search_config)
        spent += result.candidates
        ok = (result.term is not None
              and integrator.signature(exam.template, result.term, library) == exam.signature)
        if ok:
            passed.append(exam.name)
        details[exam.name] = {"found": result.term is not None, "passed": ok,
                              "candidates": result.candidates}
    return {"self": self_snapshot.label, "passed": sorted(passed), "count": len(passed),
            "sat": len(exams), "spent": spent, "tasks": details}


def write_exams(author: SelfSnapshot, templates: list, rng, *, generation: int, keep: int,
                attempts: int, integrator, budget: int, search_config: dict, library: dict,
                known: set, require_author_pass: bool) -> tuple[list, int]:
    """Sample up to ``keep`` new exams with known answers from the author grammar.

    An exam is skipped if any public example fails to evaluate, if every
    output is the same value or every output equals the first input (constant
    and identity behaviour), or if a bank exam on the same template already
    has the same probe signature. With ``require_author_pass`` the author must
    pass it at ``budget``; the search work is returned for charging.
    """
    exams, spent = [], 0
    for index in range(attempts):
        if len(exams) >= keep:
            break
        template = templates[rng.randrange(len(templates))]
        term = sample_program(template.request_type, author.grammar, rng,
                              max_size=search_config["max_size"], max_attempts=20)
        if term is None:
            continue
        examples = []
        for inputs, _ in template.examples:
            result = evaluate(term, inputs, library=library,
                              step_budget=search_config["step_budget"])
            if not result.ok:
                break
            examples.append((inputs, result.value))
        if len(examples) != len(template.examples):
            continue
        outputs = [repr(value) for _, value in examples]
        if len(set(outputs)) == 1 or all(repr(value) == repr(inputs[0])
                                         for inputs, value in examples):
            continue
        signature = integrator.signature(template.name, term, library)
        if (template.name, signature) in known:
            continue
        exam = Exam(f"exam_g{generation}_{index}", template.name,
                    Task(f"exam_g{generation}_{index}", template.request_type,
                         tuple(examples), ()), term, signature, generation)
        if require_author_pass:
            sat = sit_exams(author, [exam], integrator, budget, search_config, library)
            spent += sat["spent"]
            if not sat["count"]:
                continue
        known.add((template.name, signature))
        exams.append(exam)
    return exams, spent


def rehearse(state, public_tasks: dict, lost, dreams, generation: int, repeats: int):
    """Refit grammar and recognition with each lost TRAIN ability rehearsed ``repeats`` more times."""
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
                 integrator, exams_per_generation: int = 0, exam_attempts: int = 64,
                 exam_author: str = "neutral"):
        if mode not in MODES:
            raise ValueError(f"unknown continuity mode {mode!r}")
        if exam_author not in AUTHORS:
            raise ValueError(f"unknown exam author {exam_author!r}")
        self.mode = mode
        self.budget = int(budget)
        self.rehearsal = int(rehearsal)
        self.search_config = dict(search_config)
        self.integrator = integrator          # a private instance: audit probes only
        self.exams_per_generation = int(exams_per_generation)
        self.exam_attempts = int(exam_attempts)
        self.exam_author = exam_author
        self.bank: list[Exam] = []
        self._known: set = set()

    def judge(self, self_snapshot: SelfSnapshot, public_tasks: dict, solutions: dict,
              library: dict) -> dict:
        train = audit(self_snapshot, public_tasks, solutions, self.integrator, self.budget,
                      self.search_config, library)
        exam = sit_exams(self_snapshot, self.bank, self.integrator, self.budget,
                         self.search_config, library)
        return {"train": train, "exam": exam, "score": train["count"] + exam["count"],
                "spent": train["spent"] + exam["spent"]}

    def _write(self, old: SelfSnapshot, public_tasks: dict, library: dict, seed: int,
               generation: int) -> tuple[list, int]:
        if self.exams_per_generation <= 0:
            return [], 0
        if self.exam_author == "neutral":
            author = SelfSnapshot("neutral", Grammar(library=dict(library)), None)
        else:
            author = old
        rng = random.Random(f"rsi3-self-exam-{seed}-{generation}")
        templates = [public_tasks[name] for name in sorted(public_tasks)]
        exams, spent = write_exams(
            author, templates, rng, generation=generation, keep=self.exams_per_generation,
            attempts=self.exam_attempts, integrator=self.integrator, budget=self.budget,
            search_config=self.search_config, library=library, known=self._known,
            require_author_pass=self.exam_author == "self")
        self.bank.extend(exams)
        return exams, spent

    def after_sleep(self, state, old: SelfSnapshot, public_tasks: dict, dreams,
                    generation: int) -> dict:
        """Audit the rewrite; in ``restore`` mode, possibly replace the new self."""
        if self.mode == "off":
            return {"mode": "off", "charged": 0}
        solutions = dict(state.solutions)
        library = state.grammar.library
        new = SelfSnapshot("new", state.grammar, state.recognition)
        new_j = self.judge(new, public_tasks, solutions, library)
        old_j = self.judge(old, public_tasks, solutions, library)
        lost_train = sorted(set(old_j["train"]["retained"]) - set(new_j["train"]["retained"]))
        lost_exam = sorted(set(old_j["exam"]["passed"]) - set(new_j["exam"]["passed"]))
        record = {"mode": self.mode, "old": old_j, "new": new_j, "lost": lost_train,
                  "lost_exams": lost_exam, "bank": len(self.bank),
                  "old_better": old_j["score"] > new_j["score"]}
        charged = 0
        winner, winner_j = new, new_j
        if self.mode == "restore":
            charged = new_j["spent"] + old_j["spent"]
            record["decision"] = "accept_new"
            if lost_train or lost_exam:
                candidates = [(new, new_j)]
                if lost_train:
                    rehearsed = rehearse(state, public_tasks, lost_train, dreams, generation,
                                         self.rehearsal)
                    rehearsed_j = self.judge(rehearsed, public_tasks, solutions, library)
                    charged += rehearsed_j["spent"]
                    candidates.append((rehearsed, rehearsed_j))
                    record["rehearsed"] = rehearsed_j
                # Reverting keeps the current library (entries are never
                # removed) and restores the old self's weights and recognition
                # model. With an unchanged library that is exactly the old
                # self, so its judgement is reused.
                restored = SelfSnapshot("old", Grammar(library=dict(library),
                                                       weights=old.grammar.weights,
                                                       context_weights=old.grammar.context_weights),
                                        old.recognition)
                restored_j = old_j
                if set(library) != set(old.grammar.library):
                    restored_j = self.judge(restored, public_tasks, solutions, library)
                    charged += restored_j["spent"]
                    record["restored"] = restored_j
                candidates.append((restored, restored_j))
                # max() keeps the first maximum: ties keep the new self, then
                # the rehearsed one; the old self wins only by scoring more.
                winner, winner_j = max(candidates, key=lambda pair: pair[1]["score"])
                record["decision"] = {"new": "accept_new", "rehearsed": "rehearse",
                                      "old": "revert"}[winner.label]
                state.grammar = winner.grammar
                state.recognition = winner.recognition
        exams, written_spent = self._write(old, public_tasks, library, state.seed, generation)
        if self.mode == "restore":
            charged += written_spent
        record.update({"charged": charged, "score": winner_j["score"],
                       "retained": winner_j["train"]["count"],
                       "audited": winner_j["train"]["audited"],
                       "exams_passed": winner_j["exam"]["count"],
                       "exams_sat": winner_j["exam"]["sat"],
                       "exams_written": [e.name for e in exams],
                       "exam_writing_spent": written_spent})
        return record
