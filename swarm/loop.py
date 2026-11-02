"""One SWARM generation (OWNER_DIRECTIVE.md §6): the Breaker poses, the kernel certifies, the Builder attacks,
the kernel checks crossings, the Builder learns and self-edits under the kernel's judgement, both agents
write the field, the mapper is refit, the kernel ledgers the generation.

    1. Breaker reads the Builder's region and proposes n_prop triples; the
       kernel seals, certifies (K0, Kd, Ka, Kc, Kb against the snapshot
       taken at the start of the generation) and ledgers each.
    2. Builder reads the Breaker's region (retrieval boosts through the
       mapper), attacks the open tasks it has not solved under B_gen minus
       what its forge spent last generation, from its live tree
       (checkpointed search frontiers, failure memory, its allocation);
       every wake solution goes through the kernel's mined-solve gate.
    3. Kernel runs the crossing check on every open task admitted before
       this generation, from the generation's snapshot at B_inst with
       everything learned from the task itself excluded.
    4. Builder learns through its tree's own adoption rule from
       kernel-verified programs, then proposes at most k_edit patches; each
       candidate tree passes the Builder's scope guard and the kernel's
       judge (crossings per budget on the archive, no regression, isolation
       guard) and is adopted or discarded.
    5. Both agents write their state into the field (vectors; records in
       arm S1); the mapper is refit from scratch on every (task signature,
       crossing program) pair.
    6. Kernel retires open tasks beyond the horizon to markers and appends
       the generation summary to the ledger.

No step reads text between the agents (arm S1 excepted, by design), no
step reads a benchmark, and nothing here computes a reward: the kernel
counts, the agents keep their own credit from the kernel's decisions.
Every number in the ledger is deterministic in (arm, seed, config); wall
time is kept out of it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import time

from swarm import latent
from swarm.breaker.agent import Breaker
from swarm.builder import self_edit
from swarm.builder.agent import Builder
from swarm.kernel import PINS
from swarm.kernel.admit import CERTIFICATES
from swarm.kernel.runtime import KernelRuntime
from swarm.kernel.snapshot import tree_sha256
from swarm.mapper import Mapper

ROOT = Path(__file__).resolve().parents[1]
GENERATION0 = ROOT / "swarm" / "builder" / "mutable"


@dataclass(frozen=True)
class ArmConfig:
    name: str
    latent: bool = True        # vectors cross the field
    records: bool = False      # S1: structured records cross instead
    mapper: bool = True        # S2: raw similarity, no codebook alignment
    self_edit: bool = True     # S3: no patches, no forge
    learn: bool = True         # the generation-0 tree's own library learning
    regret: bool = True        # S4: credit per admitted task instead
    shuffled: bool = False     # S5: every written vector is permuted


ARMS = {
    "SWARM_FULL": ArmConfig("SWARM_FULL"),
    "SWARM_RECORDS": ArmConfig("SWARM_RECORDS", latent=False, records=True, mapper=False),
    "SWARM_NO_MAPPER": ArmConfig("SWARM_NO_MAPPER", mapper=False),
    "SWARM_NO_SELFEDIT": ArmConfig("SWARM_NO_SELFEDIT", self_edit=False),
    "SWARM_NO_BREAKER_REGRET": ArmConfig("SWARM_NO_BREAKER_REGRET", regret=False),
    "SWARM_SHUFFLED_FIELD": ArmConfig("SWARM_SHUFFLED_FIELD", shuffled=True),
    # Sanity row, not a registered comparison: nothing in the tree changes,
    # so no crossing can occur by the kernel's definition.
    "SWARM_FROZEN": ArmConfig("SWARM_FROZEN", self_edit=False, learn=False),
}


class Run:
    def __init__(self, arm: ArmConfig, seed: int, config: dict, run_dir: Path):
        self.arm, self.seed, self.config = arm, int(seed), config
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.live = self.dir / "live"
        self_edit.copy_tree(GENERATION0, self.live / "mutable")
        self.candidates_root = self.dir / "candidates"
        budgets = config["budgets"]
        self.kernel = KernelRuntime(self.dir, b_inst=budgets["B_inst"],
                                    probe_seed=config["breaker"]["probe_set_seed"], horizon=config["horizon"],
                                    executor_timeout_s=budgets["executor_timeout_s"],
                                    executor_mem_mb=budgets["executor_mem_mb"],
                                    regression_sample=config["builder"].get("regression_sample", 6))
        kernel = self.kernel
        self.meter, self.ledger, self.archive = kernel.meter, kernel.ledger, kernel.archive
        self.snapshots, self.admission, self.crossings, self.judge = (kernel.snapshots, kernel.admission,
                                                                      kernel.crossings, kernel.judge)
        d = int(config["latent"]["D"])
        self.field = latent.Field(d=d, shuffled=arm.shuffled, seed=kernel.field_nonce(self.seed))
        self.mapper = Mapper(ridge=config["mapper"].get("ridge", 1.0)) if arm.mapper else None
        self.breaker = Breaker(self.field.port("breaker"), kernel.breaker_runner, self.seed, d,
                               lineages=tuple(config["breaker"]["lineages"]), regret=arm.regret,
                               latent_channel=arm.latent, mapper=self.mapper, records=arm.records)
        self.builder = Builder(self.field.port("builder"), self._solver, kernel.builder_runner,
                               self.live / "mutable", self.seed, d, latent_channel=arm.latent,
                               mapper=self.mapper, enable_self_edit=arm.self_edit,
                               enable_forge=arm.self_edit and bool(config["builder"]["forge"]),
                               records=arm.records)
        # The forge spends the Builder's budget: at most a quarter of B_gen
        # per generation, charged as candidate evaluations, and the next
        # wake gets B_gen minus what the forge spent.
        self.builder.forge_limit = int(budgets["B_gen"]) // 4
        self._forge_spent = 0
        self.generation_number = 0
        self.crossings_cumulative = 0
        self.history: list = []
        self.wall_started = time.perf_counter()
        self.ledger.append("run", {"arm": arm.name, "arm_config": asdict(arm), "seed": self.seed,
                                   "config": config, "kernel_sha256": PINS,
                                   "generation0_sha256": tree_sha256(self.live / "mutable")})

    # ---- what the Builder is handed ---------------------------------------------------
    def _solver(self, function, payload):
        return self.kernel.live_call(self.live / "mutable", function, payload)

    def _tree_facts(self) -> dict:
        forged = json.loads((self.live / "mutable" / "forged.json").read_text(encoding="utf-8"))
        library = json.loads((self.live / "mutable" / "library.json").read_text(encoding="utf-8"))
        params = json.loads((self.live / "mutable" / "params.json").read_text(encoding="utf-8"))
        return {"primitives_forged": len(forged), "library_entries": len(library.get("entries", {})),
                "params": params}

    # ---- one generation ---------------------------------------------------------------
    def generation(self) -> dict:
        g = self.generation_number + 1
        self.generation_number = g
        self.meter.mark_generation(g)
        timings, clock = {}, [time.perf_counter()]

        def lap(name):
            now = time.perf_counter()
            timings[name] = round(now - clock[0], 2)
            clock[0] = now

        sha = self.snapshots.take(self.live / "mutable")
        if self.arm.records:
            view = self.archive.public_view()
            self.breaker.records_in = self.builder.state_records()
            self.builder.records_in = self.breaker.state_records(view)
        # 1. Breaker proposes; kernel certifies.
        view = self.archive.public_view()
        proposals = self.breaker.propose(g, view, self.kernel.ledger_view(), self.config["breaker"]["n_prop"])
        admitted, margins = [], []
        rejections = {c: 0 for c in CERTIFICATES}
        kernel_failed = 0
        for proposal in proposals:
            key = proposal.pop("key")
            decision = self.admission.admit(proposal, g, sha)
            self.breaker.observe_admission(g, key, decision, self.archive.public_view())
            if decision["admitted"]:
                admitted.append(decision["id"])
                margins.append(float(decision["kb_margin"]))
            elif decision.get("kernel_failed"):
                kernel_failed += 1
            else:
                rejections[decision["certificate"]] += 1
        lap("propose_and_admit")
        # 2. Builder reads the field and attacks.
        view = self.archive.public_view()
        boosts = self.builder.read_state(view)
        open_tasks = [t for t in view if t["status"] == "open"]
        wake_budget = max(0, int(self.config["budgets"]["B_gen"]) - self._forge_spent)
        wake = self.builder.attack(g, open_tasks, wake_budget)
        mined, mined_failed = [], 0
        for task_id, solution in wake["solved"].items():
            accepted = self.crossings.mined(task_id, solution["program"], g)
            self.builder.observe_mined(task_id, accepted)
            if accepted:
                mined.append(task_id)
            elif accepted is None:
                mined_failed += 1
        lap("wake_and_mined")
        # 3. Crossing checks from the generation's snapshot.
        checks_failed_before = len(self.ledger.of_kind("crossing_check_failed"))
        crossed = self.crossings.check([t["id"] for t in open_tasks], sha, g)
        crossing_checks_failed = len(self.ledger.of_kind("crossing_check_failed")) - checks_failed_before
        retrieval_hits = 0
        for task_id in crossed:
            crossing = self.archive.tasks[task_id]["crossing"]
            self.breaker.observe_crossing(task_id, crossing["generations_to_crossing"])
            retrieval_hits += bool(set(crossing["fragments"]) & set(boosts.get(task_id, {})))
        lap("crossing_check")
        # 4. Builder learns and proposes self-edits; kernel judges.
        view = self.archive.public_view()
        learned = self.builder.learn(g, view) if self.arm.learn else {"adopted": [], "offered": 0}
        lap("learn")
        edits = []
        forge_before = self.meter.total("builder")["evaluations"]
        if self.arm.self_edit:
            incumbent = self.snapshots.take(self.live / "mutable")
            patches = self.builder.propose_edits(g, view, self.config["builder"]["k_edit"])
            lap("propose_edits")
            for index, patch in enumerate(patches):
                candidate = self_edit.make_candidate(self.live, self.candidates_root / f"g{g}", index, patch)
                violations = self_edit.guard(candidate, self.live)
                if violations:
                    decision = self.judge.refuse(g, patch, "scope: " + "; ".join(violations))
                else:
                    decision = self.judge.judge(candidate / "mutable", incumbent, g, self.dir, patch)
                    if decision["adopted"]:
                        self_edit.adopt(candidate, self.live)
                        incumbent = self.snapshots.take(self.live / "mutable")
                self.builder.observe_edit(patch, decision)
                edits.append({"kind": patch["kind"], "adopted": decision["adopted"], "reason": decision["reason"],
                              "incumbent_solved": decision["incumbent_solved"],
                              "candidate_solved": decision["candidate_solved"]})
                shutil.rmtree(candidate, ignore_errors=True)
        self._forge_spent = self.meter.total("builder")["evaluations"] - forge_before
        lap("judge")
        # 5. Both agents write the field; the mapper is refit from scratch on paired events.
        view = self.archive.public_view()
        written = {"breaker": self.breaker.write_state(view), "builder": self.builder.write_state(view)}
        mapper_fit = None
        if self.mapper is not None:
            pairs = [(self.breaker.signatures[t["id"]], self.builder.program_vector(t["crossing"]["dsl"]))
                     for t in self.archive.crossed_tasks()
                     if t["id"] in self.breaker.signatures and t["crossing"].get("dsl")]
            mapper_fit = self.mapper.fit(pairs)
            self.ledger.append("mapper", {"generation": g, **mapper_fit})
        # 6. Retire beyond the horizon; ledger the generation.
        retired = self.archive.retire(g)
        self.breaker.observe_retired(retired)
        self.crossings_cumulative += len(crossed)
        builder_total = self.meter.total("builder")
        facts = self._tree_facts()
        summary = {
            "generation": g, "snapshot": sha, "archive": self.archive.counts(),
            "proposals": len(proposals), "admitted": len(admitted), "rejections": rejections,
            "kernel_failed": kernel_failed,
            "kb_margin_mean": (sum(margins) / len(margins)) if margins else None,
            "open_attacked": len([t for t in open_tasks if t["id"] not in self.builder.solutions]),
            "wake_budget": wake_budget, "forge_candidates": self._forge_spent,
            "wake_failed": bool(wake.get("failed")), "wake_solved": len(wake["solved"]), "mined": len(mined),
            "mined_checks_failed": mined_failed, "crossing_checks_failed": crossing_checks_failed,
            "judge_failed": sum(1 for e in edits if "evaluation failed" in e["reason"]),
            "crossings": len(crossed), "crossed_ids": crossed,
            "crossings_cumulative": self.crossings_cumulative,
            "crossings_per_budget": (self.crossings_cumulative / builder_total["evaluations"]
                                     if builder_total["evaluations"] else 0.0),
            "retrieval_hits": retrieval_hits, "retired": len(retired),
            "budget": {agent: self.meter.generation_total(g, agent) for agent in ("breaker", "builder", "kernel")},
            "budget_cumulative": {agent: self.meter.total(agent) for agent in ("breaker", "builder", "kernel")},
            "primitives_forged": facts["primitives_forged"], "library_entries": facts["library_entries"],
            "params": facts["params"],
            "learned": learned.get("adopted", []), "learn_offered": learned.get("offered", 0),
            "self_edits": {"proposed": len(edits), "adopted": sum(e["adopted"] for e in edits), "decisions": edits},
            "lineage_credit": dict(self.breaker.credit), "lineage_multiplier": dict(self.breaker.multiplier),
            "field": self.field.statistics(), "written": written,
            "mapper": mapper_fit,
        }
        self.ledger.append("generation", summary)
        lap("write_and_summarize")
        # Wall-clock phase timings go to summary.json only; the ledger stays deterministic.
        self.history.append(dict(summary, timings=timings))
        self.checkpoint()
        return summary

    def run(self, generations: int, wall_cap_s: float | None = None, log=None) -> dict:
        for _ in range(int(generations)):
            summary = self.generation()
            if log is not None:
                log(summary)
            if wall_cap_s is not None and time.perf_counter() - self.wall_started > wall_cap_s:
                break
        return self.checkpoint()

    # ---- artifacts ----------------------------------------------------------------------------
    def checkpoint(self) -> dict:
        self.kernel.checkpoint()
        summary = {"arm": self.arm.name, "seed": self.seed, "config": self.config,
                   "generations": self.history,
                   "final": {"archive": self.archive.counts(), "crossings": self.crossings_cumulative,
                             "generations_to_crossing": sorted(t["crossing"]["generations_to_crossing"]
                                                                for t in self.archive.crossed_tasks()),
                             "tree": self._tree_facts(), "breaker": self.breaker.summary(),
                             "builder": self.builder.summary(), "meter": self.meter.snapshot(),
                             "executors": self.kernel.timeouts()},
                   "ledger_digest": self.ledger.digest(), "ledger_entries": len(self.ledger.entries),
                   "wall_seconds": time.perf_counter() - self.wall_started}
        self.kernel.write_atomic(self.dir / "summary.json", json.dumps(summary, indent=1, default=str) + "\n")
        return summary
