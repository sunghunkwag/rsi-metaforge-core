# Behavioral Novelty Search: exploratory RSI-4 pilot

This is an **isolated, opt-in experiment**, not a modification to the registered
RSI-4 Phase 1 trajectory or the external evaluation service. Everything in the
existing RSI-2, RSI-3, RSI-4 pipeline remains unchanged.

## Scientific basis

Joel Lehman and Kenneth O. Stanley, *Abandoning Objectives: Evolution through
the Search for Novelty Alone*, Evolutionary Computation 19(2), 2011,
DOI: [10.1162/EVCO_a_00025](https://doi.org/10.1162/EVCO_a_00025).

The original method selects candidates by behavioral sparseness rather than
distance to an assumed fixed objective:

    novelty(x) = mean_{y in nearest_k(x, population_without_x + archive)} d(x, y)

This pilot uses:

1. The incumbent RSI-3 self-curriculum candidate generator, without changes.
2. A 25-dimensional descriptor built only from public examples: 17 public
   RSI-3 relation features plus eight bounded input/output statistics.
   Neither the generating program nor any target performance measure is used.
3. Euclidean k-NN sparseness against the current candidate population and a
   distinct, FIFO bounded historical archive.
4. The *same* one-chunk minimal-criterion search used by the incumbent to
   discard trivially solved generated tasks.
5. Sort the remaining tasks by novelty (descending, name-ordered ties) rather
   than input order. Keep the same maximum number of tasks sent to the
   *unchanged* verifier-backed solver.
6. Archive selected hard behaviors whether or not the solver solves them.
   Add only actually solved programs to the RSI-3 curriculum pool. The
   inherited sleep-phase learner remains in control of any library changes.

**This is novelty-guided task selection, not proof of unrestricted open-ended
evolution.** A finite task generator, small public descriptor and a fixed
primitive vocabulary still constrain the reachable space. The nearest-
neighbor function adds CPU work not included in candidate-evaluation counts.

## Run

    pip install numpy
    export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
    python -m unittest rsi4.tests.test_novelty
    python -m unittest discover -s rsi4/tests -t .
    python -m rsi4.novelty_pilot --smoke
    python -m rsi4.novelty_pilot --generations 4 --output /tmp/novelty-dev.json

The pilot prints **development-only** trajectories for the same seed, number
of generations, public TRAIN tasks, baseline engine, and training budgets.
No unopened evaluation partition is read for selection, early stopping or
tuning. The smoke flag uses only eight TRAIN tasks and reduced budgets:
it tests wiring, not generalization.

## Registered follow-up required before any performance claim

- Freeze the new code and choose archive capacity and k using a dedicated
  development instrument (not previously exposed holdout scores).
- Pre-register three or more seeds, fixed candidate-evaluation *and* CPU
  budgets, the candidate generator and stop conditions.
- Compare the incumbent curriculum ordering with novelty ordering and
  randomized ordering under identical budgets. Include an ablation for the
  eight continuous behavior features.
- Preserve the external evaluation's isolation; never inspect its task
  contents or choose policies from its one-time confirmation results.
- Report failures and neutral results, changes in verified library entries,
  retained-task forgetting, and transfer to genuinely unseen task families.

The original runtime and pre-registered RSI-4 evidence should stay separate
until an owner-approved study shows a repeatable gain.
