# RSI MetaForge Core

[![CI](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/ci.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/ci.yml)
[![RSI-6 tests](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/rsi6-tests.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/rsi6-tests.yml)

An experiment on **recursive improvement of a capability-acquisition mechanism**: one
learner enters every environment with the same code, modifies its own learning mechanism,
and keeps a modification only when it passes a gate on kinds of environment the search did
not see. The environments are published benchmark families from operations research and
prediction, fetched as data and scored against their published references.

**Status: no recursive self-improvement has been observed.** One modification of the learner
has passed a registered gate on four categories no learner had run on (process d, generation
1; below). That is the first half of the hypothesis for one step, and it rests on one of the
four categories. A design built to exercise the second half, in which the improver is the
learner's own acquisition procedure (design s; below), did not show it in development, and
its tables show that no improver had a second step to find. Every registered number is in the
hash-chained ledger
[`rsi6/ledger/main.jsonl`](rsi6/ledger/main.jsonl); the full account, misses first, is
[`rsi6/RESULTS.md`](rsi6/RESULTS.md).

## The hypothesis

> A system that modifies its own capability-acquisition mechanism, and adopts only
> independently validated modifications, becomes better at acquiring capabilities in kinds
> of environment it has never met, at matched compute; and the modified mechanism is also
> better at producing the next modification.

It fails if the modified mechanism is not better on unseen kinds of environment, or is
better only by what extra compute, retained solutions, better uninformed search or chance
explain. The protocol is [`rsi6/RESEARCH_PLAN.md`](rsi6/RESEARCH_PLAN.md); the directive it
answers is recorded verbatim in [`rsi6/OWNER_DIRECTIVE.md`](rsi6/OWNER_DIRECTIVE.md).

## What has been measured

| Process | What could be modified | Outcome |
| --- | --- | --- |
| Rounds 1 and 2 (first design) | a version record of 38 fields written by the experimenter | 4 nominees (the learner's own and a random proposer's, in each round); none passed its gate |
| Round b1 (second design) | the same kind of record, redesigned | 2 nominees; none passed. At equal counted units the redesign acquired no more than the first design and cost 1.3 to 3.8 times the CPU |
| Process c (four techniques in turn) | the 38-field record | generation 1 adopted one version provisionally (7 fields; gate +0.0176 with lower bound +0.0066, confirmation +0.0035). Generation 2, from the adopted version: three nominees did not pass; the fourth has no registered gate yet, and computed outside the ledger it costs at least 2.6 times the incumbent's CPU where the rule allows 1.15. Stopped there; six generations are registered |
| Open design | the learner's representation and its learning principle, as programs of a small vector machine; in the recursive arm each accepted mechanism re-learns how the next candidates are generated | 152 discovery steps, 912 candidates, 18 confirmations, **0 accepted** in every arm. The recursion was never exercised |
| Relay (design r) | the discovery machinery, rebuilt at every acquisition from the learner's own record | development only. Its second development check is negative: on a category it had not met, the learner carrying the relay's memory acquired 0.0078 less than the learner carrying nothing (24 chains, 80% interval −0.0147 to −0.0010). Not registered, not run |
| Scan of generation 0 (development, 2026-11-22) | one field of the 38-field record at a time, every change measured on every category of the pool, the few it picks out measured again on new seeds | development only. The change the scan put first did not hold on new seeds. One did, twice, the second time fixed before the run: `model.batch` 4 → 2 adds +0.0246 to what is acquired over the nine categories (5 % point +0.0154) at 1.04 times the CPU, +0.0066 (5 % point +0.0009) with set covering, which carries most of it, left out, and is above zero on the three categories it was picked without. The statistic by which the continued process ranks candidates in its search (amendment 2: no category counts for more than +0.01) puts it at +0.0037; the registered gate, which decides an adoption, counts the plain mean. A candidate for a registered test, not a result: [`rsi6/results/dev_landscape_20261122/`](rsi6/results/dev_landscape_20261122/) |
| Design s (development, 2026-11-23 to 24, instruction 19) | one search procedure that is the learner's acquisition and, with the fields of the improving version, the improver of versions; two steps that adapt inside a search; all 324 mechanisms of its list measured on eight categories (36,864 runs), chains of self-modification run on those tables from every mechanism, read by rules fixed beforehand | **none of the three statistics holds.** On categories the chains did not read they end +0.0011 above their starts (0.005 was needed); a chain whose improver is the current version ends where one ends whose improver stayed the start (+0.0000); a uniformly drawn nominee does as well (+0.0002). Mechanisms that acquire more are not better improvers (rank correlation −0.28). With every table in hand, the best version chosen on seven categories is −0.0070 against the adopted version on the eighth: the list holds no second step. The registered stage was not run. [`rsi6/results/design_s_20261124/`](rsi6/results/design_s_20261124/) |
| After the adoption (development, 2026-11-23) | the same scan one step on, and the recursion question asked with the learner's own acquisition loop as the improver | no second step: of the five changes the scan around the adopted version picked out, none held on new seeds (largest mean +0.0015, 5 % point −0.0025), while settings that help one category hurt another. The recursion run gave no answer: no improver, changed or not, produced a next step. [`G1.md`](rsi6/results/dev_landscape_20261122/G1.md), [`rsi6/results/dev_recursion_20261122/`](rsi6/results/dev_recursion_20261122/) |
| Process d, generation 1 (amendment 6) | one field, `model.batch` 4 → 2, the change the scan left standing; put once through the registered gate against generation 0 on four categories no learner had run on, 32 seeds at the gate and 32 at the confirmation | **passed, narrowly.** Gate +0.0195 (10 % point +0.0135, CPU 1.04 times generation 0's); confirmation +0.0009. With both halves, quadratic 0-1 is up by 0.055, weighted tardiness by 0.005, project scheduling is flat and maximum clique is down by 0.018. Adopted as generation 1 of process d. Not recursion: as an improver the adopted learner is generation 0 exactly. [`rsi6/results/gate_d1_20261122/`](rsi6/results/gate_d1_20261122/) |

Not run yet: the external gate of process c, the recursion check, and the test on the
sealed target categories that decides the hypothesis. No learner has run on the two reserves
or the four sealed targets.

What limits the result, as measured (details in `rsi6/RESULTS.md`):

* Modifications found on one set of categories did not carry over to new ones. Every
  nominee the learner found by following its own measurements lost on the gate categories;
  the two that came closest were single-field changes proposed at random.
* In the open design almost every edit of a program made the learner worse (mean effect
  -0.018 against a one-seed noise of 0.009), and the few that looked better on the
  discovery seeds were not better on fresh seeds (+0.0080 against +0.0000).
* The versions of the first three processes are points of a closed list. The improver
  chooses among values; it cannot write a mechanism that is not on the list.
* Where the first design stands, what it acquires is bounded by what the weights of its
  policy can express, not by its search: 16 times the training budget adds about 0.02 where
  it was tried, and of 324 search mechanisms measured in full none beats the adopted version
  on a category it was not chosen on. A second step, and with it any recursion, needs a
  learner that can acquire more, not a better search for the same weights.
* Every environment is an assignment problem or a prediction problem in one generic form.
  Nothing is claimed about software, proof, planning or judgement: they are not in the
  experiment.

## The learner and its interface

The learner (`rsi6/learner/`) sees no environment by name. The kernel
(`rsi6/kernel/problem.py`) presents every instance in one of two generic forms: an
*assignment* problem (variables take options; the published objective and constraints appear
as term groups with exact incremental totals) or a *prediction* problem (observed entities
with targets, query entities to predict). Entity order and labels are permuted on every run.
Compute is enforced in counted work units and measured in CPU-seconds. No code of the
experiment calls a language model or executes third-party code.

Three numbers are measured on fresh instances, never on training ones: *untrained* (the
learner's uninformed behaviour), *acquired* (after acquisition) and *gain* (the difference).

## Environments

Adapters exist for 19 published benchmark families. Data are not committed: `rsi6/fetch.py`
downloads each file from its publisher and pins it by SHA-256 in
[`rsi6/environments/manifests/`](rsi6/environments/manifests/).

| Role | Categories | Source |
| --- | --- | --- |
| source | bin packing, job shop, forecasting | OR-Library, JSPLIB, M4 |
| adoption sets 1 to 3 (used once as gates, then joined the pool) | quadratic assignment, p-median; multidimensional knapsack, regression; set covering, graph partitioning | QAPLIB, OR-Library, SRSD-Feynman, DIMACS |
| targets (sealed; no learner has run on them) | satisfiability, vehicle routing, facility location, generalised assignment | SATLIB, CVRPLIB, OR-Library |
| reserves (external gate of process c; no learner has run on them) | travelling salesman, graph colouring | TSPLIB, DIMACS |
| adoption set 5 (held out until 2026-11-22, used once as the gate of process d, then joined the pool) | weighted tardiness, quadratic 0-1, project scheduling, maximum clique | OR-Library, Biq Mac, PSPLIB, DIMACS |

Learner runs recorded so far: 9,630: 9,118 on the nine source and adoption categories of
the first processes and 512 at the gate of process d.

## Reproduce

Python 3.13 and NumPy; nothing else.

```bash
pip install numpy
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

python -m rsi6.tests.test_kernel         # kernel, adapters and the learner's contract (fetches the data)
python -m rsi6.tests.test_fresh          # the adapter checks on the fresh categories
python -m rsi6.tests.test_design_q
python -m rsi6.tests.test_design_r
python -m rsi6.tests.test_relay
python -m rsi6.tests.test_design_s       # design s: the learner, its list of mechanisms, chains on tables

python -m rsi6.experiments.report        # every number of the rounds, from the ledger
python -m rsi6.experiments.replay        # every search again, from the ledger alone
python -m rsi6.open.report               # every number of the open experiment
python -m rsi6.open.diagnose --ledger rsi6/ledger/main.jsonl   # what limited its discovery
```

## Layout

```
rsi6/
  OWNER_DIRECTIVE.md   the research directive and every later instruction, verbatim
  RESEARCH_PLAN.md     the protocol
  RESULTS.md           what was measured, misses first
  kernel/              problem forms, environment contract, measured runs, ledger, role locks
  learner/             the learner: first and second design, the open design (o), designs q, r and s
  meta/                the space of versions and the rounds of self-modification; chains of design s on tables of measured runs
  experiments/         drivers of the registered rounds, process c, external gate, recursion check, target test
  open/                discovery of mechanisms for the open design; the relay driver and report
  environments/        adapters and data manifests of the 19 benchmark families
  registry/            registrations, amendments, roles, corrections (written before the runs they govern)
  runs/                plans for long runs on GitHub-hosted runners (.github/workflows/rsi6-runs.yml)
  ledger/main.jsonl    append-only, hash-chained record of every run and decision
  results/             reports printed from the ledger, development records, the check on a second machine
  audit/               records of independent reviews and audits
  tests/
docs/                  governance records: work orders, a draft amendment, the outer-loop ledger
OUTER_LOOP_CONSTITUTION.md
```

## What is not claimed

* No recursive self-improvement was observed.
* An adoption inside process c is provisional and is not evidence of improvement on unseen
  categories; that is decided once, on the reserves and the sealed targets.
* The thresholds are operating points chosen before the runs, not external facts.
* Nothing here is evidence about artificial general intelligence.

## Governance

The repository is run under [`OUTER_LOOP_CONSTITUTION.md`](OUTER_LOOP_CONSTITUTION.md):
work orders are approved by the Owner, predictions are registered before final runs, and
misses are scored, not reinterpreted. The constitution and its two earliest drafts
(`docs/amendments/A1_learned_proposal_layer.md`,
`docs/work_orders/WO-1_phase_r_learned_proposal_layer.md`) were written for the earlier
runtime and still refer to it; they are kept unchanged because only the Owner amends them.

## Earlier work

Until 2026-11-22 this repository also held the earlier program-synthesis line of the
project: a stack-VM runtime on integer-list tasks (`rsi_levels_metaforge_unified.py`,
Phases 0 to P) and the packages RSI-2, RSI-3 and RSI-5 on DreamCoder's list tasks. They were
removed from the tree by the Owner's instruction of that date
(`rsi6/OWNER_DIRECTIVE.md`, instruction 15) so that the repository is about one question.
Nothing was rewritten: the complete earlier tree, with its results and its negative
findings, stays in the history.

* [`c4f0a86`](https://github.com/sunghunkwag/rsi-metaforge-core/tree/c4f0a8627a1c9f37dd3aa6291b0eee0c78648210):
  the unified runtime, `EVIDENCE.md`, the Phase 0 to P records under `docs/`, RSI-2 and the
  first two studies of RSI-3.
* [`572100d`](https://github.com/sunghunkwag/rsi-metaforge-core/tree/572100d05234b5d48f4ce01b34c28a87bc8ad0d0): the same, with
  the later studies of RSI-3, RSI-5 and the exploratory loops.

## Support

See [FUNDING.md](FUNDING.md).

---

<sub>Intelligence Research Project. A research artifact: results, terminology and
implementation are experimental and subject to revision.</sub>
