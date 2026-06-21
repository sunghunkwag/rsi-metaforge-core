#!/usr/bin/env python3
"""
verify_rsi.py -- single-command verification that recursive self-improvement
actually occurs in this repository.

This harness is intentionally narrow and falsifiable. It does NOT assert any
"AGI/ASI achieved" flag. It runs two independent, measured demonstrations and
fails loudly if either one does not hold:

  GATE 1 -- Distilled core self-improvement suite (asi_unified_core.py)
    Runs the full 49-test suite across the 8 layers of the self-contained core.
    Among those tests, the self-improvement claims are backed directly:
      * learning lowers search cost vs. a no-learning control,
      * cumulative abstraction lineage reaches depth >= 3
        (an improvement built on top of a previous improvement),
      * the solved library compresses below its fully-expanded size,
      * a derived operator reduces future search cost,
      * operator promotion is gated by an adversarial Socratic audit
        (spurious operators are rejected; only verified ones are adopted).
    The immutable, hash-pinned kernel is the judge throughout and never moves.

  GATE 2 -- Cross-domain meta-gate self-improvement (rsi_metaforge_core.py)
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
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
UNIFIED = os.path.join(HERE, "asi_unified_core.py")
MONOLITH = os.path.join(HERE, "rsi_metaforge_core.py")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def gate_distilled_core() -> bool:
    print("=" * 78)
    print("GATE 1: distilled-core self-improvement suite (asi_unified_core.py test)")
    print("=" * 78)
    res = _run([PY, UNIFIED, "test"])
    sys.stdout.write(res.stdout)
    if res.stderr.strip():
        sys.stderr.write(res.stderr)
    ok = res.returncode == 0 and "0 failed" in res.stdout
    print(f"GATE 1 -> {'PASS' if ok else 'FAIL'} (exit={res.returncode})\n")
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


def main() -> int:
    g1 = gate_distilled_core()
    g2 = gate_meta_gate()
    print("=" * 78)
    if g1 and g2:
        print("RESULT: RECURSIVE SELF-IMPROVEMENT VERIFIED "
              "(both gates passed; measured, reproducible, sealed-evaluation).")
        print("Boundary: CPU-scale research system. Not a verified "
              "superintelligence; no AGI/ASI flag is set.")
        return 0
    print("RESULT: VERIFICATION FAILED "
          f"(gate1={'pass' if g1 else 'fail'}, gate2={'pass' if g2 else 'fail'}). "
          "Do not commit.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
