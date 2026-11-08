#!/usr/bin/env python3
"""Bounded audit of the immutable 2026-06-13 MetaForge root commit.

Read historical source through git-show; never alter it or sealed TEST/J pools.
Compare baseline, uniform-weight null, and weighted proposals on a synthetic
length task with paired random seeds and a fixed mutation-iteration allowance.
Executed candidate evaluations and CPU are separately reported, not assumed equal.
"""
from __future__ import annotations

import argparse
import ast
import json
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

ROOT_SHA = "3cfc329eca17a08e1a1565064b61a5bd4a1dd520"
PATH = "rsi_levels_metaforge_unified.py"


def load_initial_module(repo: Path):
    source = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{ROOT_SHA}:{PATH}"], text=True
    )
    # Entire historical kernel up to the first test suite; all definitions
    # complete, no integrated later sections or CLI side effects.
    prefix = "\n".join(source.splitlines()[:2288]) + "\n"
    mod = types.ModuleType("_metaforge_first_commit_probe")
    mod.__file__ = f"{ROOT_SHA}:{PATH}"
    sys.modules[mod.__name__] = mod
    exec(compile(prefix, mod.__file__, "exec"), mod.__dict__)
    return source, mod


def static_contract(source: str) -> dict:
    tree = ast.parse(source, filename=f"{ROOT_SHA}:{PATH}")
    functions = {
        n.name: n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in ("build_enum_table", "meta_gate", "synthesize", "_sample_token"):
        assert name in functions, f"missing original function: {name}"
    enum_attrs = {
        n.attr for n in ast.walk(functions["build_enum_table"])
        if isinstance(n, ast.Attribute)
    }
    sampler_attrs = {
        n.attr for n in ast.walk(functions["_sample_token"])
        if isinstance(n, ast.Attribute)
    }
    assert "weight" in sampler_attrs
    assert "weights" not in enum_attrs and "weight" not in enum_attrs
    return {
        "root_sha": ROOT_SHA,
        "root_lines": len(source.splitlines()),
        "top_level_functions": len(functions),
        "enum_reads_proposal_weights": False,
        "sampler_reads_proposal_weights": True,
    }


def weight_settings(mod):
    baseline = mod.SearcherState()
    uniform = baseline.clone()
    uniform.weights = {t: 1.0 for t in uniform.vocab()}
    weighted = baseline.clone()
    weighted.weights = {
        t: (6.0 if t in (4, 16) else 0.25) for t in weighted.vocab()
    }
    return baseline, uniform, weighted


def measure_search(mod, arms, seeds: int, iterations: int):
    pairs = tuple((xs, len(xs)) for xs in mod.TRAIN_INPUTS)
    shift_inputs = [
        tuple((i * 3 + j) % 19 for i in range(length))
        for j in range(5) for length in (5, 8, 13, 21, 34)
    ]
    results = {name: [] for name in arms}
    start = time.perf_counter()
    for seed in range(seeds):
        for name, state in arms.items():
            result = mod.synthesize(
                pairs, "synthetic_length", state, seed,
                restarts=1, iters=iterations, drift_rate=0.0
            )
            shift_ok = False
            if result.solved:
                try:
                    program = mod.expand_tokens(result.tokens, state.macros)
                    shift_ok = all(
                        mod.run_base_program(program, xs) == len(xs)
                        for xs in shift_inputs
                    )
                except mod.VMCrash:
                    shift_ok = False
            results[name].append({
                "seed": seed,
                "train_solved": bool(result.solved),
                "shift_passed": bool(shift_ok),
                "evals": int(result.evals_used),
                "tokens": list(result.tokens),
                "best_score": float(result.best_score),
            })
    assert results["baseline"] == results["uniform_null"], "RNG/null mismatch"
    summary = {}
    for name, rows in results.items():
        summary[name] = {
            "train_solved": sum(row["train_solved"] for row in rows),
            "shift_passed": sum(row["shift_passed"] for row in rows),
            "median_evals": statistics.median(row["evals"] for row in rows),
            "mean_evals": sum(row["evals"] for row in rows) / len(rows),
        }
    return {
        "seeds": seeds,
        "mutation_iterations_per_seed_arm": iterations,
        "restarts_per_seed_arm": 1,
        "train_examples": len(pairs),
        "independent_shift_examples": len(shift_inputs),
        "summary": summary,
        "elapsed_wall_seconds": round(time.perf_counter() - start, 4),
        "paired_details": results,
        "limitation": "Same mutation-iteration allowance, NOT necessarily equal executed candidate evaluations or CPU",
    }


def test_original_gate(mod, weighted):
    # The gate itself is from the original commit; only caps are lowered.
    mod.ENUM_SURFACE_MAX = 2
    mod.ENUM_CLASS_CAP = 160
    rs = mod.RunState(adaptive=True)
    rs.screen_cap = 160
    rs.tasks = [mod.SealedTask(
        tid="synthetic_unreachable_probe", family="synthetic",
        train_pairs=(((1,), 987654321),),
        holdout_gate=lambda _fn: True, cf_gate=lambda _fn: True,
    )]
    rs.work_table = mod.build_enum_table(
        rs.searcher, surface_max=mod.ENUM_SURFACE_MAX,
        class_cap=mod.ENUM_CLASS_CAP,
    )
    incumbent_digest = rs.searcher.digest()
    proposal = mod.ImprovementProposal(
        wave=0, new_macros=[], new_weights=dict(weighted.weights),
        note="weight-only counterfactual (not a production proposal)",
    )
    accepted = mod.meta_gate(rs, proposal, wave=0)
    assert accepted is False, "unexpected adoption by weight-only gate"
    assert rs.searcher.digest() == incumbent_digest
    assert len(rs.gate_records) == 2
    return {
        "accepted": accepted,
        "gate_records": [
            {
                "accepted": row.accepted,
                "inc_solved": row.inc_solved,
                "cand_solved": row.cand_solved,
                "inc_extensions": row.inc_extensions,
                "cand_extensions": row.cand_extensions,
                "note": row.note,
            }
            for row in rs.gate_records
        ],
        "incumbent_digest_unchanged": rs.searcher.digest() == incumbent_digest,
        "original_enum_classes": rs.work_table.classes_per_len,
    }




def namespace_shadow_audit(source: str) -> dict:
    """Find globals redefined in the originally shipped monolithic file."""
    tree = ast.parse(source)
    defs = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.setdefault(node.name, []).append(node.lineno)
    duplicated = {k: v for k, v in defs.items() if len(v) > 1}
    critical = {
        k: defs.get(k, []) for k in
        ("synthesize", "run_system", "compile_program", "mine_macros",
         "run_tests", "main", "meta_gate")
    }
    # The final CLI calls run_system(adaptive=...), while the final bound
    # run_system declaration does not accept adaptive or arbitrary keywords.
    final_system = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_system"
    ][-1]
    params = [p.arg for p in final_system.args.args]
    last_main = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ][-1]
    adaptive_call = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_system"
        and any(kw.arg == "adaptive" for kw in node.keywords)
        for node in ast.walk(last_main)
    )
    return {
        "duplicate_top_level_names": len(duplicated),
        "critical_definitions_by_line": critical,
        "final_run_system_parameters": params,
        "final_run_system_accepts_kwargs": final_system.args.kwarg is not None,
        "final_cli_requests_adaptive": adaptive_call,
        "cli_signature_incompatibility": (
            adaptive_call and "adaptive" not in params
            and final_system.args.kwarg is None
        ),
        "scope": "static audit of full historical 33k-line module",
    }


