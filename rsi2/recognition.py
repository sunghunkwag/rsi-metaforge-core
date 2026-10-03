"""Seeded numpy task recognition learned from supplied solution derivations.

The feature map and optimization settings are fixed before measurement. Only
public search examples enter features. Each parent/argument context predicts a
softmax distribution over observed production keys; predictions multiply the
current grammar prior by K times that probability, so a uniform prediction is
neutral. Unseen contexts and production keys retain the current prior.

The coordinator supplies both actual solved tasks and tasks dreamed by running
programs from its current grammar. This module opens no task files and does not
choose evaluation partitions or examples.
"""
from __future__ import annotations

import math

import numpy as np

from .grammar import Grammar


FEATURE_DIM = 32
FEATURE_VERSION = 1
TRAINING_STEPS = 80
REGULARIZATION = 1e-3
VALUE_LIMIT = 1_000_000
STANDARDIZED_LIMIT = 10.0
LOG_FACTOR_LIMIT = 20.0


def _leaves(value):
    values, booleans = [], 0
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, (list, tuple)):
            pending.extend(reversed(item))
        elif type(item) in (int, bool):
            booleans += type(item) is bool
            values.append(float(max(-VALUE_LIMIT, min(VALUE_LIMIT, item))))
        else:
            raise TypeError("recognition examples require int, bool, or list values")
    return np.asarray(values, dtype=np.float64), booleans


def _side_statistics(vectors, booleans):
    lengths = np.asarray([len(values) for values in vectors], dtype=np.float64)
    values = np.concatenate(vectors) if vectors else np.empty(0)
    length_stats = ([float(lengths.mean()), float(lengths.std()),
                     float(lengths.min()), float(lengths.max())]
                    if len(lengths) else [0.0] * 4)
    value_stats = ([float(values.mean()), float(values.std()), float(values.min()),
                    float(values.max()), float(np.abs(values).mean()),
                    float((values == 0).mean()), float((values > 0).mean()),
                    float((values < 0).mean()), float(booleans / len(values))]
                   if len(values) else [0.0] * 9)
    return length_stats + value_stats


def task_features(task):
    """Return 32 fixed statistics from ``task.examples`` and no other fields."""
    examples = task.examples
    inputs, outputs, arities = [], [], []
    input_booleans = output_booleans = list_inputs = list_outputs = total_inputs = 0
    for arguments, expected in examples:
        values, count = _leaves(arguments)
        inputs.append(values)
        input_booleans += count
        values, count = _leaves(expected)
        outputs.append(values)
        output_booleans += count
        arities.append(len(arguments))
        total_inputs += len(arguments)
        list_inputs += sum(isinstance(value, list) for value in arguments)
        list_outputs += isinstance(expected, list)
    in_sums = np.asarray([values.sum() for values in inputs], dtype=np.float64)
    out_sums = np.asarray([values.sum() for values in outputs], dtype=np.float64)
    correlation = 0.0
    if len(examples) > 1 and in_sums.std() > 0 and out_sums.std() > 0:
        correlation = float(np.mean((in_sums - in_sums.mean()) *
                                    (out_sums - out_sums.mean())) /
                            (in_sums.std() * out_sums.std()))
    extra = [math.log1p(len(examples)), float(np.mean(arities)) if arities else 0.0,
             list_inputs / total_inputs if total_inputs else 0.0,
             list_outputs / len(examples) if examples else 0.0, correlation,
             float(np.mean(out_sums - in_sums)) if examples else 0.0]
    result = np.asarray(_side_statistics(inputs, input_booleans) +
                        _side_statistics(outputs, output_booleans) + extra,
                        dtype=np.float64)
    if result.shape != (FEATURE_DIM,) or not np.isfinite(result).all():
        raise ValueError("recognition features must be a finite fixed-width vector")
    return result


def _log_softmax(logits):
    shifted = logits - logits.max(axis=-1, keepdims=True)
    return shifted - np.log(np.exp(shifted).sum(axis=-1, keepdims=True))


