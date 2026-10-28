"""Exact public-only preferences from completed own-search genealogy.

This research module opens no task files and runs no interpreter. Preferences
are proposal evidence, never verified-program or library labels. The caller
supplies the original grammar snapshot and a frozen fitting-name allowlist.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from fractions import Fraction
import hashlib
import json
import time

from ..grammar import Grammar
from ..recognition import FEATURE_DIM, task_features
from ..terms import Term
from ..types import Type, library_entries, library_entry


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(value):
    return hashlib.sha256(_encoded(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicTask:
    name: str
    request_type: Type
    examples: tuple


@dataclass
class ExtractionWork:
    task_filter_rejections: int = 0
    edges: int = 0
    missing_parents: int = 0
    excluded_failures: int = 0
    excluded_incomplete: int = 0
    excluded_outputs: int = 0
    excluded_unknown: int = 0
    excluded_syntax: int = 0
    quality_ties: int = 0
    zero_differences: int = 0
    eligible_preferences: int = 0
    compared_value_nodes: int = 0
    validated_value_nodes: int = 0
    fraction_operations: int = 0
    fraction_constructions: int = 0
    fraction_comparisons: int = 0
    canonicalization_ast_visits: int = 0
    canonicalization_type_visits: int = 0
    derivation_ast_visits: int = 0
    derivation_type_visits: int = 0
    compiler_invocations: int = 0
    production_queries: int = 0
    production_options: int = 0
    decision_events: int = 0
    feature_calls: int = 0
    semantic_evaluator_calls: int = 0
    cpu_seconds: float = 0.0
    wall_seconds: float = 0.0
    exclusions: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _ground_kind(value):
    kind = type(value)
    if kind not in (bool, int, list):
        raise TypeError("public values require ground bool/int/list values")
    return kind


def typed_equal(actual, expected, work=None):
    """Recursive DSL equality; bool is never an integer for this purpose."""
    work = ExtractionWork() if work is None else work
    work.compared_value_nodes += 1
    if _ground_kind(actual) is not _ground_kind(expected):
        return False
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            typed_equal(a, b, work) for a, b in zip(actual, expected))
    return actual == expected


def _fraction(work, numerator=0, denominator=1):
    # Constructions are included in total Fraction operations and also exposed
    # separately. Arithmetic increments the same total at its execution site.
    work.fraction_constructions += 1
    work.fraction_operations += 1
    return Fraction(numerator, denominator)


def exact_residual(actual, expected, work=None):
    """The preregistered generic residual, with no clipping or float ties."""
    work = ExtractionWork() if work is None else work
    work.compared_value_nodes += 1
    if _ground_kind(actual) is not _ground_kind(expected):
        return _fraction(work, 1)
    if type(expected) is bool:
        return _fraction(work, int(actual != expected))
    if type(expected) is int:
        return _fraction(work, abs(actual - expected), 1 + abs(actual) + abs(expected))
    total = _fraction(work, abs(len(actual) - len(expected)))
    for a, b in zip(actual, expected):
        distance = exact_residual(a, b, work)
        work.fraction_operations += 1
        total += distance
    work.fraction_operations += 1
    return total / max(len(actual), len(expected), 1)


def quality(outputs, examples, work=None):
    """Return (type-aware exact matches, exact mean residual)."""
    work = ExtractionWork() if work is None else work
    if not examples or type(outputs) is not list or len(outputs) != len(examples):
        raise ValueError("quality requires exactly one output per public example")
    def validate(value):
        work.validated_value_nodes += 1
        if _ground_kind(value) is list:
            for child in value:
                validate(child)

    matches, residual = 0, _fraction(work)
    for output, (_, expected) in zip(outputs, examples):
        validate(output)
        validate(expected)
        matches += typed_equal(output, expected, work)
        distance = exact_residual(output, expected, work)
        work.fraction_operations += 1
        residual += distance
    work.fraction_operations += 1
    return matches, residual / len(examples)


def _quality_compare(first, second, work):
    if first[0] != second[0]:
        return 1 if first[0] > second[0] else -1
    work.fraction_comparisons += 1
    work.fraction_operations += 1
    if first[1] == second[1]:
        return 0
    work.fraction_comparisons += 1
    work.fraction_operations += 1
    return 1 if first[1] < second[1] else -1


def _canonical_type(type_, variables, work):
    work.canonicalization_type_visits += 1
    if type_.is_variable:
        variables.setdefault(type_.name, f"preference_type_{len(variables)}")
        return Type("var", (variables[type_.name],))
    return Type(type_.tag, tuple(_canonical_type(a, variables, work) for a in type_.args))


def canonical_term(term, work=None):
    """Rename existing annotations only; leave the generated term unchanged."""
    work = ExtractionWork() if work is None else work
    variables = {}

    def visit(node):
        work.canonicalization_ast_visits += 1
        value = (_canonical_type(node.value, variables, work)
                 if node.tag in ("lam", "hole") else node.value)
        return Term(node.tag, value, tuple(visit(c) for c in node.children))

    return visit(term)


def _type_visits(type_, work):
    work.derivation_type_visits += 1
    if not type_.is_variable:
        for arg in type_.args:
            _type_visits(arg, work)


def _complete_walk(term, work):
    """Count an explicit compiler-input scan, including annotation nodes.

    These counters are metering traversals, not an estimate of every internal
    unification operation in frozen Grammar; all compiler CPU is timed.
    """
    pending = [term]
    while pending:
        node = pending.pop()
        work.derivation_ast_visits += 1
        if node.tag == "hole":
            raise ValueError("incomplete AST")
        if node.tag == "lam":
            _type_visits(node.value, work)
        pending.extend(node.children)


class _MeteredGrammar(Grammar):
    def __init__(self, work, **kwargs):
        self.work = work
        super().__init__(**kwargs)

    def productions(self, request_type, env=(), substitutions=None, context=("ROOT", 0)):
        self.work.production_queries += 1
        for type_ in (request_type, *env, *(substitutions or {}).values()):
            _type_visits(type_, self.work)
        choices = super().productions(request_type, env, substitutions, context)
        self.work.production_options += len(choices)
        return choices


def snapshot_grammar(grammar, work=None):
    """Copy executable library entries and persist the exact original scope."""
    if not isinstance(grammar, Grammar):
        raise TypeError("an original Grammar snapshot is required")
    work = ExtractionWork() if work is None else work
    library, entries = {}, []
    for name, entry in library_entries(grammar.library).items():
        body, declared = library_entry(entry)
        if not isinstance(body, Term):
            raise TypeError("preference snapshots require executable library entries")
        library[name] = body if declared is None else (declared, body)
        entries.append({"name": name, "term": body.to_dict(),
                        "type": None if declared is None else declared.to_dict()})
    scope = {"library": entries,
             "primitives": [[name, type_.to_dict()] for name, type_ in grammar.primitives.items()],
             "constants": [t.to_dict() for t in grammar.constants],
             "weights": list(grammar.weights.items()),
             "context_weights": [[list(c), list(w.items())]
                                 for c, w in grammar.context_weights.items()]}
    return (_MeteredGrammar(work, library=library, primitives=grammar.primitives,
                            constants=grammar.constants, weights=grammar.weights,
                            context_weights=grammar.context_weights), _encoded(scope))


def task_fingerprint(task, work=None):
    work = ExtractionWork() if work is None else work
    request = _canonical_type(task.request_type, {}, work)
    return _fingerprint({"request_type": request.to_dict(), "examples": task.examples})


@dataclass(frozen=True)
class Preference:
    task_name: str
    task_fingerprint: str
    library_fingerprint: str
    generation: int
    parent_id: int
    child_id: int
    request_type: Type
    grammar_snapshot: str
    parent_raw: Term
    child_raw: Term
    parent_current: Term
    child_current: Term
    lo: Term
    hi: Term
    lo_fingerprint: str
    hi_fingerprint: str
    label: int
    difference: tuple
    features: tuple
    lo_quality: tuple
    hi_quality: tuple
    lo_decisions: tuple
    hi_decisions: tuple

    @property
    def key(self):
        # Library versions are provenance, never a way to multiply the same
        # task-public/AST contrast's influence in later generations.
        return (self.task_fingerprint, self.lo_fingerprint, self.hi_fingerprint)

    def to_dict(self):
        record = dict(vars(self))
        record["request_type"] = self.request_type.to_dict()
        for field_ in ("parent_raw", "child_raw", "parent_current", "child_current", "lo", "hi"):
            record[field_] = getattr(self, field_).to_dict()
        for field_ in ("lo_quality", "hi_quality"):
            matches, distance = getattr(self, field_)
            record[field_] = [matches, [distance.numerator, distance.denominator]]
        return json.loads(_encoded(record))

    @classmethod
    def from_dict(cls, record):
        record = dict(record)
        record["request_type"] = Type.from_dict(record["request_type"])
        for field_ in ("parent_raw", "child_raw", "parent_current", "child_current", "lo", "hi"):
            record[field_] = Term.from_dict(record[field_])
        for field_ in ("lo_quality", "hi_quality"):
            matches, distance = record[field_]
            record[field_] = (matches, Fraction(*distance))
        record["difference"] = tuple((tuple(c), p, n) for c, p, n in record["difference"])
        for field_ in ("lo_decisions", "hi_decisions"):
            record[field_] = tuple((tuple(c), p) for c, p in record[field_])
        record["features"] = tuple(record["features"])
        result = cls(**record)
        _validate_preference(result)
        return result


def _validate_preference(record):
    if not isinstance(record, Preference) or type(record.label) is not int or record.label not in (-1, 1):
        raise TypeError("memory accepts measured signed Preference records")
    if not record.lo_fingerprint < record.hi_fingerprint:
        raise ValueError("preference AST fingerprints must have canonical orientation")
    if (record.lo_fingerprint != _fingerprint(record.lo.to_dict()) or
            record.hi_fingerprint != _fingerprint(record.hi.to_dict())):
        raise ValueError("preference AST fingerprint mismatch")
    if len(record.features) != FEATURE_DIM:
        raise ValueError("preference requires frozen public features")
    lo, hi = Counter(record.lo_decisions), Counter(record.hi_decisions)
    expected = tuple((context, production, hi[context, production] - lo[context, production])
                     for context, production in sorted(set(lo) | set(hi))
                     if hi[context, production] != lo[context, production])
    if not expected or record.difference != expected:
        raise ValueError("preference difference must equal D(hi)-D(lo)")
    lo_rank, hi_rank = ((q[0], -q[1]) for q in (record.lo_quality, record.hi_quality))
    if lo_rank == hi_rank or record.label != (1 if hi_rank > lo_rank else -1):
        raise ValueError("preference label must follow exact public quality")


def extract_preferences(task, search, source_grammar, *, fitting_names, generation=0):
    """Extract actual parent-child edges; preserve every exclusion's evidence."""
    started, wall_started = time.process_time(), time.perf_counter()
    work = ExtractionWork()

    def finish(records):
        work.cpu_seconds = time.process_time() - started
        work.wall_seconds = time.perf_counter() - wall_started
        return records, work

    if task.name not in frozenset(fitting_names):
        work.task_filter_rejections += 1
        work.exclusions.append({"reason": "outside_fitting_group", "task_name": task.name,
                                "generation": generation})
        return finish([])
    if type(generation) is not int or generation < 0:
        raise ValueError("generation must be a nonnegative integer")
    examples, request_type = tuple(task.examples), task.request_type
    if not examples or not isinstance(request_type, Type):
        raise ValueError("preferences require public examples and the original request type")
    snapshot, scope = snapshot_grammar(source_grammar, work)
    library_key = _fingerprint(json.loads(scope)["library"])
    task_key = task_fingerprint(task, work)
    trials = search.get("trials", ()) if isinstance(search, dict) else search.trials
    if not isinstance(trials, (list, tuple)):
        raise TypeError("completed search trials must be a materialized sequence")
    indexed = {}
    for trial in trials:
        identifier = trial.get("id")
        if type(identifier) is not int or identifier in indexed:
            raise ValueError("search trial IDs must be unique integers")
        indexed[identifier] = trial
    features, syntax_cache, quality_cache = None, {}, {}

    def reject(reason, child, parent=None, detail=None):
        counter = {"missing_parent": "missing_parents", "runtime_failure": "excluded_failures",
                   "incomplete_assessment": "excluded_incomplete", "invalid_outputs": "excluded_outputs",
                   "unknown_evidence": "excluded_unknown", "invalid_syntax": "excluded_syntax",
                   "equal_quality": "quality_ties", "zero_difference": "zero_differences"}[reason]
        setattr(work, counter, getattr(work, counter) + 1)
        # Store complete supplied evidence, including raw/current ASTs. Copy via
        # JSON so subsequent caller mutations cannot rewrite exclusion history.
        evidence = {"reason": reason, "task_name": task.name, "task_fingerprint": task_key,
                    "generation": generation, "parent_id": child.get("parent_id"),
                    "child_id": child["id"], "parent": parent, "child": child,
                    "request_type": request_type.to_dict(), "grammar_snapshot": scope}
        if detail is not None:
            evidence["detail"] = detail
        work.exclusions.append(json.loads(_encoded(evidence)))

    def syntax(trial):
        if trial["id"] not in syntax_cache:
            current, raw = Term.from_dict(trial["term"]), Term.from_dict(trial["raw_term"])
            _complete_walk(raw, work)
            _complete_walk(current, work)
            _type_visits(request_type, work)
            canonical = canonical_term(current, work)
            work.compiler_invocations += 1
            decisions = tuple((tuple(c), p) for c, p in
                              snapshot.decisions(current, request_type=request_type))
            work.decision_events += len(decisions)
            syntax_cache[trial["id"]] = (canonical, _fingerprint(canonical.to_dict()),
                                          decisions, current, raw)
        return syntax_cache[trial["id"]]

    def measured_quality(trial):
        if trial["id"] not in quality_cache:
            quality_cache[trial["id"]] = quality(trial["outputs"], examples, work)
        return quality_cache[trial["id"]]

    preferences = []
    for child in trials:
        if child.get("parent_id") is None:
            continue
        work.edges += 1
        parent = indexed.get(child["parent_id"]) if type(child["parent_id"]) is int else None
        if parent is None or parent["id"] >= child["id"]:
            reject("missing_parent", child, parent)
            continue
        pair = (parent, child)
        required = ("runtime_failure", "incomplete", "heuristic_incomplete", "term", "raw_term", "outputs")
        if any(any(key not in trial for key in required) for trial in pair):
            reject("unknown_evidence", child, parent)
            continue
        if any(trial["runtime_failure"] is not None for trial in pair):
            reject("runtime_failure", child, parent)
            continue
        if any(trial["incomplete"] is not False or trial["heuristic_incomplete"] is not False or
               trial.get("public_incomplete", False) is not False for trial in pair):
            reject("incomplete_assessment", child, parent)
            continue
        if any(type(trial["outputs"]) is not list or len(trial["outputs"]) != len(examples)
               for trial in pair):
            reject("invalid_outputs", child, parent)
            continue
        try:
            parent_quality, child_quality = map(measured_quality, pair)
        except (TypeError, ValueError, RecursionError) as error:
            reject("invalid_outputs", child, parent, str(error))
            continue
        child_comparison = _quality_compare(child_quality, parent_quality, work)
        if child_comparison == 0:
            reject("equal_quality", child, parent)
            continue
        try:
            p, c = syntax(parent), syntax(child)
        except (TypeError, ValueError, KeyError, RecursionError) as error:
            reject("invalid_syntax", child, parent, str(error))
            continue
        lo, hi, lo_q, hi_q = ((p, c, parent_quality, child_quality) if p[1] < c[1] else
                              (c, p, child_quality, parent_quality))
        lo_counts, hi_counts = Counter(lo[2]), Counter(hi[2])
        difference = tuple((context, production, hi_counts[context, production] - lo_counts[context, production])
                           for context, production in sorted(set(lo_counts) | set(hi_counts))
                           if hi_counts[context, production] != lo_counts[context, production])
        if not difference:
            reject("zero_difference", child, parent)
            continue
        if features is None:
            work.feature_calls += 1
            features = tuple(float(value) for value in task_features(task))
        preferred_fingerprint = c[1] if child_comparison > 0 else p[1]
        label = 1 if preferred_fingerprint == hi[1] else -1
        preferences.append(Preference(
            task.name, task_key, library_key, generation, parent["id"], child["id"],
            request_type, scope, p[4], c[4], p[3], c[3], lo[0], hi[0], lo[1], hi[1],
            label, difference, features, lo_q, hi_q, lo[2], hi[2]))
        work.eligible_preferences += 1
    return finish(preferences)


