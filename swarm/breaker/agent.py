"""The Breaker agent: four setter lineages, admission bookkeeping, regret reward, latent writes.

Lineages (OWNER_DIRECTIVE.md §4; the Phase K L_A/L_B/L_D pattern with separate credit):

- ``mutate``: a random edit of an archived task's witness (or of a seed
  program while the archive is empty): a constant, a primitive swap, or a
  wrapping stage.
- ``compose``: the composition of two witnesses, the inner one list-valued
  (crossed tasks' witnesses when two exist, seed programs otherwise).
- ``analogy``: the latent lineage. For an open task T with a residue
  vector the Builder wrote (a near miss bound to T's signature) and a
  crossed task C with its crossing program's vector, the Breaker forms
  ``D = analogy(S_C, P_C, S_T)`` in its task space (the Builder's program
  vector is mapped into task space by the mapper when one is given) and
  proposes, among candidate mutations of T's and C's witnesses, the one
  whose signature is nearest to D: a task that stands to the near miss as
  the crossed task stood to its solution. In the records arm the same
  choice is made by token overlap with the Builder's residue text and the
  crossing program (the human-structured exchange).
- ``distinguisher``: for a crossed task, inputs on which the Builder's
  crossing program (public in the ledger) disagrees with the witness are
  sought; a task with those inputs among its instances is proposed, so
  the Builder's program must generalize to cross it.

Credit: with regret (the default), a lineage is paid
``1 / (1 + generations-to-crossing)`` when one of its tasks crosses; tasks
rejected or never crossed within the horizon count as wasted. Without
regret (arm S4) a lineage is paid 1 per admitted task. Proposal slots
follow credit through the R3 rule of the original core: a multiplier per
lineage moves up when validated outcomes exceed wasted ones and down
otherwise, bounded, with one slot always kept per lineage.

What the Breaker writes to the field: the signature of every admitted
task (bundle over position ⊗ input ⊗ output of its public examples, in
the Breaker's codebook) tagged with the task's archive ordinal, written
when the task is admitted and again when its status changes, and one
bundle of lineage-credit symbols (tag -1). What it reads: the Builder's
region, as vectors with ordinal tags.

The Breaker never sees the Builder's source, the vault or the kernel's
internals: it receives the public archive view, public ledger outcomes
and a metered runner for its own programs, and its only import from the
package is ``swarm.latent``.
"""
from __future__ import annotations

import json
import random

import numpy as np

from swarm import latent
from . import programs

R3_MIN, R3_MAX, R3_ETA = 0.25, 4.0, 0.25
PUBLIC, HIDDEN = 8, 6
MAX_WITNESS_SIZE = 60
ANALOGY_CANDIDATES = 4
LINEAGES = ("mutate", "compose", "analogy", "distinguisher")


