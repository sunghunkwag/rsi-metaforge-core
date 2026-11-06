"""J's service: one request in, one deterministic response out, every decision logged.

    python -m rsi4.judge --request REQUEST.json --response RESPONSE.json

Agent code never imports this package. ``rsi4/client.py`` starts it in a
fresh process (``multiprocessing``, spawn start method) with a request file
and reads the response file. J copies and hashes the checkpoints it is sent,
loads the hidden examples itself, and decides every count.

Operations (``op``) and the pools each may read:

| op | reads | ledger |
| --- | --- | --- |
| ``run_start`` | nothing; hashes ``rsi4/judge/**`` and the registered config, audits the agent code | run |
| ``run_end`` | nothing; re-hashes and compares with ``run_start``; a mismatch voids the run | run |
| ``evaluate`` | ``stage_eval_S1..S3``; report-only: ``exposed:<partition>``, ``report:train``, ``report:stage_train_S<k>`` | run |
| ``sleep_check`` | ``probe`` (two checkpoints, before and after a sleep change) | run |
| ``select`` | ``selection_r<k>``, once per round | canonical |
| ``confirm`` | ``confirmation_r<k>``, once, only for round k's selected candidate; then burned | canonical |
| ``final_test`` | ``final_test_2`` and ``final_test_3``, once | canonical |
| ``compare`` | J's own logged evaluations; exact sign tests with Holm correction | canonical |
| ``metrics`` | J's own logged stage-eval evaluations; ACC, BWT, FGT, FWT with bootstrap CIs | canonical |

Any other use of a pool is refused, and the refusal is logged. Every
operation first checks J's files against ``MANIFEST.sha256`` and refuses if
they differ. A response holds only deterministic content: the same
checkpoint and request give byte-identical responses (red-team R3). J's own
CPU time goes to ``judge_costs.jsonl`` beside the ledger, outside every
budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from . import adopt, ledger, metrics, pools, sleep_check
from .audit import problems as audit_problems
from .evaluate import EvaluationError, evaluate_checkpoint, read_only_copy, summary
from .registry import (EVAL_SEEDS, JUDGE_DIR, PACKAGE_DIR, canonical, file_sha256,
                       tree_digest, verify_manifest)


class Refused(RuntimeError):
    """J declines the request; the reason is logged."""


# ---- helpers ------------------------------------------------------------------------
def _config(request: dict) -> tuple[dict, str]:
    path = Path(request["config"])
    return json.loads(path.read_text(encoding="utf-8")), file_sha256(path)


def _run_ledger(request: dict) -> Path:
    return Path(request["run_dir"]) / "judge_log.jsonl"


def _arm(spec: dict, config: dict, pool: str, judge_dir: Path, solvers) -> dict:
    """Evaluate one solver specification {checkpoint, solver, rules} on a pool."""
    return evaluate_checkpoint(Path(spec["checkpoint"]), pool, config, judge_dir=judge_dir,
                               solver=spec.get("solver", "rsi3"), rules=spec.get("rules"),
                               solvers=solvers)


def _check_rules(spec: dict) -> None:
    rules = spec.get("rules")
    if rules is None:
        return
    bad = adopt.out_of_bounds(rules)
    if bad:
        raise Refused(f"rules outside the registered bounds: {bad}")


def _trained_rules_match(spec: dict) -> None:
    """A training-time candidate's checkpoint must carry the rules it declares."""
    rules = spec.get("rules")
    if rules is None:
        return
    import pickle
    blob, _ = read_only_copy(Path(spec["checkpoint"]))
    trained = pickle.loads(blob).get("rules")
    if trained is None:
        return
    differ = [k for k in adopt.TRAINING_RULES if trained.get(k) != rules.get(k)]
    if differ:
        raise Refused(f"checkpoint was trained with other values of {differ}")


def _pooled_union(results: list[dict]) -> dict:
    merged = {}
    for result in results:
        for name, solved in result["pooled"]["tasks"].items():
            merged[f"{result['pool']}/{name}"] = solved
    return merged


