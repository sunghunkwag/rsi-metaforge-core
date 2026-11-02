"""Admission certificates Ka-Kd for a Breaker proposal (OWNER_DIRECTIVE.md §2; Phase K §4).

A proposal is a triple with public examples, a checker, a witness and
hidden instances (inputs with the witness's outputs). The kernel seals the
secrets first, then certifies, in a frozen order, and ledgers every
disposition:

- **K0 structure**: well-formed programs within size limits, ``PUBLIC``
  public and ``HIDDEN`` hidden instances with distinct inputs, values in
  the shared domain (ints, bools, lists of them).
- **Kd well-posedness**: the checker returns a bool on every hidden and
  public instance, both for the witness's output and for a null output
  (the input itself and an empty value), so it is total where it is used.
- **Ka feasibility**: the witness reproduces every public output and the
  checker accepts the witness's output on every hidden instance.
- **Kc novelty**: the witness's behaviour on the canonical probe set of
  the task's input kind is not an archived signature, and the public
  examples are not an archived set.
- **Kb difficulty**: the Builder snapshot taken at admission, run fresh at
  the instrument budget ``B_inst`` on the public examples, does not
  produce a program the checker accepts on every hidden instance. The
  snapshot's best public match fraction is the task's Kb margin.

Every executor run here is charged to the meter under the kernel.
"""
from __future__ import annotations

import hashlib
import json
import random

from . import checker_lang
from .vault import SealedError

PUBLIC = 8
HIDDEN = 6
MAX_PROGRAM_SIZE = 96
MAX_VALUE_NODES = 64
PROBES = 10
KINDS = ("int", "bool", "list[int]", "list[bool]")
CERTIFICATES = ("K0", "Kd", "Ka", "Kc", "Kb")


class Rejected(Exception):
    def __init__(self, certificate: str, detail: str):
        super().__init__(f"{certificate}: {detail}")
        self.certificate, self.detail = certificate, detail


def _domain_ok(value, nodes=(0,)) -> bool:
    nodes[0] += 1
    if nodes[0] > MAX_VALUE_NODES:
        return False
    if type(value) is bool or type(value) is int:
        return type(value) is bool or abs(value) < 10 ** 9
    if type(value) is list:
        kinds = {type(v) for v in value}
        return len(kinds) <= 1 and all(_domain_ok(v, nodes) for v in value)
    return False


def value_kind(value) -> str | None:
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if type(value) is list:
        if not value:
            return "list[int]"
        inner = {value_kind(v) for v in value}
        if inner == {"int"}:
            return "list[int]"
        if inner == {"bool"}:
            return "list[bool]"
    return None


def probe_inputs(kind: str, seed: int) -> list:
    """The canonical probe set of an input kind (registered seed), for Kc signatures."""
    rng = random.Random(f"swarm-probes-{seed}-{kind}")
    probes = []
    for index in range(PROBES):
        if kind == "int":
            probes.append(rng.randint(-6, 12))
        elif kind == "bool":
            probes.append(index % 2 == 0)
        elif kind == "list[int]":
            probes.append([rng.randint(-4, 9) for _ in range(rng.randint(0, 7))])
        else:
            probes.append([rng.random() < 0.5 for _ in range(rng.randint(0, 7))])
    return probes


def signature_of(outputs: list) -> str:
    return hashlib.sha256(json.dumps([checker_lang.to_jsonable(o) for o in outputs],
                                     sort_keys=True).encode("utf-8")).hexdigest()[:24]


def examples_key(examples: list) -> str:
    return hashlib.sha256(json.dumps(examples, sort_keys=True).encode("utf-8")).hexdigest()[:24]


