"""Prospective two-generation grouped TRAIN probe; no heldout capability is used.

Register after committing the implementation, then execute the registration.
The component result is never an assertion that the original RSI criteria pass.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time

from ..grammar import Grammar
from ..heuristics import zero_heuristic
from ..terms import Term
from ..types import Type, infer, unify
from .budget_policy import POLICY_NAME, allocate_roots
from .compression import verify_solutions
from .coordinate_diagnostic_run import _check_search, _valid_proof, SEARCH_WORK, PROOF_WORK
from .journal_checkpoint import JournalCheckpoint, JournalCorruption, reconstruct
from .recursive_bootstrap import CpuGuard, CpuStop, atomic_write, jsonable
from .repair_search import RepairSeed
from .run import CPUController, _run_phase


ARMS = ("predecessor", "positive", "uniform", "contrastive", "oneshot", "permuted")
REGISTERED_CONFIG = {
    "schema_version": 1, "protocol": "FAILURE_CREDIT_EXECUTION_PROTOCOL.md",
    "seeds": [11, 22, 33], "generations": 2, "train_tasks": 36,
    "arms": list(ARMS), "budget": 64, "cpu_limit_seconds": 1800,
    "max_cpu_seconds_per_search": 10, "initial_fresh_prefix": 16,
    "root_policy": POLICY_NAME, "shadow_groups": [0], "fitting_groups": [1, 2],
    "library": "fixed empty", "dreams": 0, "heuristic": "frozen zero",
    "arity_context": False, "production_priority": True, "eta_exposure": True,
    "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000,
               "max_normalization_steps": 20000, "beta_normalize": True,
               "force_wrapper_lambdas": True},
}
MANIFEST = Path(__file__).with_name("FAILURE_CREDIT_GROUPS.json")


def grouping(names):
    """Pure name-only registration; no examples or performances are arguments."""
    names = sorted(names)
    if len(names) != len(set(names)) or any(not isinstance(n, str) for n in names):
        raise ValueError("grouping requires unique task names")
    rows = []
    for name in names:
        family = name.split(" with ", 1)[0]
        digest = hashlib.sha256(family.encode("utf-8")).hexdigest()
        rows.append({"name": name, "family": family, "family_sha256": digest,
                     "group": int(digest, 16) % 3})
    return {"schema_version": 1,
            "rule": 'SHA256(UTF-8 task name before first " with ") as big-endian integer modulo 3',
            "shadow_groups": [0], "fitting_groups": [1, 2], "tasks": rows,
            "names_groups_sha256": hashlib.sha256(json.dumps(
                rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def training_names():
    return sorted(row["name"] for row in json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "train.json").read_text()))


def _git(*args):
    return subprocess.check_output(["git", *args], cwd=Path(__file__).resolve().parents[2],
                                   text=True).strip()


def register(path):
    """Write a simple config/group/source-commit registration without searching."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    manifest = json.loads(MANIFEST.read_text())
    if manifest != grouping(training_names()):
        raise ValueError("registered name-only grouping disagrees with TRAIN names")
    if _git("status", "--porcelain", "--untracked-files=no", "--", "rsi2"):
        raise ValueError("commit tracked implementation changes before registration")
    # Source files must be committed; unrelated untracked result files are fine.
    for name in ("failure_credit_run.py", "failure_preferences.py", "failure_recognition.py",
                 "arity_population.py", "arity_neighborhood.py", "priority_neighborhood.py",
                 "FAILURE_CREDIT_PROTOCOL.md", "FAILURE_CREDIT_EXECUTION_PROTOCOL.md",
                 "FAILURE_CREDIT_GROUPS.json"):
        _git("ls-files", "--error-unmatch", f"rsi2/research/{name}")
    record = {"config": copy.deepcopy(REGISTERED_CONFIG), "grouping": manifest,
              "source_commit": _git("rev-parse", "HEAD"), "performance_read": False}
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, record)
    return record


def validate_registration(path):
    record = json.loads(Path(path).read_text())
    if (record["config"] != REGISTERED_CONFIG or record["grouping"] != grouping(training_names())
            or record["grouping"] != json.loads(MANIFEST.read_text())
            or record.get("performance_read") is not False):
        raise ValueError("registration differs from frozen config/grouping")
    if record["source_commit"] != _git("rev-parse", "HEAD"):
        raise ValueError("checkout differs from registered source commit")
    if _git("status", "--porcelain", "--untracked-files=no", "--", "rsi2"):
        raise ValueError("tracked implementation changed after registration")
    return record