class PreferenceMemory:
    """Deduplicated replay plus durable repeated-source/exclusion provenance."""
    def __init__(self):
        self._records = {}
        self.duplicates = 0
        self.occurrences = []
        self.exclusions = []

    def add(self, records, exclusions=()):
        added = 0
        for record in records:
            _validate_preference(record)
            if record.key in self._records:
                previous = self._records[record.key]
                if previous.label != record.label or previous.difference != record.difference:
                    raise ValueError("identical public AST pair has contradictory evidence")
                self.duplicates += 1
            else:
                self._records[record.key] = record
                added += 1
            self.occurrences.append(record.to_dict())
        self.exclusions.extend(json.loads(_encoded(list(exclusions))))
        return added

    def records(self):
        return tuple(self._records[key] for key in sorted(self._records))

    def __len__(self):
        return len(self._records)

    def to_dict(self):
        return {"version": 1, "records": [r.to_dict() for r in self.records()],
                "occurrences": self.occurrences, "duplicates": self.duplicates,
                "exclusions": self.exclusions}

    @classmethod
    def from_dict(cls, record):
        if record["version"] != 1:
            raise ValueError("unsupported preference memory version")
        result = cls()
        result.add(Preference.from_dict(r) for r in record["records"])
        result.occurrences = json.loads(_encoded(record["occurrences"]))
        result.duplicates = int(record["duplicates"])
        result.exclusions = json.loads(_encoded(record["exclusions"]))
        return result
