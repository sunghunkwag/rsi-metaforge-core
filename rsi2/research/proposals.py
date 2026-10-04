"""Development-only proposal streams and a prior-audit productivity ranker.

The learned objective is runtime validity AND informative score contrast. It
is a productivity proxy, never a prediction or measurement of task success.
All proposals come from the existing typed enumerator or original mutation.
"""
from __future__ import annotations

import copy
import json
import random

import numpy as np

from ..enumeration import enumerate_programs
from ..grammar import Grammar
from ..heuristics import MUTATION_SEED_MULTIPLIER, mutate, zero_heuristic
from ..search import HEURISTIC_TYPE
from ..terms import Term
from ..types import PRIMITIVE_TYPES, Type, library_entries, library_entry


ENUMERATION_SLOTS = 32
MUTATION_SLOTS = 2
SELECTION_QUOTA = 6
TRAINING_STEPS = 80
REGULARIZATION = 1e-3
FEATURE_VERSION = 1
FEATURE_NAMES = tuple(f"primitive:{name}" for name in sorted(PRIMITIVE_TYPES)) + (
    "lambda", "var", "int", "bool", "ref", "application", "size", "depth",
    "positive_int", "negative_int", "zero_int")
MODES = ("original", "static", "learned")
OBJECTIVE = "previous_audit_valid_and_informative_productivity_proxy"


