# Reference record: the repository IsaiahN/Ouroboros, read on 2026-11-22

Instruction 17 of the Owner (`rsi6/OWNER_DIRECTIVE.md`) names
<https://github.com/IsaiahN/Ouroboros> as a reference for making recursive self-improvement
succeed in a general domain. This directory records what was read, what was found, what was
fetched from outside this package, the two commands the session's permission classifier denied,
and what is and is not carried over. It is a record. Nothing in it is evidence for any research
claim.

Nothing of the reference repository and nothing of the ARC-AGI toolkit was executed or imported,
on this machine or on a GitHub-hosted runner. No file of either is in this repository.

## What was read

The repository was cloned outside this package at commit
`31078e2bfbede37a2d735e570039f10dac8d3293` (dated 2026-02-16; it is the only commit): 359 files,
299 of them Python, 190,492 lines of Python. Read: `README.md`, `loop_state.md`,
`assesment.md`, the first part of `SUBAGENTS_PLAN.md`, `architecture/ORPHANED_SYSTEMS_AUDIT.md`,
`requirements.txt`, the outline and the crossover and mutation code of `evolutionary_engine.py`,
the metadata and the licence headers of the three game files, and the results of text searches
over the Python files. The rest was not read.

## What it is

A population of agents that play the games of ARC-AGI-3 and write what they observe to one
SQLite database that all of them read ("horizontal transfer", "viral packages"). An agent
chooses each action through a ladder of 67 hand-written components ("rungs") built on a file of
hand-written perceptual primitives (`seed_primitives.py`, 616 KB).

* **No language model at run time.** No Python file imports a client library of a language
  model or names an endpoint or a model of one (text search). `torch` is imported by one file
  (`representation_learner.py`); one checkpoint of 7.7 MB is in `models/`.
* **The environment.** The games are reached through the official toolkit (`arc_agi`,
  `arcengine`). Three game files are in `environment_files/`: `ls20-cb3b57cc`, `ft09-9ab2447a`,
  `vc33-9851e02b`, each a Python program under the MIT licence of the ARC Prize Foundation,
  each with the human action count of every level in its `metadata.json`.
* **What its evolution changes.** Six numbers in [0, 1] (`exploration_weight`,
  `conservative_bias`, `action_diversity`, `score_optimization_priority`,
  `win_focus_threshold`, `action_efficiency_preference`), one choice among five click patterns
  and thirteen further numbers it calls epigenetic, by crossover, mutation and inheritance
  (`evolutionary_engine.py`). The ladder, the primitives and the code are not changed by it.
* **What changes its code.** Coding agents driven by a language model: `SUBAGENTS_PLAN.md`
  ("Based on: Copilot Instructions v3.0 + Full Codebase Audit"), `.github/copilot-instructions.md`,
  and the table of `loop_state.md`, which has two rows of diagnosis and fix.

## What its own records say it has reached

`loop_state.md`, "Current Metrics Snapshot (post iter 2, gen 5112)" and "Known Persistent
Problems":

| | |
|---|---|
| Levels completed | 242 in 38,357 games (0.0063 per game) |
| `ls20` | about 240 levels in about 19,000 games |
| `ft09` | 2 levels in about 335 games |
| `vc33` | 0 levels in about 18,853 games |
| Whole games won | none (`alignment_velocity: 0.00 (no full game wins)`) |
| Its health gauges | report "EXCELLENT"; its own note: this "may not reflect actual system health" |

`architecture/ORPHANED_SYSTEMS_AUDIT.md` (2026-02-03): about 25 context keys read by rungs and
set by nothing; 131 database tables defined and never written.

Its README reports no score. No file read shows a later generation improving faster because of
what an earlier one changed. As a reference it is an attempt on a general benchmark, not a
method known to work.

## Its domain: ARC-AGI-3, as of 2026-11-23