def _grammar_record(grammar):
    return {"library": {}, "weights": dict(grammar.weights), "context_weights": [
        {"parent": p, "argument": a, "weights": dict(w)}
        for (p, a), w in sorted(grammar.context_weights.items())]}


def _grammar_from(record):
    if record["library"]:
        raise ValueError("this registered probe has no learned library")
    return Grammar(weights=record["weights"], context_weights={
        (r["parent"], r["argument"]): r["weights"] for r in record["context_weights"]})


def _bank(entries):
    return tuple(RepairSeed(Term.from_dict(entries[name]["term"]), entries[name]["id"])
                 for name in sorted(entries))


def _public(task):
    from .failure_preferences import PublicTask
    return PublicTask(task.name, task.request_type, task.examples)


def _measure(tasks, model, grammar, bank, seed, generation, config, guard,
             report, save, *, kernel):
    """Only the verifier receives Task.hidden; model and search get public views."""
    report.update(status="running", tasks=[], solved_names=[])
    for number, task in enumerate(tasks):
        guard.check()
        report["in_progress"] = {"name": task.name, "stage": "public_search"}
        save()
        started = time.process_time()
        maximum = min(config["max_cpu_seconds_per_search"], guard.remaining())
        conditioned = model.grammar_for(_public(task), grammar) if model is not None else _grammar_from(_grammar_record(grammar))
        allocation = allocate_roots(config["budget"], bank, seed_prefix=config["initial_fresh_prefix"])
        setup_cpu = time.process_time() - started
        search_seed = seed * 1000003 + (generation + 1) * 1009 + number
        result = kernel(task.examples, task.request_type, config["budget"], conditioned,
                        accepted_seeds=allocation.selected_bank, seed_prefix=allocation.fresh_prefix,
                        heuristic=zero_heuristic(), seed=search_seed,
                        arity_context=config["arity_context"],
                        production_priority=config["production_priority"],
                        eta_exposure=config["eta_exposure"],
                        max_cpu_seconds=max(0.0, maximum - setup_cpu), **config["search"])
        elapsed = time.process_time() - started
        search = jsonable(result)
        term = result.get("term") if isinstance(result, dict) else result.term
        row = {"name": task.name, "request_type": task.request_type.to_dict(),
               "public_examples": jsonable(task.examples),
               "search": search, "root_allocation": allocation.to_record(),
               "search_seed": search_seed, "source_grammar": _grammar_record(conditioned),
               "public_selected": term is not None, "verification": None, "solved": None,
               "setup_cpu_seconds": setup_cpu, "search_cpu_seconds": elapsed,
               "policy_deadline_exceeded": elapsed >= maximum}
        report["tasks"].append(row)
        report["in_progress"]["stage"] = "search_contract_check"
        save()
        _check_search(search, config["budget"], config["search"])
        if not isinstance(term, (Term, type(None))):
            raise ValueError("selected root must be an own-language Term")
        report["in_progress"]["stage"] = "independent_public_hidden_verification"
        guard.check()
        if term is not None:
            proof = verify_solutions({task.name: term}, {}, [task],
                                     step_budget=config["search"]["step_budget"])
            row["verification"] = proof
            row["solved"] = bool(proof["passed"] and term.size <= config["search"]["max_size"]
                                 and not row["policy_deadline_exceeded"])
        else:
            row["solved"] = False
        report["solved_names"] = sorted(r["name"] for r in report["tasks"] if r["solved"] is True)
        save()
    report.pop("in_progress", None)
    report["status"] = "complete"
    save()