class Recognition:
    """A small linear model, refit deterministically on the supplied corpus."""

    def __init__(self, seed=0):
        self.seed = int(seed)
        self.contexts = ()
        self.productions = ()
        self.mean = np.zeros(FEATURE_DIM, dtype=np.float64)
        self.scale = np.ones(FEATURE_DIM, dtype=np.float64)
        self.weights = np.empty((FEATURE_DIM + 1, 0, 0), dtype=np.float64)

    def _design(self, features):
        scaled = np.clip((features - self.mean) / self.scale,
                         -STANDARDIZED_LIMIT, STANDARDIZED_LIMIT)
        return np.concatenate((scaled, np.ones((len(scaled), 1))), axis=1)

    def fit(self, pairs, grammar):
        """Fit on supplied real and dreamed (task, solution) pairs for 80 steps."""
        pairs = list(pairs)
        derivations = [grammar.decisions(term, request_type=task.request_type)
                       for task, term in pairs]
        self.contexts = tuple(sorted({tuple(context) for decisions in derivations
                                     for context, _ in decisions}))
        self.productions = tuple(sorted({production for decisions in derivations
                                        for _, production in decisions}))
        metrics = {"examples": len(pairs), "decisions": sum(map(len, derivations)),
                   "contexts": len(self.contexts), "productions": len(self.productions),
                   "steps": TRAINING_STEPS if pairs else 0}
        if not pairs:
            self.mean = np.zeros(FEATURE_DIM)
            self.scale = np.ones(FEATURE_DIM)
            self.weights = np.empty((FEATURE_DIM + 1, 0, 0))
            return {**metrics, "objective_before": 0.0, "objective_after": 0.0}
        features = np.asarray([task_features(task) for task, _ in pairs])
        self.mean = features.mean(axis=0)
        self.scale = features.std(axis=0)
        self.scale[self.scale < 1e-8] = 1.0
        design = self._design(features)
        contexts = {context: index for index, context in enumerate(self.contexts)}
        productions = {key: index for index, key in enumerate(self.productions)}
        counts = np.zeros((len(pairs), len(contexts), len(productions)))
        for index, decisions in enumerate(derivations):
            for context, key in decisions:
                counts[index, contexts[tuple(context)], productions[key]] += 1.0
        total = float(counts.sum())
        if total == 0:
            raise ValueError("recognition needs at least one production decision")
        totals = counts.sum(axis=-1, keepdims=True)
        rng = np.random.default_rng(self.seed)
        self.weights = rng.normal(0.0, 0.01,
                                  (FEATURE_DIM + 1, len(contexts), len(productions)))
        # An analytic covariance bound fixes a stable step size from the fitting
        # data, without evaluating or selecting any optimization hyperparameter.
        row_weights = counts.sum(axis=(1, 2)) / total
        covariance = design.T @ (row_weights[:, None] * design)
        rate = 1.0 / (float(np.linalg.eigvalsh(covariance).max()) + REGULARIZATION)

        def objective():
            log_probs = _log_softmax(np.einsum("nd,dck->nck", design, self.weights))
            return float(-(counts * log_probs).sum() / total +
                         0.5 * REGULARIZATION * np.square(self.weights).sum())

        before = objective()
        for _ in range(TRAINING_STEPS):
            logits = np.einsum("nd,dck->nck", design, self.weights)
            residual = (np.exp(_log_softmax(logits)) * totals - counts) / total
            gradient = np.einsum("nd,nck->dck", design, residual)
            gradient += REGULARIZATION * self.weights
            self.weights -= rate * gradient
        after = objective()
        return {**metrics, "objective_before": before, "objective_after": after}

    def grammar_for(self, task, grammar):
        """Condition a copy of the current prior on this task's public examples."""
        tables = {tuple(context): dict(weights)
                  for context, weights in grammar.context_weights.items()}
        if self.contexts:
            design = self._design(task_features(task)[None, :])[0]
            logits = np.einsum("d,dck->ck", design, self.weights)
            factors = np.clip(_log_softmax(logits) + math.log(len(self.productions)),
                              -LOG_FACTOR_LIMIT, LOG_FACTOR_LIMIT)
            for context_index, context in enumerate(self.contexts):
                table = tables.setdefault(context, {})
                original = grammar.context_weights.get(context, {})
                for production_index, key in enumerate(self.productions):
                    name = key.rsplit("/", 1)[0]
                    keys = (key, name) + (("var",) if name.startswith("var:") else ())
                    prior = 1.0
                    for source in (original, grammar.weights):
                        match = next((source[k] for k in keys if k in source), None)
                        if match is not None:
                            prior = float(match)
                            break
                    combined = math.log(prior) + float(factors[context_index, production_index])
                    table[key] = math.exp(max(-700.0, min(700.0, combined)))
        return Grammar(library=grammar.library, primitives=grammar.primitives,
                       constants=grammar.constants, weights=grammar.weights,
                       context_weights=tables)

    def to_dict(self):
        return {"version": FEATURE_VERSION, "seed": self.seed,
                "contexts": [list(context) for context in self.contexts],
                "productions": list(self.productions), "mean": self.mean.tolist(),
                "scale": self.scale.tolist(), "weights": self.weights.tolist()}

    @classmethod
    def from_dict(cls, record):
        if record["version"] != FEATURE_VERSION:
            raise ValueError("unsupported recognition feature version")
        model = cls(record["seed"])
        model.contexts = tuple((str(parent), int(argument))
                               for parent, argument in record["contexts"])
        model.productions = tuple(map(str, record["productions"]))
        model.mean = np.asarray(record["mean"], dtype=np.float64)
        model.scale = np.asarray(record["scale"], dtype=np.float64)
        shape = (FEATURE_DIM + 1, len(model.contexts), len(model.productions))
        model.weights = np.asarray(record["weights"], dtype=np.float64).reshape(shape)
        if (model.mean.shape != (FEATURE_DIM,) or model.scale.shape != (FEATURE_DIM,)
                or not all(np.isfinite(array).all()
                           for array in (model.mean, model.scale, model.weights))
                or not (model.scale > 0).all()):
            raise ValueError("invalid recognition model parameters")
        return model