def _logged_evaluation(ref) -> dict:
    path, index = ref
    entry = ledger.entry_at(Path(path), int(index))
    if entry.get("op") != "evaluate" or not entry.get("result", {}).get("complete"):
        raise Refused(f"{path}#{index} is not a complete J evaluation")
    return entry


# ---- operations -------------------------------------------------------------------------
def op_run_start(request, judge_dir, canonical_ledger, solvers):
    config, config_hash = _config(request)
    found = audit_problems(Path(judge_dir).parent)
    result = {"run_id": request["run_id"], "judge_tree": tree_digest(judge_dir),
              "config": str(request["config"]), "config_sha256": config_hash,
              "audit": found or "pass"}
    if found:
        raise Refused(f"agent code fails the sealing audit: {found}")
    return result, _run_ledger(request)


def op_run_end(request, judge_dir, canonical_ledger, solvers):
    path = _run_ledger(request)
    starts = [e for e in ledger.entries(path, "run_start")
              if e["result"]["run_id"] == request["run_id"]]
    if not starts:
        raise Refused(f"no run_start for {request['run_id']!r}")
    start = starts[-1]["result"]
    reasons = []
    if tree_digest(judge_dir) != start["judge_tree"]:
        reasons.append("rsi4/judge/** changed during the run")
    if file_sha256(Path(start["config"])) != start["config_sha256"]:
        reasons.append("the registered config changed during the run")
    return {"run_id": request["run_id"], "valid": not reasons, "void_reasons": reasons}, path


def op_evaluate(request, judge_dir, canonical_ledger, solvers):
    pool = request["pool"]
    report_only = pool.startswith(("exposed:", "report:"))
    if not report_only and pools.use_of(pool) != "evaluate":
        raise Refused(f"pool {pool!r} is not read by evaluate")
    config, config_hash = _config(request)
    _check_rules(request)
    result = _arm(request, config, pool, judge_dir, solvers)
    result["label"] = request.get("label")
    result["report_only"] = report_only
    result["config_sha256"] = config_hash
    return result, _run_ledger(request)


def op_sleep_check(request, judge_dir, canonical_ledger, solvers):
    import pickle
    config, config_hash = _config(request)
    _check_rules(request)
    spec = {"solver": request.get("solver", "rsi3"), "rules": request.get("rules")}
    before = _arm(dict(spec, checkpoint=request["before"]), config, "probe", judge_dir, solvers)
    after = _arm(dict(spec, checkpoint=request["after"]), config, "probe", judge_dir, solvers)
    decision = sleep_check.decide(before["pooled"]["tasks"], after["pooled"]["tasks"])
    rederive = {}
    for label, key in (("before", "before"), ("after", "after")):
        blob, _ = read_only_copy(Path(request[key]))
        rederive[label] = sleep_check.rederive(pickle.loads(blob)["runtime"], config, label)
    result = {"generation": request.get("generation"), "change": request.get("change"),
              "config_sha256": config_hash, "before": summary(before), "after": summary(after),
              "rederive_report_only": rederive, **decision}
    return result, _run_ledger(request)


def _round_pools(round_: int) -> tuple[str, str]:
    if round_ not in range(1, 4):
        raise Refused(f"no round {round_}")
    return f"selection_r{round_}", f"confirmation_r{round_}"


def op_select(request, judge_dir, canonical_ledger, solvers):
    round_ = int(request["round"])
    selection, confirmation = _round_pools(round_)
    done = ledger.entries(canonical_ledger)
    if any(e.get("op") == "select" and e["result"]["round"] == round_ for e in done):
        raise Refused(f"{selection} was already used")
    if any(e.get("op") == "burn" and e["result"]["pool"] == confirmation for e in done):
        raise Refused(f"round {round_} is closed")
    config, config_hash = _config(request)
    incumbent = request["incumbent"]
    candidates, rejected = [], {}
    for spec in request["candidates"]:
        try:
            _check_rules(spec)
            _trained_rules_match(spec)
            candidates.append(spec)
        except Refused as reason:
            rejected[spec["id"]] = str(reason)
    inc = _arm(incumbent, config, selection, judge_dir, solvers)
    evaluated = {spec["id"]: _arm(spec, config, selection, judge_dir, solvers)
                 for spec in candidates}
    decision = adopt.decide_select(inc["pooled"]["solved"],
                                   [(cid, r["pooled"]["solved"]) for cid, r in evaluated.items()])
    selected = next((s for s in candidates if s["id"] == decision["selected"]), None)
    result = {"round": round_, "pool": selection, "config_sha256": config_hash,
              "candidate_order": [spec["id"] for spec in candidates],
              "incumbent": summary(inc), "candidates": {c: summary(r) for c, r in evaluated.items()},
              "rejected": rejected, "selected_spec": selected,
              "selected_checkpoint_sha256": (evaluated[selected["id"]]["checkpoint_sha256"]
                                             if selected else None),
              **decision}
    return result, canonical_ledger


