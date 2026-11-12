"""Adapters of the external environments. The registry maps a category to its adapter."""
from __future__ import annotations

import importlib

REGISTRY = {
    "jobshop": ("rsi6.environments.jobshop", "JobShop"),
    "binpacking": ("rsi6.environments.binpacking", "BinPacking"),
    "forecasting": ("rsi6.environments.forecasting", "Forecasting"),
    "quadassign": ("rsi6.environments.quadassign", "QuadAssign"),
    "pmedian": ("rsi6.environments.pmedian", "PMedian"),
    "knapsack": ("rsi6.environments.knapsack", "Knapsack"),
    "regression": ("rsi6.environments.regression", "Regression"),
}
_CACHE = {}


def load(name: str):
    if name not in _CACHE:
        module, cls = REGISTRY[name]
        _CACHE[name] = getattr(importlib.import_module(module), cls)()
    return _CACHE[name]
