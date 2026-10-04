"""Public-input semantic probes and evidence-only research failure summaries.

This module consumes explicitly supplied terms, public examples, and reports.
It does not acquire tasks or load experiment artifacts. Probe outcomes check
whether a heuristic is callable and discriminates candidate features; they are
not task fitness measurements and do not change the frozen interpreter/search.
"""
from __future__ import annotations

from collections.abc import Mapping
import json

from ..evaluator import evaluate


def default_profile():
    """Return twelve deterministic probes, repeated within two fixed targets.

    The six feature settings separately vary outputs, size, and depth. Empty
    outputs exercise the partial-program contract. Fresh lists prevent callers
    from changing the profile used by subsequent audits.
    """
    features = (((), 4, 2), ((0,), 4, 2), ((1, -2, 3), 4, 2),
                ((), 8, 2), ((), 4, 4), ((1, -2, 3), 8, 4))
    return [{"candidate_outputs": list(outputs), "target_outputs": list(target),
             "size": size, "depth": depth, "name": f"fixed_{target_index}_{index}"}
            for target_index, target in enumerate(((0,), (1, -2, 3)))
            for index, (outputs, size, depth) in enumerate(features)]


def _flatten(value):
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in _flatten(item)]
    return [int(value)] if isinstance(value, (int, bool)) else []


def profile_from_tasks(tasks):
    """Make exactly two probes per task from its public examples only.

    Both probes share the flattened public target. One has empty candidate
    outputs, and the other has the first public output, with a fixed crossing
    of size/depth settings. No request type, private examples, or task outcomes
    are needed. A task with no public example cannot define the second probe.
    """
    profile = []
    for index, task in enumerate(tasks):
        examples = tuple(task.examples)
        if not examples:
            raise ValueError("a task-derived profile requires a public example")
        target = _flatten([expected for _, expected in examples])
        name = str(getattr(task, "name", index))
        profile.extend((
            {"candidate_outputs": [], "target_outputs": list(target),
             "size": 4, "depth": 2, "name": f"{name}:partial"},
            {"candidate_outputs": _flatten(examples[0][1]),
             "target_outputs": list(target), "size": 8, "depth": 4,
             "name": f"{name}:complete"},
        ))
    return profile


def _profile_copy(profile):
    probes = []
    for index, probe in enumerate(profile):
        outputs = list(probe["candidate_outputs"])
        targets = list(probe["target_outputs"])
        size, depth = probe["size"], probe["depth"]
        if not all(type(value) is int for value in outputs + targets):
            raise ValueError("probe outputs and targets must be integer lists")
        if type(size) is not int or type(depth) is not int or not 1 <= depth <= size:
            raise ValueError("probe features require 1 <= depth <= size")
        probes.append({"candidate_outputs": outputs, "target_outputs": targets,
                       "size": size, "depth": depth,
                       "name": str(probe.get("name", index))})
    return probes


