# External task corpus

RSI-2 uses DreamCoder's published `data/list_tasks.json`, acquired once through
the configured HTTPS Git proxy from
<https://github.com/ellisk42/ec> at upstream commit
`cb0e63f5c33cd2de360b791038b0f5272750270e` on 2026-10-02. The complete, unchanged
217-task JSON is retained as `data/source_list_tasks.json`, with the unchanged
upstream MIT notice in `data/LICENSE`. Acquisition details are in
`data/provenance.json`. No network requests occur when loading or running tasks.

The preferred Josh Rule repository names `list-function`, `list-functions`, and
`list_function` returned repository-not-found through the Git proxy; the
authorized DreamCoder alternative was available. DreamCoder's own JSON loader
documents records as `{name, type: {input, output}, examples: [{i, o}]}`. These
are external named list routines and their parameter variants, including list
and scalar outputs. We use the published examples directly. We do not use the
90 MB depth-composition corpus `list_tasks2.json`, construct new reference
functions, generate labels, or filter tasks by RSI-2 expressibility or success.

Each source task has 15 example records. Identical inputs are deduplicated in
their original order; there are no conflicting labels. The first ten distinct
inputs become search examples; every remaining distinct input becomes hidden
evaluation. Ten source tasks have fewer than eleven distinct inputs, so cannot
provide the required ten search inputs plus a separate hidden input. Their
names and counts are recorded in provenance. All other 207 tasks are eligible.
Original external input/output types are retained, with an independent
example-type consistency check; even an all-empty list output keeps its
declared element type.

To fit the 24 CPU-hour experiment limit, `random.Random(20261002)` shuffles the
sorted eligible identifiers once. The first 60 are selected without inspecting
DSL representability or solver results. The first 36 selected tasks form TRAIN,
the next 12 VALIDATION, and the last 12 TEST. The exact assignment and eligible
population are committed in `data/split_manifest.json`. `corpus.split_ids`
replays this procedure. The unit of splitting is a named parameterized task;
different parameter variants of one source routine can appear in different
partitions.

`corpus.load_train()` and `corpus.load_validation()` are fixed, argument-free
development capabilities. `corpus.parse_task()` parses an already supplied
record and opens no files. Only `sealed_evaluation.load_test()` opens
`data/test.json`; that separate module imports parsing and frozen search,
without importing learning modules. Its measurements are reporting outputs and
cannot be used for grammar, library, recognition, heuristic, or budget decisions.

Budget calibration uses VALIDATION only, once, before any learning module
exists. The budget selection, search limits, validation solve fraction, and
timing belong in `data/calibration.json`; this corpus acquisition does not
choose budgets or measure TEST performance.