class _CountingGrammar(Grammar):
    """Transparent metering of partial expansion calls in the original streams."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.partial_expansion_calls = 0

    def productions(self, *args, **kwargs):
        self.partial_expansion_calls += 1
        return super().productions(*args, **kwargs)


def canonical_term(term):
    """Preserve the generated AST while renaming only inferred type variables."""
    if term is None:
        return None
    variables = {}

    def annotation(type_):
        if type_.is_variable:
            variables.setdefault(type_.name, f"proposal_type_{len(variables)}")
            return Type("var", (variables[type_.name],))
        return Type(type_.tag, tuple(annotation(arg) for arg in type_.args))

    def visit(node):
        value = annotation(node.value) if node.tag in ("lam", "hole") else node.value
        return Term(node.tag, value, tuple(visit(child) for child in node.children))

    return visit(term)


def _term_key(term):
    return json.dumps(canonical_term(term).to_dict(), sort_keys=True, separators=(",", ":"))


def features(term):
    """Fixed syntax counts; fitted coefficients are the only learned choices."""
    values = dict.fromkeys(FEATURE_NAMES, 0.0)
    pending = [term]
    names = {"lam": "lambda", "var": "var", "int": "int", "bool": "bool",
             "ref": "ref", "app": "application"}
    while pending:
        node = pending.pop()
        if node.tag == "prim":
            key = f"primitive:{node.value}" if node.value in PRIMITIVE_TYPES else "ref"
            values[key] += 1
        elif node.tag in names:
            values[names[node.tag]] += 1
        elif node.tag != "hole":
            raise ValueError(f"unknown AST feature tag {node.tag!r}")
        if node.tag == "int":
            sign = "positive_int" if node.value > 0 else "negative_int" if node.value < 0 else "zero_int"
            values[sign] += 1
        pending.extend(node.children)
    values["size"], values["depth"] = float(term.size), float(term.depth)
    return np.asarray([values[name] for name in FEATURE_NAMES], dtype=np.float64)


def grammar_scope(grammar):
    """Include production insertion order: ties in enumeration depend on it."""
    entries = []
    for name, entry in library_entries(grammar.library).items():
        body, declared = library_entry(entry)
        entries.append({"name": name, "term": None if body is None else body.to_dict(),
                        "type": None if declared is None else declared.to_dict()})
    return {"library": entries,
            "primitives": [{"name": name, "type": type_.to_dict()}
                           for name, type_ in grammar.primitives.items()],
            "constants": [term.to_dict() for term in grammar.constants],
            "weights": [[name, value] for name, value in grammar.weights.items()],
            "context_weights": [{"parent": parent, "argument": argument,
                                 "weights": [[name, value] for name, value in weights.items()]}
                                for (parent, argument), weights in grammar.context_weights.items()],
            "request_type": HEURISTIC_TYPE.to_dict(), "feature_version": FEATURE_VERSION,
            "feature_names": list(FEATURE_NAMES)}


def _grammar(scope):
    library = {}
    for record in scope["library"]:
        body = None if record["term"] is None else Term.from_dict(record["term"])
        declared = None if record["type"] is None else Type.from_dict(record["type"])
        library[record["name"]] = body if declared is None else (declared, body)
    return _CountingGrammar(library=library,
                   primitives={item["name"]: Type.from_dict(item["type"]) for item in scope["primitives"]},
                   constants=[Term.from_dict(term) for term in scope["constants"]],
                   weights=dict(scope["weights"]),
                   context_weights={(item["parent"], item["argument"]): dict(item["weights"])
                                    for item in scope["context_weights"]})


def _serialize(records):
    return [{**record, "term": None if record["term"] is None else record["term"].to_dict()}
            for record in records]


def _deserialize(records):
    return [{**record, "term": None if record["term"] is None else Term.from_dict(record["term"])}
            for record in records]


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


class ProposalPool:
    def __init__(self, grammar, seed, mode, state=None):
        if mode not in MODES:
            raise ValueError(f"unknown proposal mode {mode!r}")
        self.seed, self.mode = _integer(seed, "seed"), mode
        self.scope = grammar_scope(grammar)
        self.grammar = _grammar(self.scope)
        self.offset, self.exhausted, self.last_cycle = 0, False, 0
        self.searchconfig, self._iterator = None, None
        self.selected = {}
        self.samples = []
        self.mean = np.zeros(len(FEATURE_NAMES))
        self.scale = np.ones(len(FEATURE_NAMES))
        self.coefficients = np.zeros(len(FEATURE_NAMES) + 1)
        self.raw_draws_total = self.replay_draws_total = 0
        self.draw_report, self.selection_report = {}, {}
        self.pending_records, self.selection_indices = None, None
        self.pending_audits = None
        if state is not None:
            self._restore(state)

    def _restore(self, state):
        if (state.get("version") != 1 or state.get("seed") != self.seed
                or state.get("mode") != self.mode or state.get("scope") != self.scope):
            raise ValueError("proposal checkpoint does not match the frozen grammar, seed, or mode")
        self.offset = _integer(state["offset"], "offset")
        self.last_cycle = _integer(state["last_cycle"], "last_cycle")
        if type(state["exhausted"]) is not bool:
            raise ValueError("checkpoint exhausted must be boolean")
        self.exhausted = state["exhausted"]
        self.searchconfig = copy.deepcopy(state["searchconfig"])
        self.raw_draws_total = _integer(state["raw_draws_total"], "raw_draws_total")
        self.replay_draws_total = _integer(state["replay_draws_total"], "replay_draws_total")
        for item in state["selected_terms"]:
            term = canonical_term(Term.from_dict(item))
            self.selected[_term_key(term)] = term
        self.samples = copy.deepcopy(state["samples"])
        for sample in self.samples:
            term = canonical_term(Term.from_dict(sample["term"]))
            if (sample["features"] != features(term).tolist() or type(sample["label"]) is not int
                    or sample["label"] not in (0, 1)):
                raise ValueError("checkpoint training row disagrees with fixed features or binary label")
            if (not 1 <= _integer(sample["cycle"], "sample cycle", minimum=1) <= self.last_cycle
                    or not 0 <= _integer(sample["index"], "sample index") < ENUMERATION_SLOTS + MUTATION_SLOTS):
                raise ValueError("checkpoint contains an out-of-round training row")
        self.mean = np.asarray(state["model"]["mean"], dtype=np.float64)
        self.scale = np.asarray(state["model"]["scale"], dtype=np.float64)
        self.coefficients = np.asarray(state["model"]["coefficients"], dtype=np.float64)
        if (self.mean.shape != (len(FEATURE_NAMES),) or self.scale.shape != self.mean.shape
                or self.coefficients.shape != (len(FEATURE_NAMES) + 1,)
                or not all(np.isfinite(array).all() for array in (self.mean, self.scale, self.coefficients))
                or not (self.scale > 0).all()):
            raise ValueError("checkpoint linear model has invalid dimensions or values")
        pending = state.get("pending_records")
        self.pending_records = None if pending is None else _deserialize(pending)
        self.selection_indices = copy.deepcopy(state.get("selection_indices"))
        self.pending_audits = copy.deepcopy(state.get("pending_audits"))
        if self.pending_records is not None:
            if (len(self.pending_records) != ENUMERATION_SLOTS + MUTATION_SLOTS
                    or any(record["index"] != index or record["cycle"] != self.last_cycle
                           for index, record in enumerate(self.pending_records))
                    or any(sample["cycle"] >= self.last_cycle for sample in self.samples)):
                raise ValueError("checkpoint pending round overlaps observed training data")
            if self.selection_indices is not None:
                if (len(set(self.selection_indices)) != len(self.selection_indices)
                        or len(self.selection_indices) > SELECTION_QUOTA
                        or any(type(index) is not int or not 0 <= index < len(self.pending_records)
                               for index in self.selection_indices)):
                    raise ValueError("checkpoint contains invalid selection indices")
        elif self.selection_indices is not None or self.pending_audits is not None:
            raise ValueError("checkpoint selection has no pending proposal round")
        if state["model"].get("trained_count") != (len(self.samples) if self.mode == "learned" else 0):
            raise ValueError("checkpoint model count disagrees with previous training rows")
        self.draw_report = copy.deepcopy(state.get("draw_report", {}))
        self.selection_report = copy.deepcopy(state.get("selection_report", {}))

    def _check_scope(self):
        if grammar_scope(self.grammar) != self.scope:
            raise ValueError("proposal grammar changed after its scope was frozen")

    def _stream(self, searchconfig):
        return iter(enumerate_programs(HEURISTIC_TYPE, self.grammar,
                                      max_size=searchconfig["max_size"],
                                      max_expansions=searchconfig["max_expansions"]))

    def draw(self, incumbent, cycle, searchconfig):
        self._check_scope()
        cycle = _integer(cycle, "cycle", minimum=1)
        if cycle <= self.last_cycle or self.pending_records is not None:
            raise ValueError("finish the pending round before drawing a strictly later cycle")
        searchconfig = copy.deepcopy(searchconfig)
        for name in ("max_size", "max_expansions", "step_budget"):
            _integer(searchconfig[name], name, minimum=1)
        if self.searchconfig is not None and searchconfig != self.searchconfig:
            raise ValueError("proposal search bounds changed after the first draw")
        self.searchconfig = searchconfig
        replay = 0
        replay_started = self.grammar.partial_expansion_calls
        if self.mode == "original":
            iterator, exhausted = self._stream(searchconfig), False
        else:
            if self._iterator is None and not self.exhausted:
                self._iterator = self._stream(searchconfig)
                for _ in range(self.offset):
                    if next(self._iterator, None) is None:
                        raise ValueError("checkpoint enumeration offset exceeds the frozen stream")
                    replay += 1
            iterator, exhausted = self._iterator, self.exhausted
        replay_calls = self.grammar.partial_expansion_calls - replay_started
        records = []
        yielded = 0
        enumeration_started = self.grammar.partial_expansion_calls
        for index in range(ENUMERATION_SLOTS):
            candidate = None if exhausted else next(iterator, None)
            if candidate is None:
                exhausted = True
            else:
                yielded += 1
            records.append({"index": index, "cycle": cycle, "origin": "enumeration",
                            "term": canonical_term(candidate.term) if candidate is not None else None,
                            "mutation_path": None,
                            "rejection": None if candidate is not None else "enumerator_exhausted"})
        if self.mode != "original":
            self.offset += yielded
            self.exhausted = exhausted
        enumeration_calls = self.grammar.partial_expansion_calls - enumeration_started
        rng = random.Random(self.seed * MUTATION_SEED_MULTIPLIER + cycle)
        incumbent = zero_heuristic() if incumbent is None else incumbent
        mutation_started = self.grammar.partial_expansion_calls
        for index in range(MUTATION_SLOTS):
            term, path, rejection = mutate(incumbent, self.grammar, rng, searchconfig,
                                           template_library=self.grammar.library, primitive_only=False)
            records.append({"index": ENUMERATION_SLOTS + index, "cycle": cycle,
                            "origin": "mutation", "term": canonical_term(term),
                            "mutation_path": list(path), "rejection": rejection})
        mutation_calls = self.grammar.partial_expansion_calls - mutation_started
        self.last_cycle = cycle
        self.raw_draws_total += ENUMERATION_SLOTS + MUTATION_SLOTS
        self.replay_draws_total += replay
        self.draw_report = {"cycle": cycle, "enumeration_slots": ENUMERATION_SLOTS,
                            "mutation_slots": MUTATION_SLOTS, "new_raw_draws": len(records),
                            "enumerated_candidates": yielded, "replay_draws": replay,
                            "enumeration_offset": self.offset, "stream_exhausted": exhausted,
                            "partial_expansion_calls": {"enumeration": enumeration_calls,
                                                        "replay": replay_calls,
                                                        "mutation": mutation_calls},
                            "new_enumeration_frontier_pops": enumeration_calls + yielded,
                            "replay_frontier_pops": replay_calls + replay,
                            "enumeration_frontier_pops": enumeration_calls + yielded + replay_calls + replay,
                            "mutation_complete_frontier_pops_bounds": [0, MUTATION_SLOTS],
                            "model_trained_count": self.model_report["trained_count"],
                            "expansion_limit_scope": "per_cycle_restart" if self.mode == "original"
                            else "cumulative_persistent_stream"}
        self.pending_records = copy.deepcopy(records)
        self.selection_indices = None
        self.pending_audits = None
        return records

    def _check_records(self, records):
        if self.pending_records is None or _serialize(records) != _serialize(self.pending_records):
            raise ValueError("records do not match the pending raw proposal draw")

    @staticmethod
    def _audit(audits, index):
        try:
            audit = audits[index] if not isinstance(audits, dict) or index in audits else audits[str(index)]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"missing proposal audit at index {index}") from exc
        if type(audit.get("valid")) is not bool or type(audit.get("informative")) is not bool:
            raise ValueError("proposal audits must contain boolean valid and informative outcomes")
        return audit

    def predict(self, term):
        normalized = (features(term) - self.mean) / self.scale
        return float(normalized @ self.coefficients[:-1] + self.coefficients[-1])

    def select(self, records, audits, quota=SELECTION_QUOTA):
        self._check_scope()
        self._check_records(records)
        if quota != SELECTION_QUOTA or type(quota) is not int:
            raise ValueError("research selection quota is fixed at six")
        if self.selection_indices is not None:
            raise ValueError("this proposal draw has already been selected")
        predictions = {}
        audited = None if audits is None else [
            {"valid": self._audit(audits, record["index"])["valid"],
             "informative": self._audit(audits, record["index"])["informative"]}
            for record in records]
        if self.mode == "original":
            selected = [0, 1, 2, 3, ENUMERATION_SLOTS, ENUMERATION_SLOTS + 1]
        else:
            eligible, unique = [], set(self.selected)
            for record in records:
                audit, term = self._audit(audited, record["index"]), record["term"]
                if term is None or record["rejection"] is not None or not (audit["valid"] and audit["informative"]):
                    continue
                key = _term_key(term)
                if key in unique:
                    continue
                unique.add(key)
                index = record["index"]
                predictions[index] = self.predict(term) if self.mode == "learned" else 0.0
                eligible.append(index)
            selected = sorted(eligible, key=lambda index: (-predictions[index], index))[:quota]
        for index in selected:
            term = records[index]["term"]
            if term is not None:
                self.selected[_term_key(term)] = canonical_term(term)
        self.selection_indices = selected
        self.pending_audits = audited
        self.selection_report = {"selection_indices": list(selected),
                                 "model_trained_count": self.model_report["trained_count"],
                                 "predictions": {str(index): score for index, score in predictions.items()},
                                 "eligibility": "fixed_original_slots" if self.mode == "original"
                                 else "valid_and_informative_and_ast_novel"}
        return list(selected)

    def observe(self, records, audits):
        """Fit only after ranking; all nonempty raw ASTs contribute binary labels."""
        self._check_scope()
        self._check_records(records)
        if self.selection_indices is None:
            raise ValueError("observe must follow selection to prevent current-round label training")
        additions = []
        for record in records:
            audit = self._audit(audits, record["index"])
            flags = {"valid": audit["valid"], "informative": audit["informative"]}
            if self.pending_audits is not None and flags != self.pending_audits[record["index"]]:
                raise ValueError("observed audit labels changed after proposal selection")
            if record["term"] is not None:
                additions.append({"cycle": record["cycle"], "index": record["index"],
                                  "term": canonical_term(record["term"]).to_dict(),
                                  "features": features(record["term"]).tolist(),
                                  "label": int(audit["valid"] and audit["informative"])})
        self.samples.extend(additions)
        if self.mode == "learned":
            self._fit()
        self.pending_records, self.selection_indices = None, None
        self.pending_audits = None
        return {**self.model_report, "new_training_rows": len(additions)}

    def _fit(self):
        if not self.samples:
            return
        inputs = np.asarray([row["features"] for row in self.samples], dtype=np.float64)
        targets = np.asarray([row["label"] for row in self.samples], dtype=np.float64)
        self.mean, self.scale = inputs.mean(axis=0), inputs.std(axis=0)
        self.scale[self.scale < 1e-8] = 1.0
        design = np.column_stack(((inputs - self.mean) / self.scale, np.ones(len(inputs))))
        self.coefficients = np.zeros(design.shape[1], dtype=np.float64)
        covariance = design.T @ design / len(design)
        rate = 1.0 / (0.25 * float(np.linalg.eigvalsh(covariance).max()) + REGULARIZATION)
        for _ in range(TRAINING_STEPS):
            logits = np.clip(design @ self.coefficients, -40.0, 40.0)
            probabilities = 1.0 / (1.0 + np.exp(-logits))
            gradient = design.T @ (probabilities - targets) / len(design)
            gradient += REGULARIZATION * self.coefficients
            self.coefficients -= rate * gradient

    @property
    def model_report(self):
        return {"objective": OBJECTIVE, "kind": "numpy_linear_logistic_ranker",
                "observed_count": len(self.samples),
                "trained_count": len(self.samples) if self.mode == "learned" else 0,
                "training_steps": TRAINING_STEPS if self.samples and self.mode == "learned" else 0,
                "regularization": REGULARIZATION, "feature_names": list(FEATURE_NAMES),
                "mean": self.mean.tolist(), "scale": self.scale.tolist(),
                "coefficients": self.coefficients.tolist()}

    def to_dict(self):
        self._check_scope()
        return {"version": 1, "seed": self.seed, "mode": self.mode,
                "scope": copy.deepcopy(self.scope), "offset": self.offset,
                "exhausted": self.exhausted, "last_cycle": self.last_cycle,
                "searchconfig": copy.deepcopy(self.searchconfig),
                "raw_draws_total": self.raw_draws_total, "replay_draws_total": self.replay_draws_total,
                "selected_terms": [term.to_dict() for term in self.selected.values()],
                "samples": copy.deepcopy(self.samples), "model": self.model_report,
                "pending_records": None if self.pending_records is None else _serialize(self.pending_records),
                "selection_indices": copy.deepcopy(self.selection_indices),
                "pending_audits": copy.deepcopy(self.pending_audits),
                "draw_report": copy.deepcopy(self.draw_report),
                "selection_report": copy.deepcopy(self.selection_report)}