def admission(seed_reports, seeds, generation, previous=None):
    """The all-seed strict no-loss gate; incomplete evidence cannot qualify."""
    comparisons, passed = {}, True
    for seed in seeds:
        item = seed_reports.get(str(seed), {})
        arms = item.get("arms", {})
        complete = (item.get("status") == "complete"
            and item.get("permutation", {}).get("status") in ("informative", "uninformative")
            and all(arms.get(arm, {}).get("status") == "complete" for arm in ARMS))
        target = set(arms.get("contrastive", {}).get("solved_names", []))
        controls = ["predecessor", "positive", "uniform"]
        if generation > 0:
            controls.append("oneshot")
        informative = item.get("permutation", {}).get("status") == "informative"
        if informative:
            controls.append("permuted")
        tests = {arm: set(arms.get(arm, {}).get("solved_names", [])) < target for arm in controls}
        previous_solved = set((previous or {}).get("retained_solved", {}).get(str(seed), []))
        no_loss = previous_solved <= target
        new = type(item.get("new_preferences")) is int and item["new_preferences"] > 0
        success = bool(complete and new and no_loss and all(tests.values()))
        passed = passed and success
        comparisons[str(seed)] = {"complete": complete, "strict_expansions": tests,
            "no_loss_against_previous_admission": no_loss, "new_preferences": item.get("new_preferences"),
            "permutation_control": "informative" if informative else "uninformative",
            "passed": success, "solved_names": sorted(target)}
    retained = {str(seed): (comparisons[str(seed)]["solved_names"] if passed else
               list((previous or {}).get("retained_solved", {}).get(str(seed), []))) for seed in seeds}
    return {"generation": generation, "admitted": bool(passed), "seeds": comparisons,
            "retained_solved": retained,
            "reason": "all registered seeds pass strict verified expansion" if passed else
                      "reject: incomplete evidence, no new credit, loss, or no strict control expansion"}


