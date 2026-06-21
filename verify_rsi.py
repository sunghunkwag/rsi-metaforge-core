#!/usr/bin/env python3
"""
verify_rsi.py -- single-command verification that recursive self-improvement
actually occurs in this repository.

This harness is intentionally narrow and falsifiable. It does NOT assert any
"AGI/ASI achieved" flag. It runs two independent, measured demonstrations
against the single consolidated runtime (rsi_metaforge_core.py) and fails
loudly if either one does not hold:

  GATE 1 -- Per-layer self-improvement suites
    Runs every ASI/RSI layer's built-in test suite via the runtime's own modes
    (asi-integrated-test, asi-open-test, asi-evolve-test, asi-unify-test,
    asi-auto-test, asi-search-test, asi-socratic-test, asi-guarded-test).
    Together these cover the 8 layers. Among them the self-improvement claims
    are backed directly:
      * learning lowers search cost vs. a no-learning control,
      * cumulative abstraction lineage reaches depth >= 3
        (an improvement built on top of a previous improvement),
      * the solved library compresses below its fully-expanded size,
      * a derived operator reduces future search cost,
      * operator promotion is gated by an adversarial Socratic audit
        (spurious operators are rejected; only verified ones are adopted).
    The immutable, hash-pinned kernel is the judge throughout and never moves.

  GATE 2 -- Cross-domain meta-gate self-improvement
    Runs the general-domain self-improvement test. The system proposes a macro
    abstraction from its OWN solved programs, then an A/B meta-gate measures a
    "warm" searcher (with the self-proposed abstraction) against a "cold"
    baseline (without it) on a SEALED held-out cross-domain frontier
    (list / string / grid / record). Self-improvement is the measured delta:
    the run is accepted only when the warm searcher validates frontier tasks
    that the cold baseline cannot, and out-of-scope probes are honestly
    rejected (no leakage).

Exit code 0 means BOTH gates passed: measured, reproducible recursive
self-improvement. Any other exit code means at least one gate failed and the
failing log is printed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
MONOLITH = os.path.join(HERE, "rsi_metaforge_core.py")

# One mode per ASI/RSI layer; together they exercise all 8 layers.
LAYER_TEST_MODES = [
    "asi-integrated-test",   # kernel + substrates + Kuramoto + compression curriculum
    "asi-open-test",         # stack-VM substrate + meta-proposer + transfer
    "asi-evolve-test",       # operator evolution + cross-substrate transfer
    "asi-unify-test",        # recursive higher-order operator expansion
    "asi-auto-test",         # verified normalizer enabling transfer
    "asi-search-test",       # bottom-up synthesis loop
    "asi-socratic-test",     # Socratic CEGIS debate
    "asi-guarded-test",      # Socratic-gated autonomous promotion loop
]

_RESULT_RE = re.compile(r"RESULT:\s+(\d+)\s+passed,\s+(\d+)\s+failed")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def gate_layer_suites() -> bool:
    print("=" * 78)
    print("GATE 1: per-layer self-improvement suites (rsi_metaforge_core.py asi-*-test)")
    print("=" * 78)
    total_passed = 0
    total_failed = 0
    all_ok = True
    for mode in LAYER_TEST_MODES:
        res = _run([PY, MONOLITH, "--mode", mode])
        m = _RESULT_RE.search(res.stdout)
        passed = int(m.group(1)) if m else 0
        failed = int(m.group(2)) if m else -1
        ok = res.returncode == 0 and m is not None and failed == 0
        total_passed += max(0, passed)
        total_failed += max(0, failed)
        print(f"  {mode:<22} -> {passed} passed, {max(0, failed)} failed "
              f"[{'ok' if ok else 'FAIL'}]")
        if not ok:
            all_ok = False
            sys.stdout.write(res.stdout[-2000:])
            if res.stderr.strip():
                sys.stderr.write(res.stderr[-2000:])
    print(f"GATE 1 total: {total_passed} passed, {total_failed} failed "
          f"across {len(LAYER_TEST_MODES)} layers")
    ok = all_ok and total_failed == 0 and total_passed > 0
    print(f"GATE 1 -> {'PASS' if ok else 'FAIL'}\n")
    return ok


def gate_meta_gate() -> bool:
    print("=" * 78)
    print("GATE 2: cross-domain meta-gate self-improvement "
          "(rsi_metaforge_core.py --mode general-domain-test)")
    print("=" * 78)
    with tempfile.TemporaryDirectory() as td:
        report_path = os.path.join(td, "general_domain_report.json")
        res = _run([PY, MONOLITH, "--mode", "general-domain-test",
                    "--save", report_path])
        if res.returncode != 0:
            sys.stdout.write(res.stdout[-4000:])
            sys.stderr.write(res.stderr[-4000:])
            print(f"GATE 2 -> FAIL (process exit={res.returncode})\n")
            return False
        try:
            with open(report_path) as fh:
                report = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"GATE 2 -> FAIL (could not read report: {exc!r})\n")
            return False

    mg = report.get("meta_gate", {})
    accepted = bool(mg.get("accepted"))
    delta = int(mg.get("delta", 0))
    warm = int(mg.get("warm_frontier_validated", 0))
    cold = int(mg.get("cold_frontier_validated", 0))
    unsupported = report.get("unsupported_probe", {}).get("validated", 0)
    print(json.dumps({"meta_gate": mg,
                      "unsupported_probe_validated": unsupported,
                      "claim_boundary": report.get("claim_boundary")},
                     indent=2, sort_keys=True))
    # Self-improvement: the self-proposed abstraction must enable held-out
    # frontier tasks the cold baseline cannot reach, with no out-of-scope leak.
    ok = accepted and delta > 0 and warm > cold and unsupported == 0
    print(f"GATE 2 -> {'PASS' if ok else 'FAIL'} "
          f"(accepted={accepted}, delta={delta}, warm={warm}, cold={cold}, "
          f"unsupported_validated={unsupported})\n")
    return ok


def gate_repo_patch_agent() -> bool:
    print("=" * 78)
    print("GATE 3: repository code-repair agent "
          "(real source edits; adaptive vs frozen; anti-cheat)")
    print("=" * 78)
    # (a) anti-cheat + functional + structural-divergence + determinism tests
    res = _run([PY, os.path.join(HERE, "repo_rsi.py"), "test"])
    tail = "\n".join(res.stdout.strip().splitlines()[-3:])
    print(tail)
    tests_ok = res.returncode == 0 and "0 failed" in res.stdout
    # (b) measured adaptive-vs-frozen delta on real repository patch tasks
    demo_ok = False
    with tempfile.TemporaryDirectory() as td:
        rp = os.path.join(td, "repo_rsi_report.json")
        d = _run([PY, MONOLITH, "--mode", "repo-rsi-demo", "--out-json", rp])
        if d.returncode == 0 and os.path.exists(rp):
            with open(rp) as fh:
                rep = json.load(fh)
            baselines_real = all(v is False
                                 for v in rep.get("baseline_public_pass", {}).values())
            demo_ok = (rep.get("adaptive_beats_frozen") is True
                       and rep.get("recursive_gain_evaluations", 0) > 0
                       and rep.get("adaptive", {}).get("skill_reuse_count", 0) >= 1
                       and rep.get("adaptive_score", 0) >= 6
                       and baselines_real)
            print(json.dumps({
                "frozen_score": rep.get("frozen_score"),
                "adaptive_score": rep.get("adaptive_score"),
                "recursive_gain_evaluations": rep.get("recursive_gain_evaluations"),
                "recursive_gain_pct": rep.get("recursive_gain_pct"),
                "skill_reuse_count": rep.get("adaptive", {}).get("skill_reuse_count"),
                "open_tasks": rep.get("open_tasks"),
            }, indent=2, sort_keys=True))
        else:
            sys.stdout.write(d.stdout[-2000:])
            sys.stderr.write(d.stderr[-2000:])
    ok = tests_ok and demo_ok
    print(f"GATE 3 -> {'PASS' if ok else 'FAIL'} "
          f"(anticheat_tests={'pass' if tests_ok else 'fail'}, "
          f"adaptive_delta={'pass' if demo_ok else 'fail'})\n")
    return ok


def main() -> int:
    g1 = gate_layer_suites()
    g2 = gate_meta_gate()
    g3 = gate_repo_patch_agent()
    print("=" * 78)
    if g1 and g2 and g3:
        print("RESULT: RECURSIVE SELF-IMPROVEMENT VERIFIED "
              "(all gates passed; measured, reproducible, sealed-evaluation).")
        print("  Gate 1: per-layer symbolic self-improvement suites (8 layers).")
        print("  Gate 2: cross-domain meta-gate (self-proposed abstraction).")
        print("  Gate 3: real repository code-repair agent, adaptive > frozen.")
        print("Boundary: CPU-scale research system. Not a verified "
              "superintelligence; no AGI/ASI flag is set.")
        return 0
    print("RESULT: VERIFICATION FAILED "
          f"(gate1={'pass' if g1 else 'fail'}, gate2={'pass' if g2 else 'fail'}, "
          f"gate3={'pass' if g3 else 'fail'}). Do not commit.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