class Breaker:
    def __init__(self, port, runner, seed: int, d: int, lineages=LINEAGES, regret: bool = True,
                 latent_channel: bool = True, mapper=None, records: bool = False):
        self.port = port                      # latent Port (write own region, read the Builder's)
        self.runner = runner                  # metered: runner(program, inputs) -> list of outputs or None
        self.rng = random.Random(f"swarm-breaker-{seed}")
        self.book = latent.Codebook(seed=seed * 7919 + 1, d=d)
        self.lineages = tuple(lineages)
        self.regret = bool(regret)
        self.records = bool(records)
        self.latent_channel = bool(latent_channel) and not self.records
        self.mapper = mapper
        self.multiplier = {name: 1.0 for name in self.lineages}
        self.validated = {name: 0 for name in self.lineages}
        self.wasted = {name: 0 for name in self.lineages}
        self.credit = {name: 0.0 for name in self.lineages}
        self.authored: dict = {}              # task id -> {"body", "lineage", "generation"}
        self.pending: dict = {}               # proposal key -> (lineage, body) awaiting the kernel's decision
        self.signatures: dict = {}            # task id -> signature vector (own codebook)
        self.records_in: dict = {}            # S1 only: structured records from the Builder
        self._written: dict = {}              # task id -> status last written to the field
        self._analogy_choice = None

    # ---- inputs ------------------------------------------------------------
    def _distinct_inputs(self, kind: str, count: int, must_include=()) -> list:
        found, seen = [], set()
        for value in must_include:
            key = json.dumps(value)
            if key not in seen:
                seen.add(key)
                found.append(value)
        attempts = 0
        while len(found) < count and attempts < 50 * count:
            attempts += 1
            length = self.rng.randint(0, 7) if self.rng.random() < 0.08 else self.rng.randint(1, 7)
            if kind == "list[bool]":
                value = [self.rng.random() < 0.5 for _ in range(length)]
            else:
                value = [self.rng.randint(-3, 9) for _ in range(length)]
            key = json.dumps(value)
            if key not in seen:
                seen.add(key)
                found.append(value)
        return found

    def _triple(self, lineage: str, body, must_include=()):
        """Public and hidden instances from the witness; None when the witness is not total enough."""
        if programs.size(body) > MAX_WITNESS_SIZE:
            return None
        inputs = self._distinct_inputs("list[int]", PUBLIC + HIDDEN + 4, must_include)
        outputs = self.runner(programs.witness(body), inputs)
        if outputs is None:
            return None
        instances = [{"inputs": [x], "output": o} for x, o in zip(inputs, outputs) if o is not None]
        if len(instances) < PUBLIC + HIDDEN:
            return None
        public_values = {json.dumps(i["output"]) for i in instances[:PUBLIC]}
        if len(public_values) < 2:
            return None                       # constant on the public examples
        if all(i["output"] == i["inputs"][0] for i in instances):
            return None                       # the identity
        return {"lineage": lineage, "witness": programs.witness(body),
                "checker": programs.equality_checker(body),
                "examples": instances[:PUBLIC], "hidden": instances[PUBLIC:PUBLIC + HIDDEN],
                "body": body}

    # ---- lineages -------------------------------------------------------------
    def _bodies(self, archive_view: list, status=None) -> list:
        return [self.authored[t["id"]]["body"] for t in archive_view
                if t["id"] in self.authored and (status is None or t["status"] == status)]

    def _mutate(self, archive_view: list):
        pool = self._bodies(archive_view) or list(programs.SEED)
        base = pool[self.rng.randrange(len(pool))] if self.rng.random() < 0.7 or not self.authored else \
            programs.SEED[self.rng.randrange(len(programs.SEED))]
        return programs.mutate(base, self.rng)

    def _compose(self, archive_view: list):
        crossed = self._bodies(archive_view, "crossed")
        pool = crossed if len(crossed) >= 2 else (crossed + list(programs.SEED))
        inners = [b for b in pool if programs.output_kind_hint(b) == "list"] or list(programs.SEED[:6])
        outer = pool[self.rng.randrange(len(pool))]
        inner = inners[self.rng.randrange(len(inners))]
        return programs.compose(outer, inner)

    def _distinguisher(self, archive_view: list, ledger_view: dict):
        """Inputs where the Builder's crossing program disagrees with the witness."""
        crossed = [t for t in archive_view if t["status"] == "crossed" and t["id"] in self.authored
                   and t.get("crossing_program") is not None]
        if not crossed:
            return None, ()
        task = crossed[self.rng.randrange(len(crossed))]
        body = self.authored[task["id"]]["body"]
        probes = self._distinct_inputs("list[int]", 24)
        ours = self.runner(programs.witness(body), probes)
        theirs = self.runner(task["crossing_program"], probes)
        if ours is None or theirs is None:
            return None, ()
        disagreeing = [x for x, a, b in zip(probes, ours, theirs) if a is not None and a != b]
        if not disagreeing:
            return None, ()
        return body, tuple(disagreeing[:HIDDEN])

    def _latest_from_other(self, ordinal: int):
        """The Builder's most recent vector tagged with ``ordinal``, or None."""
        if not self.latent_channel:
            return None
        tags = self.port.read_tags()
        for index in range(len(tags) - 1, -1, -1):
            if tags[index] == ordinal:
                return self.port.read()[index]
        return None

    def _analogy(self, archive_view: list):
        """Pick, among candidate mutations, the one nearest to the analogy target."""
        open_tasks = [t for t in archive_view if t["status"] == "open" and t["id"] in self.authored]
        crossed = [t for t in archive_view if t["status"] == "crossed" and t["id"] in self.authored
                   and t.get("crossing_program") is not None]
        if not open_tasks or not crossed:
            return self._mutate(archive_view)
        target_task = open_tasks[self.rng.randrange(len(open_tasks))]
        crossed_task = crossed[self.rng.randrange(len(crossed))]
        candidates = [programs.mutate(base, self.rng)
                      for base in (self.authored[target_task["id"]]["body"], self.authored[crossed_task["id"]]["body"])
                      for _ in range(ANALOGY_CANDIDATES)]
        scored = []
        if self.records:
            residue = (self.records_in.get("residues") or {}).get(target_task["id"]) or {}
            reference = set(_tokens(crossed_task["crossing_program"])) | set(_dsl_tokens(residue.get("best_dsl")))
            for body in candidates:
                triple = self._triple("analogy", body)
                if triple is None:
                    continue
                tokens = set(_tokens(body))
                scored.append((len(tokens & reference) / max(len(tokens | reference), 1), body, triple))
        else:
            s_c = self.signatures[crossed_task["id"]]
            s_t = self.signatures[target_task["id"]]
            p_c = self.book.encode_tokens(_tokens(crossed_task["crossing_program"]))
            residue = self._latest_from_other(_ordinal(archive_view, target_task["id"]))
            if residue is not None:
                residue = residue.astype(np.float64)
                if self.mapper is not None:
                    residue = self.mapper.program_to_task(residue)
                s_t = latent.bundle([s_t, np.where(residue >= 0, 1, -1).astype(np.int8)])
            target = latent.analogy(s_c, p_c, s_t)
            for body in candidates:
                triple = self._triple("analogy", body)
                if triple is None:
                    continue
                signature = self.book.encode_examples(triple["examples"])
                scored.append((latent.similarity(target, signature), body, triple))
        if not scored:
            return self._mutate(archive_view)
        scored.sort(key=lambda item: -item[0])
        self._analogy_choice = scored[0][2]
        return scored[0][1]

    # ---- the generation's proposals ------------------------------------------------
    def slots(self, n_prop: int) -> dict:
        """Proposal slots per lineage: one each, the rest by multiplier (Phase K allocation)."""
        names = list(self.lineages)
        base = {name: 1 for name in names}
        spare = max(int(n_prop) - len(names), 0)
        total = sum(self.multiplier[n] for n in names)
        shares = {name: spare * self.multiplier[name] / total for name in names}
        for name in names:
            base[name] += int(shares[name])
        remaining = spare - sum(int(shares[name]) for name in names)
        for name in sorted(names, key=lambda n: (-(shares[n] - int(shares[n])), n))[:remaining]:
            base[name] += 1
        return base

    def propose(self, generation: int, archive_view: list, ledger_view: dict, n_prop: int) -> list:
        proposals = []
        for lineage, count in self.slots(n_prop).items():
            for index in range(count):
                triple, body, include = None, None, ()
                if lineage == "mutate":
                    body = self._mutate(archive_view)
                elif lineage == "compose":
                    body = self._compose(archive_view)
                elif lineage == "distinguisher":
                    body, include = self._distinguisher(archive_view, ledger_view)
                    if body is None:
                        body = self._mutate(archive_view)
                elif lineage == "analogy":
                    self._analogy_choice = None
                    body = self._analogy(archive_view)
                    triple = self._analogy_choice
                if triple is None and body is not None:
                    triple = self._triple(lineage, body, include)
                if triple is None:
                    self.wasted[lineage] += 1
                    continue
                key = f"g{generation}-{lineage}-{index}"
                triple["key"] = key
                self.pending[key] = (lineage, triple["body"])
                proposals.append(triple)
        return proposals

    # ---- outcomes --------------------------------------------------------------------
    def observe_admission(self, generation: int, key: str, decision: dict, archive_view: list) -> None:
        lineage, body = self.pending.pop(key)
        if decision["admitted"]:
            task_id = decision["id"]
            self.authored[task_id] = {"body": body, "lineage": lineage, "generation": generation}
            examples = next(t["examples"] for t in archive_view if t["id"] == task_id)
            self.signatures[task_id] = self.book.encode_examples(examples)
            if not self.regret:
                self.credit[lineage] += 1.0
                self._tune(lineage, True)
        elif decision.get("kernel_failed"):
            return                      # the kernel could not judge it: neither validated nor wasted
        else:
            self._tune(lineage, False)

    def observe_crossing(self, task_id: str, generations_to_crossing: int) -> None:
        record = self.authored.get(task_id)
        if record is None:
            return
        lineage = record["lineage"]
        if self.regret:
            self.credit[lineage] += 1.0 / (1.0 + int(generations_to_crossing))
        self._tune(lineage, True)

    def observe_retired(self, task_ids: list) -> None:
        for task_id in task_ids:
            record = self.authored.get(task_id)
            if record is not None:
                self._tune(record["lineage"], False)

    def _tune(self, lineage: str, validated: bool) -> None:
        if validated:
            self.validated[lineage] += 1
        else:
            self.wasted[lineage] += 1
        v, w = self.validated[lineage], self.wasted[lineage]
        factor = (1 + R3_ETA) if v > w else (1 - R3_ETA) if w > v else 1.0
        old = self.multiplier[lineage]
        self.multiplier[lineage] = min(R3_MAX, max(R3_MIN, old * factor))

    # ---- the channel -----------------------------------------------------------------
    def write_state(self, archive_view: list) -> int:
        """Write new or status-changed task signatures (tag = archive ordinal) and lineage credit (tag -1)."""
        if not self.latent_channel:
            return 0
        written = 0
        for ordinal, task in enumerate(archive_view):
            task_id = task["id"]
            if task_id not in self.signatures or self._written.get(task_id) == task["status"]:
                continue
            self._written[task_id] = task["status"]
            self.port.write(self.signatures[task_id], tag=ordinal)
            written += 1
        parts = [self.book(f"lineage:{name}") for name in self.lineages
                 for _ in range(1 + int(round(self.credit[name])))]
        self.port.write(latent.bundle(parts), tag=-1)
        return written + 1

    def state_records(self, archive_view: list) -> dict:
        """Arm S1 only: the structured record the Builder receives instead of vectors."""
        return {"credit": dict(self.credit), "multiplier": dict(self.multiplier),
                "tasks": {t["id"]: {"lineage": t["lineage"], "status": t["status"],
                                    "input_kind": t["input_kind"],
                                    "output_kind": _output_kind(t["examples"])}
                          for t in archive_view if t["id"] in self.authored}}

    def summary(self) -> dict:
        return {"credit": dict(self.credit), "multiplier": dict(self.multiplier),
                "validated": dict(self.validated), "wasted": dict(self.wasted),
                "authored": len(self.authored)}


def _tokens(program) -> list:
    if isinstance(program, list):
        out = []
        for item in program:
            out.extend(_tokens(item))
        return out
    return [str(program)]


def _dsl_tokens(text) -> list:
    if not text:
        return []
    return str(text).replace("(", " ( ").replace(")", " ) ").split()


def _ordinal(archive_view: list, task_id: str) -> int:
    for index, task in enumerate(archive_view):
        if task["id"] == task_id:
            return index
    return -1


def _output_kind(examples) -> str:
    kinds = set()
    for item in examples:
        y = item["output"]
        if type(y) is bool:
            kinds.add("bool")
        elif type(y) is int:
            kinds.add("int")
        elif type(y) is list:
            kinds.add("list[bool]" if y and all(type(v) is bool for v in y) else "list[int]")
        else:
            kinds.add("other")
    return kinds.pop() if len(kinds) == 1 else "mixed"
