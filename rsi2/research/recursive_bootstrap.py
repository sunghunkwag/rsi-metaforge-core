"""A TRAIN-only recursive learning controller with fresh causal task searches.

This module cannot acquire evaluation partitions. Only its CLI worker loads
TRAIN. Injected kernels receive public examples, a prior-generation verified
raw-program bank, the current conditioned grammar and an executable DSL scorer.
Every learning label has independent public AND hidden TRAIN verification.
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import copy
from dataclasses import dataclass, field, is_dataclass
import json
from pathlib import Path
import random
import time

from ..corpus import Task
from ..evaluator import evaluate
from ..grammar import Grammar
from ..heuristics import zero_heuristic
from ..recognition import Recognition
from ..sampling import sample_program
from ..search import HEURISTIC_TYPE
from ..terms import Term, pretty
from ..types import TypeInferenceError, infer, unify
from .compression import compress_verified, verify_solutions
from .diagnostics import audit_candidate, profile_from_tasks
from .repair_search import RepairSeed


ARMS = ("BASE", "BRUTE640", "ONESHOT", "FULL", "NO_LIBRARY",
        "NO_RECOGNITION", "NO_HEURISTIC")
REGISTERED_CONFIG = {
    "schema_version": 1, "generations": 8, "seeds": [11, 22, 33],
    "arms": list(ARMS), "B_wake": 64, "B_eval": 64, "B_brute": 640,
    "screen_budget": 16, "screen_tasks": 4, "confirm_candidates": 2,
    "dreams": 16, "dream_attempts": 256,
    "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000,
               "beta_normalize": True, "max_normalization_steps": 20000,
               "force_wrapper_lambdas": True},
    "max_cpu_seconds_per_search": 10, "cpu_limit_seconds": 600,
    "proposal_provider": "HeuristicProposalProvider", "kernel": "population",
    "heuristics": {"N_h": 4, "N_m": 2, "screen_tasks": 4,
                   "screen_budget_divisor": 4, "confirm_candidates": 2},
}
WORK_FIELDS = (
    "task_candidates", "task_example_evaluations", "task_evaluator_steps",
    "heuristic_calls", "heuristic_evaluations", "heuristic_steps",
    "heuristic_failures", "expansions", "normalization_steps", "beta_reductions",
    "verification_programs", "verification_examples", "verification_steps",
    "proposal_slots", "proposal_terms", "probe_programs", "probe_examples",
    "probe_steps", "dream_sampling_calls", "dream_programs", "dream_examples",
    "dream_steps", "proposal_frontier_pops", "proposal_raw_terms",
    "proposal_replayed_terms", "proposal_normalization_steps",
    "proposal_beta_reductions",
)


class CpuStop(Exception):
    pass


class CpuGuard:
    """Between-operation guard; the CLI's score-blind parent enforces the cap."""
    def __init__(self, seconds):
        self.started, self.seconds = time.process_time(), float(seconds)

    def remaining(self):
        return self.seconds - (time.process_time() - self.started)

    def check(self):
        if self.remaining() <= 0:
            raise CpuStop("CPU budget exhausted")


def _work():
    return dict.fromkeys(WORK_FIELDS, 0)


def _add(target, source):
    for field in target:
        target[field] += source.get(field, 0)


def _delta(after, before):
    return {field: after[field] - before[field] for field in before}