def op_confirm(request, judge_dir, canonical_ledger, solvers):
    round_ = int(request["round"])
    _, confirmation = _round_pools(round_)
    done = ledger.entries(canonical_ledger)
    if any(e.get("op") == "burn" and e["result"]["pool"] == confirmation for e in done):
        raise Refused(f"{confirmation} is burned")
    picks = [e["result"] for e in done if e.get("op") == "select"
             and e["result"]["round"] == round_]
    candidate, incumbent = request["candidate"], request["incumbent"]
    if not picks or picks[-1]["selected"] != candidate.get("id"):
        raise Refused(f"round {round_} selected no candidate {candidate.get('id')!r}")
    pick = picks[-1]
    _, digest = read_only_copy(Path(candidate["checkpoint"]))
    if digest != pick["selected_checkpoint_sha256"] or \
            candidate.get("rules") != pick["selected_spec"].get("rules"):
        raise Refused("the candidate differs from the one selected")
    _check_rules(candidate)
    config, config_hash = _config(request)
    inc = _arm(incumbent, config, confirmation, judge_dir, solvers)
    cand = _arm(candidate, config, confirmation, judge_dir, solvers)
    paired = adopt.pairs(inc["pooled"]["tasks"], cand["pooled"]["tasks"])
    complete = inc["complete"] and cand["complete"]
    decision = adopt.decide_confirm(paired, len(pools.load_records(confirmation, judge_dir))
                                    if complete else -1)
    result = {"round": round_, "pool": confirmation, "config_sha256": config_hash,
              "candidate_id": candidate["id"], "incumbent": summary(inc),
              "candidate": summary(cand), "pairs": paired, **decision}
    return result, canonical_ledger


def op_final_test(request, judge_dir, canonical_ledger, solvers):
    if any(e.get("op") == "final_test" for e in ledger.entries(canonical_ledger)):
        raise Refused("the final test was already run")
    config, config_hash = _config(request)
    star, base = request["theta_star"], request["theta_0"]
    _check_rules(star)
    _check_rules(base)
    parts = {}
    for pool in ("final_test_2", "final_test_3"):
        parts[pool] = {"theta_0": _arm(base, config, pool, judge_dir, solvers),
                       "theta_star": _arm(star, config, pool, judge_dir, solvers)}
    b = _pooled_union([parts[p]["theta_0"] for p in parts])
    s = _pooled_union([parts[p]["theta_star"] for p in parts])
    paired = adopt.pairs(b, s)
    complete = all(parts[p][k]["complete"] for p in parts for k in parts[p])
    expected = sum(len(pools.load_records(p, judge_dir)) for p in parts)
    decision = adopt.decide_final(paired, expected if complete else -1)
    result = {"config_sha256": config_hash, "pairs": paired, **decision,
              "parts": {p: {k: summary(v) for k, v in parts[p].items()} for p in parts}}
    return result, canonical_ledger


