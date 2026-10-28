"""Registered public-preference recognizer, separate from the default learner.

This module opens no task files and executes no candidate. Callers supply only
fitting-group tasks, verified positive labels and common dreams. In particular,
the caller, not a name heuristic here, must exclude shadow labels from that
corpus. Preference decisions were replayed against their immutable source
library by the extractor; they are never replayed against a newer library here.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import time

import numpy as np

from rsi2.recognition import (
    FEATURE_DIM, FEATURE_VERSION, Recognition, REGULARIZATION,
    STANDARDIZED_LIMIT, TRAINING_STEPS, _log_softmax, task_features,
)

INITIALIZATION_SCALE = 0.01


def _validate(contexts, productions, mean, scale, weights):
    if (contexts != tuple(sorted(set(contexts))) or
            productions != tuple(sorted(set(productions)))):
        raise ValueError("recognition keys must be unique and sorted")
    if bool(contexts) != bool(productions):
        raise ValueError("recognition context and production axes must coexist")
    if (mean.shape != (FEATURE_DIM,) or scale.shape != (FEATURE_DIM,) or
            weights.shape != (FEATURE_DIM + 1, len(contexts), len(productions)) or
            not all(np.isfinite(a).all() for a in (mean, scale, weights)) or
            not (scale > 0).all()):
        raise ValueError("invalid recognition model parameters")


@dataclass(frozen=True)
class SharedState:
    """Owned, read-only arrays shared by all matched optimizer arms."""

    seed: int
    contexts: tuple
    productions: tuple
    mean: np.ndarray
    scale: np.ndarray
    weights: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, "seed", int(self.seed))
        object.__setattr__(self, "contexts", tuple(tuple(c) for c in self.contexts))
        object.__setattr__(self, "productions", tuple(self.productions))
        for name in ("mean", "scale", "weights"):
            value = np.asarray(getattr(self, name), dtype=np.float64).copy()
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        _validate(self.contexts, self.productions, self.mean, self.scale, self.weights)

    def to_dict(self):
        return {"version": FEATURE_VERSION, "seed": self.seed,
                "contexts": [list(c) for c in self.contexts],
                "productions": list(self.productions), "mean": self.mean.tolist(),
                "scale": self.scale.tolist(), "weights": self.weights.tolist()}

    @classmethod
    def from_dict(cls, record):
        model = PairwiseRecognition.from_dict(record)
        return _state(model)


def _state(model):
    return SharedState(model.seed, model.contexts, model.productions,
                       model.mean, model.scale, model.weights)


def _records(memory):
    records = tuple(sorted(memory.records(), key=lambda record: record.key))
    if len({r.key for r in records}) != len(records):
        raise ValueError("preference memory must deduplicate canonical pair keys")
    return records


def _design(features, state):
    features = np.asarray(features, dtype=np.float64).reshape((-1, FEATURE_DIM))
    if not np.isfinite(features).all():
        raise ValueError("public task features must be finite")
    scaled = np.clip((features - state.mean) / state.scale,
                     -STANDARDIZED_LIMIT, STANDARDIZED_LIMIT)
    return np.concatenate((scaled, np.ones((len(features), 1))), axis=1)


def _matrices(*, temporary_shapes=None, **arrays):
    """Inventory named persistent/temporary tensors, not a peak-RSS claim."""
    shapes = {name: list(a.shape) for name, a in arrays.items()}
    shapes.update({name: list(shape) for name, shape in (temporary_shapes or {}).items()})
    elements = sum(int(np.prod(shape)) for shape in shapes.values())
    return {"matrix_shapes": shapes, "matrix_elements": elements,
            "matrix_bytes": elements * np.dtype(np.float64).itemsize,
            "matrix_accounting": "named algorithm tensors; not simultaneous peak memory"}


def _timing(started, wall_started):
    cpu = time.process_time() - started
    return {"cpu_seconds": cpu, "training_cpu_seconds": cpu,
            "wall_seconds": time.perf_counter() - wall_started}


def align_state(prior, template):
    """Copy retained offsets by key, with neutral new axes and no scaler rebase.

    Standardized clipping makes general exact scaler rebasing impossible. A
    retained comparison therefore requires the same frozen transform; unequal
    transforms fail explicitly instead of silently changing old predictions.
    """
    if not isinstance(prior, (Recognition, SharedState)):
        raise TypeError("prior must be a recognition model or shared state")
    if not (np.array_equal(prior.mean, template.mean) and
            np.array_equal(prior.scale, template.scale)):
        raise ValueError("retained states require the same frozen feature transform")
    if (not set(prior.contexts).issubset(template.contexts) or
            not set(prior.productions).issubset(template.productions)):
        raise ValueError("alignment cannot discard retained recognition keys")
    weights = np.zeros_like(template.weights)
    contexts = {c: i for i, c in enumerate(template.contexts)}
    productions = {p: i for i, p in enumerate(template.productions)}
    for i, context in enumerate(prior.contexts):
        for j, production in enumerate(prior.productions):
            weights[:, contexts[context], productions[production]] = prior.weights[:, i, j]
    return SharedState(prior.seed, template.contexts, template.productions,
                       template.mean, template.scale, weights)


def prepare_common_state(positive_pairs, grammar, memory, *, fitting_tasks,
                         seed=0, prior=None):
    """Align all evidence, then do the common positive-only 80-step base fit.

    A fresh scaler uses one row per supplied fitting task and one per supplied
    positive/dream pair. Those explicit rows (including repeats) are reported.
    With a retained prior its public-only scaler stays frozen across generations.
    The fresh sorted union is initialized with seeded N(0, .01) offsets; later
    newly introduced axes are zero before the common positive fit.
    """
    started, wall_started = time.process_time(), time.perf_counter()
    pairs, fitting_tasks, records = list(positive_pairs), list(fitting_tasks), _records(memory)
    derivations = [tuple(grammar.decisions(term, request_type=task.request_type))
                   for task, term in pairs]
    # Include shared/cancelled decisions, not merely the nonzero difference.
    decisions = [decision for derivation in derivations for decision in derivation]
    decisions.extend(decision for record in records
                     for derivation in (record.lo_decisions, record.hi_decisions)
                     for decision in derivation)
    contexts = {tuple(c) for c, _ in decisions}
    productions = {p for _, p in decisions}
    if prior is not None:
        if not isinstance(prior, (Recognition, SharedState)):
            raise TypeError("prior must be a recognition model or shared state")
        contexts.update(prior.contexts)
        productions.update(prior.productions)
    contexts, productions = tuple(sorted(contexts)), tuple(sorted(productions))
    features = np.asarray([task_features(task) for task in
                           fitting_tasks + [task for task, _ in pairs]],
                          dtype=np.float64).reshape((-1, FEATURE_DIM))
    if prior is not None:
        mean, scale = prior.mean, prior.scale
    elif len(features):
        mean, scale = features.mean(axis=0), features.std(axis=0)
        scale[scale < 1e-8] = 1.0
    else:
        mean, scale = np.zeros(FEATURE_DIM), np.ones(FEATURE_DIM)
    shape = (FEATURE_DIM + 1, len(contexts), len(productions))
    weights = (np.zeros(shape) if prior is not None else
               np.random.default_rng(seed).normal(0.0, INITIALIZATION_SCALE, shape))
    initial = SharedState(seed, contexts, productions, mean, scale, weights)
    if prior is not None:
        initial = align_state(prior, initial)
    model = PairwiseRecognition.from_state(initial)
    metrics = model._fit_positive(pairs, derivations)
    metrics.update({"phase": "common_positive_base", "fitting_tasks": len(fitting_tasks),
                    "transform_feature_rows": len(features),
                    "transform_source": "retained_prior" if prior is not None else "fitting_public_and_common_positive",
                    "initialization_scale": INITIALIZATION_SCALE,
                    "new_key_initialization": "zero" if prior is not None else "seeded_normal",
                    "retained_prior": prior is not None,
                    "preference_decision_visits": sum(len(r.lo_decisions) + len(r.hi_decisions)
                                                      for r in records),
                    "transform_matrix_shape": list(features.shape),
                    "transform_matrix_elements": int(features.size),
                    "transform_matrix_bytes": int(features.nbytes),
                    **_timing(started, wall_started)})
    return _state(model), metrics


common_state = prepare_common_state


def permuted_labels(memory, seed):
    """Fixed-seed permutation of canonical signed labels, without mutating memory."""
    records = _records(memory)
    labels = np.asarray([r.label for r in records], dtype=np.float64)
    if not np.isin(labels, (-1, 1)).all():
        raise ValueError("preference labels must be signed")
    order = np.random.default_rng(seed).permutation(len(records))
    shuffled = labels[order]
    changed = int((shuffled != labels).sum())
    return shuffled, {
        "seed": int(seed), "canonical_pair_keys": [list(r.key) for r in records],
        "source_row_mapping": order.tolist(), "permuted_labels": shuffled.tolist(),
        "changed_labels": changed,
        "status": "informative" if len(set(labels)) > 1 and changed else "uninformative",
    }


def contrast_rows(memory, state, *, labels_override=None):
    records = _records(memory)
    labels = np.asarray([r.label for r in records] if labels_override is None else
                        labels_override, dtype=np.float64).copy()
    if labels.shape != (len(records),) or not np.isin(labels, (-1, 1)).all():
        raise ValueError("control labels must be one signed value per canonical pair")
    counts = Counter(r.task_fingerprint for r in records)
    alpha = np.asarray([1.0 / (len(counts) * counts[r.task_fingerprint])
                        for r in records], dtype=np.float64)
    design = _design([r.features for r in records], state)
    contexts = {c: i for i, c in enumerate(state.contexts)}
    productions = {p: i for i, p in enumerate(state.productions)}
    difference = np.zeros((len(records), len(contexts), len(productions)))
    for i, record in enumerate(records):
        for context, production, count in record.difference:
            try:
                difference[i, contexts[tuple(context)], productions[production]] += count
            except KeyError as error:
                raise ValueError("preference key absent from frozen common state") from error
        norm = float(np.linalg.norm(difference[i]))
        if not np.isfinite(norm) or norm == 0:
            raise ValueError("preference needs a finite nonzero contextual difference")
        difference[i] /= norm
    return records, design, difference, labels, alpha


def preference_objective_gradient(weights, design, difference, labels, alpha):
    """Task-balanced logistic preference loss plus the frozen ridge penalty."""
    margins = labels * np.einsum("nd,dck,nck->n", design, weights, difference)
    objective = float((alpha * np.logaddexp(0, -margins)).sum() +
                      0.5 * REGULARIZATION * np.square(weights).sum())
    residual = -alpha * labels * np.exp(-np.logaddexp(0, margins))
    gradient = np.einsum("n,nd,nck->dck", residual, design, difference)
    gradient += REGULARIZATION * weights
    return objective, gradient


class PairwiseRecognition(Recognition):
    """Frozen feature map and prediction API with matched positive/contrast fits."""

    def __init__(self, seed=0):
        super().__init__(seed)
        self.prediction_metrics = {"calls": 0, "cpu_seconds": 0.0, "wall_seconds": 0.0}

    def _load_shared(self, state):
        self.seed = state.seed
        self.contexts, self.productions = state.contexts, state.productions
        self.mean, self.scale, self.weights = state.mean.copy(), state.scale.copy(), state.weights.copy()

    @classmethod
    def from_state(cls, state):
        model = cls(state.seed)
        model._load_shared(state)
        return model

    @classmethod
    def from_dict(cls, record):
        model = super().from_dict(record)
        _validate(model.contexts, model.productions, model.mean, model.scale, model.weights)
        return model

    def grammar_for(self, task, grammar):
        started, wall_started = time.process_time(), time.perf_counter()
        result = super().grammar_for(task, grammar)
        self.prediction_metrics["calls"] += 1
        self.prediction_metrics["cpu_seconds"] += time.process_time() - started
        self.prediction_metrics["wall_seconds"] += time.perf_counter() - wall_started
        shape = (len(self.contexts), len(self.productions))
        self.prediction_metrics.update({
            "weight_matrix_shape": list(self.weights.shape),
            "weight_matrix_elements": int(self.weights.size),
            "logit_matrix_shape": list(shape),
            "logit_matrix_elements": int(np.prod(shape)),
            "feature_vector_elements": FEATURE_DIM,
            "design_vector_elements": FEATURE_DIM + 1,
            "semantic_evaluator_calls": 0})
        return result

    def fit_preferences(self, memory, state, *, labels_override=None):
        started, wall_started = time.process_time(), time.perf_counter()
        self._load_shared(state)
        records, design, difference, labels, alpha = contrast_rows(
            memory, state, labels_override=labels_override)
        covariance = design.T @ (alpha[:, None] * design)
        eigmax = float(np.linalg.eigvalsh(covariance).max())
        rate = 1.0 / (eigmax + REGULARIZATION)
        before, gradient = preference_objective_gradient(
            self.weights, design, difference, labels, alpha)
        for _ in range(TRAINING_STEPS if records else 0):
            _, gradient = preference_objective_gradient(
                self.weights, design, difference, labels, alpha)
            self.weights -= rate * gradient
        after, gradient = preference_objective_gradient(
            self.weights, design, difference, labels, alpha)
        return {
            "pairs": len(records), "tasks": len({r.task_fingerprint for r in records}),
            "contexts": len(self.contexts), "productions": len(self.productions),
            "feature_version": FEATURE_VERSION, "steps": TRAINING_STEPS if records else 0,
            "ridge": REGULARIZATION, "semantic_evaluator_calls": 0,
            "signed_control_labels": labels_override is not None,
            "objective_before": before, "objective_after": after,
            "pair_weights": alpha.tolist(), "learning_rate": rate,
            "covariance_eigenvalue_max": eigmax,
            "hessian_bound": 0.25 * eigmax + REGULARIZATION,
            "preference_decision_visits": sum(len(r.lo_decisions) + len(r.hi_decisions)
                                              for r in records),
            **_matrices(design=design, difference=difference, labels=labels, alpha=alpha,
                        weights=self.weights, gradient=gradient, covariance=covariance,
                        mean=self.mean, scale=self.scale,
                        temporary_shapes={"features": (len(records), FEATURE_DIM),
                                          "standardized_features": (len(records), FEATURE_DIM),
                                          "weighted_design": design.shape,
                                          "margins": labels.shape,
                                          "logistic_residual": labels.shape}),
            **_timing(started, wall_started),
        }

    def _fit_positive(self, pairs, derivations):
        contexts = {c: i for i, c in enumerate(self.contexts)}
        productions = {p: i for i, p in enumerate(self.productions)}
        counts = np.zeros((len(pairs), len(contexts), len(productions)))
        for i, decisions in enumerate(derivations):
            for context, production in decisions:
                try:
                    counts[i, contexts[tuple(context)], productions[production]] += 1
                except KeyError as error:
                    raise ValueError("positive key absent from frozen common state") from error
        total = float(counts.sum())
        if pairs and total == 0:
            raise ValueError("positive recognition needs a production decision")
        design = self._design(np.asarray([task_features(task) for task, _ in pairs],
                                        dtype=np.float64).reshape((-1, FEATURE_DIM)))
        alpha = counts.sum(axis=(1, 2)) / total if total else np.empty(0)
        covariance = design.T @ (alpha[:, None] * design)
        eigmax = float(np.linalg.eigvalsh(covariance).max())
        rate = 1.0 / (eigmax + REGULARIZATION)
        totals = counts.sum(axis=-1, keepdims=True)

        def objective_gradient():
            if not pairs:
                return 0.5 * REGULARIZATION * float(np.square(self.weights).sum()), np.zeros_like(self.weights)
            log_probs = _log_softmax(np.einsum("nd,dck->nck", design, self.weights))
            loss = float(-(counts * log_probs).sum() / total +
                         0.5 * REGULARIZATION * np.square(self.weights).sum())
            residual = (np.exp(log_probs) * totals - counts) / total
            gradient = np.einsum("nd,nck->dck", design, residual) + REGULARIZATION * self.weights
            return loss, gradient

        before, gradient = objective_gradient()
        for _ in range(TRAINING_STEPS if pairs else 0):
            _, gradient = objective_gradient()
            self.weights -= rate * gradient
        after, gradient = objective_gradient()
        return {"examples": len(pairs), "steps": TRAINING_STEPS if pairs else 0,
                "decisions": int(total), "contexts": len(contexts),
                "productions": len(productions), "feature_version": FEATURE_VERSION,
                "typed_derivation_replays": len(pairs),
                "positive_ast_input_nodes": sum(term.size for _, term in pairs),
                "positive_contextual_decision_visits": int(total),
                "ridge": REGULARIZATION, "objective_before": before, "objective_after": after,
                "learning_rate": rate, "covariance_eigenvalue_max": eigmax,
                "semantic_evaluator_calls": 0,
                **_matrices(design=design, counts=counts, alpha=alpha, totals=totals,
                            weights=self.weights, gradient=gradient, covariance=covariance,
                            mean=self.mean, scale=self.scale,
                            temporary_shapes={"features": (len(pairs), FEATURE_DIM),
                                              "standardized_features": (len(pairs), FEATURE_DIM),
                                              "weighted_design": design.shape,
                                              "logits": counts.shape,
                                              "log_probabilities": counts.shape,
                                              "softmax_probabilities": counts.shape,
                                              "positive_residual": counts.shape})}

    def fit_positive_extra(self, pairs, grammar, state):
        """The matched 80-step positive-only update, from the same common state."""
        started, wall_started = time.process_time(), time.perf_counter()
        self._load_shared(state)
        pairs = list(pairs)
        derivations = [tuple(grammar.decisions(term, request_type=task.request_type))
                       for task, term in pairs]
        return {**self._fit_positive(pairs, derivations),
                **_timing(started, wall_started)}