def run_probe(tasks, manifest, path, config, *, kernel=None, initial_cpu_seconds=0.0):
    """Core coordinator, with injected corpus-free kernels for focused tests."""
    from .arity_population import solve_arity_population
    from .failure_preferences import PreferenceMemory, extract_preferences
    from .failure_recognition import (PairwiseRecognition, align_state,
                                      prepare_common_state, permuted_labels)
    kernel = solve_arity_population if kernel is None else kernel
    tasks = sorted(tasks, key=lambda t: t.name)
    if manifest != grouping([t.name for t in tasks]) or len(tasks) != config["train_tasks"]:
        raise ValueError("task coverage differs from frozen name-only manifest")
    groups = {r["name"]: r["group"] for r in manifest["tasks"]}
    fitting = [t for t in tasks if groups[t.name] in config["fitting_groups"]]
    shadow = [t for t in tasks if groups[t.name] in config["shadow_groups"]]
    if not fitting or not shadow:
        raise ValueError("empty fitting/shadow group is inadequate; result is UNKNOWN")
    fitting_names = {t.name for t in fitting}
    started, wall = time.process_time(), time.perf_counter()
    guard = CpuGuard(max(0.0, config["worker_cpu_allowance_seconds"] - initial_cpu_seconds))
    record = {"status": "running", "source": "TRAIN only", "config": config,
              "grouping": manifest, "fitting_names": sorted(fitting_names),
              "shadow_names": [t.name for t in shadow], "generations": [],
              "evaluation_partitions_opened": False, "rsi_success": False,
              "loop_improvement": False, "input_setup_cpu_seconds": initial_cpu_seconds,
              "accounting_scope": "completed_operations_lower_bound"}
    states = {seed: {"bank": {}, "memory": PreferenceMemory(), "grammar": Grammar(),
                     "retained": None, "oneshot": None} for seed in config["seeds"]}
    gates = []
    with JournalCheckpoint(path) as writer:
        def save():
            record.update(cpu_seconds=initial_cpu_seconds + time.process_time() - started,
                          wall_seconds=time.perf_counter() - wall)
            writer(record)

        def archive(event):
            record.pop("active", None)
            record["generations"].append(event)
            save()

        try:
            for generation in range(config["generations"]):
                # All fitting acquisition/model construction precedes shadow admission.
                models, reports = {}, {}
                for seed in config["seeds"]:
                    state = states[seed]
                    source = {"kind": "fitting", "generation": generation, "seed": seed,
                              "retained_from_admitted_update": bool(generation and gates[-1]["admitted"]),
                              "input_bank": copy.deepcopy(state["bank"]),
                              "input_grammar": _grammar_record(state["grammar"]),
                              "input_model": state["retained"].to_dict() if state["retained"] else None}
                    # Archive sizeable immutable input state before the active trace grows.
                    archive(source)
                    source_search = {"kind": "fitting_search", "generation": generation, "seed": seed}
                    record["active"] = source_search
                    _measure(fitting, state["retained"], state["grammar"], _bank(state["bank"]),
                             seed, generation - 1, config, guard, source_search, save, kernel=kernel)
                    new_preferences = 0
                    for task, row in zip(fitting, source_search["tasks"]):
                        guard.check()
                        prefs, work = extract_preferences(_public(task), row["search"],
                            _grammar_from(row["source_grammar"]), fitting_names=fitting_names,
                            generation=generation)
                        added = state["memory"].add(prefs, exclusions=work.exclusions)
                        row["extraction"] = {"new_preferences": added, "work": work.to_dict()}
                        new_preferences += added
                        if row["solved"] and task.name not in state["bank"]:
                            state["bank"][task.name] = {
                                "id": f"failure-credit:seed{seed}:g{generation}:{task.name}",
                                "task": task.name, "generation": generation,
                                "term": row["search"]["term"], "verification": row["verification"]}
                        save()
                    archive(source_search)
                    guard.check()
                    pairs = [(_public(t), Term.from_dict(state["bank"][t.name]["term"]))
                             for t in fitting if t.name in state["bank"]]
                    grammar = Grammar()
                    training_started = time.process_time()
                    grammar_metrics = grammar.fit([(term, task.request_type) for task, term in pairs])
                    shared, common_metrics = prepare_common_state(pairs, grammar, state["memory"],
                        fitting_tasks=[_public(t) for t in fitting], seed=seed,
                        prior=state["retained"])
                    guard.check()
                    predecessor = PairwiseRecognition.from_state(shared)
                    positive = PairwiseRecognition(seed)
                    positive_metrics = positive.fit_positive_extra(pairs, grammar, shared)
                    guard.check()
                    contrastive = PairwiseRecognition.from_state(shared)
                    contrastive_metrics = (contrastive.fit_preferences(state["memory"], shared)
                        if new_preferences else {"steps": 0, "reason": "no new preferences"})
                    guard.check()
                    labels, permutation = permuted_labels(state["memory"], seed)
                    permuted = PairwiseRecognition.from_state(shared)
                    permuted_metrics = (permuted.fit_preferences(state["memory"], shared, labels_override=labels)
                        if new_preferences else {"steps": 0, "reason": "no new preferences"})
                    guard.check()
                    if state["oneshot"] is None:
                        state["oneshot"] = PairwiseRecognition.from_dict(contrastive.to_dict())
                    oneshot = PairwiseRecognition.from_state(align_state(state["oneshot"], shared))
                    models[seed] = {"predecessor": predecessor, "positive": positive,
                                    "uniform": None, "contrastive": contrastive,
                                    "oneshot": oneshot, "permuted": permuted}
                    state["grammar"] = grammar
                    model_event = {"kind": "models", "generation": generation, "seed": seed,
                        "bank": copy.deepcopy(state["bank"]), "grammar": _grammar_record(grammar),
                        "positive_names": [task.name for task, _ in pairs], "dreams": [],
                        "memory": copy.deepcopy(state["memory"].to_dict()), "new_preferences": new_preferences,
                        "common_state": shared.to_dict(),
                        "models": {arm: model.to_dict() if model else None for arm, model in models[seed].items()},
                        "metrics": {"grammar": grammar_metrics, "common": common_metrics,
                                    "positive": positive_metrics, "contrastive": contrastive_metrics,
                                    "permuted": permuted_metrics}, "permutation": permutation,
                        "training_cpu_seconds": time.process_time() - training_started}
                    archive(model_event)
                    reports[str(seed)] = {"kind": "shadow", "generation": generation, "seed": seed,
                        "status": "running", "new_preferences": new_preferences,
                        "permutation": permutation, "arms": {}}
                for seed in config["seeds"]:
                    state, report = states[seed], reports[str(seed)]
                    record["active"] = report
                    for arm in config["arms"]:
                        report["arms"][arm] = {}
                        _measure(shadow, models[seed][arm], state["grammar"], _bank(state["bank"]),
                                 seed, generation, config, guard, report["arms"][arm], save, kernel=kernel)
                        model = models[seed][arm]
                        report["arms"][arm]["prediction_metrics"] = copy.deepcopy(
                            model.prediction_metrics) if model is not None else {"calls": 0, "cpu_seconds": 0.0}
                    report["status"] = "complete"
                    archive(report)
                gate = admission(reports, config["seeds"], generation, gates[-1] if gates else None)
                gate.update(kind="admission")
                gates.append(gate)
                for seed in config["seeds"]:
                    states[seed]["retained"] = models[seed]["contrastive" if gate["admitted"] else "predecessor"]
                archive(gate)
            record.update(status="complete", accounting_scope="exact_completed_operations",
                          loop_improvement=all(gate["admitted"] for gate in gates) and len(gates) >= 2)
        except CpuStop:
            record.update(status="partial", stop_reason="worker remaining CPU allowance exhausted")
        except Exception as error:
            record.update(status="failed", stop_reason=f"{type(error).__name__}: {error}")
            save()
            raise
        save()
        return {"status": record["status"], "loop_improvement": record["loop_improvement"],
                "stop_reason": record.get("stop_reason"), "persistence": writer.metrics}


