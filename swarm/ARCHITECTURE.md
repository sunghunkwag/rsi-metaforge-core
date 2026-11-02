# SWARM architecture

SWARM is an adversarial co-evolution loop between two agents that share
one latent field, judged by a frozen kernel. The **Breaker** manufactures
tasks as `(public examples, checker, witness)` triples; the **Builder**
solves them with a program-synthesis substrate it owns and may rewrite;
the **kernel** certifies tasks, counts cost, checks crossings by execution
and keeps an append-only ledger. The reported quantity is the crossing
curve of the self-posed archive. The directive is `OWNER_DIRECTIVE.md`;
this file says what was built, how each directive clause was read, and
where the implementation is narrower than the clause.

```mermaid
flowchart LR
    subgraph Breaker
        L[lineages: mutate, compose,<br/>analogy, distinguisher] --> P[proposals]
        R[regret credit, R3 slots] --> L
    end
    subgraph Kernel
        A[admission K0 Kd Ka Kc Kb] --> AR[(archive)]
        V[(witness vault)]
        X[crossing check<br/>fresh B_inst solve,<br/>own fragments excluded]
        J[self-edit judge]
        M[meter] --- LG[(hash-chained ledger)]
        S[(content-addressed snapshots)]
    end
    subgraph Builder
        W[wake on the live tree<br/>resumable, failure memory] --> MI[mined-solve gate]
        LE[learning: the tree's own rule] --> SE[self-edit patches<br/>forge, unforge, param, prune]
    end
    F{{latent field<br/>breaker region | builder region}}
    MP[mapper<br/>paired events only]
    P --> A
    AR --> W
    W --> X
    SE --> J
    J -->|adopt| S
    Breaker <-->|vectors| F
    Builder <-->|vectors| F
    F --- MP
```

## 1. The frozen kernel (`swarm/kernel/`)

Every kernel file (`hashes.py` and the package `__init__.py` included)
and the Builder's evaluator are hash-pinned (`kernel/pins.json`);
importing `swarm.kernel` verifies the pins and aborts on a mismatch
(`tests/test_integrity.py`).

