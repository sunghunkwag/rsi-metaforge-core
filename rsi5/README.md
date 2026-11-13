# RSI-5: two-closure bootstrap

The vocabulary of a program-synthesis system as the object of its self-improvement.
RSI-2 and RSI-3 kept their grammar frozen and improved how it was searched; RSI-5 lifts
that freeze for this package only, measures what a larger budget and the vocabulary
DreamCoder's list domain had (and RSI-2 lacked) buy by enumeration alone, and then
builds a loop that invents primitives from the residuals of external failures behind a
sealed statistical gate. The directive is [OWNER_DIRECTIVE.md](OWNER_DIRECTIVE.md);
what exists now is in [ARCHITECTURE.md](ARCHITECTURE.md).

**Status.** Phase 1 (the engine, §3) is built and measured: [PREDICTIONS_P1.md](PREDICTIONS_P1.md)
was registered before the run, [RESULTS_P1.md](RESULTS_P1.md) scores it, misses first.
The §3.3 gate failed at the registered budget, so Phases 2–3 (§4–§7) are not built. An
adversarial review of the Phase 1 pull request followed: the sealing, the run driver and
the documents were corrected, and the engine's defects are pinned by tests and deferred
to a new registration ([RESULTS_P1.md](RESULTS_P1.md), "Adversarial review").

## What is here

| Part | Where | Notes |
| --- | --- | --- |
| The language C1 | [`dsl/`](dsl/) | Fork of `rsi2/{types,terms,evaluator,grammar}.py` with a pair type and the restored primitives `unfold index fix1 is_prime is_square zip pair fst snd`, constants 3 4 5 ([`dsl/VOCABULARY.md`](dsl/VOCABULARY.md)). In the reference interpreter every primitive terminates under the step budget. Two vocabularies: `original` (RSI-2's) and `restored`. |
| The engine | [`engine/`](engine/) | Bottom-up enumeration by size with observational equivalence on the public inputs plus a frozen probe set ([`data/probe_set.json`](data/probe_set.json)); normal-form filter ([`engine/NORMAL_FORMS.md`](engine/NORMAL_FORMS.md)); vectorised first-order evaluation and compiled closures for higher-order constructions; deterministic, budget-monotone. The fast paths differ from the interpreter in known ways that cost completeness, never correctness ([`tests/test_review_findings.py`](tests/test_review_findings.py)). |
| The verifier | [`verifier.py`](verifier.py) | Frozen; the only module outside `judge/` that reads hidden examples; receipts; one query per task per generation. |
| The judge J | [`judge/`](judge/) | Byte-for-byte copy of `rsi4/judge/` at `c48c820` with its pools, seed and manifest; `data/stage_train.json` beside it. Never edited; not used in Phase 1 (see ARCHITECTURE.md for the conflict its unchanged evaluator creates for Phase 2). |
| Sealing | [`guard.py`](guard.py), [`tests/test_guard.py`](tests/test_guard.py), [`tests/test_sealing.py`](tests/test_sealing.py) | An audit hook, a tripwire and not a wall: J's directory and RSI-2's unexposed task file cannot be opened, listed, entered, linked or renamed by any name, J cannot be imported, no other program can be started. Statically: J's own audit over every solver module, a short list of permitted imports, no name of the sealed partition. `guard.py` lists what the hook does not stop. |
| Partitions | [`partitions.py`](partitions.py) | The exposed partitions through the read-only `rsi2`/`rsi3` loaders; TEST's file is never opened and no TEST record becomes a task. |
| Phase 1 run | [`phase1.py`](phase1.py), [`runs/p1.json`](runs/p1.json), [`results_p1/`](results_p1/), [`report_p1.py`](report_p1.py), [`audit_p1.py`](audit_p1.py) | Enumeration only, both vocabularies, every exposed partition, B = 10⁶ with the 10³–10⁵ counts read off the same deterministic run; a report-only generalisation audit of the verified programs. Search workers are forked before any task is loaded and receive public examples only; the driver holds the hidden examples and the verifier. |

## Run it

```bash
pip install numpy                      # rsi2/rsi3 loaders need it; rsi5 itself is standard library
export PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m unittest discover -s rsi5/tests -t .          # unit, anti-cheat and throughput tests
python -m rsi5.phase1 --output NEW_DIR --partition fresh1 --vocabulary restored --workers 4
python -m rsi5.report_p1 --results NEW_DIR
python -m rsi5.audit_p1 --results NEW_DIR           # report-only generalisation audit
```

The registered run is `python -m rsi5.phase1 --plan rsi5/runs/p1.json --output rsi5/results_p1`.
On GitHub Actions, a push to a branch named `rsi5/run-<name>` runs `rsi5/runs/<name>.json`
one (vocabulary, partition) per job (`.github/workflows/rsi5-runs.yml`).

## Rules kept

Standard library and NumPy only; no network at run time; no transformer or attention
layer. No learned controller, value model or policy in Phases 1–3. TEST is never opened.
J's pools are read by J only. Hidden examples are read only by the frozen verifier and
by J. Predictions are registered before every final run and misses are scored first.
`rsi2/`, `rsi3/`, `rsi4/`, `docs/` and the unified runtime are read-only. No personal
names in the package. Attribution: Intelligence Research Project.
