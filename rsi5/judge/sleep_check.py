"""Loop 3's sleep check: J keeps or reverts a discrete change to slow knowledge S.

Purpose (F4). The check *prices* discrete sleep changes (a library entry or a
concept added or removed). It is not the mechanism expected to produce gains:
the Owner decided on 2026-10-29 that a guard which only prevents losses
cannot produce a capability leap. Ablation A4 (a placebo revert at the
measured revert rate) measures what it costs, and Gate 3 drops it for
Phase 4 if it does not pay.

Procedure (OWNER_DIRECTIVE.md §5). It runs only when sleep changed S
discretely. J evaluates the learned solver with S before and with S after the
change, on the 60 probe tasks at B_eval = 64, with the same seeds; the runtime
is deterministic, so the comparison has no sampling noise (red-team R3). Per
probe task, solved means solved on at least 2 of 3 seeds; a win is solved
only after the change, a loss solved only before. Revert when
losses - wins >= DELTA_SLEEP (2); otherwise keep.

For reporting only, J also records whether each self can still re-derive the
receipted training tasks, with ``rsi3.continuity.audit`` (ContinuityGuard's
re-derivation check, imported unchanged). It enters no decision.

The probe pool feeds a decision, so no probe number is ever reported as a
result.
"""
from __future__ import annotations

from .registry import B_EVAL, DELTA_SLEEP


def decide(before: dict, after: dict) -> dict:
    names = sorted(set(before) & set(after))
    wins = [n for n in names if after[n] and not before[n]]
    losses = [n for n in names if before[n] and not after[n]]
    revert = len(losses) - len(wins) >= DELTA_SLEEP
    return {"tasks": len(names), "wins": len(wins), "losses": len(losses),
            "win_tasks": wins, "loss_tasks": losses, "delta": DELTA_SLEEP,
            "decision": "revert" if revert else "keep"}


def rederive(runtime, config: dict, label: str) -> dict:
    """Report-only: how many receipted training tasks this self re-derives at B_eval."""
    from rsi3.continuity import audit, snapshot
    from rsi3.integrator import BindingIntegrator
    public = getattr(runtime, "sleep_public", None) or runtime.public
    tasks = {task.name: task for task in public}
    solutions = {name: term for name, term in runtime.state.solutions.items() if name in tasks}
    integrator = BindingIntegrator(list(tasks.values()),
                                   step_budget=config["search"]["step_budget"])
    result = audit(snapshot(runtime.state, label), tasks, solutions, integrator, B_EVAL,
                   config["search"], runtime.state.grammar.library)
    return {"retained": result["count"], "audited": result["audited"],
            "not_retained": sorted(set(solutions) - set(result["retained"]))}