def _row_valid(row, config):
    _check_search(row["search"], config["budget"], config["search"])
    if (row["search"].get("edit_mode") != "arity_coordinates" or
            any(row["search"].get("neighborhood_work", {}).get(flag) is not config[flag]
                for flag in ("arity_context", "production_priority", "eta_exposure"))):
        return False
    if any(type(row.get(field)) is not bool for field in ("solved", "public_selected", "policy_deadline_exceeded")):
        return False
    if type(row["search"].get("seed")) is not int or row["search"]["seed"] != row["search_seed"]:
        return False
    selected, proof = row["search"].get("term"), row["verification"]
    if selected is None:
        return not row["solved"] and not row["public_selected"] and proof is None
    term = Term.from_dict(selected)
    unify(infer(term, library={}), Type.from_dict(row["request_type"]))
    return (row["public_selected"] and term.size <= config["search"]["max_size"] and
            _valid_proof(proof, [row["name"]], config["search"]["step_budget"]) and
            row["solved"] == (proof["passed"] and not row["policy_deadline_exceeded"]))


def complete_record(record, config, manifest):
    """Parent's independent structural/budget/proof gate over persisted evidence."""
    try:
        from .failure_preferences import PublicTask
        from .failure_recognition import PairwiseRecognition, SharedState, align_state
        if (record["status"] != "complete" or record["config"] != config or record["grouping"] != manifest
                or record["source"] != "TRAIN only" or record["evaluation_partitions_opened"] is not False
                or record["rsi_success"] is not False or "active" in record):
            return False
        fitting = sorted(r["name"] for r in manifest["tasks"] if r["group"] in config["fitting_groups"])
        shadow = sorted(r["name"] for r in manifest["tasks"] if r["group"] in config["shadow_groups"])
        if not fitting or not shadow or record["fitting_names"] != fitting or record["shadow_names"] != shadow:
            return False
        events = record["generations"]
        expected_events = config["generations"] * (4 * len(config["seeds"]) + 1)
        if len(events) != expected_events:
            return False
        lookup = {}
        for event in events:
            key = (event["kind"], event["generation"], event.get("seed"))
            if key in lookup:
                return False
            lookup[key] = event
        gates = []
        for generation in range(config["generations"]):
            reports = {}
            for seed in config["seeds"]:
                source = lookup["fitting", generation, seed]
                fit = lookup["fitting_search", generation, seed]
                model = lookup["models", generation, seed]
                report = lookup["shadow", generation, seed]
                if fit["status"] != "complete" or report["status"] != "complete":
                    return False
                if source["retained_from_admitted_update"] != bool(generation and gates[-1]["admitted"]):
                    return False
                if generation == 0 and (source["input_bank"] or source["input_model"] is not None
                                        or source["input_grammar"] != _grammar_record(Grammar())):
                    return False
                if generation:
                    old = lookup["models", generation - 1, seed]
                    arm = "contrastive" if gates[-1]["admitted"] else "predecessor"
                    if (source["input_bank"] != old["bank"] or source["input_grammar"] != old["grammar"]
                            or source["input_model"] != old["models"][arm]):
                        return False
                if (model["dreams"] or model["grammar"]["library"] or model["positive_names"] != sorted(model["bank"])
                        or not set(model["bank"]) <= set(fitting)
                        or any(r["task_name"] not in fitting for r in model["memory"]["records"])):
                    return False
                if set(model["models"]) != set(ARMS) or model["models"]["uniform"] is not None:
                    return False
                if model["models"]["predecessor"] != model["common_state"]:
                    return False
                first = lookup["models", 0, seed]["models"]["contrastive"]
                expected_oneshot = align_state(PairwiseRecognition.from_dict(first),
                    SharedState.from_dict(model["common_state"])).to_dict()
                if model["models"]["oneshot"] != expected_oneshot:
                    return False
                for arm in ARMS:
                    if arm != "uniform" and any(model["models"][arm][field] != model["common_state"][field]
                        for field in ("contexts", "productions", "mean", "scale")):
                        return False
                for name, item in model["bank"].items():
                    if (item["task"] != name or item["verification"]["passed"] is not True or
                            not _valid_proof(item["verification"], [name], config["search"]["step_budget"])):
                        return False
                    origins = [row for g in range(generation + 1)
                               for row in lookup["fitting_search", g, seed]["tasks"]
                               if row["name"] == name and row["solved"] and row["search"]["term"] == item["term"]
                               and row["verification"] == item["verification"]]
                    if not origins:
                        return False
                if set(report["arms"]) != set(ARMS) or report["permutation"] != model["permutation"]:
                    return False
                if report["new_preferences"] != model["new_preferences"] or model["new_preferences"] != sum(
                    row["extraction"]["new_preferences"] for row in fit["tasks"]):
                    return False
                for arm, measured, names, bank in [(None, fit, fitting, source["input_bank"])] + [
                        (arm, report["arms"][arm], shadow, model["bank"]) for arm in ARMS]:
                    if measured["status"] != "complete" or [r["name"] for r in measured["tasks"]] != names:
                        return False
                    allocation = allocate_roots(config["budget"], _bank(bank),
                                                seed_prefix=config["initial_fresh_prefix"]).to_record()
                    base = _grammar_from(source["input_grammar"] if arm is None else model["grammar"])
                    parameters = source["input_model"] if arm is None else model["models"][arm]
                    recognizer = PairwiseRecognition.from_dict(parameters) if parameters is not None else None
                    for number, row in enumerate(measured["tasks"]):
                        offset = generation if arm is None else generation + 1
                        if (row["root_allocation"] != allocation or
                                row["search_seed"] != seed * 1000003 + offset * 1009 + number or
                                not _row_valid(row, config)):
                            return False
                        public = PublicTask(row["name"], Type.from_dict(row["request_type"]),
                            tuple((tuple(inputs), expected) for inputs, expected in row["public_examples"]))
                        expected_grammar = recognizer.grammar_for(public, base) if recognizer is not None else base
                        if row["source_grammar"] != _grammar_record(expected_grammar):
                            return False
                    if measured["solved_names"] != sorted(r["name"] for r in measured["tasks"] if r["solved"]):
                        return False
                reports[str(seed)] = report
            expected = admission(reports, config["seeds"], generation, gates[-1] if gates else None)
            expected["kind"] = "admission"
            if lookup["admission", generation, None] != expected:
                return False
            gates.append(expected)
        return record["loop_improvement"] == (len(gates) >= 2 and all(g["admitted"] for g in gates))
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
        return False


