# Wake–sleep learning

Each generation retries every TRAIN task under the frozen wake budget. Selected
programs must also pass that task's hidden examples. Incumbent solutions are
retained unless a new verified solution has higher probability under the same
current task-conditioned grammar.

Repeated solved-program subtrees propose library bodies. Free de Bruijn indices
are lifted into typed lambda parameters; matching literals can be generalized
into parameters. Greedy adoption examines at most 256 distinct proposals and
keeps at most eight entries per generation. Total description length is measured
in fixed AST-node units: all library bodies plus all rewritten solutions. Every
adoption strictly lowers this quantity. No designer-supplied library body is
installed. Earlier entries remain available to later learned bodies.

Grammar fitting counts parent/argument production decisions in rewritten TRAIN
solutions with fixed pseudocount one. Recognition uses 32 fixed statistics of
public input/output examples and an 80-step seeded NumPy linear contextual
softmax fit. It multiplies the current grammar prior by learned contextual
probabilities. Fitting receives verified TRAIN solutions plus sixteen dreamed
tasks. Dreams draw directly from the current grammar and are labeled by running
the sampled ASTs on TRAIN public inputs, never by consulting an external oracle
or using hidden inputs. Unsuccessful sampled evaluations also count as logical
candidate evaluations. Feature and optimizer constants were set before any
held-out reporting measurements.

The structural isolation tests forbid sealed-loader/path references in learning,
abstraction, recognition, heuristic and search modules. The separate evaluation
capability can apply a frozen recognizer to public search examples for inference;
it does not fit recognition or send hidden results to learning.

Stage 3 acceptance: **79 tests passed in 6.660 seconds**. A real seed-11
development smoke generation used 36 TRAIN tasks and frozen budget 64: six
verified training solutions, zero adopted library entries, sixteen valid dreams
from 26 attempted samples, 2006 wake evaluations. Recognition objective fell
from 3.36764 to 1.81620. VALIDATION was **1/12** after learning versus calibration
**2/12**; a lower training objective did not produce a validation gain. These
development measurements do not establish recursive improvement. No sealed
performance numbers were measured or used at this stage.

Reproduce a development smoke run from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /workspace/.venvs/rsi2/bin/python -m rsi2.learning \
  --seed 11 --output /workspace/scratch/rsi2/stage3-smoke.json
```