| Piece | File | What it does |
| --- | --- | --- |
| Checker language | `checker_lang.py` | JSON S-expressions over ints, bools, lists, strings and tuples: `lambda`, `rec` (bounded recursion), `let`, `if`, `and`/`or`, about 55 primitives (arithmetic, comparison, `map`/`filter`/`fold`, `sort`, `reverse`, `unique`, `take`/`drop`, `zip`, `count`, `index-of`, strings). Step, depth, integer-size and length limits. Richer than the Builder's generation-0 DSL by design. |
| Executor | `executor.py` | Runs programs in a guarded child (`python -s -P -B`, fixed environment with `PYTHONHASHSEED=0`, memory cap `RLIMIT_AS`, wall-clock timeout), batched; a timeout fails the whole batch and charges no steps. The guard is an audit hook installed before any import: the child reads only its own tree, the kernel package and the Python installation, writes only inside its tree, imports no other `swarm` module, and cannot spawn processes, open sockets or load native code. `isolated_call` runs a function of a Builder tree the same way (the directive's filesystem path guard, §9). `accepts` is the one verdict routine (program on the hidden inputs, checker on the outputs) and reports an executor failure separately from a rejection. Three executor instances share one meter so that steps are charged to the kernel, the Breaker or the Builder. |
| Witness vault | `vault.py` | Write-once; holds each sealed task's witness, checker and hidden instances. Every accessor is `sealed_*`; the AST audit asserts no module outside `kernel/` names a vault symbol. |
| Budget meter | `budget.py` | The sole counter of logical cost: interpreter steps and candidate evaluations, per generation, agent and module. No other module charges it (`test_meter_is_the_sole_cost_counter`). |
| Ledger and replay | `ledger.py`, `replay.py` | Append-only SHA-256 chain of every proposal, certificate outcome, admission, mined solve, crossing, self-edit decision, mapper refit, live-call failure and generation summary. `replay` first checks that `vault.json` and `archive.json` hash to the digests the ledger recorded at sealing (witness, checker, hidden instances, public examples) and agree with the admission and crossing records, then re-derives Kd, Ka and Kc from the sealed data (fast) and Kb and the crossing solves from the snapshots (`--full`). Written atomically. |
| Admission | `admit.py` | K0 structure (well-formed programs, 8 public and 6 hidden instances with distinct inputs, values in the shared domain), **Kd** well-posedness (the checker returns a bool on every instance, for the witness's output and for null outputs), **Ka** feasibility (the witness reproduces the public outputs and the checker accepts it on every hidden instance), **Kc** novelty (behaviour on the canonical probe set and the public example set are new), **Kb** difficulty (the Builder snapshot taken at the start of the generation, run fresh at `B_inst`, does not produce a program the checker accepts on every hidden instance; its best public match is the Kb margin). An executor failure while Kb runs is retried once and then ledgered as `kernel_failed` (disposition `K!`): neither an admission nor a rejection, and not a wasted proposal for the Breaker. |
| Archive | `archive.py` | The public face of admitted tasks: examples, lineage, status (`open`, `crossed`, `marker`), admission and crossing generations, the crossing program and its DSL term. Open tasks older than the horizon become markers: kept, never deleted, no longer checked. |
| Crossing | `crossing.py` | **Mined solve**: a wake solution run on the hidden instances; accepted ones may be learned from, and are not crossings. **Crossing**: the current snapshot, run fresh at `B_inst` on the public examples with everything learned from the task itself excluded (its sourced library entries and forged primitives, every entry that references one of them, and the grammar weights refit without the task's own solutions), yields a program the checker accepts on every hidden instance. The record carries the program, its fragments (closed through the library entries' bodies) and their source tasks. Verdicts are memoized per snapshot; a task admitted in the current generation is not checked (Kb ran on the same snapshot); a failed executor check leaves no verdict and is ledgered. |
| Snapshots | `snapshot.py` | Content-addressed copies of the Builder's mutable tree (`sha256` over paths and contents). Kb, crossing checks and the judge run `mutable.solve` from a snapshot in an isolated child. `call_tree` is the metered call into the live tree for the wake. Timeouts scale with the requested budget. |
| Self-edit judge | `edits.py` | A candidate tree is snapshotted and solved on every open task plus a sample of six crossed tasks, with own-task exclusion, at `B_inst`; so is the incumbent (cached). Adopted iff accepted solves of **open** tasks per candidate spent on them strictly increase and no crossed task of the sample the incumbent solves is lost (the sample is the regression test only). An executor failure on either side refuses the candidate and caches nothing. An isolation guard requires every file of the run directory outside the candidate and its snapshot to be unchanged (size and mtime) across the evaluation. |
| Runtime | `runtime.py` | Wires all of the above over a run directory; the loop never names the vault. Live-call failures (crash, timeout) are ledgered with the child's error. The forge's program checks are charged as Builder candidate evaluations. Checkpoints are atomic; the vault dump is owner-readable only and, like the rest of the run directory, outside what the guard lets a Builder tree read. The field's shuffle permutation (S5) is seeded here from the run seed through a kernel-side hash; an agent could recompute it only by reproducing kernel code, which the import audit forbids. |

## 2. The latent field (`swarm/latent.py`) and the mapper (`swarm/mapper.py`)

Ported from the original core's `HDCSpace` (§9) and the §14 sequence
encoding: bipolar vectors, `bind` = elementwise product (its own inverse),
`bundle` = majority, `permute` = cyclic shift, `similarity` = normalized dot
product, `analogy(a, b, c) = c ⊗ a ⊗ b`, position-permuted sequence
bundling. Each agent has a `Codebook` (symbol → fixed random vector,
deterministic in its seed) and a `Port` that writes to its own region and
reads the other's. What crosses is `np.ndarray` only; a write of anything
else raises. Items carry an integer tag: the archive ordinal of the task
they concern (both agents already know the ordinals from the public
archive view), or −1 for a summary vector. Arm S5 permutes every written
vector by a fixed secret permutation.

The mapper is kernel ridge regression (dual form) between the Breaker's
task vectors and the Builder's program vectors, fit from scratch every
generation on the pairs (signature of a crossed task, vector of the
program that crossed it) and on nothing else; `fit_from_events` drops any
event missing either side. `task_to_program` carries a Breaker signature
into the Builder's program space for retrieval; `program_to_task` carries
a Builder residue vector into task space for the analogy lineage. Before
the first crossing the mapper is the identity, so S0 behaves as S2.

## 3. The Breaker (`swarm/breaker/`)

`programs.py` is the setter vocabulary: 66 seed bodies in the checker
language (stages the generation-0 DSL lacks, such as `sort`, `reverse`,
`unique`, `take`, `drop`, `count`, `index-of`, `append`; and stages within
its reach, such as `map`, `filter`, `fold`, `head`, `tail`, `cons` with
small arithmetic), one-step mutations (a constant, a primitive swap, a
wrapping stage) and composition (`outer(inner(x))`, inner list-valued).

`agent.py` proposes `n_prop` triples per generation from four lineages
with separate credit: **mutate** (an archived witness or a seed, mutated),
**compose** (two crossed witnesses, or seeds), **analogy** (for an open task
T and a crossed task C: `D = analogy(S_C, P_C, S_T)` in the Breaker's task
space, with the Builder's residue vector for T mapped into task space and
bundled into `S_T`; the proposal is the mutation of T's or C's witness
whose signature is nearest to D), and the **distinguisher** (inputs on which
the Builder's crossing program for a crossed task disagrees with the
witness; a task with those inputs among its public instances). Public and
hidden instances are drawn from the witness on random distinct inputs; a
proposal whose witness is constant on the public examples, is the
identity, or fails on too many inputs is dropped as wasted.

Credit: with regret, a lineage is paid `1/(1 + generations_to_crossing)`
when one of its tasks crosses; rejected and retired tasks are wasted; S4
pays 1 per admitted task. Slots per generation follow the original core's
R3 rule: one slot per lineage, the rest in proportion to a bounded
multiplier that rises when validated outcomes exceed wasted ones.

The Breaker writes each admitted task's signature (bundle over position ⊗
input ⊗ output of its public examples) when the task is admitted and when
its status changes, plus one bundle of lineage-credit symbols. It reads
the Builder's region directly.

## 4. The Builder (`swarm/builder/`)

`mutable/` is the generation-0 tree: RSI-2's typed DSL, evaluator,
enumerator, grammar, MDL abstraction learner and RSI-3's resumable search
and failure memory, copied, with three additions: a `METER` in the pinned
evaluator, forged primitives (`forged.json`, run through the checker
language inside the evaluator), a compiler from DSL terms to the checker
language (`compile.py`), and the entry points `solve_many`, `learn`,
`inventory` (`solve.py`). `params.json` holds the parameters the Builder
may change. The Builder's library learning is the tree's own rule: the
generation-0 default learns from kernel-verified wake solutions (RSI-2's
rule, with the mined-solve gate as the verifier); `learn.from = crossed`
restricts it to crossing programs.

`agent.py`: each generation the Builder reads the Breaker's region, maps
each open task's latest signature through the mapper, retrieves the three
nearest fragment vectors and boosts their grammar weights for that task
(`boost`), attacks the open tasks it has not solved under `B_gen` (even
split, or committed to high partial matches, as `allocation.strategy`
says) through the kernel's metered live call with persistent search state
(checkpointed search frontiers per task and grammar order, failure memory), hands wake solutions to the mined
gate, learns, then proposes at most `k_edit` patches: a **forge** (the
first checker-language body over a template vocabulary of depth ≤ 2 that
reproduces the public examples of its highest partial-match residue, as a
new primitive sourced from that task; each residue task is forged at most
once), and from a menu, a **param** change, a library **prune** or an
**unforge**, kinds weighted by their own adoption record. It writes the
residue vector of each task it failed this generation (the program vector
of its best partial match bound to the task's signature), each solution
once, and a bundle of its fragment vectors. A fragment vector is the name
token bundled with the sequence-permuted body tokens; a program vector is
the sequence-permuted token bundle bundled with the unordered token bag.

`self_edit.py`: a patch is applied to a copy of the live tree; `guard`
rejects a candidate whose files other than `forged.json`, `params.json`
and `library.json` differ from the live tree's; `adopt` copies those three
files back when the kernel says yes. `forge.py` is the forge enumerator.

## 5. The loop (`swarm/loop.py`), arms and measurements

One generation: snapshot → Breaker proposes, kernel certifies → Builder
reads, attacks, mined gate → crossing check on every open task from the
generation's snapshot → Builder learns and proposes patches, kernel judges
→ both write the field, mapper refit → retire beyond the horizon, ledger
the generation summary (archive counts, admissions and rejections per
certificate, mined and crossed, crossings per Builder budget, primitives
and library size, self-edits proposed and adopted with their solve deltas,
lineage credit, field norms, mapper residual, per-agent budget).

| Arm | Flag | What differs |
| --- | --- | --- |
| S0 `SWARM_FULL` | | the design |
| S1 `SWARM_RECORDS` | `records` | no vectors: the Breaker receives the Builder's residues (DSL text, match fraction), solution text and fragment names; the Builder receives per-task lineage, status and output kind, and boosts fragments whose source tasks share the open task's output kind; the analogy lineage picks by token overlap |
| S2 `SWARM_NO_MAPPER` | `mapper=False` | retrieval and analogy by raw similarity across the two codebooks |
| S3 `SWARM_NO_SELFEDIT` | `self_edit=False` | no patches and no forge; the generation-0 library learning stays on (the tree runs as written at generation 0) |
| S4 `SWARM_NO_BREAKER_REGRET` | `regret=False` | credit per admitted task |
| S5 `SWARM_SHUFFLED_FIELD` | `shuffled` | every written vector is permuted before storage |
| `SWARM_FROZEN` | `self_edit=False, learn=False` | sanity row, not a registered comparison: no substrate change, so no crossing is possible by definition |

`swarm/report.py` computes X(g), ΔX, the last-half second differences,
frontier motion, substrate growth, channel statistics, collapse detectors
and the K1–K6 rules; K7 runs the replay. `swarm/experiment.py` runs arms ×
seeds with one process per job.

## 6. Interpretations and restrictions, stated

- **Self-edit is structured, not free-form.** The directive lets the
  Builder rewrite "search code"; this implementation rewrites the tree's
  data files through four operators and refuses any candidate whose
  Python differs from the live tree. The evaluator is pinned because its
  meter is the Builder's cost; nothing else in the tree is pinned, but
  nothing else is rewritten either. A free-form code-edit operator was
  not built.
- **Judge counts crossings in the kernel's sense.** Own-fragment exclusion
  applies inside the judge, so a forged primitive is adopted only when it
  lets other tasks be solved at `B_inst`. Parameter changes that affect
  only future learning (`learn.*`) cannot show a strict gain and are never
  adopted; they stay on the menu and cost one judge evaluation each.
- **Retrieval reaches crossings indirectly.** The kernel's fresh solves use
  no boosts; the channel acts on the wake, whose mined solutions feed the
  tree's learning. The retrieval hit rate counts crossings whose program
  used a fragment that was boosted for that task in the wake.
- **Tags are integers both agents already know.** Archive ordinals label
  items in the field; they carry no information beyond the public archive
  view. The regret estimate per task is not written (only lineage credit).
- **The Breaker's vocabulary is designer-written**, as in Phase K's setter
  policies; it straddles the generation-0 DSL on purpose so that mutations
  and compositions can land on the frontier. Kc rejects duplicates.
- **S3 keeps generation-0 learning**; `SWARM_FROZEN` is the fully frozen row.
- **Timeouts are wall-clock**, generous (step budgets bind first), and a
  caveat on determinism across machines; the byte-identical re-run is the
  check.
- **Horizon.** Open tasks older than `horizon` generations become markers
  and stop being checked, which bounds the kernel's per-generation cost;
  they count as never crossed.
- **The forge spends the Builder's budget.** Every forge body checked
  against a task's public inputs is a candidate evaluation; a quarter of
  `B_gen` is reserved for the forge each generation and the wake gets
  the rest, so every arm's Builder spends at most `B_gen` candidate
  evaluations per generation (S3, with no forge, gives the wake all of
  `B_gen`; an arm with a forge that finds nothing to forge leaves the
  reserve unspent).
- **The learning corpus is part of the tree.** `library.json` keeps one
  rewritten solution per source task; the stored weights are the fit on
  that corpus, and an own-task exclusion refits without the excluded
  tasks. Learning from a task's own mined solution therefore cannot
  cross it (`test_review_fixes`), and the exclusion is transitive
  through library bodies.
- **Kernel failures are counted, not interpreted.** A crashed or
  timed-out child during Kb, a mined check, a crossing check or the judge
  is ledgered (`kernel_failed`, `mined_check_failed`,
  `crossing_check_failed`, a refused self-edit) and reported in the
  summaries; it never becomes a certificate, a crossing or an adoption.
- **The analogy lineage reads the public archive.** Its program vector
  `P_C` is the Breaker's own encoding of the crossing program's DSL text
  from the archive's public view (a kernel record), not a vector the
  Builder wrote; the field contributes the task signatures and the
  Builder's residue, solution and fragment vectors through retrieval.
  S2 and S5 therefore act on the mapper and on what the Builder reads,
  not on `P_C`.
- **Floating point in the ledger.** The mapper's residual is a BLAS
  float rounded to six decimals before it is ledgered; the retrieval
  sign decisions are taken on BLAS outputs. Byte-identity of the ledger
  holds on one machine and library build; the re-run check is on the
  same machine.
- **The records arm keeps the latent arms' lag.** A task the Breaker has
  not recorded yet (admitted this generation) is not boosted in S1, as
  it cannot be in the latent arms, whose signature is written one
  generation after admission.
- **A wake solution the gate could not check** (executor failure) is
  resubmitted next generation; one the gate rejected on the hidden
  instances is passed over in later windows (the search's skip set), so
  the window does not stall on it.
- **What the guard does not cover.** `pwd` and `grp` (imported by
  `pathlib`) read the system account files through C calls that raise
  no audit event, and a directory listing of the repository root or the
  `swarm` package exposes file metadata beyond names; neither reaches
  the run directory or the vault. Native-code escapes through `ctypes`,
  `_ctypes`, `mmap`, sockets and subprocesses are denied at import.
- **The library is capped** at 64 entries (`learn.max_library`, not on
  the self-edit menu): adoption stops at the cap, so solver cost per
  candidate stays bounded; pruning by a judged edit reopens room.
- **The excluded refit is conservative.** A corpus solution of another
  task that was rewritten with an entry sourced from the excluded task
  is left out of the refit (its original form is not kept), so the
  excluded grammar has at most the evidence of the counterfactual, never
  more: the exclusion can lose a crossing, not invent one.
- **Retrieval boosts reach fitted weights.** The grammar looks a
  production up by `name/arity` and by context before the plain name, so
  a boost multiplies every key that can answer for the fragment. Before
  this fix (commit after 46308bf) a boost on a fitted grammar was inert,
  which the pilot did not expose because no arm's grammar had been fit
  while a boost was offered.

## 7. Integrity invariants and the tests that hold them

| Invariant (directive §9) | Test |
| --- | --- |
| kernel hash-pinned, abort on mismatch | `test_integrity.test_kernel_is_hash_pinned`, `test_tampering_with_a_kernel_file_aborts_import` |
| vault unreadable outside the kernel | `test_vault_symbols_appear_only_in_the_kernel` |
| agents do not read each other or the kernel | `test_interface.test_agents_do_not_read_each_other_or_the_kernel`, `test_agents_share_exactly_one_package_import` |
| Kb on the admission snapshot, not the live tree | `test_kernel.test_kb_uses_the_snapshot_not_the_live_tree` |
| crossing attribution excludes own fragments | `test_kernel.test_crossing_requires_other_sourced_substrate_and_replays`, `test_builder.test_improving_edit_adopted_regressing_edit_discarded` |
| one shared import, `np.ndarray` only | `test_interface.*` |
| mapper fit on paired events only | `test_latent.*` |
| meter the sole cost counter | `test_integrity.test_meter_is_the_sole_cost_counter` |
| self-edit isolation; writes outside the tree rejected | `test_builder.test_candidate_that_writes_outside_its_tree_is_rejected`, `test_review_fixes.GuardTests` |
| filesystem path guard in the executor | `test_review_fixes.GuardTests.test_child_cannot_read_the_run_directory_or_import_agents` |
| own-solution exclusion covers learned weights and dependent entries | `test_review_fixes.OwnSolutionExclusionTests` |
| kernel failures are not verdicts | `test_review_fixes.KernelFailureTests`, `test_review_fixes.JudgeTests` |
| replay checks the artifacts' digests | `test_review_fixes.ReplayTests` |
| forge checks charged as Builder evaluations; timeouts charge nothing | `test_review_fixes.AccountingTests` |
| import audit resolves relative imports, bans dynamic-import and object-graph names, scans the mutable tree | `test_interface.test_relative_imports_are_resolved`, `test_agents_do_not_read_each_other_or_the_kernel`, `test_mutable_tree_imports_only_the_checker_language` |
| fixed hash seed in every child | `test_review_fixes.GuardTests.test_child_hash_seed_is_fixed` |
| determinism | the byte-identical re-run recorded in RESULTS.md |

## 8. Claim boundary

What is reported is the crossing curve of a self-posed task archive under
a frozen executor; it is not a benchmark result and not a
general-capability claim. The archive is the Breaker's; nothing in
`swarm/` reads TEST, VALIDATION or any human-set task.