* Launched 2026-03-25. 25 public, 55 semi-private and 55 private environments. No instructions:
  an agent sees a 64 by 64 grid, has up to seven actions, and must find out the rules and the
  goal. A level scores (human actions / actions used) squared, capped at 1.15; a game is the
  mean over its levels weighted by level number; on the leaderboard a level is cut off at five
  times the human count. At launch the best language model scored below 1 per cent
  (<https://arxiv.org/abs/2603.24621>).
* The leaderboard of the ARC Prize Foundation, read 2026-11-23
  (<https://arcprize.org/leaderboard>): the four newest large language models (rows dated
  2026-11-09 to 2026-11-17) are at 54.9 to 81.2 per cent with the standard harness and at 97.7
  to 100.0 with the provider harness; smaller models on the same page are below 6. The human
  panel is at 100.
* Systems without a large language model: in the preview competition of 2025 the best scored
  12.58 per cent; a method with no training at all, a graph of visited states explored
  systematically, came third and solved a median of 30 of 52 levels of six games
  (<https://arxiv.org/abs/2512.24156>, <https://arcprize.org/competitions/arc-agi-3-preview-agents>).
  The results of the 2026 competition are announced on 2026-12-04
  (<https://arcprize.org/competitions/2026>).
* The toolkit is under the MIT licence and runs the games locally. Three games are open to an
  anonymous key; the other public games need a free registered key
  (<https://docs.arcprize.org/available-games>).

## ARC-AGI-3 against the admission rule of this package

`RESEARCH_PLAN.md`, section 2, admits a benchmark as an environment if (a) to (f) hold.
(a) holds: the games are published by others. (b) holds: the scoring rule is public. (c) holds:
every level has a human action count. **(d) does not hold**: a game is a Python program, and its
rules are not published as a specification (that the rules are hidden is the point of the
benchmark), so an evaluator cannot "be written from the specification without executing
third-party code". Running a game is executing third-party code. (e) and (f) were not examined.

So the games cannot be an environment of this package as its rules stand. Changing rule (d) is
an amendment, and amendments are the Owner's (`OUTER_LOOP_CONSTITUTION.md`).

## What was fetched from outside this package

| What | How | What was done with it |
|---|---|---|
| The reference repository | `git clone`, outside this package | read |
| `arc_agi-0.9.10-py3-none-any.whl`, sha256 `cbe3d69384cbb90d415a699e4ea3ccff39511eb1ff7df06d248c7782715b8a4e` | `pip download --no-deps` from PyPI | unpacked and read; not installed, not imported |
| `arcengine-0.9.3-py3-none-any.whl`, sha256 `5f9739d6d0055780a4581fd6fe09066bb08775c4c8212c9adcca2eb008aef59c` | the same | the same |
| `https://arcprize.org/api/games` | one `GET` without a key | answer 401 "unauthorized"; no key was requested, no game was downloaded |
| Pages of arcprize.org, docs.arcprize.org, arxiv.org | read through the session's web tools | the facts of the section above |

## The two denied commands

`denied_commands.json` has both, with the replies.

1. A command that would have installed the toolkit into a virtual environment and imported it,
   as the first step of a probe (an agent without a language model on the three games open to
   anonymous users). The classifier denied it. It was not retried or reworded, the probe was
   dropped, and the work was not moved to a GitHub-hosted runner, which would have been the
   same action somewhere else.
2. A command that would have read the session's own transcript to find the time stamp of the
   first for this record. Denied; not retried. The time of the first is given as an interval.

As in `../external_code_execution_20261111/`: no permission to execute external code is
requested. Whether the toolkit is ever run for this project is decided by the Owner, together
with rule (d).

## What is carried over, and what is not

**Carried over: the form.** An agent that acts step by step in a state machine whose rules it
is not told, and is scored by the steps it used against a reference, is the third form this
package's plan already names ("steps accepted by a state machine", `RESEARCH_PLAN.md`,
section 2) and has not built. Under rule (d) its carriers are state machines defined by
published files with public semantics: IPC STRIPS planning problems (C2), where the reference
is a best-known plan length, and Metamath (C1). The scoring rule of ARC-AGI-3, the square of
reference steps over steps used with later instances weighing more, is a candidate measure
there. None of this is built; it is a proposal for the Owner.

**Not carried over.**

* Evolving a handful of numeric weights over a fixed, hand-written system. Rounds 1 and 2 and
  process c of this package are that already, over the fields of a version, with gates.
* A store that every agent reads and writes. The relay's memory is the corresponding mechanism
  here, and its development check D2 was negative (`../../results/dev_r_d2_20261122/`).
* Gauges of the system's own health as a measure of progress. The reference reports
  "EXCELLENT" beside no game won. In this package only a registered test on categories a
  modification was not chosen on counts, and that stays.
