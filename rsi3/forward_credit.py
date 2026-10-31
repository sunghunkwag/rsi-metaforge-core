"""Forward-only, public-example credit for discrete program-search probes.

This is a Q Labs-inspired experiment, NOT a port of Dust or Noise. Their
activation-perturbation credit estimator applies to neural weights; here the
perturbation unit is the candidate program and the observable is public task
output. No hidden verifier data, validation examples, or test examples enter
these computations. The proxy may be misleading and must be ablated.
"""
from __future__ import annotations

import math


def output_credit(actual, expected) -> float:
    """Bounded, type-aware forward loss surrogate in [0, 1].

    Exact matches return 1.0. Type mismatches or failures return 0.0.
    For integer outputs, relative displacement gives a dense reward.
    For sequences, length and positional agreement provide partial credit.
    This is a search proxy, not a correctness certificate.
    """
    if type(actual) is not type(expected):
        return 0.0
    if actual == expected:
        return 1.0
    if type(expected) is bool:
        return 0.0
    if type(expected) is int:
        return 1.0 / (1.0 + abs(actual - expected))
    if type(expected) is float:
        if not math.isfinite(actual) or not math.isfinite(expected):
            return 0.0
        return 1.0 / (1.0 + abs(actual - expected))
    if type(expected) in (list, tuple, str):
        n, m = len(actual), len(expected)
        if max(n, m) == 0:
            return 0.0
        matched = sum(a == b for a, b in zip(actual, expected))
        return matched / float(max(n, m))
    if type(expected) is dict:
        keys = set(actual) | set(expected)
        if not keys:
            return 0.0
        return sum(k in actual and k in expected and
                   actual[k] == expected[k] for k in keys) / float(len(keys))
    return 0.0


def public_credit(outcomes, expected):
    """Score forward executions on public inputs only, preserving total cost."""
    if len(outcomes) != len(expected) or not expected:
        raise ValueError("credit requires one outcome per public example")
    return sum(output_credit(a, b) if ok else 0.0
               for (ok, a), b in zip(outcomes, expected)) / len(expected)