def audit_candidate(term, library, profile=None, step_budget=2000):
    """Execute a complete, charged probe profile and return JSON-safe evidence.

    One candidate program attempt contains one interpreter invocation per
    probe, including failed invocations. Costs sum the frozen evaluator's exact
    steps; failure does not short-circuit later probes. A candidate is valid
    only when every invocation returns an integer that the frozen queue can
    use: bools and scores above its 1,023-bit magnitude limit are invalid.
    Informativeness requires score variation within a fixed target,
    so a score depending solely on target values is uninformative.
    """
    probes = _profile_copy(default_profile() if profile is None else profile)
    failures, scores, steps = [], [], 0
    for index, probe in enumerate(probes):
        result = evaluate(term, (probe["candidate_outputs"], probe["target_outputs"],
                                 probe["size"], probe["depth"]),
                          library=library, step_budget=step_budget)
        steps += result.steps
        if not result.ok:
            error = result.error or "evaluator_failure"
            failures.append({"probe_index": index, "name": probe["name"],
                             "kind": error.split(":", 1)[0], "error": error})
            scores.append(None)
        elif type(result.value) is not int:
            failures.append({"probe_index": index, "name": probe["name"],
                             "kind": "non_integer_score",
                             "error": f"score type is {type(result.value).__name__}"})
            scores.append(None)
        elif result.value.bit_length() > 1023:
            failures.append({"probe_index": index, "name": probe["name"],
                             "kind": "unusable_queue_score",
                             "error": "integer score exceeds the frozen queue's 1023-bit limit"})
            scores.append(None)
        else:
            scores.append(result.value)
    if not probes:
        failures.append({"probe_index": None, "name": None,
                         "kind": "empty_profile", "error": "no probes supplied"})
    valid = not failures
    grouped = {}
    for index, probe in enumerate(probes):
        grouped.setdefault(tuple(probe["target_outputs"]), []).append(index)
    groups = [{"target_outputs": list(target), "probe_indices": indices,
               "informative": len({scores[i] for i in indices if scores[i] is not None}) > 1}
              for target, indices in grouped.items()]
    return {"valid": valid, "informative": valid and any(g["informative"] for g in groups),
            "failures": failures, "score_signatures": scores, "target_groups": groups,
            "profile": probes, "program_evaluations": 1,
            "example_evaluations": len(probes), "evaluator_steps": steps}


def _observed(count, evidence, **details):
    return {"status": "observed" if count else "none", "count": count,
            "evidence": evidence, **details}


def _unknown(reason):
    return {"status": "unknown", "count": None, "evidence": [], "reason": reason}


def _audit_at(audits, record, position):
    if isinstance(audits, Mapping):
        index = record.get("index", position)
        return audits.get(index, audits.get(str(index)))
    return audits[position] if position < len(audits) else None


def _public_match(record):
    for key in ("public_matched", "selected_public_matched", "public_examples_matched"):
        if key in record:
            return record[key] if type(record[key]) is bool else None
    return None


def _canonical_term(term):
    if term is None:
        return None
    if hasattr(term, "to_dict"):
        term = term.to_dict()
    return json.dumps(term, sort_keys=True, separators=(",", ":"))


def _screen_outcome(record):
    screen = record.get("screen")
    if not isinstance(screen, Mapping):
        return None
    # The fraction is an observed screening outcome, never a new objective.
    return screen.get("solved_fraction")


