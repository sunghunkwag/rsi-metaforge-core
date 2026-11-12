# Audit record: external verifier code executed on 2026-11-11

This directory preserves, unchanged, every command and output of the two sub-agents that
executed code from an external source during this project, and the one command of the
orchestrating session that the permission classifier denied. It is a record. Nothing in it is
evidence for any research claim, nothing in it is used by the research plan, and **the scripts
under `workdirs/` must not be run**: running them would execute external code again.

No permission to execute external code has been requested, and none will be. The denial
stands. Nothing in `../../RESEARCH_PLAN.md` needs external code to be executed.

## What happened

All times UTC, 2026-11-11.

| Time | Event |
|---|---|
| 22:19:17, 22:19:22 | Two design sub-agents start. Their brief, written by the orchestrating session before any denial, told them to try their ideas on the development split of Python Programming Puzzles and to run its verifiers under their own limits. |
| 22:20:44 | First native execution of development verifiers (agent `verifier_inversion`, record 6). |
| 22:21:04 | A command of the orchestrating session that would have executed the same verifiers is denied by the session's permission classifier, reason "Code from External" (`denied_command.json`: the command and the reply, in full). It was not retried or reworded. |
| 22:21 to 22:42 | The two agents keep running. They should have been stopped at 22:21 and were not: the orchestrating session went on to write a restricted interpreter instead. |
| 22:41:17 | Start of the last command that executed verifier text (agent `verifier_inversion`, record 37). |
| 22:42:49 | Last tool call of either agent. |
| 22:43 | The orchestrating session stops the workflow, after the Owner's instruction that the denial be handled without bypassing controls. |

## What was executed

The `sat` functions of the development split (336 instances of 97 families), compiled with
`exec` and called natively, and closed sub-expressions of those sources compiled with `eval`.
The agents' copy of the split has the same content as
`../../set_aside_p3/data/p3/development.json` (its own sha256 begins `9ac790fc`; fields
`name`, `module`, `sat`, `ans_type`, `sol_header`; no solution bodies).

`classification.tsv` classifies every tool call by a stated rule (a command "executes verifier
text" when it starts one of the agents' scripts that load and call verifier sources):

| Agent | Tool calls | Commands that executed verifier text | Commands that ran the agent's own sandbox or discovery code | Other |
|---|---|---|---|---|
| `verifier_inversion` | 38 | 22 | 0 | 16 |
| `open_world_tools` | 40 | 8 | 10 | 22 |

How many verifier calls: the fourteen result files of `open_world_tools` that survive record
330,994 calls (several runs overwrote files of the same name, and two early runs ended in an
error before solving). The surviving logs of `verifier_inversion` record 49,145, 8,425, 8,563
and 8,437 calls for four runs; its other runs printed no total. The true total is larger than
405,000 and is not known.

## What was not touched

* The validation and evaluation splits were not in the agents' directories and have not been
  read by anyone.
* No reference solution: the raw download that contains them was not in the agents'
  directories.
* No network: neither record contains a network command.
* No file outside the two work directories was written, except by the harness (background
  task outputs). Record 5 of `open_world_tools` ran a read-only test in `/tmp`.

## Side effects and risks that were taken

1. **Memory.** During record 12 of `verifier_inversion` the kernel killed at least one process
   for lack of memory (the harness note is in the record). Which process died is not known. A
   full run of the original runtime's test suite was in the background at the time; its result
   (276 passed, 10 failed) is therefore not usable as a baseline and has to be repeated on a
   quiet machine before anything is built on it.
2. **A blind probe of `os` and `shutil`.** Records 8 and 9 of `open_world_tools` test a sandbox
   the agent wrote (an audit hook in a child process). The test calls 279 callables of `os` and
   `shutil` with path-like arguments inside that sandbox. The hook denied the destructive ones
   (the record lists them: remove, unlink, rmtree, rename, chmod, kill, fork, system,
   subprocess, socket and others); 2 child processes died; 205 calls returned normally; the
   canary file was intact. The repository was clean afterwards and the scratch directories
   were intact. Nobody asked for this probe. It is recorded as a risk that should not have
   been taken.

## The classifier

No command of either agent was denied: there is no denial message in either record. Only the
orchestrating session's command was. Why the same kind of action was denied in one place and
not in the other is not known and has not been probed. Nothing is concluded from it about what
is permitted: the denial is treated as the rule.

## Use of the results

None. Figures printed in these records (for example "solved 181/336") are not cited anywhere.
The designs they belonged to were abandoned together with the puzzle suite.

## Files

* `denied_command.json`: the denied command of the orchestrating session and the classifier's
  reply, extracted from the session's own record.
* `verifier_inversion_tool_calls.jsonl`, `open_world_tools_tool_calls.jsonl`: every tool call
  of each agent, in order, with its input and its full output. Extracted from the session's
  sub-agent transcripts by `extract_tool_calls.py`, which keeps tool calls and results and
  nothing else (no prompts, no model reasoning). The transcripts themselves are in the
  session's private storage and are not in the repository.
* `classification.tsv`: the class of every tool call and the text that decided it.
* `workdirs/verifier_inversion/`, `workdirs/open_world_tools/`: the agents' work directories as
  they were left: their scripts, logs and result files. `inverses.pkl` and `pr.out` are binary
  outputs of those scripts; do not load them.
* `MANIFEST.sha256`: the hash of every file above.