class Admission:
    """Runs the certificates with the kernel's executor, vault, archive, snapshots and ledger."""

    def __init__(self, executor, vault, archive, snapshots, ledger, meter, b_inst: int,
                 probe_seed: int):
        self.executor = executor
        self.vault = vault
        self.archive = archive
        self.snapshots = snapshots
        self.ledger = ledger
        self.meter = meter
        self.b_inst = int(b_inst)
        self.probe_seed = int(probe_seed)
        self.counter = 0

    # -- helpers ---------------------------------------------------------------
    def _structure(self, triple: dict) -> None:
        for key in ("examples", "hidden", "witness", "checker", "lineage"):
            if key not in triple:
                raise Rejected("K0", f"missing {key}")
        for program in (triple["witness"], triple["checker"]):
            try:
                checker_lang.validate(program)
            except checker_lang.CheckerError as exc:
                raise Rejected("K0", f"malformed program: {exc}")
            if checker_lang.size(program) > MAX_PROGRAM_SIZE:
                raise Rejected("K0", "program too large")
        if len(triple["examples"]) < PUBLIC or len(triple["hidden"]) < HIDDEN:
            raise Rejected("K0", "too few instances")
        seen = set()
        kinds = set()
        for item in list(triple["examples"]) + list(triple["hidden"]):
            if set(item) != {"inputs", "output"} or len(item["inputs"]) != 1:
                raise Rejected("K0", "malformed instance")
            x, y = item["inputs"][0], item["output"]
            if not _domain_ok(x, [0]) or not _domain_ok(y, [0]):
                raise Rejected("K0", "value outside the shared domain")
            kinds.add(value_kind(x))
            key = json.dumps(x, sort_keys=True)
            if key in seen:
                raise Rejected("K0", "duplicate input")
            seen.add(key)
        if None in kinds or len(kinds) != 1:
            raise Rejected("K0", "inputs must share one kind")
        triple["input_kind"] = kinds.pop()

    def _run(self, program, inputs: list) -> list:
        return self.executor.run_batch(program, [[x] for x in inputs], module="admit")

    def _verdicts(self, checker, pairs: list) -> list:
        return self.executor.check_batch(checker, pairs, module="admit")

    # -- the certificates ----------------------------------------------------------
    def certify(self, triple: dict, generation: int, snapshot_sha: str) -> dict:
        """Seal, certify and either admit (returns the archive record) or raise Rejected."""
        self.counter += 1
        task_id = f"t{self.counter:04d}"
        self._structure(triple)
        digests = self.vault.seal(task_id, triple["witness"], triple["checker"], triple["hidden"])
        self.ledger.append("proposal", {"id": task_id, "generation": generation,
                                        "lineage": triple["lineage"], **digests,
                                        "examples_key": examples_key(triple["examples"]),
                                        "input_kind": triple["input_kind"]})
        public = [(i["inputs"][0], i["output"]) for i in triple["examples"]]
        hidden = [(i["inputs"][0], i["output"]) for i in triple["hidden"]]
        checker, witness = triple["checker"], triple["witness"]
        # Kd: total checker on hidden and public inputs, for the given output and null outputs.
        pairs = hidden + public
        nulls = [(x, x) for x, _ in pairs] + [(x, [] if type(x) is list else 0) for x, _ in pairs]
        verdicts = self._verdicts(checker, pairs + nulls)
        if any(v is None for v in verdicts):
            raise Rejected("Kd", "checker crashed or timed out")
        # Ka: the witness reproduces public outputs and satisfies the checker on hidden ones.
        runs = self._run(witness, [x for x, _ in pairs])
        if any(not r["ok"] for r in runs):
            raise Rejected("Ka", "witness fails on an instance")
        hidden_outputs = [r["value"] for r in runs[:len(hidden)]]
        public_outputs = [r["value"] for r in runs[len(hidden):]]
        if any(o != y for o, (_, y) in zip(public_outputs, public)):
            raise Rejected("Ka", "witness disagrees with a public example")
        if any(o != y for o, (_, y) in zip(hidden_outputs, hidden)):
            raise Rejected("Ka", "witness disagrees with a hidden instance")
        if not all(verdicts[:len(hidden)]):
            raise Rejected("Ka", "checker rejects the witness on a hidden instance")
        if not all(verdicts[len(hidden):len(pairs)]):
            raise Rejected("Ka", "checker rejects the witness on a public example")
        # Kc: novelty on the canonical probe set and of the public example set.
        probes = probe_inputs(triple["input_kind"], self.probe_seed)
        probe_runs = self._run(witness, probes)
        signature = signature_of([r["value"] if r["ok"] else "!error" for r in probe_runs])
        if signature in self.archive.signatures:
            raise Rejected("Kc", "duplicate behaviour on the probe set")
        if any(examples_key(t["examples"]) == examples_key(triple["examples"])
               for t in self.archive.tasks.values()):
            raise Rejected("Kc", "duplicate public examples")
        # Kb: the admission-time Builder snapshot must fail at B_inst.
        public_task = {"id": task_id, "examples": triple["examples"]}
        results = self.snapshots.solve(snapshot_sha, [public_task], self.b_inst, agent="kernel")
        if results is None:
            raise Rejected("Kb", "snapshot solver crashed or timed out")
        result = results[0]
        margin = float(result.get("best_public", 0.0))
        if result.get("program") is not None:
            runs = self._run(result["program"], [x for x, _ in hidden])
            outputs = [r["value"] if r["ok"] else None for r in runs]
            accepted = self._verdicts(checker, [(x, o) for (x, _), o in zip(hidden, outputs)])
            if all(v is True for v in accepted):
                raise Rejected("Kb", "the frozen snapshot already solves the task")
        record = {"id": task_id, "lineage": triple["lineage"], "examples": triple["examples"],
                  "input_kind": triple["input_kind"], "signature": signature,
                  "admitted_generation": int(generation), "snapshot": snapshot_sha,
                  "kb_margin": margin, "witness_sha": digests["witness_sha"],
                  "checker_sha": digests["checker_sha"], "hidden_sha": digests["hidden_sha"]}
        self.archive.add(record)
        self.ledger.append("admission", {k: v for k, v in record.items() if k != "examples"})
        return record

    def admit(self, triple: dict, generation: int, snapshot_sha: str) -> dict:
        """Certify a proposal; returns {"admitted": bool, "id", "certificate", "detail"}."""
        try:
            record = self.certify(triple, generation, snapshot_sha)
        except Rejected as exc:
            self.ledger.append("rejection", {"generation": generation, "lineage": triple.get("lineage"),
                                             "certificate": exc.certificate, "detail": exc.detail})
            return {"admitted": False, "certificate": exc.certificate, "detail": exc.detail}
        except SealedError as exc:
            self.ledger.append("rejection", {"generation": generation, "lineage": triple.get("lineage"),
                                             "certificate": "K0", "detail": str(exc)})
            return {"admitted": False, "certificate": "K0", "detail": str(exc)}
        return {"admitted": True, "id": record["id"], "kb_margin": record["kb_margin"]}
