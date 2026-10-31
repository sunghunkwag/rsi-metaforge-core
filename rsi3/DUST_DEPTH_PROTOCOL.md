# Actual two-chunk self-play credit for Q Labs DUST Meta-RL

Pre-result development specification. Compare
`RSI3_META_HONEST_DUST` vs `RSI3_META_HONEST_DUST_DEPTH`.
Only the new `meta_dust_depth` arm flag differs. The same generated
self-play tasks and public programs are used. Each behavioural search
action is evaluated for one chunk as before. In this arm only, an
unsuccessful, non-exhausted action is *resumed for exactly one more
chunk*; its real output is credited as a second training episode
`context(shape,spent_action=1,spent_task=1)`. The first failed
chunk retains its zero label. Candidate expansions during synthetic
training are counted. There is no increased TRAIN wake budget.

This directly addresses a distribution mismatch: previous self-play
taught the search policy almost exclusively what happens after zero
chunks, while deployed action selection often occurs after one or
more failed chunks. The Q Labs DUST gradient estimator is unchanged
and still acts on the MetaPolicy logits. This second-chunk training
intervention is not original Q Labs DUST.

Four generations / seed 11, TRAIN-only, fixed B_wake=64 and B_eval=64;
run all tests, record TRAIN solves, CPU, and practice costs. No
VALIDATION, RESERVE, FAR2 or TEST is opened. Existing published FAR2
is not a clean blind benchmark for modifications inspired by its
failure descriptions. Any follow-up requires pre-registration
before new unseen-family measurements. No performance claim before
measured results and no direct main commits.