def jsonable(value):
    if isinstance(value, Term):
        return value.to_dict()
    if is_dataclass(value):
        return {name: jsonable(item) for name, item in vars(value).items()}
    if isinstance(value, dict):
        return {str(name): jsonable(item) for name, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    return value


def atomic_write(path, record):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")

    def encode(value):
        if isinstance(value, Term):
            return value.to_dict()
        if is_dataclass(value):
            return vars(value)
        raise TypeError(f"unsupported checkpoint value: {type(value).__name__}")

    # Preserve every field while avoiding a second entire history-sized object.
    with temporary.open("w") as stream:
        json.dump(record, stream, default=encode, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


@dataclass
class RecursiveState:
    seed: int
    arm: str
    generation: int = 0
    grammar: Grammar = field(default_factory=Grammar)
    raw_solutions: dict = field(default_factory=dict)
    solutions: dict = field(default_factory=dict)
    acceptance_records: dict = field(default_factory=dict)
    recognition: object = None
    heuristic: Term = field(default_factory=zero_heuristic)
    library_history: list = field(default_factory=list)
    heuristic_history: list = field(default_factory=list)

    def condition(self, task):
        return (self.recognition.grammar_for(task, self.grammar)
                if self.recognition is not None else self.grammar)


def state_record(state):
    return copy.deepcopy({"seed": state.seed, "arm": state.arm, "generation": state.generation,
            "raw_solutions": state.raw_solutions, "solutions": state.solutions,
            "acceptance_records": state.acceptance_records,
            "library": state.grammar.library, "grammar_weights": state.grammar.weights,
            "grammar_context_weights": [{"parent": p, "argument": a, "weights": w}
                                        for (p, a), w in state.grammar.context_weights.items()],
            "recognition": state.recognition.to_dict() if state.recognition is not None else None,
            "heuristic": state.heuristic, "heuristic_readable": pretty(state.heuristic),
            "library_history": state.library_history,
            "heuristic_history": state.heuristic_history})


def _bank(state):
    return tuple(RepairSeed(state.raw_solutions[name], state.acceptance_records[name]["id"])
                 for name in sorted(state.raw_solutions))


def population_kernel_factory():
    from .population_search import solve_population

    def call(examples, request_type, budget, grammar, *, bank, heuristic, seed, limits):
        return solve_population(examples, request_type, budget, grammar,
                                accepted_seeds=bank, heuristic=heuristic, seed=seed, **limits)
    return call


def _get(record, name, default=0):
    return record.get(name, default) if isinstance(record, dict) else getattr(record, name, default)


def _search(task, state, budget, heuristic, bank, generation, number,
            config, factory, guard, work):
    guard.check()
    limits = dict(config["search"])
    limits["max_cpu_seconds"] = min(config["max_cpu_seconds_per_search"], guard.remaining())
    # A fresh instance prevents cache or frontier state crossing calls/seeds/arms.
    result = factory()(task.examples, task.request_type, budget, state.condition(task),
                       bank=bank, heuristic=heuristic,
                       seed=state.seed * 1000003 + generation * 1009 + number,
                       limits=limits)
    candidates = _get(result, "candidates")
    logical = _get(result, "logical_evaluations", candidates)
    if (type(candidates) is not int or type(logical) is not int
            or not 0 <= candidates <= logical <= budget):
        raise ValueError("task kernel violated the complete/helper candidate budget")
    if not isinstance(_get(result, "term", None), (Term, type(None))):
        raise ValueError("task kernel must return an actual Term or None")
    work["task_candidates"] += logical
    work["task_example_evaluations"] += _get(result, "evaluator_calls", _get(result, "example_evaluations"))
    work["task_evaluator_steps"] += _get(result, "evaluation_steps", _get(result, "evaluator_steps"))
    for field in ("heuristic_calls", "heuristic_evaluations", "heuristic_steps",
                  "heuristic_failures", "expansions", "normalization_steps", "beta_reductions"):
        work[field] += _get(result, field)
    return result


def _verify(task, term, library, config, guard, work):
    guard.check()
    proof = verify_solutions({task.name: term}, library, [task],
                             step_budget=config["search"]["step_budget"])
    _proof_cost(proof["cost"], work)
    return proof


def _proof_cost(cost, work):
    for origin, target in (("program_evaluations", "verification_programs"),
                           ("example_evaluations", "verification_examples"),
                           ("evaluator_steps", "verification_steps")):
        work[target] += cost[origin]


def _measure(state, tasks, budget, heuristic, bank, generation, config,
             factory, guard, work, checkpoint=lambda: None, *, update=False, destination=None):
    report = {} if destination is None else destination
    rows = []
    report.update(status="running", tasks=len(tasks), tasks_completed=0, solved=0,
                  solved_names=[], solved_fraction=None, budget=budget, records=rows,
                  measurement_generation=generation, bank_records=[s.training_record for s in bank],
                  heuristic=heuristic)
    for number, task in enumerate(tasks):
        report["in_progress"] = {"name": task.name, "stage": "public_search"}
        checkpoint()
        result = _search(task, state, budget, heuristic, bank, generation, number,
                         config, factory, guard, work)
        term = _get(result, "term", None)
        row = {"name": task.name, "solved": None, "public_selected": term is not None,
               "search": jsonable(result), "verification": None}
        rows.append(row)
        report["in_progress"]["stage"] = "independent_verification"
        checkpoint()
        proof = _verify(task, term, state.grammar.library, config, guard, work) if term is not None else None
        accepted = proof is not None and proof["passed"]
        row.update(solved=accepted, verification=proof)
        if update and accepted:
            previous = state.solutions.get(task.name)
            better = previous is None or (term.size, -state.grammar.log_probability(
                term, request_type=task.request_type)) < (previous.size, -state.grammar.log_probability(
                    previous, request_type=task.request_type))
            if better:
                identifier = f"seed{state.seed}:{state.arm}:g{generation}:{task.name}"
                state.raw_solutions[task.name] = term
                state.solutions[task.name] = term
                state.acceptance_records[task.name] = {"id": identifier, "generation": generation,
                                                       "task": task.name, "verification": proof}
                row["retained_as_learning_label"] = True
        report.update(tasks_completed=len(rows), solved=sum(r["solved"] is True for r in rows),
                      solved_names=sorted(r["name"] for r in rows if r["solved"] is True))
        checkpoint()
    names = sorted(row["name"] for row in rows if row["solved"])
    report.update(status="complete", solved_fraction=len(names) / len(rows) if rows else 0.0)
    report.pop("in_progress", None)
    checkpoint()
    return report


def _dreams(state, train, config, guard, work, destination=None):
    rng_seed = state.seed * 1000003 + state.generation
    rng = random.Random(rng_seed)
    trials = [] if destination is None else destination
    pairs = []
    for index in range(config["dream_attempts"]):
        if len(pairs) >= config["dreams"]:
            break
        guard.check()
        task = train[rng.randrange(len(train))]
        trial = {"sampler_index": index, "rng_seed": rng_seed,
                 "task": task.name, "request_type": task.request_type.to_dict(),
                 "term": None, "sampled": False, "sampling_completed": False,
                 "evaluations": [], "completed": False, "accepted": False,
                 "reason": "sampling_in_progress"}
        trials.append(trial)
        work["dream_sampling_calls"] += 1
        term = sample_program(task.request_type, state.grammar, rng,
                              max_size=config["search"]["max_size"], max_attempts=20)
        trial.update(term=term, sampled=term is not None, sampling_completed=True)
        if term is None:
            trial.update(completed=True, reason="sampler_returned_none")
            continue
        work["dream_programs"] += 1
        examples = []
        for inputs, _ in task.examples:
            guard.check()
            result = evaluate(term, inputs, library=state.grammar.library,
                              step_budget=config["search"]["step_budget"])
            work["dream_examples"] += 1
            work["dream_steps"] += result.steps
            trial["evaluations"].append({
                "public_example_index": len(trial["evaluations"]),
                "inputs": inputs, "ok": result.ok, "value": result.value,
                "error": result.error, "steps": result.steps})
            if not result.ok:
                break
            examples.append((inputs, result.value))
        accepted = len(examples) == len(task.examples)
        trial.update(completed=True, accepted=accepted,
                     reason="accepted" if accepted else "public_runtime_failure")
        if accepted:
            pairs.append((Task(f"dream_{index}", task.request_type, tuple(examples), ()), term))
    return pairs


def _learn(state, train, config, guard, work, checkpoint=lambda: None, destination=None):
    report = {} if destination is None else destination
    report.update(status="running", compression=None, grammar=None, recognition=None,
                  dream_trials=[], dream_rng_seed=state.seed * 1000003 + state.generation)
    checkpoint()
    guard.check()
    compression = None
    if state.arm != "NO_LIBRARY":
        compression = compress_verified(state.solutions, state.grammar.library,
                                        state.generation, train,
                                        step_budget=config["search"]["step_budget"])
        _proof_cost(compression["cost"], work)
        if compression["status"] != "complete":
            raise ValueError("retained TRAIN solutions failed independent compression verification")
        state.solutions = compression["solutions"]
        state.grammar = Grammar(library=compression["library"],
                                primitives=state.grammar.primitives, constants=state.grammar.constants,
                                weights=state.grammar.weights, context_weights=state.grammar.context_weights)
        state.library_history.extend(compression["records"])
        report["compression"] = compression
        checkpoint()
    guard.check()
    lookup = {t.name: t for t in train}
    grammar_metrics = state.grammar.fit([(state.solutions[name], lookup[name].request_type)
                                         for name in sorted(state.solutions)])
    report["grammar"] = grammar_metrics
    checkpoint()
    recognition_metrics, dreams = None, []
    if state.arm != "NO_RECOGNITION":
        dreams = _dreams(state, train, config, guard, work, report["dream_trials"])
        guard.check()
        model = Recognition(state.seed * 1000003 + state.generation)
        recognition_metrics = model.fit(
            [(lookup[name], state.solutions[name]) for name in sorted(state.solutions)] + dreams,
            state.grammar)
        state.recognition = model
    report.update(status="complete", recognition=recognition_metrics, dreams=len(dreams),
                  real_learning_labels=sorted(state.solutions),
                  dreams_never_compression_or_verified_bank_labels=True)
    checkpoint()
    return report


def _probe(term, library, profile, config, guard, work):
    guard.check()
    report = audit_candidate(term, library, profile=profile,
                             step_budget=config["search"]["step_budget"])
    work["probe_programs"] += report["program_evaluations"]
    work["probe_examples"] += report["example_evaluations"]
    work["probe_steps"] += report["evaluator_steps"]
    return report


def _provider_work(provider, work):
    telemetry = copy.deepcopy(getattr(provider, "last_report", {}))
    supplied = telemetry.get("work", {})
    # The complete provider report is retained even when extra keys are added.
    aliases = {"frontier_pops": "proposal_frontier_pops",
               "generated_full_candidates": "proposal_raw_terms",
               "replayed_ast_draws": "proposal_replayed_terms",
               "normalization_steps": "proposal_normalization_steps",
               "beta_reductions": "proposal_beta_reductions"}
    for origin, target in aliases.items():
        work[target] += supplied.get(origin, 0)
    return telemetry


def improve(state, train, config, factory, provider, guard, work, checkpoint=lambda: None,
            destination=None):
    """Admit only a valid informative strict paired TRAIN solved-set expansion."""
    bank, incumbent = _bank(state), state.heuristic
    report = {} if destination is None else destination
    report.update(status="running", generation=state.generation, incumbent=incumbent,
                  incumbent_full={}, candidates=[], adopted=False)
    incumbent_full = _measure(state, train, config["B_eval"], incumbent, bank,
                              state.generation, config, factory, guard, work, checkpoint,
                              destination=report["incumbent_full"])
    guard.check()
    checkpoint()
    records = provider.draw(state, config)
    provider_report = _provider_work(provider, work)
    if len(records) != 6 or len({r["index"] for r in records}) != 6:
        raise ValueError("heuristic provider must log six distinct Nh4+Nm2 slots")
    if sum(r.get("origin") == "enumeration" for r in records) != 4 or sum(
            r.get("origin") == "mutation" for r in records) != 2:
        raise ValueError("heuristic provider changed preregistered enumeration/mutation quotas")
    records = copy.deepcopy(records)
    report.update(candidates=records, provider=provider_report)
    work["proposal_slots"] += 6
    work["proposal_terms"] += sum(isinstance(r.get("term"), Term) for r in records)
    screened = []
    public_profile = profile_from_tasks(train)
    for record in records:
        record.update(screen=None, full=None, adopted=False, semantic_probe=None, train_probe=None)
        term = record.get("term")
        if term is None or record.get("rejection") is not None:
            continue
        try:
            unify(infer(term, library=state.grammar.library), HEURISTIC_TYPE)
        except (TypeInferenceError, RecursionError) as error:
            record["rejection"] = f"invalid_type: {error}"
            continue
        record["semantic_probe"] = _probe(term, state.grammar.library, None, config, guard, work)
        checkpoint()
        record["train_probe"] = _probe(term, state.grammar.library, public_profile, config, guard, work)
        checkpoint()
        record["screen"] = {}
        _measure(
            state, train[:config["screen_tasks"]], config["screen_budget"], term, bank,
            state.generation, config, factory, guard, work, checkpoint,
            destination=record["screen"])
        if all(p["valid"] and p["informative"] for p in
               (record["semantic_probe"], record["train_probe"])):
            screened.append(record)
        else:
            record["rejection"] = "invalid_or_uninformative"
    screened.sort(key=lambda r: (-r["screen"]["solved"], r["index"]))
    previous = set(incumbent_full["solved_names"])
    best, selected = incumbent_full, None
    for record in screened[:config["confirm_candidates"]]:
        record["full"] = {}
        full = _measure(state, train, config["B_eval"], record["term"], bank,
                        state.generation, config, factory, guard, work, checkpoint,
                        destination=record["full"])
        probes = (record["semantic_probe"], record["train_probe"])
        admissible = all(p["valid"] and p["informative"] for p in probes)
        current = set(full["solved_names"])
        if admissible and previous < current and full["solved"] > best["solved"]:
            best, selected = full, record
        else:
            record["rejection"] = ("invalid_or_uninformative" if not admissible
                                   else "no_strict_solved_set_expansion")
    if selected is not None:
        selected.update(adopted=True, rejection=None)
        state.heuristic = selected["term"]
    report.update({"status": "complete", "best_full": best,
              "adopted": selected is not None,
              "adopted_index": selected["index"] if selected else None,
              "next_wake_heuristic": state.heuristic,
              "selection_scope": "TRAIN development only; finite-case evidence",
              "admission_rule": "both probes valid/informative and strict hidden-verified solved-set expansion"})
    state.heuristic_history.append({"generation": state.generation,
                                   "adopted": report["adopted"], "adopted_index": report["adopted_index"],
                                   "next_wake_heuristic": state.heuristic,
                                   "incumbent_solved_names": incumbent_full["solved_names"],
                                   "best_solved_names": best["solved_names"],
                                   "evidence_reference": f"generations[{state.generation}].heuristic"})
    checkpoint()
    return report


def _online(row, state, train):
    wake, learning, heuristic = row["wake"], row.get("learning"), row.get("heuristic")
    failed = [r["name"] for r in wake["records"] if not r["solved"]]
    new_labels = row["new_retained_tasks"]
    return {
        "current_performance": {"wake_hidden_verified": wake["solved"], "tasks": len(train),
                                "wake_fraction": wake["solved_fraction"], "retained_tasks": len(state.solutions)},
        "failure_clusters": {"unsolved": failed,
                             "selected_but_failed_verification": [r["name"] for r in wake["records"]
                                                                   if r["public_selected"] and not r["solved"]]},
        "bottleneck": {"new_verified_labels": len(new_labels),
                       "strict_mdl_adoptions": len(learning["compression"]["records"])
                       if learning and learning["compression"] else 0,
                       "heuristic_adopted": bool(heuristic and heuristic["adopted"])},
        "previous_attempt_insufficiency": "No previous cycle" if row["generation"] == 0 else
            {"new_task_names_since_previous_cycle": new_labels,
             "remaining_unsolved_names": failed},
        "intervention": {"arm": state.arm, "prior_generation_bank_records": row["bank_records"],
                         "learning_updated": learning is not None},
        "mechanism": "Verified own programs seed future typed edits; fitted grammar/recognizer change production weights; an admitted DSL scorer chooses future parents.",
        "verification_plan": "Independent TRAIN public+hidden verification, strict total AST MDL, paired fresh-kernel heuristic confirmation and solved-set nonloss.",
        "risks": "Finite TRAIN cases and related variants; prior collapse; extra interpreter cost; partial prefixes cannot establish eight generations or original a-e.",
        "result": {"wake_solved_names": wake["solved_names"], "new_retained_names": new_labels,
                   "library_entries": len(state.grammar.library), "work": row["work"]},
        "keep_revert_revise": "Retain independently verified task labels/strict-MDL rewrites; " +
            ("use admitted scorer next wake" if heuristic and heuristic["adopted"] else "retain incumbent scorer") +
            "; recursive capability remains unverified",
        "updated_rule": {"type": "loop", "scope": "TRAIN development", "next_bank": sorted(state.raw_solutions),
                         "next_heuristic": state.heuristic, "source_generation": row["generation"]},
    }


def run_arm(train_tasks, seed, arm, config=None, *, kernel_factory=population_kernel_factory,
            proposal_provider=None, through_generation=None, guard=None, checkpoint=None):
    """Execute a new independent arm; shortened campaigns are always partial."""
    config = copy.deepcopy(REGISTERED_CONFIG if config is None else config)
    if arm not in ARMS or seed not in config["seeds"] or config["generations"] < 8:
        raise ValueError("registered arms/seeds and at least eight generations are required")
    train = sorted(tuple(train_tasks), key=lambda t: t.name)
    if len(train) < config["screen_tasks"] or len({t.name for t in train}) != len(train):
        raise ValueError("TRAIN requires unique tasks and the fixed screen-task count")
    if (config["B_wake"], config["B_eval"], config["B_brute"], config["screen_budget"],
            config["screen_tasks"], config["confirm_candidates"]) != (64, 64, 640, 16, 4, 2):
        raise ValueError("pilot budgets and screen/confirmation quotas are frozen")
    if proposal_provider is None:
        from .heuristic_proposals import HeuristicProposalProvider
        proposal_provider = HeuristicProposalProvider()
    limit = config["generations"] if through_generation is None else through_generation
    if type(limit) is not int or not 0 <= limit <= config["generations"]:
        raise ValueError("through_generation must lie within the campaign")
    guard = guard or CpuGuard(config["cpu_limit_seconds"])
    state, work = RecursiveState(seed, arm), _work()
    started, cpu = time.perf_counter(), time.process_time()
    record = {"seed": seed, "arm": arm, "status": "running", "source": "TRAIN only",
              "config": config, "generations": [], "work": work,
              "original_a_e": "NOT ASSESSED", "evaluation_partitions_opened": False,
              "candidate_evaluations_scope": "completed_operations_lower_bound"}

    def save():
        record.update(final_state=state_record(state), cpu_seconds=time.process_time() - cpu,
                      wall_seconds=time.perf_counter() - started)
        if checkpoint is not None:
            checkpoint(record)

    try:
        for generation in range(limit + 1):
            guard.check()
            state.generation = generation
            frozen = generation > 0 and (arm in ("BASE", "BRUTE640") or
                                         (arm == "ONESHOT" and generation > 1))
            if frozen:
                frozen_measurement = (record["generations"][1]["heuristic"]["best_full"]
                                      if arm == "ONESHOT" else record["generations"][0]["wake"])
                row = {"generation": generation, "wake": copy.deepcopy(frozen_measurement),
                       "learning": None, "heuristic": None, "bank_records": [],
                       "new_retained_tasks": [], "reused_measurement": True,
                       "reuse_source_generation": 1 if arm == "ONESHOT" else 0,
                       "reuse_source_phase": "heuristic.best_full" if arm == "ONESHOT" else "wake",
                       "work": _work(), "state": state_record(state)}
                row["online_report"] = _online(row, state, train)
                record["generations"].append(row)
                save()
                continue
            before, previous_names = dict(work), set(state.solutions)
            bank = () if arm in ("BASE", "BRUTE640") else _bank(state)
            row = {"generation": generation, "bank_records": [s.training_record for s in bank],
                   "learning": None, "heuristic": None, "reused_measurement": False}
            record["in_progress"] = row
            save()
            budget = config["B_brute"] if arm == "BRUTE640" else config["B_wake"]
            row["wake"] = {}
            _measure(state, train, budget, state.heuristic, bank, generation,
                     config, kernel_factory, guard, work, save, update=True, destination=row["wake"])
            if generation > 0 and any(h["adopted"] for h in state.heuristic_history):
                row["same_state_zero"] = {}
                _measure(
                    state, train, budget, zero_heuristic(), bank, generation,
                    config, kernel_factory, guard, work, save, destination=row["same_state_zero"])
            if generation > 0 and arm not in ("BASE", "BRUTE640"):
                row["learning"] = {}
                _learn(state, train, config, guard, work, save, destination=row["learning"])
                save()
                if arm != "NO_HEURISTIC":
                    row["heuristic"] = {}
                    improve(state, train, config, kernel_factory, proposal_provider, guard,
                            work, save, destination=row["heuristic"])
            row.update(new_retained_tasks=sorted(set(state.solutions) - previous_names),
                       work=_delta(work, before), state=state_record(state))
            row["online_report"] = _online(row, state, train)
            record["generations"].append(row)
            record.pop("in_progress", None)
            save()
        record["status"] = "complete" if limit == config["generations"] else "partial"
        if record["status"] == "partial":
            record["stop_reason"] = "requested development prefix; full campaign unrun"
    except CpuStop:
        record.update(status="partial", stop_reason="CPU budget exhausted")
    except Exception as error:
        record.update(status="failed", stop_reason=f"{type(error).__name__}: {error}")
        save()
        raise
    record["candidate_evaluations_scope"] = ("exact_completed_operations" if record["status"] == "complete"
                                             else "completed_operations_lower_bound")
    save()
    return record


def _worker(args):
    from ..corpus import load_train
    output = Path(args.output)
    path = output / f"{args.arm}_seed{args.seed}.json"
    if path.exists():
        raise FileExistsError(path)
    output.mkdir(parents=True, exist_ok=True)
    record = run_arm(load_train(), args.seed, args.arm, through_generation=args.through_generation,
                     checkpoint=lambda r: atomic_write(path, r))
    print(json.dumps({"status": record["status"], "completed_rows": len(record["generations"])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__ + "\nUse recursive_bootstrap_run for the aggregate CPU watchdog.")
    parser.add_argument("--seed", type=int, choices=REGISTERED_CONFIG["seeds"], default=11)
    parser.add_argument("--arm", choices=ARMS, default="FULL")
    parser.add_argument("--through-generation", type=int, default=8)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    _worker(args)


if __name__ == "__main__":
    main()
