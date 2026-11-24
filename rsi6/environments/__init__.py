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
    "partitioning": ("rsi6.environments.partitioning", "Partitioning"),
    "setcover": ("rsi6.environments.setcover", "SetCover"),
    "satisfiability": ("rsi6.environments.satisfiability", "Satisfiability"),
    "routing": ("rsi6.environments.routing", "Routing"),
    "facility": ("rsi6.environments.facility", "Facility"),
    "tour": ("rsi6.environments.tour", "Tour"),
    "colouring": ("rsi6.environments.colouring", "Colouring"),
    "genassign": ("rsi6.environments.genassign", "GenAssign"),
}
_CACHE = {}


def load(name: str):
    if name not in _CACHE:
        module, cls = REGISTRY[name]
        _CACHE[name] = getattr(importlib.import_module(module), cls)()
    return _CACHE[name]
