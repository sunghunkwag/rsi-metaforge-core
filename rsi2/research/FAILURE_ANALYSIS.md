# What the first improvement loop failed to improve

The completed first study did not establish RSI. Its development evidence shows
two coupled stalls: all three FULL seeds retained the same six TRAIN solutions,
and the improver repeatedly confirmed programs that could not execute.

Across the 24 FULL development rounds, 30 always-unsolved TRAIN tasks consumed
46,080 of 46,498 wake candidates (99.1%). There was no new library abstraction
to expand the improver's effective vocabulary. Repetition alone created no new
learning signal. The remaining difficulty may involve the bounded search space,
proposal coverage or compression's bootstrap requirement; these observations
do not identify a single proven cause of task-learning failure.

The improvement procedure has a more directly testable failure. Its 144 slots
contained only six distinct ASTs. Every four-task screen solved zero tasks, so
index-based ties repeatedly selected the same two `head(nil)` variants for all
48 full confirmations. The frozen evaluator reports `head of empty list` for
both. Type compatibility did not imply a runnable improvement. Runtime failures
fell back to zero priority, allowing the failed candidates to resemble the
incumbent. Those confirmations consumed 33,148 inner task candidate attempts;
the entire heuristic stage consumed 8,517.788 of FULL's 11,357.587 CPU seconds.

The follow-up separates the levels of intervention:

- Object level: a task heuristic can change only on strict hidden-verified
  VALIDATION gain without losing a solved confirmation task.
- Loop level: runtime probes, persistent frontier/history and correctly scoped
  evaluation memory alter how improvement candidates are generated and tested.
- Meta-loop level: a proposal ranker learns from previous verified candidate
  outcomes and changes which proposals reach expensive confirmation. Its quality
  proxy must beat a static novelty control before it is called an improvement.

Two regression risks deserve explicit verifiers. Grammar insertion order affects
search ties, so cached measurements must preserve it. Also, a candidate-constant
nonzero score can change the frozen queue's evaluated prefix through partial/
complete scheduling; apparent gains from such a score receive no capability
credit. The follow-up rejects input-constant candidates rather than altering the
original interpreter, search or completed study.

`PROTOCOL.md` fixes the comparisons before fresh-family performance is measured.
Per-cycle reports and raw records decide keep/revise/reject. More runnable or
novel candidates can verify a procedure gain, but cannot establish cumulative
task improvement or recursive self-improvement by themselves.
