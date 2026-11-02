"""The Builder agent: attacks the archive with its mutable tree, learns, forges, proposes self-edits.

The Builder never imports the kernel: the loop hands it a metered
``solver`` that runs its live tree's ``solve_many``/``learn``/``inventory``
in isolation, a metered ``batch_runner`` for checker-language programs
(the forge), and a latent ``Port``. Its only package import is
``swarm.latent`` (plus its own ``forge`` and ``self_edit`` modules).

Per generation: ``read_state`` turns the Breaker's task-signature vectors
into retrieval boosts (through the mapper when one is given, by raw
similarity otherwise; in the records arm by an explicit feature rule);
``attack`` spends the generation budget over the open tasks it has not
yet solved (even split, or committed to the tasks with the highest
partial matches, as the tree's allocation parameter says) and returns
wake solutions and residues; ``learn`` offers kernel-verified programs
(crossing programs, or mined wake solutions too, as the tree's learning
parameter says) to the tree's own adoption rule; ``propose_edits`` forges
primitives from residues within the forge's share of the budget the loop
sets (``forge_limit``) and draws parameter changes from the menu,
choosing operator kinds by their own adoption record; ``write_state``
publishes residue, solution and fragment vectors.

What the Builder writes to the field: for each task attacked this
generation without success, the sequence-permuted token bundle of its
best partial match bound to the task's signature (tag = archive ordinal);
for each task it solved, the token bundle of the solution (tag =
ordinal, once); and one bundle of its fragment vectors (tag -1). A
fragment vector is the name token bundled with the sequence-permuted
tokens of the fragment's body; a program vector is the sequence-permuted
token bundle bundled with the unordered token bag, so a program that
uses a fragment shares the fragment's name token with it.
"""
from __future__ import annotations

import random

import numpy as np

from swarm import latent
from . import forge as forging
from . import self_edit

BOOST = 4.0
TOP_K = 3
FORGE_RESIDUES = 2


def _dsl_tokens(text) -> list:
    if not text:
        return []
    return str(text).replace("(", " ( ").replace(")", " ) ").split()


