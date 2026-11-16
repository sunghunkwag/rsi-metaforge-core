"""Rule adoption for loop 4: select on one pool, confirm on another (OWNER_DIRECTIVE.md §5).

The best of several candidates looks better than it is, so selection and
confirmation use different tasks.

1. **Selection.** The candidates and the incumbent run the round's 100
   selection tasks. The candidate with the most solves moves on (ties go to
   the earlier candidate). If none has more solves than the incumbent, the
   round ends without a confirmation test.
2. **Confirmation.** The selected candidate and the incumbent run the round's
   200 confirmation tasks. Each task is one pair (incumbent solved, candidate
   solved), solved meaning solved on at least 2 of the 3 seeds. J adopts the
   candidate only if all three hold: every pair was evaluated; an exact
   one-sided sign test on the discordant pairs gives p <= 0.05; at most 5
   losses (the regression budget).
3. **Burn.** The confirmation tasks are marked used and never drawn again.

This re-implements the test of the EGRL prototype's
``promote_only_on_paired_evidence`` with one task as one canary pair; the
prototype is not imported.

The rule bounds below are J's own copy of the directive's table. J rejects any
candidate outside them. ``rsi4/rules.py`` (the proposer) keeps its own copy,
and a test checks the two agree.
"""
from __future__ import annotations

from math import comb

from .registry import ALPHA, FINAL_MAX_LOSSES, REGRESSION_BUDGET, SOLVED_MIN_SEEDS

# name -> ("real", low, high) | ("int", low, high) | ("choice", values)
RULE_BOUNDS = {
    "C.threshold": ("real", 0.5, 3.0),
    "C.floor_chunks": ("int", 0, 3),
    "meta.chunk": ("choice", (8, 16, 32)),
    "controller.exploration": ("real", 0.1, 0.6),
    "meta.selfplay": ("choice", (128, 256, 512)),
    "invention.concept_weight": ("real", 0.05, 0.3),
    "dreams": ("choice", (8, 16, 32)),
    "G.offer_min_solves": ("choice", (1, 2, 3)),
}
DEFAULT_RULES = {
    "C.threshold": 1.5, "C.floor_chunks": 1, "meta.chunk": 16,
    "controller.exploration": 0.3, "meta.selfplay": 256,
    "invention.concept_weight": 0.1, "dreams": 16, "G.offer_min_solves": 1,
}
# Held-out-time rules change only how the learned solver spends B_eval; every
# other rule needs a retrain. meta.chunk is held-out time because
# rsi3.longrun.agent_validation reads it.
HELD_OUT_RULES = ("C.threshold", "C.floor_chunks", "meta.chunk")
TRAINING_RULES = tuple(k for k in RULE_BOUNDS if k not in HELD_OUT_RULES)


def out_of_bounds(rules: dict) -> list[str]:
    """Why a rule vector is outside the registered bounds; [] when inside."""
    problems = []
    for key in sorted(set(rules) - set(RULE_BOUNDS)):
        problems.append(f"{key}: not a registered rule")
    for key, spec in RULE_BOUNDS.items():
        if key not in rules:
            problems.append(f"{key}: missing")
            continue
        value = rules[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"{key}: {value!r} is not a number")
        elif spec[0] == "choice":
            if value not in spec[1]:
                problems.append(f"{key}: {value!r} not in {spec[1]}")
        elif spec[0] == "int" and (int(value) != value or not spec[1] <= value <= spec[2]):
            problems.append(f"{key}: {value!r} not an integer in [{spec[1]}, {spec[2]}]")
        elif spec[0] == "real" and not spec[1] <= value <= spec[2]:
            problems.append(f"{key}: {value!r} not in [{spec[1]}, {spec[2]}]")
    return problems


# ---- statistics ----------------------------------------------------------------
def sign_test(wins: int, losses: int) -> float:
    """Exact one-sided sign test: P(X >= wins) for X ~ Binomial(wins + losses, 1/2)."""
    n = int(wins) + int(losses)
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(int(wins), n + 1)) / 2 ** n


def holm(p_values: list[float], alpha: float = ALPHA) -> list[bool]:
    """Holm's step-down rejections, in the input order."""
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    reject = [False] * len(p_values)
    m = len(p_values)
    for rank, i in enumerate(order):
        if p_values[i] <= alpha / (m - rank):
            reject[i] = True
        else:
            break
    return reject


def pooled(per_seed: dict, names: list[str]) -> dict:
    """name -> solved on at least SOLVED_MIN_SEEDS seeds (F7)."""
    return {name: sum(bool(per_seed[s].get(name)) for s in per_seed) >= SOLVED_MIN_SEEDS
            for name in names}


def pairs(baseline: dict, candidate: dict) -> dict:
    """Paired outcomes over the tasks both evaluated."""
    names = sorted(set(baseline) & set(candidate))
    wins = [n for n in names if candidate[n] and not baseline[n]]
    losses = [n for n in names if baseline[n] and not candidate[n]]
    return {"tasks": len(names), "wins": len(wins), "losses": len(losses),
            "both": sum(1 for n in names if candidate[n] and baseline[n]),
            "neither": sum(1 for n in names if not candidate[n] and not baseline[n]),
            "win_tasks": wins, "loss_tasks": losses,
            "p": sign_test(len(wins), len(losses))}


# ---- decisions -------------------------------------------------------------------
def decide_select(incumbent_solves: int, candidate_solves: list[tuple[str, int]]) -> dict:
    """The candidate with the most solves, if it beats the incumbent; ties go to the earlier one."""
    best_id, best = None, None
    for cid, solves in candidate_solves:
        if best is None or solves > best:
            best_id, best = cid, solves
    selected = best_id if best is not None and best > incumbent_solves else None
    return {"incumbent_solves": incumbent_solves, "candidate_solves": dict(candidate_solves),
            "best": best_id, "best_solves": best, "selected": selected}


def decide_confirm(paired: dict, expected_tasks: int) -> dict:
    complete = paired["tasks"] == expected_tasks
    significant = paired["p"] <= ALPHA
    within_budget = paired["losses"] <= REGRESSION_BUDGET
    return {"complete": complete, "significant": significant, "within_budget": within_budget,
            "adopt": bool(complete and significant and within_budget)}


def decide_final(paired: dict, expected_tasks: int) -> dict:
    complete = paired["tasks"] == expected_tasks
    significant = paired["p"] <= ALPHA
    within_budget = paired["losses"] <= FINAL_MAX_LOSSES
    return {"complete": complete, "significant": significant, "within_budget": within_budget,
            "pass": bool(complete and significant and within_budget)}
