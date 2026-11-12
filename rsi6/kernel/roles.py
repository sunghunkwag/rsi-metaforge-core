"""Roles of the environment categories, and the lock that enforces them.

One seeded draw assigns every candidate category to one role. The seed is the SHA-256 of a
fixed phrase and of a commit that was already public when the draw was made, so the roles could
not be chosen.

* ``source``: the learner may be developed and modified using these.
* ``adoption:g``: read by the gate of round g only, and by nothing before it. After round g
  the pair joins the source pool.
* ``target``: untouched until every version and every budget is frozen; their data are not
  fetched and their adapters are not written before that.
* ``reserve``: replaces a target or an adoption category whose adapter cannot be built or
  fails its audit.

The lock: a learner run on a category is refused unless a record in the ledger unlocks its
role. ``source`` is unlocked from the start.
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry", "roles.json")

CANDIDATES = ("binpacking", "colouring", "facility", "flowshop", "forecasting", "genassign", "jobshop", "knapsack",
              "partitioning", "pmedian", "quadassign", "regression", "routing", "satisfiability", "setcover", "tour")
PHRASE = "rsi6 roles"
N_SOURCE, N_ROUNDS, PER_ROUND, N_TARGET = 3, 3, 2, 4


def draw(commit: str) -> dict:
    order = sorted(CANDIDATES, key=lambda c: hashlib.sha256(f"{PHRASE}|{commit}|{c}".encode()).hexdigest())
    roles, k = {}, 0
    for c in order[k:k + N_SOURCE]:
        roles[c] = "source"
    k += N_SOURCE
    for g in range(1, N_ROUNDS + 1):
        for c in order[k:k + PER_ROUND]:
            roles[c] = f"adoption:{g}"
        k += PER_ROUND
    for c in order[k:k + N_TARGET]:
        roles[c] = "target"
    k += N_TARGET
    for c in order[k:]:
        roles[c] = "reserve"
    return {"phrase": PHRASE, "commit": commit, "order": order, "roles": roles}


def load() -> dict:
    return json.load(open(REGISTRY))


def role_of(category: str) -> str:
    return load()["roles"][category]


def unlocked(ledger) -> set:
    out = {"source"}
    for record in ledger.records:
        if record.get("type") == "unlock":
            out.add(record["role"])
        if record.get("type") == "replace":          # a reserve takes over a role
            out.discard(None)
    return out


def effective_role(category: str, ledger) -> str:
    """The role of a category, after any recorded replacement by a reserve and after adoption
    categories of finished rounds have joined the source pool."""
    role = role_of(category)
    for record in ledger.records:
        if record.get("type") == "replace" and record["reserve"] == category:
            role = record["role"]
        if record.get("type") == "replace" and record["replaced"] == category:
            role = "dropped"
        if record.get("type") == "reassign" and record["category"] == category:
            role = record["role"]                    # an amendment gave a reserve another role (recorded before any use)
        if record.get("type") == "release" and role == record["role"]:
            role = "source"
    return role


def check(category: str, ledger) -> str:
    role = effective_role(category, ledger)
    if role not in unlocked(ledger):
        raise PermissionError(f"category {category!r} has role {role!r}, which is locked")
    return role