class Builder:
    def __init__(self, port, solver, batch_runner, live_dir, seed: int, d: int, latent_channel: bool = True,
                 mapper=None, enable_self_edit: bool = True, enable_forge: bool = True,
                 records: bool = False):
        self.port = port
        self.solver = solver                  # solver(function, payload) -> result dict or None (metered, isolated)
        self.batch_runner = batch_runner      # batch_runner(programs, inputs) -> [outputs or None per program] (metered)
        self.live = live_dir
        self.rng = random.Random(f"swarm-builder-{seed}")
        self.book = latent.Codebook(seed=seed * 7919 + 2, d=d)
        self.records = bool(records)
        self.latent_channel = bool(latent_channel) and not self.records
        self.mapper = mapper
        self.enable_self_edit = bool(enable_self_edit)
        self.enable_forge = bool(enable_forge)
        self.fragments: dict = {}             # name -> vector (library entries, forged primitives)
        self.fragment_sources: dict = {}      # name -> source task ids
        self.residues: dict = {}              # task id -> {"best_public", "best_dsl"}
        self.wake_solutions: dict = {}        # task id -> solution found in the wake, awaiting the mined gate
        self.solutions: dict = {}             # task id -> kernel-accepted wake solution {"program","term","dsl","fragments"}
        self.edit_credit = {"forge": 1.0, "param": 1.0, "prune": 1.0, "unforge": 1.0}
        self.edit_tries = {k: 0 for k in self.edit_credit}
        self.forged_count = 0
        self.forge_attempts: dict = {}        # task id -> "found" | "none": each residue task is forged once
        self.records_in: dict = {}            # S1 only
        self.boosts: dict = {}
        self.retrieval_hits = 0
        self.pending: dict = {}               # task id -> wake solution whose gate check failed (resubmitted)
        self.rejected: dict = {}              # task id -> [term dicts] the gate rejected (passed over in later windows)
        self.forge_limit = 4000               # candidate checks per forge attempt; the loop sets it from B_gen
        self._inventory = None
        self._fresh_residues: dict = {}
        self._written_solutions: set = set()

    # ---- inventory and vectors ---------------------------------------------------
    def inventory(self, refresh: bool = False) -> dict:
        if self._inventory is None or refresh:
            self._inventory = self.solver("inventory", {}) or {"library": {}, "forged": {}, "params": {}}
            self._refresh_fragments(self._inventory)
        return self._inventory

    def _refresh_fragments(self, inventory: dict) -> None:
        self.fragments, self.fragment_sources = {}, {}
        for name, entry in inventory.get("library", {}).items():
            self.fragments[name] = latent.bundle([self.book(f"tok:{name}"),
                                                  self.book.encode_tokens(_dsl_tokens(entry["dsl"]))])
            self.fragment_sources[name] = list(entry.get("sources", []))
        for name, entry in inventory.get("forged", {}).items():
            self.fragments[name] = latent.bundle([self.book(f"tok:{name}"),
                                                  self.book.encode_tokens([entry["type"]])])
            self.fragment_sources[name] = list(entry.get("sources", []))

    def program_vector(self, dsl: str) -> np.ndarray:
        tokens = _dsl_tokens(dsl)
        if not tokens:
            return self.book("tokens:empty")
        return latent.bundle([self.book.encode_tokens(tokens),
                              latent.bundle([self.book(f"tok:{t}") for t in tokens])])

    # ---- the channel, inbound --------------------------------------------------
    def read_state(self, archive_view: list) -> dict:
        """Retrieval boosts per open task from the Breaker's region (or from its records)."""
        self.boosts = {}
        self.inventory()
        if not self.fragments:
            return self.boosts
        names = list(self.fragments)
        if self.records:
            tasks_in = self.records_in.get("tasks") or {}
            for task in archive_view:
                if task["status"] != "open" or task["id"] not in tasks_in:
                    # A task the Breaker has not yet recorded is not boosted:
                    # the latent arms see a new task's signature one generation
                    # after its admission, and the records arm keeps that lag.
                    continue
                kind = (tasks_in.get(task["id"]) or {}).get("output_kind")
                chosen = [n for n in names
                          if any((tasks_in.get(s) or {}).get("output_kind") == kind
                                 for s in self.fragment_sources.get(n, []))][:TOP_K]
                if chosen:
                    self.boosts[task["id"]] = {n: BOOST for n in chosen}
            return self.boosts
        if not self.latent_channel:
            return self.boosts
        vectors, tags = self.port.read(), self.port.read_tags()
        matrix = np.stack([self.fragments[n] for n in names])
        latest = {}
        for index, tag in enumerate(tags):
            latest[tag] = index                        # the last write per tag wins
        for tag, index in latest.items():
            if tag < 0 or tag >= len(archive_view) or archive_view[tag]["status"] != "open":
                continue
            query = vectors[index].astype(np.float64)
            if self.mapper is not None:
                query = self.mapper.task_to_program(query)
            query = np.where(query >= 0, 1, -1).astype(np.int8)
            top = latent.top_k(query, matrix, TOP_K)
            chosen = [names[i] for i, score in top if score > 0.0]
            if chosen:
                self.boosts[archive_view[tag]["id"]] = {n: BOOST for n in chosen}
        return self.boosts

    # ---- the wake -------------------------------------------------------------------
    def budgets(self, open_tasks: list, total: int, strategy: str) -> dict:
        ids = [t["id"] for t in open_tasks]
        if not ids:
            return {}
        if strategy == "commit":
            weights = {t: 1.0 + 3.0 * self.residues.get(t, {}).get("best_public", 0.0) for t in ids}
            norm = sum(weights.values())
            return {t: max(1, int(total * weights[t] / norm)) for t in ids}
        share, remainder = divmod(int(total), len(ids))
        return {t: share + (1 if i < remainder else 0) for i, t in enumerate(ids)}

    def attack(self, generation: int, open_tasks: list, total_budget: int) -> dict:
        inventory = self.inventory()
        strategy = inventory.get("params", {}).get("allocation", {}).get("strategy", "even")
        targets = [t for t in open_tasks if t["id"] not in self.solutions]
        budgets = self.budgets(targets, total_budget, strategy)
        self.wake_solutions, residues = {}, {}
        self._fresh_residues = {}
        if not targets:
            return {"solved": {}, "residues": {}, "budgets": {}, "failed": False}
        payload = {"tasks": [{"id": t["id"], "examples": t["examples"]} for t in targets],
                   "budget": budgets, "boost": self.boosts, "state_path": str(self.live / "state.pkl"),
                   "skip": {t: list(terms) for t, terms in self.rejected.items() if t in budgets}}
        result = self.solver("solve_many", payload)
        if result is None:
            return {"solved": dict(self.pending), "residues": {}, "budgets": budgets, "failed": True}
        for task_id, solution in self.pending.items():
            if task_id in budgets:
                self.wake_solutions[task_id] = solution     # resubmitted to the gate after a failed check
        for record in result.get("results", []):
            if record.get("program") is not None:
                self.wake_solutions[record["id"]] = {
                    "program": record["program"], "term": record.get("term"), "dsl": record.get("dsl"),
                    "fragments": record.get("fragments", [])}
                if any(f in self.boosts.get(record["id"], {}) for f in record.get("fragments", [])):
                    self.retrieval_hits += 1
            else:
                residues[record["id"]] = {"best_public": record.get("best_public", 0.0),
                                          "best_dsl": record.get("best_dsl")}
        self.residues.update(residues)
        self._fresh_residues = residues
        return {"solved": dict(self.wake_solutions), "residues": residues, "budgets": budgets,
                "failed": False, "meter": result.get("meter", {})}

    def observe_mined(self, task_id: str, accepted) -> None:
        """The kernel's verdict on a wake solution: accepted (learnable), rejected (passed over from now
        on) or None (the check failed; the solution is resubmitted next generation)."""
        solution = self.wake_solutions.get(task_id)
        if solution is None:
            return
        if accepted is None:
            self.pending[task_id] = solution
            return
        self.pending.pop(task_id, None)
        if accepted:
            self.solutions[task_id] = solution
            self.residues.pop(task_id, None)
        elif solution.get("term") is not None:
            self.rejected.setdefault(task_id, []).append(solution["term"])

    def learn(self, generation: int, archive_view: list) -> dict:
        """Offer kernel-verified programs to the tree's own adoption rule (``params.json`` learn.from)."""
        rule = self.inventory().get("params", {}).get("learn", {}).get("from", "crossed")
        solutions = {t["id"]: t["crossing_term"] for t in archive_view
                     if t["status"] == "crossed" and t.get("crossing_term") is not None}
        if rule == "mined":
            for task_id, solution in self.solutions.items():
                if solution.get("term") is not None:
                    solutions.setdefault(task_id, solution["term"])
        if not solutions:
            return {"adopted": [], "offered": 0}
        result = self.solver("learn", {"solutions": solutions, "generation": int(generation)}) or {"adopted": []}
        result["offered"] = len(solutions)
        if result.get("adopted"):
            self.inventory(refresh=True)
        return result

    # ---- self-edit ----------------------------------------------------------------------
    def propose_edits(self, generation: int, archive_view: list, k_edit: int) -> list:
        if not self.enable_self_edit or k_edit <= 0:
            return []
        patches = []
        open_ids = {t["id"]: t for t in archive_view if t["status"] == "open"}
        if self.enable_forge:
            residues = sorted(((r["best_public"], t) for t, r in self.residues.items()
                               if t in open_ids and t not in self.forge_attempts), reverse=True)
            heads = set(self.inventory().get("primitive_heads", []))
            for _, task_id in residues[:FORGE_RESIDUES]:
                examples = open_ids[task_id]["examples"]
                # The forge's per-generation cap is split over the residues it may try.
                found = forging.forge(examples, self.batch_runner,
                                      limit=max(1, int(self.forge_limit) // FORGE_RESIDUES))
                self.edit_tries["forge"] += 1
                self.forge_attempts[task_id] = "none" if found is None else "found"
                if found is None:
                    continue
                # The innermost stage first, when it is one the tree's own
                # primitives do not provide (the stage it lacks), then the whole body.
                inner = found.get("inner")
                if inner is not None and forging.head(inner) not in heads:
                    inputs = [e["inputs"][0] for e in examples]
                    outputs = self.batch_runner([inner], inputs)[0]
                    kind = (forging.output_kind([{"inputs": [x], "output": o} for x, o in zip(inputs, outputs)])
                            if outputs is not None else None)
                    if kind is not None:
                        self.forged_count += 1
                        patches.append({"kind": "forge", "name": f"forged_{self.forged_count}",
                                        "type": f"list[int] -> {kind}", "body": inner, "sources": [task_id],
                                        "tried": found["tried"], "stage": True})
                self.forged_count += 1
                patches.append({"kind": "forge", "name": f"forged_{self.forged_count}",
                                "type": found["type"], "body": found["body"], "sources": [task_id],
                                "tried": found["tried"], "stage": False})
                break
        kinds = [k for k in ("param", "prune", "unforge") if self.edit_credit[k] > 0]
        while len(patches) < k_edit and kinds:
            weights = [self.edit_credit[k] / (1 + self.edit_tries[k]) for k in kinds]
            kind = self.rng.choices(kinds, weights=weights)[0]
            self.edit_tries[kind] += 1
            if kind == "param":
                path = self.rng.choice(sorted(self_edit.PARAM_MENU))
                patches.append({"kind": "param", "path": list(path),
                                "value": self.rng.choice(self_edit.PARAM_MENU[path])})
            elif kind == "prune":
                names = sorted(self.inventory().get("library", {}))
                if not names:
                    kinds.remove("prune")
                    continue
                patches.append({"kind": "prune", "name": self.rng.choice(names)})
            else:
                names = sorted(self.inventory().get("forged", {}))
                if not names:
                    kinds.remove("unforge")
                    continue
                patches.append({"kind": "unforge", "name": self.rng.choice(names)})
        return patches[:k_edit]

    def observe_edit(self, patch: dict, decision: dict) -> None:
        kind = patch["kind"]
        self.edit_credit[kind] = self.edit_credit[kind] + (1.0 if decision["adopted"] else 0.0)
        if decision["adopted"]:
            self.inventory(refresh=True)

    # ---- the channel, outbound ---------------------------------------------------------
    def write_state(self, archive_view: list) -> int:
        if not self.latent_channel:
            return 0
        written = 0
        ordinal = {task["id"]: index for index, task in enumerate(archive_view)}
        for task_id, residue in self._fresh_residues.items():
            if residue.get("best_dsl") and task_id in ordinal:
                signature = self.book.encode_examples(archive_view[ordinal[task_id]]["examples"])
                self.port.write(latent.bind(self.program_vector(residue["best_dsl"]), signature),
                                tag=ordinal[task_id])
                written += 1
        for task_id, solution in self.solutions.items():
            if solution.get("dsl") and task_id in ordinal and task_id not in self._written_solutions:
                self._written_solutions.add(task_id)
                self.port.write(self.program_vector(solution["dsl"]), tag=ordinal[task_id])
                written += 1
        if self.fragments:
            self.port.write(latent.bundle(list(self.fragments.values())), tag=-1)
            written += 1
        return written

    def state_records(self) -> dict:
        """Arm S1 only: structured records instead of vectors."""
        return {"residues": {t: dict(r) for t, r in self.residues.items()},
                "solutions": {t: s.get("dsl") for t, s in self.solutions.items()},
                "fragments": sorted(self.fragments),
                "fragment_sources": {n: list(s) for n, s in self.fragment_sources.items()}}

    def summary(self) -> dict:
        return {"edit_credit": dict(self.edit_credit), "edit_tries": dict(self.edit_tries),
                "forged": self.forged_count, "retrieval_hits": self.retrieval_hits,
                "forge_attempts": {k: sum(1 for v in self.forge_attempts.values() if v == k)
                                   for k in ("found", "none")},
                "solutions": len(self.solutions), "residues": len(self.residues),
                "rejected_programs": sum(len(v) for v in self.rejected.values()),
                "fragments": len(self.fragments)}
