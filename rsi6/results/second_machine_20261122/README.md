# The package on a second machine, 2026-11-22

The first runs of this package on a machine that had never held its data or its working
ledger. Nothing here is in the ledger and nothing here is a registered record. Two questions
were asked, because the registered program was stopped inside generation 2 of process c and
continuing it means continuing on another machine.

## 1. Does a recorded run repeat on another machine?

The 18 incumbent runs of the gate of generation 2 (the version adopted in generation 1, on job
shop, knapsack and set covering, seeds 2021 to 2026) were measured again with
`kernel/run.measure`, four workers, nothing written (`scripts/replay_gate_incumbent.py`,
`replay_gate_incumbent.json`).

| | recorded | here |
|---|---|---|
| runs with the same scores, per-instance scores, counted units and capability digest | | 18 of 18 |
| CPU the gate counts, CPU-seconds | 906.3 | 704.5 |

Scores do not depend on the machine. CPU-seconds do: this machine needs 0.78 of the CPU the
first one recorded, and the factor differs by category (job shop 0.60, knapsack 0.85, set
covering 0.79).

**What follows.** The gate's third condition is a ratio of measured CPU, and a driver that is
started again serves the incumbent's runs from the ledger and measures only the nominee's. On
another machine that ratio compares two machines. The registered driver of process c was
therefore not continued here: its next record would have been a gate with a CPU ratio that
means nothing. Continuing the process on any machine but the first needs a rule for this,
written before the runs, for example measuring the incumbent again beside the nominee.

## 2. The gate that generation 2 had not run

Generation 2's fourth nominee (technique climb, ledger record 4504) was found by the adopted
version acting as the improver. Its gate was computed here with the package's own rule
(`meta/rounds.gate`), the incumbent's records taken from the ledger and the nominee's runs
measured on this machine (`scripts/scratch_gate_c2_climb.py`). The harness was checked first:
from recorded runs alone it gives the recorded gate of the generation's other nominee, with
the same values, lower bound, CPU ratio and conditions.

The nominee's 18 gate runs did not end. After 20 minutes with nothing else running, the four
workers had used 2,393 CPU-seconds, and 3,726 when they were stopped after 32 minutes. The
incumbent's same 18 runs took 455 seconds of wall-clock on the same two cores, at most 909
CPU-seconds. So the nominee costs at least 2.6 times the incumbent on the categories set aside,
and at least 4.1 times by the time it was stopped; the rule allows 1.15. The ratio in the
rule's own count needs the run records and was not obtained, the score conditions were not
measured and the confirmation was not run (`gate_c2_climb_stopped.json`).

**Reading.** By the registered rule this nominee is not adopted, whatever its scores:
generation 2 closes with no adoption, and process c has one adopting generation. The search
that named the nominee held its CPU to 1.25 times the current version on the categories it
searched; on the categories it had not seen the cost did not hold. That is the pattern of the
earlier rounds, for cost instead of score.

The registered record of this gate is still to be written, by the driver, under a rule for
the second machine.
