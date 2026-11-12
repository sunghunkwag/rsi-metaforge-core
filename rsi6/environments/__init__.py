"""Adapters of the external environments. The registry maps a category to its adapter."""
from __future__ import annotations

import importlib

REGISTRY = {
    "jobshop": ("rsi6.environments.jobshop", "JobShop"),
    "binpacking": ("rsi6.environments.binpacking", "BinPacking"),
    "forecasting": ("rsi6.environments.forecasting", "Forecasting"),
}
_CACHE = {}


def load(name: str):
    if name not in _CACHE:
        module, cls = REGISTRY[name]
        _CACHE[name] = getattr(importlib.import_module(module), cls)()
    return _CACHE[name]