def clusters(task_assessment, proposal_records, audits):
    """Classify supplied failure evidence without attributing unseen causes.

    Task assessment follows the measurement ``records`` schema. To distinguish
    a selected program's private-verifier failure from absence of a public
    solution, a task record must explicitly report ``public_matched``. Audits
    may be aligned to proposal order or keyed by proposal index.
    """
    task_assessment = task_assessment or {}
    records = list(task_assessment.get("records", ()))
    proposals = list(proposal_records or ())
    audits = audits if audits is not None else ()
    no_solution, verifier_failures = [], []
    public_observations = 0
    budget_count = exhausted_count = unknown_count = 0
    for position, record in enumerate(records):
        matched = _public_match(record)
        public_observations += matched is not None
        if record.get("solved") is True:
            continue
        if matched is True:
            verifier_failures.append({"record_index": position, "name": record.get("name")})
            continue
        # Without an explicit public-match flag, an unsolved record does not
        # prove absence of a public solution. Record its limit evidence only.
        reason = "unknown"
        if record.get("exhausted") is True:
            reason, exhausted_count = "search_exhausted", exhausted_count + 1
        elif record.get("exhausted") is False:
            budget = record.get("budget", task_assessment.get("budget"))
            candidates = record.get("candidates")
            if type(budget) is int and type(candidates) is int and candidates >= budget:
                reason, budget_count = "candidate_budget", budget_count + 1
            else:
                unknown_count += 1
        else:
            unknown_count += 1
        no_solution.append({"record_index": position, "name": record.get("name"),
                            "limit": reason, "public_match_observed": matched is not None})
    taxonomy = {"no_solution_budget_vs_exhausted": _observed(
        len(no_solution), no_solution, candidate_budget=budget_count,
        search_exhausted=exhausted_count, unknown_limit=unknown_count,
        absence_of_public_solution_confirmed=sum(_public_match(r) is False for r in records
                                                 if r.get("solved") is not True)),
        "selected_hidden_verifier_failure": (
            _observed(len(verifier_failures), verifier_failures,
                      public_match_observations=public_observations)
            if public_observations else _unknown("no public-match flags were supplied"))}

    evaluator_evidence, constant_evidence, duplicate_evidence = [], [], []
    invalid_programs, seen_terms = 0, set()
    assessed = []
    for position, record in enumerate(proposals):
        index = record.get("index", position)
        audit = _audit_at(audits, record, position)
        assessed.append((record, audit))
        if audit is not None:
            invalid_programs += audit.get("valid") is False
            for failure in audit.get("failures", ()):
                evaluator_evidence.append({"proposal_index": index, **failure})
            if audit.get("valid") is True and audit.get("informative") is False:
                constant_evidence.append({"proposal_index": index,
                                          "score_signatures": audit.get("score_signatures", [])})
        key = _canonical_term(record.get("term"))
        repeated = key is not None and key in seen_terms
        if record.get("duplicate") is True or repeated:
            duplicate_evidence.append({"proposal_index": index,
                                       "explicit_duplicate": record.get("duplicate") is True,
                                       "repeated_term": repeated})
        if key is not None:
            seen_terms.add(key)
    observed_audits = sum(audit is not None for _, audit in assessed)
    taxonomy["evaluator_failure"] = (_observed(len(evaluator_evidence), evaluator_evidence,
                                               invalid_programs=invalid_programs,
                                               audited_programs=observed_audits)
                                      if observed_audits else _unknown("no candidate audits supplied"))
    taxonomy["constant_score"] = (_observed(len(constant_evidence), constant_evidence,
                                            audited_programs=observed_audits)
                                   if observed_audits else _unknown("no candidate audits supplied"))
    taxonomy["duplicate_proposals"] = _observed(len(duplicate_evidence), duplicate_evidence)

    confirmed_unusable = []
    for record, audit in assessed:
        confirmed = record.get("full") is not None or record.get("confirmed") is True
        if confirmed and audit is not None and not (
                audit.get("valid") is True and audit.get("informative") is True):
            confirmed_unusable.append(record)
    starvation = []
    for position, (record, audit) in enumerate(assessed):
        confirmed = record.get("full") is not None or record.get("confirmed") is True
        if confirmed or audit is None or not (audit.get("valid") is True
                                             and audit.get("informative") is True):
            continue
        outcome = _screen_outcome(record)
        blocked_by = [bad.get("index", proposals.index(bad)) for bad in confirmed_unusable
                      if outcome is not None and outcome == _screen_outcome(bad)]
        if blocked_by:
            starvation.append({"proposal_index": record.get("index", position),
                               "screen_fraction": outcome,
                               "confirmed_unusable_indices": blocked_by})
    has_confirmation = any(r.get("full") is not None or r.get("confirmed") is True
                           for r in proposals)
    taxonomy["confirmation_starvation"] = (
        _observed(len(starvation), starvation,
                  confirmed_unusable=len(confirmed_unusable))
        if observed_audits and has_confirmation
        else _unknown("confirmation records and candidate audits are required"))
    for category in ("planning_failure", "memory_failure", "tool_failure",
                     "environment_failure", "credit_assignment_failure"):
        taxonomy[category] = _unknown("not observable from the supplied task/proposal reports")
    return taxonomy


def summarize_clusters(taxonomy):
    """Return short factual summaries while preserving unknown evidence states."""
    summaries = []
    for category, evidence in taxonomy.items():
        label = category.replace("_", " ")
        if evidence.get("status") == "unknown":
            summaries.append(f"{label}: unknown ({evidence.get('reason', 'unobserved')}).")
        else:
            summaries.append(f"{label}: {evidence.get('count', 0)} observed evidence records.")
    return summaries