def op_compare(request, judge_dir, canonical_ledger, solvers):
    """A family of paired comparisons over J's logged evaluations, Holm-corrected."""
    rows = []
    for comparison in request["family"]:
        cand = [_logged_evaluation(ref)["result"] for ref in comparison["candidate"]]
        base = [_logged_evaluation(ref)["result"] for ref in comparison["baseline"]]
        if sorted(r["pool"] for r in cand) != sorted(r["pool"] for r in base):
            raise Refused(f"{comparison['name']}: the two sides cover different pools")
        rows.append({"name": comparison["name"], "candidate_refs": comparison["candidate"],
                     "baseline_refs": comparison["baseline"],
                     "pairs": adopt.pairs(_pooled_union(base), _pooled_union(cand))})
    rejected = adopt.holm([row["pairs"]["p"] for row in rows])
    for row, reject in zip(rows, rejected):
        row["holm_reject_null"] = reject
    return {"label": request.get("label"), "comparisons": rows,
            "direction": "candidate > baseline", "alpha": adopt.ALPHA}, canonical_ledger


def op_metrics(request, judge_dir, canonical_ledger, solvers):
    outcomes = {}
    for key, ref in request["R"].items():
        i, j = (int(x) for x in key.split(","))
        result = _logged_evaluation(ref)["result"]
        if result["pool"] != f"stage_eval_S{j}":
            raise Refused(f"R[{i}][{j}] must be an evaluation of stage_eval_S{j}")
        outcomes[(i, j)] = result["pooled"]["tasks"]
    return {"label": request.get("label"), "refs": request["R"],
            **metrics.compute(outcomes)}, canonical_ledger


OPERATIONS = {"run_start": op_run_start, "run_end": op_run_end, "evaluate": op_evaluate,
              "sleep_check": op_sleep_check, "select": op_select, "confirm": op_confirm,
              "final_test": op_final_test, "compare": op_compare, "metrics": op_metrics}
CANONICAL_OPS = {"select", "confirm", "final_test", "compare", "metrics"}


def handle(request: dict, *, judge_dir: Path = JUDGE_DIR,
           canonical_ledger: Path = ledger.CANONICAL_LEDGER, solvers: dict | None = None) -> dict:
    """Serve one request. ``judge_dir``, ``canonical_ledger`` and ``solvers`` are test hooks."""
    op = request.get("op")
    started = time.process_time()
    target = Path(canonical_ledger) if op in CANONICAL_OPS else (
        _run_ledger(request) if "run_dir" in request else Path(canonical_ledger))
    try:
        if op not in OPERATIONS:
            raise Refused(f"unknown op {op!r}")
        changed = verify_manifest(judge_dir)
        if changed:
            raise Refused(f"J's files differ from MANIFEST.sha256: {changed}")
        result, target = OPERATIONS[op](request, Path(judge_dir), Path(canonical_ledger),
                                        solvers)
        response = {"ok": True, "op": op, "result": result}
    except (Refused, EvaluationError, KeyError, ValueError, ledger.LedgerError) as reason:
        response = {"ok": False, "op": op, "refused": f"{type(reason).__name__}: {reason}"}
    except Exception as crash:          # a crash is logged, never silently retried
        response = {"ok": False, "op": op, "error": f"{type(crash).__name__}: {crash}"}
    digest = hashlib.sha256(canonical(response)).hexdigest()
    status = op if response["ok"] else ("error" if "error" in response else "refused")
    entry = {"op": status, "request_op": op, "response_sha256": digest,
             "result": _ledger_view(op, response.get("result")) if response["ok"] else None,
             "refused": response.get("refused") or response.get("error")}
    ledger.append(target, entry)
    if op == "confirm" and response["ok"]:
        ledger.append(target, {"op": "burn", "request_op": op, "response_sha256": digest,
                               "result": {"pool": response["result"]["pool"],
                                          "round": response["result"]["round"]},
                               "refused": None})
    ledger.cost(target, {"op": op, "response_sha256": digest,
                         "cpu_seconds": round(time.process_time() - started, 3)})
    return response


def _ledger_view(op: str, result: dict | None) -> dict | None:
    """What the ledger keeps: everything except the solvers' raw records."""
    if result is None or op != "evaluate":
        return result
    return dict(summary(result), label=result.get("label"),
                report_only=result.get("report_only"), config_sha256=result.get("config_sha256"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    response = handle(request)
    args.response.write_bytes(canonical(response) + b"\n")


if __name__ == "__main__":
    main()


__all__ = ["handle", "main", "OPERATIONS", "PACKAGE_DIR", "EVAL_SEEDS"]