def probe_worker(kind, key, output, config, records, events):
    try:
        started = time.process_time()
        from ..corpus import load_train
        tasks = load_train()
        # Preserve exactly the parent's config in persisted evidence; load CPU
        # remains additionally charged by the score-blind process watchdog.
        result = run_probe(tasks, config["grouping"], Path(output) / "probe.checkpoint.json", config,
                           initial_cpu_seconds=time.process_time() - started)
        events.put({"key": key, "result": result})
    except BaseException as error:
        events.put({"key": key, "error": f"{type(error).__name__}: {error}"[:512]})
    finally:
        events.close()
        events.join_thread()


def _progress(record):
    events = list(record.get("generations", []))
    if "active" in record:
        events.append(record["active"])
    conditions = []
    work = {**{key: 0 for key in SEARCH_WORK}, **{f"verification_{key}": 0 for key in PROOF_WORK}}
    for event in events:
        measurements = ([('fitting', event)] if event.get("kind") == "fitting_search" else
                        list(event.get("arms", {}).items()) if event.get("kind") == "shadow" else [])
        for arm, item in measurements:
            rows = item.get("tasks", [])
            status = item.get("status", "partial")
            conditions.append({"generation": event["generation"], "seed": event["seed"],
                "arm": arm, "status": "partial" if status == "running" else status,
                "tasks_completed": sum(type(row.get("solved")) is bool for row in rows),
                "solved_names": sorted(r["name"] for r in rows if r.get("solved") is True)})
            for row in rows:
                for key in SEARCH_WORK:
                    value = row["search"].get("logical_evaluations", row["search"].get(key)) if key == "candidates" else row["search"].get(key)
                    if type(value) is int and value >= 0:
                        work[key] += value
                if row.get("verification"):
                    for key in PROOF_WORK:
                        work[f"verification_{key}"] += row["verification"]["cost"][key]
    observed = {(row["generation"], row["seed"], row["arm"]): row for row in conditions}
    config = record.get("config", REGISTERED_CONFIG)
    conditions = [observed.get((generation, seed, arm), {
        "generation": generation, "seed": seed, "arm": arm, "status": "unrun",
        "tasks_completed": 0, "solved_names": []})
        for generation in range(config["generations"])
        for seed in config["seeds"] for arm in ("fitting", *config["arms"])]
    return conditions, work


