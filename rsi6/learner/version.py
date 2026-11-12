"""A version of the learner: one bounded record.

A version says which variant of each function the learner uses, with what parameters, and
which composite descriptors it builds. It is a flat mapping from the field names below to
values, nothing else: it has no room for a solution, an instance or an environment's name, and
it is the object that modifications change. Capabilities and memory are not part of it.

Each field belongs to one of the learner's functions (the prefix): ``prior`` and ``model`` to
*model*, ``feat`` to *represent*, ``shortlist`` and ``test`` to *decide*, ``edit`` to
*compose*, ``assess`` to *self-assess*, ``transfer`` to *consolidate*, ``predict`` to the
prediction form of *represent* and *model*. ``explore`` is the sampling inside the model
variants (``model.sigma``, ``test.temperature``).
"""
from __future__ import annotations

import hashlib
import json

TEMPLATES = ("none", "dsoft*progress", "dhard*progress", "dsoft*usage", "last0*progress", "rem0*progress",
             "dsoft*last0", "abs_dsoft")

# name: ("real", low, high, default) or ("choice", options, default)
SCHEMA = {
    "prior.dsoft": ("real", -4.0, 0.0, -1.0),
    "prior.dhard": ("real", -12.0, 0.0, -6.0),
    "feat.per_group": ("choice", (0, 1), 1),
    "feat.usage": ("choice", (0, 1), 1),
    "feat.last": ("choice", (0, 1), 1),
    "feat.rem": ("choice", (0, 1), 1),
    "feat.var_opt": ("choice", (0, 1), 1),
    "feat.opt_attr": ("choice", (0, 1), 1),
    "feat.occ": ("choice", (0, 1), 1),
    "feat.optsum": ("choice", (0, 1), 1),
    "feat.scale": ("choice", ("minmax", "z", "rank"), "minmax"),
    "feat.template1": ("choice", TEMPLATES, "none"),
    "feat.template2": ("choice", TEMPLATES, "none"),
    "shortlist": ("choice", (1, 2, 4, 8), 4),
    "model.variant": ("choice", ("cem", "es"), "cem"),
    "model.pop": ("choice", (8, 16, 32), 16),
    "model.elite": ("real", 0.1, 0.5, 0.25),
    "model.sigma": ("real", 0.2, 2.0, 1.0),
    "model.decay": ("real", 0.7, 1.0, 0.9),
    "model.batch": ("choice", (2, 4, 8), 4),
    "model.keep_best": ("choice", (0, 1), 1),
    "model.lr": ("real", 0.05, 1.0, 0.3),
    "assess.holdback": ("real", 0.1, 0.5, 0.25),
    "assess.strict": ("choice", (0, 1), 1),
    "edit.reassign": ("choice", (0, 1), 1),
    "edit.swap": ("choice", (0, 1), 1),
    "edit.reverse": ("choice", (0, 1), 0),
    "edit.move": ("choice", (0, 1), 0),
    "edit.accept_equal": ("choice", (0, 1), 0),
    "test.sampled": ("choice", (0, 1), 0),
    "test.temperature": ("real", 0.05, 1.0, 0.3),
    "transfer.on": ("choice", (0, 1), 1),
    "transfer.blend": ("real", 0.0, 1.0, 1.0),
    "predict.K": ("choice", (4, 8, 16, 32), 8),
    "predict.ridge": ("real", -3.0, 2.0, 0.0),
    "predict.selfsup": ("choice", (0, 1), 0),
    "predict.diff": ("choice", (0, 1), 0),
    "predict.attrs": ("choice", (0, 1), 1),
}
FIELDS = tuple(SCHEMA)
FUNCTION_OF = {"prior": "model", "model": "model", "feat": "represent", "shortlist": "decide", "test": "decide",
               "edit": "compose", "assess": "self-assess", "transfer": "consolidate", "predict": "represent/model"}


def default() -> dict:
    """The learner at generation 0: the simplest working form of every function."""
    return {name: spec[-1] for name, spec in SCHEMA.items()}


def validate(version: dict) -> dict:
    """The version, checked against the schema (unknown or missing fields are errors)."""
    if set(version) != set(SCHEMA):
        raise ValueError(f"version fields differ from the schema: {sorted(set(version) ^ set(SCHEMA))}")
    out = {}
    for name, spec in SCHEMA.items():
        value = version[name]
        if spec[0] == "real":
            value = float(value)
            if not spec[1] <= value <= spec[2]:
                raise ValueError(f"{name}={value} outside [{spec[1]}, {spec[2]}]")
        elif value not in spec[1]:
            raise ValueError(f"{name}={value!r} not one of {spec[1]}")
        out[name] = value
    return out


def digest(version: dict) -> str:
    text = json.dumps(validate(version), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    """Fields in which two versions differ, with the function each belongs to."""
    return {name: {"from": a[name], "to": b[name], "function": FUNCTION_OF[name.split(".")[0]]}
            for name in FIELDS if a[name] != b[name]}
