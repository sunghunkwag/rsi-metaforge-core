# SWARM

Adversarial co-evolution over a shared latent channel, judged by a frozen
kernel. A **Breaker** manufactures tasks (public examples, a checker
program, a sealed witness); a **Builder** solves them with a program
synthesizer it owns and may rewrite through kernel-judged self-edits; the
two exchange nothing but vectors in a shared VSA field, aligned by a
mapper trained on paired events only. The kernel certifies every task by
execution (Ka feasibility, Kb difficulty against a frozen snapshot, Kc
novelty, Kd well-posedness), counts every logical cost, checks crossings
by execution on hidden instances with own-solution fragments excluded,
and keeps a hash-chained ledger that replays. `OWNER_DIRECTIVE.md` is the
specification; `ARCHITECTURE.md` says what was built and where it is
narrower than the specification.

**What is reported is the crossing curve of a self-posed task archive
under a frozen executor; it is not a benchmark result and not a
general-capability claim.** Nothing here reads TEST, VALIDATION or any
human-set task.

## Status

P0–P5 built and tested (67 unit tests: kernel, certificates, crossings,
self-edit judge, executor guard, replay, agents, channel, interface,
search checkpoint, review fixes). The P4 pilot is recorded in
[`pilot/PILOT.md`](pilot/PILOT.md); an adversarial review of the package
was folded in before registration (commit 969d2be: own-solution
exclusion of learned weights, guarded executor, kernel failures as
non-verdicts, judge on open tasks, replay digests, forge accounting).
`PREDICTIONS.md` and `experiment_config.json` are the registration; the
final runs and `RESULTS.md` follow (P6).

## Layout

| Path | What |
| --- | --- |
| `kernel/` | the frozen kernel: checker language and executor, vault, meter, ledger and replay, admission, archive, crossing, snapshots, self-edit judge, runtime; hash-pinned (`pins.json`) |
| `latent.py`, `mapper.py` | the field (ported HDC/VSA) and the paired-events mapper |
| `breaker/` | the setter: program vocabulary, four lineages, regret credit |
| `builder/` | the solver: `mutable/` (generation-0 tree from RSI-2 and RSI-3, Builder-owned), `agent.py`, `forge.py`, `self_edit.py` |
| `loop.py`, `experiment.py`, `report.py` | one generation, the arms runner, the report (curves, K1–K7) |
| `tests/` | the integrity invariants as tests |

## Running

```sh
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

# unit tests (about two minutes; subprocesses)
python -m unittest discover -s swarm/tests -t .

# a short development run of one arm
python -m swarm.experiment --config swarm/pilot_config.json --output NEW_DIR --arms SWARM_FULL --generations 3

# the registered runs (P6)
python -m swarm.experiment --config swarm/experiment_config.json --output NEW_DIR
python -m swarm.report --results NEW_DIR --output report.md --replay

# replay one run's ledger (fast), or with the Kb and crossing solves re-run
python -m swarm.kernel.replay NEW_DIR/SWARM_FULL_seed11 [--full]
```

A run directory holds `ledger.jsonl` (the hash chain), `vault.json` (the
kernel-only artifact replay needs), `archive.json`, `run_config.json`,
`snapshots/` (every content-addressed tree the kernel ran), `live/` (the
Builder's tree) and `summary.json`. The runner refuses to overwrite a
non-empty output directory. Python 3.11+ and NumPy; no model, no network.