def run_campaign(registration_path, output, *, worker_target=probe_worker):
    registration = validate_registration(registration_path)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    budget = CPUController(REGISTERED_CONFIG["cpu_limit_seconds"])
    config = {**copy.deepcopy(REGISTERED_CONFIG), "grouping": registration["grouping"],
              "source_commit": registration["source_commit"],
              "worker_cpu_allowance_seconds": max(0.0, budget.limit - budget.spent() - budget.cleanup_margin)}
    initial = {"status": "running", "registration": registration, "source": "TRAIN only",
               "evaluation_partitions_opened": False, "rsi_success": False, "loop_improvement": False}
    atomic_write(output / "summary.json", initial)
    phase = _run_phase("failure_credit", ["probe"], output, config, budget,
                       workers=1, worker_target=worker_target)
    phase.pop("exception", None)
    terminal = phase["results"].get("probe", {})
    record, recovery, corruption = None, None, None
    checkpoint = output / "probe.checkpoint.json"
    if checkpoint.exists():
        try:
            recovered = reconstruct(checkpoint)
            record = recovered.record
            recovery = {"interrupted": recovered.interrupted, "ignored_bytes": recovered.ignored_bytes,
                        "cpu_seconds": recovered.cpu_seconds}
        except JournalCorruption as error:
            corruption = str(error)
    complete = bool(phase["reason"] is None and "error" not in terminal and record is not None
        and terminal.get("result", {}).get("status") == "complete"
        and complete_record(record, config, registration["grouping"])
        and budget.spent() < budget.limit)
    conditions, work = _progress(record or {})
    gates = [r for r in (record or {}).get("generations", []) if r.get("kind") == "admission"]
    summary = {**initial, "status": "complete" if complete else "partial", "conditions": conditions,
               "work": work, "admissions": gates, "phase": phase, "reconstruction": recovery,
               "loop_improvement": bool(complete and record["loop_improvement"]),
               "stop_reason": None if complete else phase["reason"] or terminal.get("error") or corruption or
                              (record or {}).get("stop_reason") or "persisted completion gate failed",
               "cpu_seconds": budget.spent(), "wall_seconds": time.perf_counter() - started,
               "accounting_scope": "exact_completed_operations" if complete else "completed_operations_lower_bound",
               "claim_scope": "grouped TRAIN failure-credit component only; original RSI criteria remain unverified"}
    atomic_write(output / "summary.json", summary)
    summary["cpu_seconds"] = budget.spent()
    if summary["cpu_seconds"] >= budget.limit:
        summary.update(status="partial", loop_improvement=False,
                       stop_reason="aggregate CPU ceiling reached including final metadata",
                       accounting_scope="completed_operations_lower_bound")
    atomic_write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.freeze:
        if args.registration or args.output:
            parser.error("--freeze is separate from execution")
        print(json.dumps(register(args.freeze)))
    elif args.registration and args.output:
        result = run_campaign(args.registration, args.output)
        print(json.dumps({key: result[key] for key in ("status", "loop_improvement", "rsi_success", "stop_reason")}))
    else:
        parser.error("provide --freeze PATH or --registration PATH --output DIRECTORY")


if __name__ == "__main__":
    main()
