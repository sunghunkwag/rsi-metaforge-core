# Causal screening and persistence revision

Registered from the still-running frozen seed11 recursive TRAIN pilot before
running any revised method. The original pilot/source/artifacts stay intact.

## Measured failure

Generation0 and generation1 wake solve the same5/36 tasks. Independent audit
finds that every B16 screen of all six own-generated heuristic candidates has
zero descendants and zero parent selections: the verified bank and initial
root prefix exhaust its entire candidate budget. All six screen AST sequences
are identical and all scores are1/4. The scorer's only causal action is choosing
future edit parents, which the screen never exercises. Its confirmation order
therefore assigns credit by index ties instead of measuring that action.

Separately, at490.10 process CPU seconds the completed kernel searches sum
to217.59 CPU seconds. Repeated serialization of the growing12.36MB checkpoint
accounts for much of the remaining272.51 seconds; a single independently
measured exact write costs2.062 CPU seconds. This overhead makes the registered
600-second eight-generation pilot unrealistic. Efficiency is not a capability
or RSI result.

## Interventions and mechanisms

Use a budget-dependent initial-root quota shared by all arms and scorers:
at most floor(B/2) bank plus fresh roots, at most floor(B/4) bank roots, and
at least one fresh root whenever B is positive. Fresh prefix is capped16.
For B16 this leaves at least eight opportunities for the causal edit stage;
for B64 the cold prefix remains16. Bank selection is deterministic from the
same supplied proof-ID order, without task-name branching. B1 cannot reserve
both stages and is reported as such. No candidate evaluation is refunded.

Replace repeated whole-history persistence with an append-only journal of
immutable completed searches/generations and a small atomic live checkpoint.
Reconstruction must recover every original field, candidate AST, provenance,
counter, proof and ordering exactly. Journal writes and reconstruction CPU
remain measured. This intervention changes persistence overhead, not task
outcomes or verifier definitions.

## Verification and admission

Before TRAIN execution, verify under B16 that own-enumerated informative DSL
scorers can alter descendant production, that zero/no scorer sequences match,
and that all controls obey identical root/candidate/structural/compiler limits.
Compare journal versus original persistence on the same frozen complete and
partial records; reconstructed values must be exactly equal. Interrupted
journals must retain every committed operation and explicitly mark uncommitted
work as a lower bound. Reject either intervention if provenance or accounting
changes, or if screening still has no causal edit stage.

Then run a separately bounded TRAIN-only diagnostic with the same state,
bank, grammar, candidate caps and task order, changing only root reservation.
Report real hidden-verified solved sets, losses, screen descendant counts,
candidate-sequence differences and selected confirmations. Correcting a blind
screen is a loop-level implementation fix; only causally verified cumulative
capability gains justify a loop-level improvement claim. These tests do not
establish generalization or original RSI criteria a-e. No evaluation partitions
are opened. A full revised eight-generation campaign needs its own preregistered
physical ceiling; partial prefixes stay partial.

Preserve the eleven-field failure/intervention/result/decision/rule record.
Reusable lesson: an evaluation stage must exercise the downstream action it
purports to select, under the actual evaluation budget, and verified memory
growth must not silently remove that action from the candidate schedule.
