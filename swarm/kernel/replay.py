"""Replay: re-derive every certificate and crossing from the ledger (Phase K's K3 replay).

Inputs are the artifacts a run writes: ``ledger.jsonl``, the kernel-only
``vault.json`` (sealed witnesses, checkers and hidden instances),
``archive.json`` and the snapshot store. Replay verifies the hash chain,
checks that the vault and archive dumps hash to the digests the ledger
recorded when each task was sealed (witness, checker, hidden instances,
public examples) and that the archive's records agree with the ledger,
then for every admission re-runs Kd, Ka and Kc from the sealed data and
for every crossing re-runs the recorded program through the checker on
the hidden instances and re-checks the own-solution exclusion against the
recorded sources. With ``full=True`` it also re-runs Kb and the crossing
solves from the snapshots (fresh ``B_inst`` solves), which is the
expensive part. The report lists every disagreement; an empty list is K7.
"""
from __future__ import annotations

import json
from pathlib import Path

from .admit import examples_key, probe_inputs, signature_of
from .archive import Archive
from .executor import Executor
from .ledger import Ledger
from .snapshot import SnapshotStore
from .vault import Vault, _sha as digest_of


def replay(run_dir: Path, full: bool = False, b_inst: int | None = None,
           probe_seed: int | None = None) -> dict:
    run_dir = Path(run_dir)
    ledger = Ledger.load(run_dir / "ledger.jsonl")
    vault = Vault.load(json.loads((run_dir / "vault.json").read_text(encoding="utf-8")))
    archive = Archive.load(json.loads((run_dir / "archive.json").read_text(encoding="utf-8")))
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    b_inst = int(config["B_inst"] if b_inst is None else b_inst)
    probe_seed = int(config["probe_set_seed"] if probe_seed is None else probe_seed)
    executor = Executor(timeout_s=config.get("executor_timeout_s", 2.0),
                        memory_mb=config.get("executor_mem_mb", 512))
    snapshots = SnapshotStore(run_dir / "snapshots", executor)
    disagreements = []
    certificates = 0
    crossings = 0
    admissions = {e["payload"]["id"]: e["payload"] for e in ledger.of_kind("admission")}
    proposals = {e["payload"]["id"]: e["payload"] for e in ledger.of_kind("proposal")}
    for task_id, payload in admissions.items():
        task = archive.tasks[task_id]
        witness, checker = vault.sealed_witness(task_id), vault.sealed_checker(task_id)
        # The loaded artifacts must be the ones the ledger sealed: every
        # digest recorded at proposal time is recomputed from vault.json and
        # archive.json before anything is re-derived from them.
        proposal = proposals.get(task_id, {})
        recorded = {"witness_sha": proposal.get("witness_sha", payload.get("witness_sha")),
                    "checker_sha": proposal.get("checker_sha", payload.get("checker_sha")),
                    "hidden_sha": proposal.get("hidden_sha", payload.get("hidden_sha")),
                    "examples_key": proposal.get("examples_key")}
        actual = {"witness_sha": digest_of(witness), "checker_sha": digest_of(checker),
                  "hidden_sha": digest_of(vault.sealed_hidden(task_id)),
                  "examples_key": examples_key(task["examples"])}
        for name in ("witness_sha", "checker_sha", "hidden_sha", "examples_key"):
            if recorded[name] is not None and recorded[name] != actual[name]:
                disagreements.append({"id": task_id, "artifact": name})
        for name in ("signature", "admitted_generation", "snapshot", "kb_margin"):
            if task.get(name) != payload.get(name):
                disagreements.append({"id": task_id, "archive": name})
        hidden = [(i["inputs"][0], i["output"]) for i in vault.sealed_hidden(task_id)]
        public = [(i["inputs"][0], i["output"]) for i in task["examples"]]
        runs = executor.run_batch(witness, [[x] for x, _ in hidden + public])
        ka = (all(r["ok"] for r in runs)
              and all(r["value"] == y for r, (_, y) in zip(runs, hidden + public)))
        verdicts = executor.check_batch(checker, hidden + public)
        kd = all(v is not None for v in verdicts)
        ka = ka and all(v is True for v in verdicts)
        probes = probe_inputs(task["input_kind"], probe_seed)
        probe_runs = executor.run_batch(witness, [[x] for x in probes])
        signature = signature_of([r["value"] if r["ok"] else "!error" for r in probe_runs])
        kc = signature == payload["signature"]
        certificates += 3
        for name, ok in (("Ka", ka), ("Kd", kd), ("Kc", kc)):
            if not ok:
                disagreements.append({"id": task_id, "certificate": name})
        if full:
            results = snapshots.solve(payload["snapshot"], [{"id": task_id, "examples": task["examples"]}],
                                      b_inst)
            kb = True
            if results and results[0].get("program") is not None:
                outs = executor.run_batch(results[0]["program"], [[x] for x, _ in hidden])
                ver = executor.check_batch(checker, [(x, r["value"] if r["ok"] else None)
                                                     for (x, _), r in zip(hidden, outs)])
                kb = not all(v is True for v in ver)
            certificates += 1
            if not kb:
                disagreements.append({"id": task_id, "certificate": "Kb"})
    for entry in ledger.of_kind("crossing"):
        payload = entry["payload"]
        task_id = payload["id"]
        recorded_crossing = (archive.tasks.get(task_id) or {}).get("crossing") or {}
        if (recorded_crossing.get("program") != payload["program"]
                or recorded_crossing.get("generation") != payload["generation"]):
            disagreements.append({"id": task_id, "archive": "crossing record"})
        checker = vault.sealed_checker(task_id)
        hidden = [(i["inputs"][0], i["output"]) for i in vault.sealed_hidden(task_id)]
        outs = executor.run_batch(payload["program"], [[x] for x, _ in hidden])
        verdicts = executor.check_batch(checker, [(x, r["value"] if r["ok"] else None)
                                                  for (x, _), r in zip(hidden, outs)])
        crossings += 1
        if not all(v is True for v in verdicts):
            disagreements.append({"id": task_id, "crossing": "checker rejects on hidden"})
        if any(task_id in sources for sources in payload["sources"].values()):
            disagreements.append({"id": task_id, "crossing": "own-solution fragment"})
        if full:
            results = snapshots.solve(payload["snapshot"], [{"id": task_id, "examples": archive.tasks[task_id]["examples"]}],
                                      b_inst, exclude={task_id: [task_id]})
            found = bool(results and results[0].get("program") is not None)
            if not found:
                disagreements.append({"id": task_id, "crossing": "fresh solve not reproduced"})
    curve = [e["payload"].get("crossings_cumulative") for e in ledger.of_kind("generation")]
    recorded = sum(1 for e in ledger.of_kind("crossing"))
    if curve and curve[-1] != recorded:
        disagreements.append({"curve": "final cumulative crossings disagree with crossing entries"})
    return {"chain_ok": ledger.verify(), "entries": len(ledger.entries), "certificates": certificates,
            "crossings": crossings, "full": full, "disagreements": disagreements,
            "digest": ledger.digest()}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Replay a SWARM run's ledger")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(replay(args.run_dir, args.full), indent=1))


if __name__ == "__main__":
    main()