def historical_cli_probe(source: str) -> dict:
    """Check the shipped historical CLI without modifying the archive."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="metaforge-root-probe-") as tmp:
        script = Path(tmp) / PATH
        script.write_text(source)
        try:
            finished = subprocess.run(
                [sys.executable, str(script), "--mode", "run-adaptive"],
                cwd=tmp, capture_output=True, text=True, timeout=15,
                check=False,
            )
            return {
                "exit_code": finished.returncode,
                "stderr_tail": finished.stderr.splitlines()[-8:],
                "stdout_tail": finished.stdout.splitlines()[-5:],
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": None, "timeout": True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument(
        "--out", type=Path, default=Path("initial_weight_gate_results.json")
    )
    parser.add_argument("--seeds", type=int, default=32)
    parser.add_argument("--iterations", type=int, default=120)
    args = parser.parse_args()
    assert 1 <= args.seeds <= 100 and 1 <= args.iterations <= 2000
    source, mod = load_initial_module(args.repo)
    contract = static_contract(source)
    baseline, uniform, weighted = weight_settings(mod)
    search = measure_search(
        mod, {
            "baseline": baseline,
            "uniform_null": uniform,
            "weighted": weighted,
        }, args.seeds, args.iterations,
    )
    gate = test_original_gate(mod, weighted)
    namespace = namespace_shadow_audit(source)
    cli_probe = historical_cli_probe(source)
    payload = {
        "design": "exploratory synthetic length task; historical root source; no sealed evaluation",
        "source": f"https://github.com/sunghunkwag/rsi-metaforge-core/commit/{ROOT_SHA}",
        "static": contract,
        "search": search,
        "gate": gate,
        "namespace": namespace,
        "historical_cli": cli_probe,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "static": contract,
        "search": search["summary"],
        "gate": gate,
        "namespace": namespace,
        "historical_cli": cli_probe,
        "result_file": str(args.out),
    }, indent=2, sort_keys=True))
    print(
        "PASS root static contract; baseline==null; paired search; "
        "historical weight-only gate"
    )


if __name__ == "__main__":
    main()
